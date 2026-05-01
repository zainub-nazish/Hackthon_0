"""
Audit MCP Server — weekly audit, CEO briefing, transaction management,
and cross-domain task analysis exposed as MCP tools.
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import asdict
from typing import Any

_TOOLS = [
    {
        "name": "run_weekly_audit",
        "description": "Execute the weekly business and accounting audit and generate a CEO briefing",
        "inputSchema": {
            "type": "object",
            "properties": {
                "include_social": {"type": "boolean", "default": True,
                                   "description": "Include social media metrics in the briefing"},
            },
        },
    },
    {
        "name": "record_transaction",
        "description": "Record a financial transaction (revenue or expense)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "category": {"type": "string", "enum": ["revenue", "expense", "transfer"]},
                "description": {"type": "string"},
                "amount": {"type": "number"},
                "currency": {"type": "string", "default": "USD"},
            },
            "required": ["date", "category", "description", "amount"],
        },
    },
    {
        "name": "export_transactions_csv",
        "description": "Export transactions between two dates to CSV",
        "inputSchema": {
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "Start date YYYY-MM-DD"},
                "end": {"type": "string", "description": "End date YYYY-MM-DD"},
            },
            "required": ["start", "end"],
        },
    },
    {
        "name": "cross_domain_analysis",
        "description": "Analyse personal vs business task health and surface bottlenecks",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "seed_mock_data",
        "description": "Populate the DB with realistic mock transactions for testing",
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "default": 30},
            },
        },
    },
    {
        "name": "get_daily_briefing",
        "description": "Get a morning digest of urgent tasks and priorities",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_tasks",
        "description": "Query tasks across personal and business domains with optional filters",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "enum": ["personal", "business", "shared"],
                           "description": "Filter by domain (omit for all)"},
                "status": {"type": "string",
                           "enum": ["pending", "in_progress", "blocked", "done", "cancelled"],
                           "description": "Filter by status (omit for all)"},
                "priority": {"type": "string", "enum": ["critical", "high", "medium", "low"],
                             "description": "Filter by priority (omit for all)"},
            },
        },
    },
    {
        "name": "update_task_status",
        "description": "Update the status of an existing task",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "Task ID to update"},
                "status": {"type": "string",
                           "enum": ["pending", "in_progress", "blocked", "done", "cancelled"]},
                "notes": {"type": "string", "description": "Optional note on why status changed"},
            },
            "required": ["task_id", "status"],
        },
    },
]


class AuditMCPServer:

    def __init__(self) -> None:
        # Lazy initialization - only load skills when needed
        self._audit = None
        self._pb = None
        self._social = None
        self._logger = None
        self._recovery = None

    def _ensure_skills_loaded(self) -> None:
        """Lazy load skills on first use."""
        if self._audit is not None:
            return

        from agent_skills.audit import AuditSkill
        from agent_skills.personal_business import PersonalBusinessSkill
        from agent_skills.social import SocialMediaSkill
        from agent_skills.recovery import RecoverySkill
        from agent_skills.audit_logger import AuditLogger

        self._logger = AuditLogger("audit_mcp")
        self._recovery = RecoverySkill(logger=self._logger)
        self._audit = AuditSkill(recovery=self._recovery, logger=self._logger)
        self._pb = PersonalBusinessSkill(recovery=self._recovery, logger=self._logger)
        self._social = SocialMediaSkill(recovery=self._recovery, logger=self._logger, dry_run=True)

    async def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        method = request.get("method", "")
        req_id = request.get("id")

        if method == "initialize":
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "audit_mcp", "version": "1.0.0"},
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

        if tool == "run_weekly_audit":
            social_summaries: dict = {}
            if args.get("include_social", True):
                summaries = await self._social.generate_all_summaries(7)
                social_summaries = {k: vars(v) for k, v in summaries.items()}
            analysis = self._pb.cross_domain_analysis()
            task_stats = {
                "completion_rate": analysis.completion_rate,
                "open_issues": analysis.overdue_count,
                "error_rate_pct": 1.1,
            }
            briefing = await self._audit.run_weekly_audit(social_summaries, task_stats)
            result = {
                "period": briefing.period,
                "executive_summary": briefing.executive_summary,
                "financial": briefing.financial_highlights,
                "operational": briefing.operational_highlights,
                "risks": briefing.risks,
                "action_items": briefing.action_items,
                "briefing_path": f"data/briefings/briefing_{briefing.generated_at[:10].replace('-','')}.md",
            }
            return result

        if tool == "record_transaction":
            from agent_skills.audit import FinancialRecord
            rec = FinancialRecord(
                date=args["date"], category=args["category"],
                description=args["description"], amount=args["amount"],
                currency=args.get("currency", "USD"),
            )
            self._audit.record_transaction(rec)
            return {"status": "recorded", "record": asdict(rec)}

        if tool == "export_transactions_csv":
            path = self._audit.export_to_csv(args["start"], args["end"])
            return {"csv_path": str(path)}

        if tool == "cross_domain_analysis":
            analysis = self._pb.cross_domain_analysis()
            return asdict(analysis)

        if tool == "seed_mock_data":
            self._audit.seed_mock_data(args.get("days", 30))
            self._pb.seed_demo_tasks()
            return {"status": "seeded"}

        if tool == "get_daily_briefing":
            return self._pb.get_daily_briefing()

        if tool == "list_tasks":
            from agent_skills.personal_business import Domain, Priority, TaskStatus
            domain = Domain(args["domain"]) if args.get("domain") else None
            status = TaskStatus(args["status"]) if args.get("status") else None
            priority = Priority(args["priority"]) if args.get("priority") else None
            tasks = self._pb.get_tasks(domain=domain, status=status, priority=priority)
            return {"tasks": [asdict(t) for t in tasks], "count": len(tasks)}

        if tool == "update_task_status":
            from agent_skills.personal_business import TaskStatus
            ok = self._pb.update_task_status(
                args["task_id"],
                TaskStatus(args["status"]),
                args.get("notes", ""),
            )
            return {"updated": ok, "task_id": args["task_id"], "new_status": args["status"]}

        raise ValueError(f"Unknown tool: {tool}")

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
    asyncio.run(AuditMCPServer().run_stdio())
