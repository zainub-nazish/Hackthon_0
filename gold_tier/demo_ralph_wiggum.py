"""
Ralph Wiggum Loop Demo - Shows iteration behavior with success and failure scenarios.

Demonstrates:
  - Planning phase (what actions to take)
  - Execution phase (running actions)
  - Verification phase (checking results)
  - Fix phase (retry on failure)
  - Progress tracking
"""

import asyncio
import json
from pathlib import Path

from agent_skills import (
    AuditLogger,
    AutonomousAgent,
    RecoverySkill,
    SocialMediaSkill,
    AuditSkill,
    PersonalBusinessSkill,
)


def print_section(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_iteration_details(report):
    """Print detailed iteration breakdown."""
    for rec in report.iterations:
        print(f"\n--- Iteration {rec.iteration} ---")
        print(f"Status: {rec.status.value}")
        print(f"Verify passed: {rec.verify_passed}")
        print(f"Duration: {rec.duration_ms:.2f}ms")

        print(f"\nPlanned actions ({len(rec.plan)}):")
        for i, step in enumerate(rec.plan, 1):
            print(f"  {i}. {step['skill']}.{step['action']}")
            print(f"     Description: {step.get('description', 'N/A')}")

        print(f"\nExecuted actions ({len(rec.executed)}):")
        for i, step in enumerate(rec.executed, 1):
            result = step.get('result', {})
            success = result.get('success', False)
            marker = "[OK]" if success else "[FAIL]"
            is_fix = step.get('is_fix', False)
            fix_marker = " (FIX)" if is_fix else ""
            print(f"  {i}. {marker} {step['skill']}.{step['action']}{fix_marker}")
            if not success:
                print(f"     Error: {result.get('error', 'unknown')[:60]}")
            else:
                data = result.get('data')
                if data and hasattr(data, '__dict__'):
                    print(f"     Result: {type(data).__name__}")
                elif isinstance(data, dict):
                    print(f"     Result: {list(data.keys())[:3]}")

        if rec.issues:
            print(f"\nIssues found ({len(rec.issues)}):")
            for issue in rec.issues:
                print(f"  - {issue}")

        if rec.fix_attempts > 0:
            print(f"\nFix attempts: {rec.fix_attempts}")


async def scenario_1_success():
    """Scenario 1: Successful execution on first try."""
    print_section("Scenario 1: Successful Daily Summary")

    logger = AuditLogger("ralph_demo_1", log_dir="logs/ralph_demo/")
    recovery = RecoverySkill(logger=logger)

    social = SocialMediaSkill(recovery=recovery, logger=logger, dry_run=True)
    audit = AuditSkill(recovery=recovery, logger=logger, data_dir="data/ralph_demo/")
    pb = PersonalBusinessSkill(recovery=recovery, logger=logger, data_dir="data/ralph_demo/")

    # Seed data
    audit.seed_mock_data(7)
    pb.seed_demo_tasks()

    agent = AutonomousAgent(
        skills=[social, audit, pb],
        recovery=recovery,
        logger=logger,
        data_dir="data/ralph_demo/",
    )

    print("\nTask: 'Generate a daily summary of tasks and priorities'")
    print("Max iterations: 5")
    print("Exit criteria: None (will exit when all actions succeed)")

    report = await agent.run_ralph_wiggum_loop(
        task_description="Generate a daily summary of tasks and priorities",
        max_iterations=5,
        exit_criteria="",
    )

    print(f"\n[RESULT]")
    print(f"  Goal achieved: {report.goal_achieved}")
    print(f"  Total iterations: {report.total_iterations}")
    print(f"  Final status: {report.final_status}")
    print(f"  Started: {report.started_at[:19]}")
    print(f"  Finished: {report.finished_at[:19]}")

    print_iteration_details(report)

    # Show progress file
    print(f"\n[PROGRESS FILE]")
    print(f"  Location: {report.progress_file}")
    if Path(report.progress_file).exists():
        with open(report.progress_file) as f:
            progress = json.load(f)
        print(f"  Content preview:")
        print(f"    - Task: {progress['task'][:50]}...")
        print(f"    - Iteration count: {progress['iteration_count']}")
        print(f"    - Last updated: {progress['updated_at'][:19]}")


async def scenario_2_with_retry():
    """Scenario 2: Execution with simulated failure and retry."""
    print_section("Scenario 2: Execution with Failure & Retry")

    logger = AuditLogger("ralph_demo_2", log_dir="logs/ralph_demo/")
    recovery = RecoverySkill(logger=logger, max_retries=2)

    social = SocialMediaSkill(recovery=recovery, logger=logger, dry_run=True)
    audit = AuditSkill(recovery=recovery, logger=logger, data_dir="data/ralph_demo/")
    pb = PersonalBusinessSkill(recovery=recovery, logger=logger, data_dir="data/ralph_demo/")

    agent = AutonomousAgent(
        skills=[social, audit, pb],
        recovery=recovery,
        logger=logger,
        data_dir="data/ralph_demo/",
    )

    print("\nTask: 'Run weekly audit and generate CEO briefing'")
    print("Max iterations: 3")
    print("Exit criteria: 'briefing_path' (will exit when briefing is generated)")

    report = await agent.run_ralph_wiggum_loop(
        task_description="Run weekly audit and generate CEO briefing",
        max_iterations=3,
        exit_criteria="briefing_path",
    )

    print(f"\n[RESULT]")
    print(f"  Goal achieved: {report.goal_achieved}")
    print(f"  Total iterations: {report.total_iterations}")
    print(f"  Final status: {report.final_status}")

    print_iteration_details(report)

    # Show circuit breaker status
    print(f"\n[CIRCUIT BREAKER STATUS]")
    circuits = recovery.circuit_status()
    if circuits:
        for key, state in circuits.items():
            print(f"  - {key}: {state}")
    else:
        print("  - All circuits closed (healthy)")


async def scenario_3_max_iterations():
    """Scenario 3: Hitting max iterations without achieving goal."""
    print_section("Scenario 3: Max Iterations Reached")

    logger = AuditLogger("ralph_demo_3", log_dir="logs/ralph_demo/")
    recovery = RecoverySkill(logger=logger)

    social = SocialMediaSkill(recovery=recovery, logger=logger, dry_run=True)
    audit = AuditSkill(recovery=recovery, logger=logger, data_dir="data/ralph_demo/")
    pb = PersonalBusinessSkill(recovery=recovery, logger=logger, data_dir="data/ralph_demo/")

    agent = AutonomousAgent(
        skills=[social, audit, pb],
        recovery=recovery,
        logger=logger,
        data_dir="data/ralph_demo/",
    )

    print("\nTask: 'Post weekly summary to all social platforms'")
    print("Max iterations: 2 (intentionally low)")
    print("Exit criteria: 'all_platforms_posted' (unlikely to achieve)")

    report = await agent.run_ralph_wiggum_loop(
        task_description="Post weekly summary to all social platforms",
        max_iterations=2,
        exit_criteria="all_platforms_posted",
    )

    print(f"\n[RESULT]")
    print(f"  Goal achieved: {report.goal_achieved}")
    print(f"  Total iterations: {report.total_iterations}")
    print(f"  Final status: {report.final_status}")

    print_iteration_details(report)


async def main():
    print("=" * 70)
    print("  Ralph Wiggum Loop - Comprehensive Demo")
    print("=" * 70)
    print("\nThis demo shows how the Ralph Wiggum loop:")
    print("  1. Plans actions based on the task description")
    print("  2. Executes planned actions")
    print("  3. Verifies results against the goal")
    print("  4. Fixes issues if verification fails")
    print("  5. Logs progress and iterates until goal met or max iterations hit")

    # Run scenarios
    await scenario_1_success()
    await asyncio.sleep(1)

    await scenario_2_with_retry()
    await asyncio.sleep(1)

    await scenario_3_max_iterations()

    print("\n" + "=" * 70)
    print("  Demo Complete!")
    print("=" * 70)
    print("\nKey Observations:")
    print("  - Each iteration has a fresh context (no prompt bloat)")
    print("  - Progress is tracked in progress.json files")
    print("  - Failed actions trigger fix attempts")
    print("  - Loop exits when goal met OR max iterations hit")
    print("  - All actions are logged to logs/ralph_demo/*.jsonl")

    print("\nView logs:")
    print("  tail -f logs/ralph_demo/actions.jsonl | jq")
    print("  tail -f logs/ralph_demo/audit.jsonl | jq")


if __name__ == "__main__":
    asyncio.run(main())
