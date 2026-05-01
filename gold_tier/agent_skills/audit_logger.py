"""
Comprehensive audit logger — every action, decision, and error is recorded
as a structured JSON line to persistent log files.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
EventType = Literal["action", "decision", "error", "state_change", "audit", "social", "recovery"]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": _utcnow(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if hasattr(record, "extra"):
            payload.update(record.extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def _make_rotating_handler(path: Path, max_bytes: int = 10 * 1024 * 1024, backups: int = 5) -> logging.Handler:
    path.parent.mkdir(parents=True, exist_ok=True)
    h = logging.handlers.RotatingFileHandler(path, maxBytes=max_bytes, backupCount=backups, encoding="utf-8")
    h.setFormatter(_JsonFormatter())
    return h


class AuditLogger:
    """Thread-safe, structured JSON logger for the Gold Tier system."""

    _instances: dict[str, "AuditLogger"] = {}
    _lock = threading.Lock()

    def __new__(cls, name: str = "gold_tier", log_dir: str | Path = "logs/") -> "AuditLogger":
        with cls._lock:
            if name not in cls._instances:
                inst = super().__new__(cls)
                inst._init(name, log_dir)
                cls._instances[name] = inst
            return cls._instances[name]

    def _init(self, name: str, log_dir: str | Path) -> None:
        self._name = name
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)

        # Three dedicated loggers for separation of concerns
        self._action_log = self._build_logger(f"{name}.actions", self._log_dir / "actions.jsonl")
        self._error_log = self._build_logger(f"{name}.errors", self._log_dir / "errors.jsonl")
        self._audit_log = self._build_logger(f"{name}.audit", self._log_dir / "audit.jsonl")

        # Also write to stdout via rich if available
        self._console = logging.getLogger(f"{name}.console")
        self._console.setLevel(logging.DEBUG)
        if not self._console.handlers:
            ch = logging.StreamHandler()
            ch.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)-8s %(message)s"))
            self._console.addHandler(ch)

    @staticmethod
    def _build_logger(name: str, path: Path) -> logging.Logger:
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        if not logger.handlers:
            logger.addHandler(_make_rotating_handler(path))
        logger.propagate = False
        return logger

    # ------------------------------------------------------------------ #
    #  Public API                                                           #
    # ------------------------------------------------------------------ #

    def log_action(
        self,
        skill: str,
        action: str,
        params: dict[str, Any] | None = None,
        result: Any = None,
        duration_ms: float | None = None,
    ) -> str:
        event_id = str(uuid.uuid4())[:8]
        record = logging.LogRecord(
            name=self._action_log.name, level=logging.INFO,
            pathname="", lineno=0,
            msg=f"{skill}.{action}",
            args=(), exc_info=None,
        )
        record.extra = {
            "event_id": event_id,
            "event_type": "action",
            "skill": skill,
            "action": action,
            "params": params or {},
            "result_summary": str(result)[:200] if result is not None else None,
            "duration_ms": duration_ms,
        }
        self._action_log.handle(record)
        self._console.info("[%s] action  %s.%s", event_id, skill, action)
        return event_id

    def log_decision(
        self,
        context: str,
        decision: str,
        rationale: str,
        alternatives: list[str] | None = None,
    ) -> str:
        event_id = str(uuid.uuid4())[:8]
        record = logging.LogRecord(
            name=self._audit_log.name, level=logging.INFO,
            pathname="", lineno=0,
            msg=f"decision: {decision[:80]}",
            args=(), exc_info=None,
        )
        record.extra = {
            "event_id": event_id,
            "event_type": "decision",
            "context": context,
            "decision": decision,
            "rationale": rationale,
            "alternatives": alternatives or [],
        }
        self._audit_log.handle(record)
        self._console.info("[%s] decision %s", event_id, decision[:60])
        return event_id

    def log_error(
        self,
        skill: str,
        action: str,
        error: Exception | str,
        severity: LogLevel = "ERROR",
        recoverable: bool = True,
    ) -> str:
        event_id = str(uuid.uuid4())[:8]
        lvl = getattr(logging, severity)
        record = logging.LogRecord(
            name=self._error_log.name, level=lvl,
            pathname="", lineno=0,
            msg=f"{skill}.{action} failed: {error}",
            args=(), exc_info=None,
        )
        record.extra = {
            "event_id": event_id,
            "event_type": "error",
            "skill": skill,
            "action": action,
            "error": str(error),
            "error_type": type(error).__name__ if isinstance(error, Exception) else "str",
            "severity": severity,
            "recoverable": recoverable,
        }
        self._error_log.handle(record)
        self._console.error("[%s] ERROR   %s.%s — %s", event_id, skill, action, str(error)[:80])
        return event_id

    def log_state_change(self, component: str, old_state: str, new_state: str, reason: str = "") -> None:
        record = logging.LogRecord(
            name=self._audit_log.name, level=logging.INFO,
            pathname="", lineno=0,
            msg=f"{component} {old_state} → {new_state}",
            args=(), exc_info=None,
        )
        record.extra = {
            "event_type": "state_change",
            "component": component,
            "old_state": old_state,
            "new_state": new_state,
            "reason": reason,
        }
        self._audit_log.handle(record)
        self._console.info("state   %s: %s → %s", component, old_state, new_state)

    def log_audit_event(self, event_type: str, data: dict[str, Any]) -> None:
        record = logging.LogRecord(
            name=self._audit_log.name, level=logging.INFO,
            pathname="", lineno=0,
            msg=f"audit:{event_type}",
            args=(), exc_info=None,
        )
        record.extra = {"event_type": event_type, **data}
        self._audit_log.handle(record)
