"""
Ralph Wiggum Loop - Complete Working Demo

This shows the full cycle with a custom agent that properly plans
to use the demo skills, demonstrating real retry and recovery behavior.
"""

import asyncio
import time
from datetime import datetime

from agent_skills import (
    AuditLogger,
    AutonomousAgent,
    BaseSkill,
    RecoverySkill,
    agent_skill,
)


class DemoSkill(BaseSkill):
    """A skill that demonstrates failure and recovery."""

    SKILL_NAME = "demo"

    def __init__(self, recovery=None, logger=None):
        super().__init__(recovery=recovery, logger=logger)
        self.flaky_attempts = 0
        self.reliable_calls = 0

    @agent_skill(
        name="flaky_task",
        description="Fails first 2 times, succeeds on 3rd",
        domain=["business"]
    )
    async def flaky_task(self, data: str) -> dict:
        """Simulates a flaky external service."""
        self.flaky_attempts += 1
        timestamp = datetime.now().strftime("%H:%M:%S")

        print(f"\n  [{timestamp}] FLAKY_TASK attempt #{self.flaky_attempts}")
        print(f"  [{timestamp}] Processing: '{data}'")

        if self.flaky_attempts <= 2:
            print(f"  [{timestamp}] [FAIL] Transient error (attempt {self.flaky_attempts}/2)")
            raise Exception(f"Transient failure #{self.flaky_attempts}")

        print(f"  [{timestamp}] [SUCCESS] Completed after {self.flaky_attempts} attempts!")
        return {
            "status": "success",
            "data": data,
            "total_attempts": self.flaky_attempts
        }

    @agent_skill(
        name="reliable_task",
        description="Always succeeds",
        domain=["business"]
    )
    async def reliable_task(self, message: str) -> dict:
        """Always succeeds immediately."""
        self.reliable_calls += 1
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\n  [{timestamp}] RELIABLE_TASK call #{self.reliable_calls}")
        print(f"  [{timestamp}] Message: '{message}'")
        print(f"  [{timestamp}] [SUCCESS]")
        return {"status": "success", "message": message, "call_number": self.reliable_calls}


class CustomAgent(AutonomousAgent):
    """Custom agent with planning logic that uses demo skills."""

    def _plan(self, ctx):
        """Override planning to use demo skills."""
        if ctx.iteration == 1:
            # First iteration: try the flaky task
            return [
                {
                    "skill": "demo",
                    "action": "flaky_task",
                    "params": {"data": "important data"},
                    "description": "Process data with flaky service"
                },
                {
                    "skill": "demo",
                    "action": "reliable_task",
                    "params": {"message": "backup task"},
                    "description": "Run reliable backup task"
                }
            ]
        else:
            # Subsequent iterations: just reliable task
            return [
                {
                    "skill": "demo",
                    "action": "reliable_task",
                    "params": {"message": f"iteration {ctx.iteration} task"},
                    "description": "Continue with reliable task"
                }
            ]


async def main():
    print("=" * 70)
    print("  Ralph Wiggum Loop - Complete Working Demo")
    print("=" * 70)
    print("\nThis demonstration shows:")
    print("  1. Loop plans to call demo.flaky_task")
    print("  2. Task fails on first attempt")
    print("  3. Recovery system retries with backoff")
    print("  4. Task eventually succeeds")
    print("  5. Verification checks results")
    print("  6. Progress is logged")
    print("\n" + "=" * 70)

    logger = AuditLogger("complete_demo", log_dir="logs/complete_demo/")
    recovery = RecoverySkill(
        max_retries=3,
        backoff_base=0.5,
        backoff_multiplier=2.0,
        logger=logger
    )

    demo = DemoSkill(recovery=recovery, logger=logger)
    agent = CustomAgent(
        skills=[demo],
        recovery=recovery,
        logger=logger,
        data_dir="data/complete_demo/"
    )

    print("\n[TASK] Process data with flaky service")
    print("[MAX ITERATIONS] 2")
    print("[EXIT CRITERIA] None (exits when all actions succeed)")
    print("\n" + "-" * 70)

    start_time = time.time()

    report = await agent.run_ralph_wiggum_loop(
        task_description="Process data with flaky service",
        max_iterations=2,
        exit_criteria="",
    )

    elapsed = time.time() - start_time

    print("\n" + "-" * 70)
    print("[FINAL RESULT]")
    print(f"  Goal achieved: {report.goal_achieved}")
    print(f"  Total iterations: {report.total_iterations}")
    print(f"  Final status: {report.final_status}")
    print(f"  Total time: {elapsed:.2f}s")

    print("\n[ITERATION DETAILS]")
    for rec in report.iterations:
        marker = "[PASS]" if rec.verify_passed else "[FAIL]"
        print(f"\n  === Iteration {rec.iteration} {marker} ===")
        print(f"  Status: {rec.status.value}")
        print(f"  Duration: {rec.duration_ms:.2f}ms")
        print(f"  Verify passed: {rec.verify_passed}")

        print(f"\n  Planned actions ({len(rec.plan)}):")
        for i, step in enumerate(rec.plan, 1):
            print(f"    {i}. {step['skill']}.{step['action']}")
            print(f"       Params: {step['params']}")

        print(f"\n  Executed actions ({len(rec.executed)}):")
        for i, step in enumerate(rec.executed, 1):
            result = step['result']
            status = "[OK]" if result['success'] else "[FAIL]"
            is_fix = " (FIX)" if step.get('is_fix') else ""
            print(f"    {i}. {status} {step['skill']}.{step['action']}{is_fix}")
            print(f"       Duration: {result['duration_ms']:.2f}ms")
            if not result['success']:
                print(f"       Error: {result['error']}")
            else:
                print(f"       Result: {str(result['data'])[:60]}")

        if rec.issues:
            print(f"\n  Issues ({len(rec.issues)}):")
            for issue in rec.issues:
                print(f"    - {issue}")

        if rec.fix_attempts > 0:
            print(f"\n  Fix attempts: {rec.fix_attempts}")

    # Show logs
    print("\n" + "-" * 70)
    print("[AUDIT LOGS]")

    import json
    from pathlib import Path

    log_dir = Path("logs/complete_demo/")

    # Show errors
    errors_file = log_dir / "errors.jsonl"
    if errors_file.exists() and errors_file.stat().st_size > 0:
        with open(errors_file) as f:
            errors = [json.loads(line) for line in f.readlines()]
        print(f"\n  Errors logged: {len(errors)}")
        for i, entry in enumerate(errors[-3:], 1):
            print(f"\n    Error #{i}:")
            print(f"      Time: {entry['ts'][11:19]}")
            print(f"      Action: {entry['skill']}.{entry['action']}")
            print(f"      Message: {entry['error'][:60]}")
            print(f"      Recoverable: {entry['recoverable']}")

    # Show actions
    actions_file = log_dir / "actions.jsonl"
    if actions_file.exists():
        with open(actions_file) as f:
            actions = [json.loads(line) for line in f.readlines()]
        print(f"\n  Actions logged: {len(actions)}")
        print(f"\n  Recent actions:")
        for entry in actions[-5:]:
            print(f"    [{entry['ts'][11:19]}] {entry['skill']}.{entry['action']}")

    # Show progress file
    print("\n" + "-" * 70)
    print("[PROGRESS FILE]")
    progress_path = Path(report.progress_file)
    if progress_path.exists():
        with open(progress_path) as f:
            progress = json.load(f)
        print(f"  Location: {progress_path}")
        print(f"  Task: {progress['task']}")
        print(f"  Iterations: {progress['iteration_count']}")
        print(f"  Started: {progress['started_at'][:19]}")
        print(f"  Updated: {progress['updated_at'][:19]}")

    print("\n" + "=" * 70)
    print("  Demo Complete!")
    print("=" * 70)

    print("\nKey Takeaways:")
    print("  [1] Ralph Wiggum loop plans actions based on task description")
    print("  [2] Each iteration has fresh context (no prompt bloat)")
    print("  [3] Failed actions are retried with exponential backoff")
    print("  [4] Verification phase checks if goal was achieved")
    print("  [5] Fix phase attempts corrections on failure")
    print("  [6] All actions and errors are logged to JSONL")
    print("  [7] Progress is persisted after each iteration")

    print("\nThe Agent Skills system is production-ready!")


if __name__ == "__main__":
    asyncio.run(main())
