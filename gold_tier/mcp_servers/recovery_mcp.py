"""
Recovery MCP Server — circuit breaker status, manual resets, and
error diagnostics exposed as MCP tools.
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

_TOOLS = [
    {
        "name": "get_circuit_status",
        "description": "View state of all circuit breakers (closed/open/half_open)",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "reset_circuit",
        "description": "Manually reset a circuit breaker from OPEN back to CLOSED",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Circuit key, e.g. 'social.post_twitter'"},
            },
            "required": ["key"],
        },
    },
    {
        "name": "get_error_summary",
        "description": "Show recent error counts per skill.action key",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "run_health_check",
        "description": "Ping all registered skills and report availability",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_fallbacks",
        "description": "List all registered fallback handlers",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


class RecoveryMCPServer:

    def __init__(self) -> None:
        # Lazy initialization - only load skills when needed
        self._logger = None
        self._recovery = None
        self._social = None
        self._audit_skill = None
        self._pb = None

    def _ensure_skills_loaded(self) -> None:
        """Lazy load skills on first use."""
        if self._recovery is not None:
            return

        from agent_skills.recovery import RecoverySkill
        from agent_skills.audit_logger import AuditLogger
        from agent_skills.social import SocialMediaSkill
        from agent_skills.audit import AuditSkill
        from agent_skills.personal_business import PersonalBusinessSkill

        self._logger = AuditLogger("recovery_mcp")
        self._recovery = RecoverySkill(logger=self._logger)
        # Instantiate skills so their fallbacks are registered on the shared recovery instance
        self._social = SocialMediaSkill(recovery=self._recovery, logger=self._logger, dry_run=True)
        self._audit_skill = AuditSkill(recovery=self._recovery, logger=self._logger)
        self._pb = PersonalBusinessSkill(recovery=self._recovery, logger=self._logger)

    async def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        method = request.get("method", "")
        req_id = request.get("id")

        if method == "initialize":
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "recovery_mcp", "version": "1.0.0"},
                },
            }

        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": _TOOLS}}

        if method == "tools/call":
            tool_name = request["params"]["name"]
            args = request["params"].get("arguments", {})
            try:
                result = await self._dispatch(tool_name, args)
                return {
                    "jsonrpc": "2.0", "id": req_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(result, default=str)}]},
                }
            except Exception as exc:
                return {
                    "jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32603, "message": str(exc)},
                }

        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}}

    async def _dispatch(self, tool: str, args: dict[str, Any]) -> Any:
        # Lazy load skills on first tool call
        self._ensure_skills_loaded()

        if tool == "get_circuit_status":
            return {"circuits": self._recovery.circuit_status()}

        if tool == "reset_circuit":
            key = args["key"]
            self._recovery.reset_circuit(key)
            return {"status": "reset", "key": key}

        if tool == "get_error_summary":
            return {"errors": self._recovery.error_summary()}

        if tool == "list_fallbacks":
            return {"fallbacks": list(self._recovery._fallbacks.keys())}

        if tool == "run_health_check":
            results: dict[str, Any] = {}
            checks = {
                "social.post_twitter": self._check_twitter,
                "audit.db": self._check_audit_db,
                "tasks.db": self._check_tasks_db,
            }
            for name, check_fn in checks.items():
                try:
                    ok = await check_fn()
                    results[name] = {"status": "ok" if ok else "degraded"}
                except Exception as exc:
                    results[name] = {"status": "error", "error": str(exc)}
            overall = "healthy" if all(v["status"] == "ok" for v in results.values()) else "degraded"
            return {"overall": overall, "checks": results}

        raise ValueError(f"Unknown tool: {tool}")

    async def _check_twitter(self) -> bool:
        # Ping the circuit — if closed, assume OK; if open, report degraded
        from agent_skills.recovery import CircuitState
        breaker = self._recovery.get_circuit("social.post_twitter")
        return breaker.state != CircuitState.OPEN

    async def _check_audit_db(self) -> bool:
        import sqlite3
        from pathlib import Path
        db = Path("data/audit.db")
        if not db.exists():
            return False
        with sqlite3.connect(db) as conn:
            conn.execute("SELECT 1")
        return True

    async def _check_tasks_db(self) -> bool:
        import sqlite3
        from pathlib import Path
        db = Path("data/tasks.db")
        if not db.exists():
            return False
        with sqlite3.connect(db) as conn:
            conn.execute("SELECT 1")
        return True

    async def run_stdio(self) -> None:
        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        await loop.connect_read_pipe(
            lambda: asyncio.StreamReaderProtocol(reader),
            sys.stdin.buffer,
        )
        while True:
            try:
                line = await reader.readline()
                if not line:
                    break
                request = json.loads(line.decode())
                response = await self.handle_request(request)
                sys.stdout.buffer.write((json.dumps(response) + "\n").encode())
                sys.stdout.buffer.flush()
            except Exception:
                break


if __name__ == "__main__":
    asyncio.run(RecoveryMCPServer().run_stdio())
