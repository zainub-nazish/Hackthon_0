"""
Ralph Wiggum Loop - Failure Scenario Demo

This demo explicitly simulates failures to show:
  - Retry mechanism with exponential backoff
  - Circuit breaker opening after repeated failures
  - Fix phase attempting corrections
  - Fallback execution
  - Detailed logging of the entire process
"""

import asyncio
import time
from dataclasses import dataclass

from agent_skills import (
    AuditLogger,
    AutonomousAgent,
    BaseSkill,
    RecoverySkill,
    SkillResult,
    agent_skill,
)


@dataclass
class FailureConfig:
    """Configure when a skill should fail."""
    fail_count: int = 0
    max_failures: int = 2
    should_fail: bool = True


class UnreliableSkill(BaseSkill):
    """A skill that fails predictably to demonstrate recovery mechanisms."""

    SKILL_NAME = "unreliable"

    def __init__(self, recovery=None, logger=None):
        super().__init__(recovery=recovery, logger=logger)
        self.call_count = 0
        self.failure_config = FailureConfig()

    @agent_skill(
        name="flaky_action",
        description="An action that fails the first N times, then succeeds",
        domain=["business"]
    )
    async def flaky_action(self, data: str) -> dict:
        """Fails first 2 times, succeeds on 3rd attempt."""
        self.call_count += 1
        print(f"\n  [FLAKY_ACTION] Attempt #{self.call_count}")

        if self.call_count <= 2:
            print(f"  [FLAKY_ACTION] Simulating failure (attempt {self.call_count}/2)")
            raise Exception(f"Temporary failure on attempt {self.call_count}")

        print(f"  [FLAKY_ACTION] Success on attempt {self.call_count}!")
        return {"status": "success", "data": data, "attempts": self.call_count}

    @agent_skill(
        name="always_fails",
        description="An action that always fails to trigger circuit breaker",
        domain=["business"]
    )
    async def always_fails(self) -> dict:
        """Always fails to demonstrate circuit breaker."""
        print(f"\n  [ALWAYS_FAILS] This will fail...")
        raise Exception("Permanent failure - circuit breaker should open")

    @agent_skill(
        name="reliable_action",
        description="An action that always succeeds",
        domain=["business"]
    )
    async def reliable_action(self, message: str) -> dict:
        """Always succeeds."""
        print(f"\n  [RELIABLE_ACTION] Processing: {message}")
        return {"status": "success", "message": message}


async def demo_retry_with_success():
    """Demo: Action fails twice, succeeds on third retry."""
    print("\n" + "=" * 70)
    print("  DEMO 1: Retry with Eventual Success")
    print("=" * 70)
    print("\nScenario: Action fails 2 times, then succeeds on retry")
    print("Expected: 3 attempts total, final success\n")

    logger = AuditLogger("failure_demo", log_dir="logs/failure_demo/")
    recovery = RecoverySkill(
        max_retries=3,
        backoff_base=0.5,
        backoff_multiplier=2.0,
        logger=logger
    )

    unreliable = UnreliableSkill(recovery=recovery, logger=logger)
    agent = AutonomousAgent(
        skills=[unreliable],
        recovery=recovery,
        logger=logger,
        data_dir="data/failure_demo/"
    )

    print("Executing task: unreliable.flaky_action")
    print("-" * 70)

    result = await agent.execute_task({
        "skill": "unreliable",
        "action": "flaky_action",
        "params": {"data": "test data"},
    })

    print("\n" + "-" * 70)
    print(f"[RESULT]")
    print(f"  Success: {result['success']}")
    print(f"  Data: {result.get('data', {})}")
    print(f"  Duration: {result['duration_ms']:.2f}ms")
    print(f"  Fallback used: {result.get('fallback_used', False)}")


async def demo_circuit_breaker():
    """Demo: Repeated failures trigger circuit breaker."""
    print("\n" + "=" * 70)
    print("  DEMO 2: Circuit Breaker Opens After Repeated Failures")
    print("=" * 70)
    print("\nScenario: Action fails 5+ times, circuit breaker opens")
    print("Expected: Circuit opens, subsequent calls fail fast\n")

    logger = AuditLogger("failure_demo", log_dir="logs/failure_demo/")
    recovery = RecoverySkill(
        max_retries=2,
        circuit_failure_threshold=3,
        circuit_recovery_timeout=5.0,
        logger=logger
    )

    unreliable = UnreliableSkill(recovery=recovery, logger=logger)
    agent = AutonomousAgent(
        skills=[unreliable],
        recovery=recovery,
        logger=logger,
        data_dir="data/failure_demo/"
    )

    print("Executing task 5 times: unreliable.always_fails")
    print("-" * 70)

    for i in range(1, 6):
        print(f"\n[ATTEMPT {i}]")
        result = await agent.execute_task({
            "skill": "unreliable",
            "action": "always_fails",
            "params": {},
        })
        print(f"  Success: {result['success']}")
        if not result['success']:
            print(f"  Error: {result.get('error', 'unknown')[:50]}")

        # Check circuit status
        status = recovery.circuit_status()
        circuit_key = "unreliable.always_fails"
        if circuit_key in status:
            print(f"  Circuit status: {status[circuit_key]}")

    print("\n" + "-" * 70)
    print("[CIRCUIT BREAKER STATUS]")
    for key, state in recovery.circuit_status().items():
        print(f"  {key}: {state}")


async def demo_fallback():
    """Demo: Fallback handler is used when primary fails."""
    print("\n" + "=" * 70)
    print("  DEMO 3: Fallback Handler Execution")
    print("=" * 70)
    print("\nScenario: Primary action fails, fallback provides degraded service")
    print("Expected: Fallback executes, returns alternative result\n")

    logger = AuditLogger("failure_demo", log_dir="logs/failure_demo/")
    recovery = RecoverySkill(max_retries=2, logger=logger)

    # Register fallback
    async def fallback_handler(data: str):
        print(f"\n  [FALLBACK] Primary failed, using fallback for: {data}")
        return {"status": "fallback", "data": data, "degraded": True}

    recovery.register_fallback("unreliable.flaky_action", fallback_handler)

    unreliable = UnreliableSkill(recovery=recovery, logger=logger)
    # Reset call count so it fails
    unreliable.call_count = 0

    agent = AutonomousAgent(
        skills=[unreliable],
        recovery=recovery,
        logger=logger,
        data_dir="data/failure_demo/"
    )

    print("Executing task: unreliable.flaky_action (will fail, trigger fallback)")
    print("-" * 70)

    result = await agent.execute_task({
        "skill": "unreliable",
        "action": "flaky_action",
        "params": {"data": "important data"},
    })

    print("\n" + "-" * 70)
    print(f"[RESULT]")
    print(f"  Success: {result['success']}")
    print(f"  Data: {result.get('data', {})}")
    print(f"  Fallback used: {result.get('fallback_used', False)}")


async def demo_ralph_wiggum_with_failures():
    """Demo: Ralph Wiggum loop with failures and fix attempts."""
    print("\n" + "=" * 70)
    print("  DEMO 4: Ralph Wiggum Loop with Failures & Fix Attempts")
    print("=" * 70)
    print("\nScenario: Loop encounters failures, attempts fixes, eventually succeeds")
    print("Expected: Multiple iterations with fix attempts\n")

    logger = AuditLogger("failure_demo", log_dir="logs/failure_demo/")
    recovery = RecoverySkill(max_retries=2, logger=logger)

    unreliable = UnreliableSkill(recovery=recovery, logger=logger)
    unreliable.call_count = 0  # Reset for fresh failures

    agent = AutonomousAgent(
        skills=[unreliable],
        recovery=recovery,
        logger=logger,
        data_dir="data/failure_demo/"
    )

    print("Task: 'Process data with unreliable service'")
    print("Max iterations: 5")
    print("-" * 70)

    report = await agent.run_ralph_wiggum_loop(
        task_description="Process data with unreliable service",
        max_iterations=5,
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
        print(f"    Actions executed: {len(rec.executed)}")
        if rec.issues:
            print(f"    Issues: {len(rec.issues)}")
            for issue in rec.issues[:2]:
                print(f"      - {issue[:60]}")
        if rec.fix_attempts > 0:
            print(f"    Fix attempts: {rec.fix_attempts}")


async def main():
    print("=" * 70)
    print("  Ralph Wiggum Loop - Failure & Recovery Demo")
    print("=" * 70)
    print("\nThis demo shows the complete error recovery flow:")
    print("  1. Retry with exponential backoff")
    print("  2. Circuit breaker opening after repeated failures")
    print("  3. Fallback execution for graceful degradation")
    print("  4. Ralph Wiggum loop fix attempts")

    await demo_retry_with_success()
    await asyncio.sleep(1)

    await demo_circuit_breaker()
    await asyncio.sleep(1)

    await demo_fallback()
    await asyncio.sleep(1)

    await demo_ralph_wiggum_with_failures()

    print("\n" + "=" * 70)
    print("  Demo Complete!")
    print("=" * 70)
    print("\nKey Takeaways:")
    print("  ✓ Retry mechanism handles transient failures")
    print("  ✓ Circuit breaker prevents cascading failures")
    print("  ✓ Fallback provides graceful degradation")
    print("  ✓ Ralph Wiggum loop attempts fixes on verification failure")
    print("  ✓ All failures are logged for debugging")

    print("\nView detailed logs:")
    print("  - Actions: logs/failure_demo/actions.jsonl")
    print("  - Errors: logs/failure_demo/errors.jsonl")
    print("  - Audit: logs/failure_demo/audit.jsonl")


if __name__ == "__main__":
    asyncio.run(main())
