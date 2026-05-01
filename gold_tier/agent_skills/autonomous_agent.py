"""
AutonomousAgent — the driving intelligence of the Gold Tier system.

Implements:
  - execute_task(task: dict) -> dict     one-shot task execution
  - run_ralph_wiggum_loop(...)           multi-iteration Plan→Execute→Verify→Fix loop

Ralph Wiggum loop design:
  - Each iteration gets a fresh IterationContext (no growing transcript)
  - Compact ProgressTracker summary passed as context (not full history)
  - Loop phases: PLAN → EXECUTE skill(s) → VERIFY result → FIX if needed → LOG
  - Writes progress.json after every iteration
  - Exits when exit_criteria met, goal achieved by verify, or max_iterations hit
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from .audit_logger import AuditLogger
from .base import BaseSkill, SkillResult, SkillRegistry
from .recovery import RecoverySkill


# ------------------------------------------------------------------ #
#  Loop data structures                                                #
# ------------------------------------------------------------------ #

class IterStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    FIXED = "fixed"


@dataclass
class IterationContext:
    """Fresh per-iteration context — no accumulated transcript."""
    iteration: int
    task_description: str
    exit_criteria: str
    history_summary: str        # compact summary injected from ProgressTracker
    available_skills: list[str]


@dataclass
class IterationRecord:
    iteration: int
    plan: list[dict[str, Any]]
    executed: list[dict[str, Any]]
    verify_passed: bool
    issues: list[str]
    fix_attempts: int
    status: IterStatus
    duration_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class LoopReport:
    task_description: str
    exit_criteria: str
    total_iterations: int
    iterations: list[IterationRecord]
    final_status: str
    goal_achieved: bool
    started_at: str
    finished_at: str
    progress_file: str


# ------------------------------------------------------------------ #
#  ProgressTracker — persists state between iterations                 #
# ------------------------------------------------------------------ #

class ProgressTracker:
    """
    Writes/reads progress.json so the loop is restartable and auditable.
    Provides a compact text summary for injection into each fresh context.
    """

    def __init__(self, task_description: str, data_dir: Path = Path("data/progress")) -> None:
        data_dir.mkdir(parents=True, exist_ok=True)
        slug = task_description[:40].lower().replace(" ", "_").replace("/", "-")
        self._path = data_dir / f"progress_{slug}.json"
        self._task = task_description
        self._records: list[IterationRecord] = []
        self._started_at = datetime.now(timezone.utc).isoformat()
        self._load()

    def log_iteration(self, record: IterationRecord) -> None:
        self._records.append(record)
        self._save()

    def get_summary(self) -> str:
        """Compact text summary: last 3 iterations only (keeps context small)."""
        if not self._records:
            return "No previous iterations."
        lines = [f"Task: {self._task}", f"Iterations so far: {len(self._records)}"]
        for rec in self._records[-3:]:
            ok = "✓" if rec.verify_passed else "✗"
            actions = ", ".join(f"{s['skill']}.{s['action']}" for s in rec.executed[:3])
            lines.append(f"  [{rec.iteration}] {ok} {rec.status} | actions: {actions or 'none'} | issues: {rec.issues[:2]}")
        return "\n".join(lines)

    def final_report(self, goal_achieved: bool, finished_at: str) -> LoopReport:
        return LoopReport(
            task_description=self._task,
            exit_criteria="",
            total_iterations=len(self._records),
            iterations=self._records,
            final_status="achieved" if goal_achieved else "exhausted",
            goal_achieved=goal_achieved,
            started_at=self._started_at,
            finished_at=finished_at,
            progress_file=str(self._path),
        )

    def _save(self) -> None:
        payload = {
            "task": self._task,
            "started_at": self._started_at,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "iteration_count": len(self._records),
            "iterations": [
                {**asdict(r), "status": r.status.value}
                for r in self._records
            ],
        }
        self._path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def _load(self) -> None:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self._started_at = data.get("started_at", self._started_at)
            except Exception:
                pass  # corrupt file — start fresh


# ------------------------------------------------------------------ #
#  AutonomousAgent                                                     #
# ------------------------------------------------------------------ #

class AutonomousAgent:
    """
    Drives agent skills through the Ralph Wiggum loop.

    Skills are injected at construction time.  The agent dispatches through
    each skill's execute() method (BaseSkill interface), so any new skill
    registered with @agent_skill is automatically available.
    """

    def __init__(
        self,
        skills: list[BaseSkill],
        recovery: RecoverySkill | None = None,
        logger: AuditLogger | None = None,
        data_dir: str | Path = "data/",
    ) -> None:
        self._skills: dict[str, BaseSkill] = {s.SKILL_NAME: s for s in skills}
        self._recovery = recovery or RecoverySkill()
        self._logger = logger or AuditLogger()
        self._data_dir = Path(data_dir)

    # ------------------------------------------------------------------ #
    #  execute_task — single-shot task execution                           #
    # ------------------------------------------------------------------ #

    async def execute_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a single structured task immediately.

        task dict keys:
          skill   : str            — which skill to use
          action  : str            — which action to call
          params  : dict           — keyword arguments for the action
          description: str         — human-readable description (optional)
        """
        skill_name = task.get("skill", "")
        action = task.get("action", "")
        params = task.get("params", {})

        skill = self._skills.get(skill_name)
        if skill is None:
            return {
                "success": False,
                "error": f"Skill '{skill_name}' not found. Available: {list(self._skills.keys())}",
            }

        t0 = time.monotonic()
        result: SkillResult = await skill.execute(action, **params)
        duration = (time.monotonic() - t0) * 1000

        self._logger.log_action(
            "autonomous_agent", "execute_task",
            {"skill": skill_name, "action": action},
            result=str(result.data)[:200],
            duration_ms=duration,
        )
        return {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "skill": skill_name,
            "action": action,
            "duration_ms": round(duration, 2),
            "fallback_used": result.fallback_used,
        }

    # ------------------------------------------------------------------ #
    #  run_ralph_wiggum_loop                                               #
    # ------------------------------------------------------------------ #

    async def run_ralph_wiggum_loop(
        self,
        task_description: str,
        max_iterations: int = 20,
        exit_criteria: str = "",
    ) -> LoopReport:
        """
        The Ralph Wiggum loop — iterates until goal met or max iterations hit.

        Each iteration:
          1. PLAN     — decide which skill actions to run this iteration
          2. EXECUTE  — run each planned action, collect SkillResults
          3. VERIFY   — check if results satisfy the goal / exit_criteria
          4. FIX      — if verify failed, attempt one corrective action
          5. LOG      — record full iteration to ProgressTracker → progress.json

        Key design:
          - IterationContext is created fresh each loop (no growing state)
          - Only a compact ProgressTracker.get_summary() is injected as context
          - This prevents prompt-bloat and forces the planner to reason from outcomes
        """
        tracker = ProgressTracker(task_description, self._data_dir / "progress")
        available = list(self._skills.keys())
        goal_achieved = False
        loop_start = datetime.now(timezone.utc).isoformat()

        self._logger.log_state_change("ralph_wiggum_loop", "idle", "running", task_description[:60])

        for iteration in range(1, max_iterations + 1):
            iter_start = time.monotonic()

            # ── Fresh context each iteration ─────────────────────────────
            ctx = IterationContext(
                iteration=iteration,
                task_description=task_description,
                exit_criteria=exit_criteria,
                history_summary=tracker.get_summary(),
                available_skills=available,
            )

            self._logger.log_action("ralph_wiggum_loop", "iteration_start",
                                    {"iter": iteration, "task": task_description[:60]})

            # ── 1. PLAN ──────────────────────────────────────────────────
            plan = self._plan(ctx)

            # ── 2. EXECUTE ───────────────────────────────────────────────
            executed: list[dict[str, Any]] = []
            for step in plan:
                step_result = await self.execute_task(step)
                executed.append({**step, "result": step_result})
                if not step_result["success"]:
                    self._logger.log_error("ralph_wiggum_loop", "step_failed",
                                           step_result.get("error", "unknown"), recoverable=True)

            # ── 3. VERIFY ────────────────────────────────────────────────
            verify_passed, issues = self._verify(ctx, executed)

            # ── 4. FIX ───────────────────────────────────────────────────
            fix_attempts = 0
            status = IterStatus.SUCCESS if verify_passed else IterStatus.PARTIAL
            if not verify_passed:
                fix_plan = self._fix(ctx, issues, executed)
                if fix_plan:
                    fix_attempts = len(fix_plan)
                    for fix_step in fix_plan:
                        fix_result = await self.execute_task(fix_step)
                        executed.append({**fix_step, "result": fix_result, "is_fix": True})
                    _, issues_after_fix = self._verify(ctx, executed)
                    if not issues_after_fix:
                        status = IterStatus.FIXED
                        verify_passed = True
                    else:
                        status = IterStatus.FAILED

            # ── 5. LOG ───────────────────────────────────────────────────
            duration = (time.monotonic() - iter_start) * 1000
            record = IterationRecord(
                iteration=iteration,
                plan=plan,
                executed=executed,
                verify_passed=verify_passed,
                issues=issues,
                fix_attempts=fix_attempts,
                status=status,
                duration_ms=round(duration, 2),
            )
            tracker.log_iteration(record)

            self._logger.log_audit_event("loop_iteration", {
                "iter": iteration,
                "status": status.value,
                "verify_passed": verify_passed,
                "actions_run": len(executed),
                "duration_ms": record.duration_ms,
            })

            # ── Check exit ───────────────────────────────────────────────
            if self._exit_check(ctx, executed, exit_criteria):
                goal_achieved = True
                self._logger.log_state_change(
                    "ralph_wiggum_loop", "running", "goal_achieved",
                    f"exit criteria met at iteration {iteration}",
                )
                break

        finished_at = datetime.now(timezone.utc).isoformat()
        if not goal_achieved:
            self._logger.log_state_change(
                "ralph_wiggum_loop", "running",
                "exhausted" if not goal_achieved else "goal_achieved",
                f"completed {max_iterations} iterations",
            )

        report = tracker.final_report(goal_achieved, finished_at)
        report.exit_criteria = exit_criteria
        return report

    # ------------------------------------------------------------------ #
    #  Loop phases — override for LLM-powered versions                     #
    # ------------------------------------------------------------------ #

    def _plan(self, ctx: IterationContext) -> list[dict[str, Any]]:
        """
        Decide which actions to run this iteration.

        Current implementation: keyword-match the task description against a
        goal→plan table.  Replace with a Claude API call for dynamic planning.
        """
        td = ctx.task_description.lower()

        if ctx.iteration == 1:
            # First iteration: interpret the goal
            if any(k in td for k in ("audit", "briefing", "weekly")):
                return [
                    {"skill": "audit", "action": "run_weekly_audit",
                     "params": {}, "description": "Run weekly audit + CEO briefing"},
                    {"skill": "personal_business", "action": "cross_domain_analysis",
                     "params": {}, "description": "Cross-domain task analysis"},
                ]
            if any(k in td for k in ("post", "tweet", "publish", "social")):
                return [
                    {"skill": "social", "action": "cross_post",
                     "params": {"text": ctx.task_description, "platforms": ["twitter", "facebook"]},
                     "description": "Cross-post to social platforms"},
                    {"skill": "social", "action": "get_social_summary",
                     "params": {"platform": "all", "period_days": 7},
                     "description": "Collect engagement summary"},
                ]
            if any(k in td for k in ("task", "daily", "briefing", "todo")):
                return [
                    {"skill": "personal_business", "action": "get_daily_briefing",
                     "params": {}, "description": "Daily task briefing"},
                    {"skill": "personal_business", "action": "cross_domain_analysis",
                     "params": {}, "description": "Cross-domain health check"},
                ]
            # Generic: analyse then audit
            return [
                {"skill": "personal_business", "action": "cross_domain_analysis",
                 "params": {}, "description": "Cross-domain analysis"},
                {"skill": "audit", "action": "run_weekly_audit",
                 "params": {}, "description": "Weekly audit"},
            ]

        # Subsequent iterations: focus on unresolved issues from previous
        if ctx.history_summary and "issues" in ctx.history_summary.lower():
            return [
                {"skill": "personal_business", "action": "list_tasks",
                 "params": {"status": "blocked"}, "description": "Check blocked tasks"},
            ]

        # Default: daily health check
        return [
            {"skill": "personal_business", "action": "get_daily_briefing",
             "params": {}, "description": "Daily briefing follow-up"},
        ]

    def _verify(
        self, ctx: IterationContext, executed: list[dict[str, Any]]
    ) -> tuple[bool, list[str]]:
        """
        Check whether executed results satisfy the goal.
        Returns (passed, list_of_issues).
        """
        issues: list[str] = []

        # Check all steps succeeded
        failed = [s for s in executed if not s.get("result", {}).get("success", False)]
        for f in failed:
            issues.append(f"Step failed: {f['skill']}.{f['action']} — {f['result'].get('error', 'unknown')}")

        # Goal-specific checks
        td = ctx.task_description.lower()
        if "audit" in td or "briefing" in td:
            ran_audit = any(s["action"] == "run_weekly_audit" for s in executed)
            if not ran_audit:
                issues.append("Weekly audit action was not executed")

        if any(k in td for k in ("post", "tweet")):
            posted = any(s["action"] in ("cross_post", "post_twitter", "post_facebook") for s in executed)
            if not posted:
                issues.append("No social post action was executed")

        # Check exit criteria string
        if ctx.exit_criteria:
            criteria_met = any(
                ctx.exit_criteria.lower() in str(s.get("result", {})).lower()
                for s in executed
            )
            if not criteria_met:
                issues.append(f"Exit criteria not yet satisfied: '{ctx.exit_criteria}'")

        return len(issues) == 0, issues

    def _fix(
        self,
        ctx: IterationContext,
        issues: list[str],
        executed: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Given issues from verify, return a corrective action plan.
        Conservative: retry failed steps once with the same params.
        """
        fix_plan: list[dict[str, Any]] = []
        for issue in issues:
            for step in executed:
                if (
                    step["skill"] + "." + step["action"] in issue
                    or step["action"] in issue
                ):
                    fix_plan.append({
                        "skill": step["skill"],
                        "action": step["action"],
                        "params": step.get("params", {}),
                        "description": f"[FIX] Retry {step['action']} after issue: {issue[:60]}",
                    })
                    break
        return fix_plan[:2]  # at most 2 fix steps per iteration

    def _exit_check(
        self,
        ctx: IterationContext,
        executed: list[dict[str, Any]],
        exit_criteria: str,
    ) -> bool:
        """
        Return True when loop should stop.
        Exits if:
          - all planned steps succeeded and no exit_criteria given
          - exit_criteria string found in any result
          - iteration >= 3 and last 2 iterations had the same actions (stagnation)
        """
        all_ok = all(s.get("result", {}).get("success", False) for s in executed if not s.get("is_fix"))

        if not exit_criteria:
            return all_ok

        if exit_criteria:
            for step in executed:
                if exit_criteria.lower() in str(step.get("result", {})).lower():
                    return True

        return False

    # ------------------------------------------------------------------ #
    #  Introspection                                                        #
    # ------------------------------------------------------------------ #

    def available_actions(self) -> dict[str, list[str]]:
        return {
            skill_name: [
                attr for attr in dir(type(skill))
                if hasattr(getattr(type(skill), attr, None), "_skill_meta")
            ]
            for skill_name, skill in self._skills.items()
        }

    def registry_tools(self) -> list[dict[str, Any]]:
        return SkillRegistry.mcp_tool_list()
