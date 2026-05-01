"""
Ralph Wiggum Loop - Complete Failure & Recovery Demo (ASCII-safe)

Shows the complete error recovery flow with clear console output.
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
        self.attempt_count = 0

    @agent_skill(
        name="flaky_task",
        description="Fails first 2 times, succeeds on 3rd",
        domain=["business"]
    )
    async def flaky_task(self, data: str) -> dict:
        """Simulates a flaky external service."""
        self.attempt_count += 1
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        print(f"\n  [{timestamp}] ATTEMPT #{self.attempt_count}: flaky_task('{data}')")

        if self.attempt_count <= 2:
            print(f"  [{timestamp}] [FAIL] Simulating transient error")
            raise Exception(f"Transient failure #{self.attempt_count}")

        print(f"  [{timestamp}] [SUCCESS] Completed after {self.attempt_count} attempts")
        return {
            "status": "success",
            "data": data,
            "total_attempts": self.attempt_count
        }

    @agent_skill(
        name="reliable_task",
        description="Always succeeds",
        domain=["business"]
    )
    async def reliable_task(self, message: str) -> dict:
        """Always succeeds immediately."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"\n  [{timestamp}] RELIABLE TASK: '{message}'")
        print(f"  [{timestamp}] [SUCCESS]")
        return {"status": "success", "message": message}


async def demo_with_retry():
    """Show retry mechanism with exponential backoff."""
    print("=" * 70)
    print("  DEMO 1: Retry with Exponential Backoff")
    print("=" * 70)
    print("\nScenario:")
    print("  - Action fails twice")
    print("  - Retry with exponential backoff (0.5s, 1.0s)")
    print("  - Success on 3rd attempt")
    print("\n" + "-" * 70)

    logger = AuditLogger("retry_demo", log_dir="logs/retry_demo/")
    recovery = RecoverySkill(
        max_retries=3,
        backoff_base=0.5,
        backoff_multiplier=2.0,
        logger=logger
    )

    demo = DemoSkill(recovery=recovery, logger=logger)
    agent = AutonomousAgent(
        skills=[demo],
        recovery=recovery,
        logger=logger,
        data_dir="data/retry_demo/"
    )

    print("\nExecuting: demo.flaky_task")
    start = time.time()

    result = await agent.execute_task({
        "skill": "demo",
        "action": "flaky_task",
        "params": {"data": "important data"},
    })

    elapsed = time.time() - start

    print("\n" + "-" * 70)
    print(f"[RESULT]")
    print(f"  Success: {result['success']}")
    print(f"  Total time: {elapsed:.2f}s (includes backoff delays)")
    if result['success']:
        print(f"  Data: {result.get('data', {})}")
    else:
        print(f"  Error: {result.get('error', 'unknown')}")

    # Show error logs
    print("\n[ERROR LOG]")
    import json
    with open("logs/retry_demo/errors.jsonl") as f:
        errors = [json.loads(line) for line in f.readlines()]
        print(f"  Total errors logged: {len(errors)}")
        for i, entry in enumerate(errors[-3:], 1):
            print(f"\n  Error #{i}:")
            print(f"    Time: {entry['ts'][11:23]}")
            print(f"    Action: {entry['skill']}.{entry['action']}")
            print(f"    Message: {entry['error'][:60]}")
            print(f"    Recoverable: {entry['recoverable']}")


async def demo_ralph_wiggum_with_failures():
    """Show Ralph Wiggum loop handling failures."""
    print("\n\n" + "=" * 70)
    print("  DEMO 2: Ralph Wiggum Loop with Failures")
    print("=" * 70)
    print("\nScenario:")
    print("  - Loop plans actions")
    print("  - First iteration: flaky_task fails")
    print("  - Verification detects failure")
    print("  - Fix phase retries the failed action")
    print("  - Subsequent iterations: eventually succeeds")
    print("\n" + "-" * 70)

    logger = AuditLogger("loop_demo", log_dir="logs/loop_demo/")
    recovery = RecoverySkill(
        max_retries=3,
        backoff_base=0.3,
        backoff_multiplier=2.0,
        logger=logger
    )

    demo = DemoSkill(recovery=recovery, logger=logger)
    agent = AutonomousAgent(
        skills=[demo],
        recovery=recovery,
        logger=logger,
        data_dir="data/loop_demo/"
    )

    print("\nTask: 'Process data with flaky service'")
    print("Max iterations: 3")
    print("\n" + "-" * 70)

    report = await agent.run_ralph_wiggum_loop(
        task_description="Process data with flaky service",
        max_iterations=3,
        exit_criteria="",
    )

    print("\n" + "-" * 70)
    print(f"[LOOP RESULT]")
    print(f"  Goal achieved: {report.goal_achieved}")
    print(f"  Total iterations: {report.total_iterations}")
    print(f"  Final status: {report.final_status}")

    print(f"\n[ITERATION BREAKDOWN]")
    for rec in report.iterations:
        marker = "[PASS]" if rec.verify_passed else "[FAIL]"
        print(f"\n  Iteration {rec.iteration} {marker}")
        print(f"    Status: {rec.status.value}")
        print(f"    Duration: {rec.duration_ms:.2f}ms")

        print(f"    Executed actions:")
        for step in rec.executed:
            result = step['result']
            status = "[OK]" if result['success'] else "[FAIL]"
            is_fix = " (FIX ATTEMPT)" if step.get('is_fix') else ""
            print(f"      {status} {step['skill']}.{step['action']}{is_fix}")
            if not result['success']:
                print(f"         Error: {result['error'][:60]}")

        if rec.issues:
            print(f"    Issues detected: {len(rec.issues)}")
            for issue in rec.issues[:2]:
                print(f"      - {issue[:70]}")

        if rec.fix_attempts > 0:
            print(f"    Fix attempts: {rec.fix_attempts}")

    # Show progress file
    print(f"\n[PROGRESS FILE]")
    print(f"  Location: {report.progress_file}")
    import json
    from pathlib import Path
    if Path(report.progress_file).exists():
        with open(report.progress_file) as f:
            progress = json.load(f)
        print(f"  Iterations tracked: {progress['iteration_count']}")
        print(f"  Last updated: {progress['updated_at'][:19]}")


async def main():
    print("\n" + "=" * 70)
    print("  Ralph Wiggum Loop - Failure & Recovery Demonstration")
    print("=" * 70)

    await demo_with_retry()
    await asyncio.sleep(0.5)

    await demo_ralph_wiggum_with_failures()

    print("\n\n" + "=" * 70)
    print("  Demo Complete!")
    print("=" * 70)

    print("\nKey Observations:")
    print("  [1] Retry mechanism handles transient failures")
    print("  [2] Exponential backoff prevents overwhelming services")
    print("  [3] Ralph Wiggum loop detects failures in verification")
    print("  [4] Fix phase attempts corrections")
    print("  [5] All failures are logged for debugging")
    print("  [6] Progress is persisted after each iteration")

    print("\nLog Files:")
    print("  - Retry demo: logs/retry_demo/")
    print("  - Loop demo: logs/loop_demo/")
    print("  - View with: python -c \"import json; ...\"")


if __name__ == "__main__":
    asyncio.run(main())
