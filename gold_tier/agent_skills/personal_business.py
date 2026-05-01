"""
Personal + Business Task Skill — cross-domain task management, priority
scoring, and unified inbox. All public actions decorated with @agent_skill.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from .audit_logger import AuditLogger
from .base import BaseSkill, SkillResult, agent_skill
from .recovery import RecoverySkill


class Domain(str, Enum):
    PERSONAL = "personal"
    BUSINESS = "business"
    SHARED = "shared"


class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    CANCELLED = "cancelled"


@dataclass
class Task:
    title: str
    domain: Domain
    priority: Priority
    description: str = ""
    due_date: str | None = None
    tags: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: str = "autonomous_agent"
    id: int | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CrossDomainAnalysis:
    total_tasks: int
    by_domain: dict[str, int]
    by_priority: dict[str, int]
    by_status: dict[str, int]
    overdue_count: int
    completion_rate: float
    bottlenecks: list[str]
    recommendations: list[str]
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PersonalBusinessSkill(BaseSkill):
    """
    Unified task and context manager for personal + business domains.
    Backed by SQLite for persistence and queryability.
    """

    SKILL_NAME = "personal_business"

    def __init__(
        self,
        data_dir: str | Path = "data/",
        recovery: RecoverySkill | None = None,
        logger: AuditLogger | None = None,
    ) -> None:
        super().__init__(recovery=recovery, logger=logger)
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self._data_dir / "tasks.db"
        self._init_db()

    # ------------------------------------------------------------------ #
    #  Public actions                                                       #
    # ------------------------------------------------------------------ #

    @agent_skill(
        name="create_task",
        description="Create a new task in the personal or business domain.",
        domain=["personal", "business"],
        input_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Task title"},
                "domain": {"type": "string", "enum": ["personal", "business", "shared"]},
                "priority": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                "description": {"type": "string"},
                "due_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "domain", "priority"],
        },
    )
    async def create_task_action(
        self,
        title: str,
        domain: str = "business",
        priority: str = "medium",
        description: str = "",
        due_date: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        task = Task(
            title=title, domain=Domain(domain), priority=Priority(priority),
            description=description, due_date=due_date, tags=tags or [],
        )
        return asdict(self.create_task(task))

    @agent_skill(
        name="list_tasks",
        description="Query tasks across personal and business domains with optional filters.",
        domain=["personal", "business"],
        input_schema={
            "type": "object",
            "properties": {
                "domain": {"type": "string", "enum": ["personal", "business", "shared"]},
                "status": {"type": "string", "enum": ["pending", "in_progress", "blocked", "done", "cancelled"]},
                "priority": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
            },
        },
    )
    async def list_tasks_action(
        self,
        domain: str | None = None,
        status: str | None = None,
        priority: str | None = None,
    ) -> dict[str, Any]:
        tasks = self.get_tasks(
            domain=Domain(domain) if domain else None,
            status=TaskStatus(status) if status else None,
            priority=Priority(priority) if priority else None,
        )
        return {"tasks": [asdict(t) for t in tasks], "count": len(tasks)}

    @agent_skill(
        name="update_task_status",
        description="Update the status of an existing task by ID.",
        domain=["personal", "business"],
        input_schema={
            "type": "object",
            "properties": {
                "task_id": {"type": "integer"},
                "status": {"type": "string", "enum": ["pending", "in_progress", "blocked", "done", "cancelled"]},
                "notes": {"type": "string"},
            },
            "required": ["task_id", "status"],
        },
    )
    async def update_task_status_action(
        self, task_id: int, status: str, notes: str = ""
    ) -> dict[str, Any]:
        ok = self.update_task_status(task_id, TaskStatus(status), notes)
        return {"updated": ok, "task_id": task_id, "new_status": status}

    @agent_skill(
        name="cross_domain_analysis",
        description="Analyse task health across personal and business domains; surface bottlenecks and recommendations.",
        domain=["personal", "business"],
        input_schema={"type": "object", "properties": {}},
    )
    async def cross_domain_analysis_action(self) -> dict[str, Any]:
        return asdict(self.cross_domain_analysis())

    @agent_skill(
        name="get_daily_briefing",
        description="Get a morning digest of urgent, blocked, and due-today tasks.",
        domain=["personal", "business"],
        input_schema={"type": "object", "properties": {}},
    )
    async def get_daily_briefing_action(self) -> dict[str, Any]:
        return self.get_daily_briefing()

    @agent_skill(
        name="seed_demo_tasks",
        description="Populate the task database with sample personal and business tasks.",
        domain=["personal", "business"],
        input_schema={"type": "object", "properties": {}},
    )
    async def seed_demo_tasks_action(self) -> dict[str, Any]:
        self.seed_demo_tasks()
        return {"status": "seeded"}

    # ------------------------------------------------------------------ #
    #  Sync core methods (also used directly by MCP and orchestrator)       #
    # ------------------------------------------------------------------ #

    def create_task(self, task: Task) -> Task:
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO tasks(title, domain, priority, description, due_date, tags,
                   status, assigned_to, created_at, updated_at, metadata)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (task.title, task.domain.value, task.priority.value, task.description,
                 task.due_date, json.dumps(task.tags), task.status.value,
                 task.assigned_to, task.created_at, task.updated_at, json.dumps(task.metadata)),
            )
            task.id = cursor.lastrowid
        self._logger.log_action(self.SKILL_NAME, "create_task",
                                {"id": task.id, "title": task.title, "domain": task.domain.value})
        return task

    def update_task_status(self, task_id: int, status: TaskStatus, notes: str = "") -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                "UPDATE tasks SET status=?, updated_at=?, metadata=json_patch(metadata, ?) WHERE id=?",
                (status.value, now, json.dumps({"last_note": notes}), task_id),
            ).rowcount
        self._logger.log_action(self.SKILL_NAME, "update_status", {"id": task_id, "status": status.value})
        return rows > 0

    def get_tasks(
        self,
        domain: Domain | None = None,
        status: TaskStatus | None = None,
        priority: Priority | None = None,
    ) -> list[Task]:
        query = "SELECT * FROM tasks WHERE 1=1"
        params: list[Any] = []
        if domain:
            query += " AND domain=?"; params.append(domain.value)
        if status:
            query += " AND status=?"; params.append(status.value)
        if priority:
            query += " AND priority=?"; params.append(priority.value)
        query += (
            " ORDER BY CASE priority"
            " WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,"
            " due_date ASC NULLS LAST"
        )
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_task(r) for r in rows]

    def get_task(self, task_id: int) -> Task | None:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return self._row_to_task(row) if row else None

    def delete_task(self, task_id: int) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute("DELETE FROM tasks WHERE id=?", (task_id,)).rowcount
        self._logger.log_action(self.SKILL_NAME, "delete_task", {"id": task_id})
        return rows > 0

    def cross_domain_analysis(self) -> CrossDomainAnalysis:
        all_tasks = self.get_tasks()
        today = datetime.now(timezone.utc).date().isoformat()

        by_domain: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        by_status: dict[str, int] = {}
        overdue = 0
        done = 0

        for t in all_tasks:
            by_domain[t.domain.value] = by_domain.get(t.domain.value, 0) + 1
            by_priority[t.priority.value] = by_priority.get(t.priority.value, 0) + 1
            by_status[t.status.value] = by_status.get(t.status.value, 0) + 1
            if t.due_date and t.due_date < today and t.status not in (TaskStatus.DONE, TaskStatus.CANCELLED):
                overdue += 1
            if t.status == TaskStatus.DONE:
                done += 1

        total = len(all_tasks)
        completion_rate = round((done / total * 100) if total else 0, 1)

        bottlenecks: list[str] = []
        if by_status.get("blocked", 0) > 2:
            bottlenecks.append(f"{by_status['blocked']} tasks are blocked — needs human resolution")
        if overdue > 0:
            bottlenecks.append(f"{overdue} overdue tasks detected")
        if by_priority.get("critical", 0) > 3:
            bottlenecks.append(f"{by_priority['critical']} critical tasks in queue — escalate")

        recommendations: list[str] = []
        if completion_rate < 70:
            recommendations.append("Completion rate below 70% — review task sizing and delegation")
        if by_domain.get("personal", 0) > by_domain.get("business", 0) * 2:
            recommendations.append("Personal tasks dominate — rebalance toward business priorities")
        recommendations = recommendations or ["Healthy task balance — maintain current cadence"]

        self._logger.log_action(self.SKILL_NAME, "cross_domain_analysis",
                                result={"total": total, "completion_rate": completion_rate})
        return CrossDomainAnalysis(
            total_tasks=total, by_domain=by_domain, by_priority=by_priority, by_status=by_status,
            overdue_count=overdue, completion_rate=completion_rate,
            bottlenecks=bottlenecks, recommendations=recommendations,
        )

    def get_daily_briefing(self) -> dict[str, Any]:
        urgent = self.get_tasks(status=TaskStatus.PENDING, priority=Priority.CRITICAL)
        urgent += self.get_tasks(status=TaskStatus.PENDING, priority=Priority.HIGH)
        blocked = self.get_tasks(status=TaskStatus.BLOCKED)
        in_progress = self.get_tasks(status=TaskStatus.IN_PROGRESS)
        today = datetime.now(timezone.utc).date().isoformat()
        due_today = [t for t in self.get_tasks() if t.due_date == today and t.status == TaskStatus.PENDING]
        briefing = {
            "date": today,
            "urgent_count": len(urgent),
            "urgent_tasks": [{"id": t.id, "title": t.title, "domain": t.domain.value} for t in urgent[:5]],
            "blocked_count": len(blocked),
            "in_progress_count": len(in_progress),
            "due_today": [{"id": t.id, "title": t.title} for t in due_today],
            "recommended_focus": urgent[0].title if urgent else "All clear — pick from backlog",
        }
        self._logger.log_action(self.SKILL_NAME, "daily_briefing", result=f"{len(urgent)} urgent tasks")
        return briefing

    def seed_demo_tasks(self) -> None:
        demo = [
            Task("Prepare Q2 investor update", Domain.BUSINESS, Priority.HIGH,
                 due_date="2026-05-08", tags=["finance", "presentation"]),
            Task("Review contractor invoices", Domain.BUSINESS, Priority.MEDIUM,
                 due_date="2026-05-05", tags=["finance"]),
            Task("Social media content calendar", Domain.BUSINESS, Priority.MEDIUM,
                 tags=["marketing", "social"]),
            Task("Book dentist appointment", Domain.PERSONAL, Priority.LOW, tags=["health"]),
            Task("Renew domain name (expires May 15)", Domain.BUSINESS, Priority.CRITICAL,
                 due_date="2026-05-14", tags=["infra"]),
            Task("Update LinkedIn profile", Domain.SHARED, Priority.LOW, tags=["branding"]),
        ]
        for t in demo:
            self.create_task(t)

    # ------------------------------------------------------------------ #
    #  Internals                                                            #
    # ------------------------------------------------------------------ #

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    due_date TEXT,
                    tags TEXT DEFAULT '[]',
                    status TEXT DEFAULT 'pending',
                    assigned_to TEXT DEFAULT 'autonomous_agent',
                    created_at TEXT,
                    updated_at TEXT,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_domain ON tasks(domain)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON tasks(status)")

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> Task:
        d = dict(row)
        return Task(
            id=d["id"], title=d["title"],
            domain=Domain(d["domain"]), priority=Priority(d["priority"]),
            description=d.get("description", ""), due_date=d.get("due_date"),
            tags=json.loads(d.get("tags", "[]")),
            status=TaskStatus(d["status"]),
            assigned_to=d.get("assigned_to", "autonomous_agent"),
            created_at=d.get("created_at", ""), updated_at=d.get("updated_at", ""),
            metadata=json.loads(d.get("metadata", "{}")),
        )
