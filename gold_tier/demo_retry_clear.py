"""
Ralph Wiggum Loop - Failure Demonstration with Clear Logging

This demo creates a skill that fails predictably to show:
  - Retry attempts with exponential backoff
  - How the loop handles failures
  - Fix phase in action
  - Detailed logging of the entire process
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
            print(f"  [{timestamp}] ❌ FAILED - Simulating transient error")
            raise Exception(f"Transient failure #{self.attempt_count}")

        print(f"  [{timestamp}] ✓ SUCCESS after {self.attempt_count} attempts")
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
        print(f"  [{timestamp}] ✓ SUCCESS")
        return {"status": "success", "message": message}


async def demo_with_retry():
    """Show retry mechanism with exponential backoff."""
    print("=" * 70)
    print("  DEMO: Retry with Exponential Backoff")
    print("=" * 70)
    print("\nThis demonstrates:")
    print("  - Action fails twice")
    print("  - Retry with exponential backoff (0.5s, 1.0s)")
    print("  - Success on 3rd attempt")
    print("  - All attempts logged")
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
    print(f"  Total time: {elapsed:.2f}s")
    print(f"  Data: {result.get('data', {})}")

    # Show error logs
    print("\n[ERROR LOG]")
    with open("logs/retry_demo/errors.jsonl") as f:
        errors = [line for line in f.readlines()]
        print(f"  Total errors logged: {len(errors)}")
        for i, line in enumerate(errors, 1):
            import json
            entry = json.loads(line)
            print(f"\n  Error #{i}:")
            print(f"    Time: {entry['ts'][11:23]}")
            print(f"    Skill: {entry['skill']}.{entry['action']}")
            print(f"    Error: {entry['error']}")
            print(f"    Recoverable: {entry['recoverable']}")


async def demo_ralph_wiggum_with_failures():
    """Show Ralph Wiggum loop handling failures."""
    print("\n\n" + "=" * 70)
    print("  DEMO: Ralph Wiggum Loop with Failures")
    print("=" * 70)
    print("\nThis demonstrates:")
    print("  - Loop plans actions")
    print("  - First iteration: flaky_task fails")
    print("  - Verification detects failure")
    print("  - Fix phase retries the failed action")
    print("  - Second iteration: succeeds")
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
        marker = "✓" if rec.verify_passed else "✗"
        print(f"\n  Iteration {rec.iteration} {marker}")
        print(f"    Status: {rec.status.value}")
        print(f"    Duration: {rec.duration_ms:.2f}ms")

        print(f"    Executed actions:")
        for step in rec.executed:
            result = step['result']
            status = "✓" if result['success'] else "✗"
            is_fix = " (FIX ATTEMPT)" if step.get('is_fix') else ""
            print(f"      {status} {step['skill']}.{step['action']}{is_fix}")
            if not result['success']:
                print(f"         Error: {result['error']}")

        if rec.issues:
            print(f"    Issues: {len(rec.issues)}")
            for issue in rec.issues:
                print(f"      - {issue[:70]}")

        if rec.fix_attempts > 0:
            print(f"    Fix attempts: {rec.fix_attempts}")


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

    print("\n📊 Summary:")
    print("  ✓ Retry mechanism handles transient failures")
    print("  ✓ Exponential backoff prevents overwhelming services")
    print("  ✓ Ralph Wiggum loop detects failures in verification")
    print("  ✓ Fix phase attempts corrections")
    print("  ✓ All failures are logged for debugging")

    print("\n📁 View logs:")
    print("  - Retry demo: logs/retry_demo/")
    print("  - Loop demo: logs/loop_demo/")


if __name__ == "__main__":
    asyncio.run(main())
