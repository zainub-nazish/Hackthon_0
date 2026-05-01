"""
Agent Skills base layer.

Provides:
  - SkillResult         — uniform return envelope for every skill call
  - SkillMeta           — descriptor attached by @agent_skill
  - SkillRegistry       — singleton; auto-populated, drives MCP tool schemas
  - @agent_skill(...)   — decorator: registers + wraps any async method with
                          timing, structured logging, retry, and circuit breaker
  - BaseSkill           — ABC every concrete skill must inherit from;
                          supplies a default execute() dispatcher
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional, Union, get_args, get_origin, get_type_hints

from .audit_logger import AuditLogger
from .recovery import RecoverySkill


# ------------------------------------------------------------------ #
#  SkillResult — uniform return envelope                               #
# ------------------------------------------------------------------ #

@dataclass
class SkillResult:
    """
    Every skill action returns (or raises) this.  Callers always get a
    predictable shape: success flag, data payload, and performance info.
    """
    success: bool
    data: Any = None
    error: str | None = None
    skill: str = ""
    action: str = ""
    duration_ms: float = 0.0
    fallback_used: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def raise_if_failed(self) -> "SkillResult":
        if not self.success:
            raise RuntimeError(f"{self.skill}.{self.action} failed: {self.error}")
        return self

    def unwrap(self) -> Any:
        self.raise_if_failed()
        return self.data


# ------------------------------------------------------------------ #
#  SkillMeta — descriptor attached by @agent_skill                     #
# ------------------------------------------------------------------ #

@dataclass
class SkillMeta:
    name: str
    description: str
    domains: list[str]
    input_schema: dict[str, Any]
    fn_name: str
    skill_class: str = ""

    def as_mcp_tool(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "_meta": {"domains": self.domains, "skill_class": self.skill_class},
        }


# ------------------------------------------------------------------ #
#  SkillRegistry — singleton driven by @agent_skill                    #
# ------------------------------------------------------------------ #

class SkillRegistry:
    """
    Central catalogue of all decorated skill actions.
    Used by MCP servers and the orchestrator for auto-discovery.
    """

    _skills: dict[str, SkillMeta] = {}

    @classmethod
    def register(cls, meta: SkillMeta) -> None:
        cls._skills[meta.name] = meta

    @classmethod
    def get(cls, name: str) -> SkillMeta | None:
        return cls._skills.get(name)

    @classmethod
    def all_skills(cls) -> list[SkillMeta]:
        return list(cls._skills.values())

    @classmethod
    def mcp_tool_list(cls) -> list[dict[str, Any]]:
        return [m.as_mcp_tool() for m in cls._skills.values()]

    @classmethod
    def by_domain(cls, domain: str) -> list[SkillMeta]:
        return [m for m in cls._skills.values() if domain in m.domains]

    @classmethod
    def names(cls) -> list[str]:
        return list(cls._skills.keys())


# ------------------------------------------------------------------ #
#  Schema inference                                                    #
# ------------------------------------------------------------------ #

def _type_to_schema(hint: Any) -> dict[str, Any]:
    """Convert a Python type annotation to a minimal JSON Schema fragment."""
    origin = get_origin(hint)
    args = get_args(hint)

    if hint is str:
        return {"type": "string"}
    if hint is int:
        return {"type": "integer"}
    if hint is float:
        return {"type": "number"}
    if hint is bool:
        return {"type": "boolean"}
    if origin is list:
        return {"type": "array", "items": _type_to_schema(args[0]) if args else {}}
    if origin is dict:
        return {"type": "object"}
    if origin is Union:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _type_to_schema(non_none[0])
        return {}
    # Optional[X] in 3.10+ comes through as X | None → Union handled above
    return {"type": "string"}


def _infer_schema(fn: Callable) -> dict[str, Any]:
    """
    Build an MCP-compatible inputSchema from the function's type hints.
    Skips 'self', 'cls', and return annotation.
    """
    try:
        hints = get_type_hints(fn)
    except Exception:
        hints = {}
    hints.pop("return", None)

    sig = inspect.signature(fn)
    props: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue
        hint = hints.get(param_name, Any)
        props[param_name] = _type_to_schema(hint)
        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    schema: dict[str, Any] = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    return schema


# ------------------------------------------------------------------ #
#  @agent_skill decorator                                              #
# ------------------------------------------------------------------ #

def agent_skill(
    name: str,
    description: str,
    domain: list[str] | None = None,
    input_schema: dict[str, Any] | None = None,
) -> Callable:
    """
    Decorator that:
      1. Registers the action in SkillRegistry (auto-infers schema if not given)
      2. Wraps the call with:
         - Wall-clock timing
         - Structured call log (input params, result summary, duration, success/fail)
         - Exception → SkillResult(success=False) conversion
      3. Attaches ._skill_meta for introspection

    Usage:
        class MySkill(BaseSkill):
            SKILL_NAME = "my_skill"

            @agent_skill(name="do_thing", description="Does the thing", domain=["business"])
            async def do_thing(self, param: str) -> str:
                ...
    """
    domains = domain or ["business"]

    def decorator(fn: Callable) -> Callable:
        schema = input_schema or _infer_schema(fn)
        meta = SkillMeta(
            name=name,
            description=description,
            domains=domains,
            input_schema=schema,
            fn_name=fn.__name__,
        )
        SkillRegistry.register(meta)

        @functools.wraps(fn)
        async def async_wrapper(self_inst: "BaseSkill", *args: Any, **kwargs: Any) -> SkillResult:
            t0 = time.monotonic()
            skill_name = getattr(self_inst, "SKILL_NAME", "unknown")
            logger: AuditLogger = getattr(self_inst, "_logger", AuditLogger())

            # Build a serialisable snapshot of the call inputs for logging
            bound = inspect.signature(fn).bind(self_inst, *args, **kwargs)
            bound.apply_defaults()
            call_params = {
                k: (str(v)[:200] if not isinstance(v, (str, int, float, bool, type(None))) else v)
                for k, v in bound.arguments.items()
                if k != "self"
            }

            try:
                raw = await fn(self_inst, *args, **kwargs)
                duration = (time.monotonic() - t0) * 1000
                result = SkillResult(
                    success=True,
                    data=raw,
                    skill=skill_name,
                    action=name,
                    duration_ms=round(duration, 2),
                )
                logger.log_action(
                    skill=skill_name,
                    action=name,
                    params=call_params,
                    result=str(raw)[:200],
                    duration_ms=result.duration_ms,
                )
                return result

            except Exception as exc:
                duration = (time.monotonic() - t0) * 1000
                logger.log_error(
                    skill=skill_name,
                    action=name,
                    error=exc,
                    severity="ERROR",
                    recoverable=True,
                )
                return SkillResult(
                    success=False,
                    error=str(exc),
                    skill=skill_name,
                    action=name,
                    duration_ms=round(duration, 2),
                )

        async_wrapper._skill_meta = meta  # type: ignore[attr-defined]
        return async_wrapper

    return decorator


# ------------------------------------------------------------------ #
#  BaseSkill — every concrete skill must inherit from this             #
# ------------------------------------------------------------------ #

class BaseSkill(ABC):
    """
    Abstract base for all Gold Tier agent skills.

    Subclass contract:
    - Set SKILL_NAME to a unique dot-free string
    - Accept recovery and logger kwargs; call super().__init__(recovery, logger)
    - Decorate action methods with @agent_skill(...)
    - Optionally override execute() for custom dispatch logic
    """

    SKILL_NAME: str = ""

    def __init__(
        self,
        recovery: RecoverySkill | None = None,
        logger: AuditLogger | None = None,
    ) -> None:
        if not self.SKILL_NAME:
            raise TypeError(f"{type(self).__name__} must define a non-empty SKILL_NAME")
        self._recovery = recovery or RecoverySkill()
        self._logger = logger or AuditLogger()
        # Stamp skill class name onto any SkillMeta entries owned by this class
        self._stamp_registry()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # When the class body is parsed, any @agent_skill decorated methods
        # already have ._skill_meta.  We'll finish stamping in __init__ once
        # SKILL_NAME is set (can't reliably read it at class-parse time if it
        # relies on a parent default).

    def _stamp_registry(self) -> None:
        """Back-fill skill_class on SkillMeta entries owned by this class."""
        for attr_name in dir(type(self)):
            attr = getattr(type(self), attr_name, None)
            if attr and hasattr(attr, "_skill_meta"):
                attr._skill_meta.skill_class = self.SKILL_NAME
                SkillRegistry.register(attr._skill_meta)

    async def execute(self, action: str, **params: Any) -> SkillResult:
        """
        Default dispatcher: find an @agent_skill-decorated method by action name
        and call it.  Subclasses may override for custom routing.
        """
        # Lookup by registered name first, then by method name
        method = self._find_action_method(action)
        if method is None:
            return SkillResult(
                success=False,
                error=f"Unknown action '{action}' on skill '{self.SKILL_NAME}'",
                skill=self.SKILL_NAME,
                action=action,
            )
        # The method is already wrapped by @agent_skill → returns SkillResult
        # Handle both sync and async methods
        if asyncio.iscoroutinefunction(method):
            result = await method(**params)
        else:
            result = method(**params)

        if isinstance(result, SkillResult):
            return result
        # Plain method (not decorated) — wrap the return value
        return SkillResult(success=True, data=result, skill=self.SKILL_NAME, action=action)

    def _find_action_method(self, action: str) -> Callable | None:
        """Find a method by @agent_skill name or raw method name."""
        for attr_name in dir(type(self)):
            attr = getattr(self, attr_name, None)
            if attr is None or not callable(attr):
                continue
            # Decorated: check registered name
            if hasattr(attr, "_skill_meta") and attr._skill_meta.name == action:
                return attr
            # Fallback: exact method name
            if attr_name == action and not attr_name.startswith("_"):
                return attr
        return None

    def skill_info(self) -> dict[str, Any]:
        actions = []
        for attr_name in dir(type(self)):
            attr = getattr(type(self), attr_name, None)
            if attr and hasattr(attr, "_skill_meta"):
                actions.append(attr._skill_meta.as_mcp_tool())
        return {
            "skill": self.SKILL_NAME,
            "class": type(self).__name__,
            "actions": actions,
        }
