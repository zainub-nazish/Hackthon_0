"""
Simple Ralph Wiggum Loop Demo - Shows actual retry behavior

This creates a minimal example that clearly demonstrates:
  1. How the loop plans actions
  2. How it executes them
  3. How it verifies results
  4. How it handles failures and retries
  5. What gets logged
"""

import asyncio
import json
from pathlib import Path

from agent_skills import (
    AuditLogger,
    AutonomousAgent,
    RecoverySkill,
    PersonalBusinessSkill,
)


async def main():
    print("=" * 70)
    print("  Ralph Wiggum Loop - Simple Working Demo")
    print("=" * 70)

    # Setup with real skills
    logger = AuditLogger("simple_demo", log_dir="logs/simple_demo/")
    recovery = RecoverySkill(
        max_retries=3,
        backoff_base=0.5,
        backoff_multiplier=2.0,
        logger=logger
    )

    pb = PersonalBusinessSkill(
        recovery=recovery,
        logger=logger,
        data_dir="data/simple_demo/"
    )

    # Seed some tasks
    pb.seed_demo_tasks()

    agent = AutonomousAgent(
        skills=[pb],
        recovery=recovery,
        logger=logger,
        data_dir="data/simple_demo/"
    )

    print("\n[TASK] Generate a daily summary")
    print("[MAX ITERATIONS] 3")
    print("[EXIT CRITERIA] None (exits when all actions succeed)")
    print("\n" + "-" * 70)

    report = await agent.run_ralph_wiggum_loop(
        task_description="Generate a daily summary",
        max_iterations=3,
        exit_criteria="",
    )

    print("\n" + "-" * 70)
    print("[FINAL RESULT]")
    print(f"  Goal achieved: {report.goal_achieved}")
    print(f"  Total iterations: {report.total_iterations}")
    print(f"  Final status: {report.final_status}")

    print("\n[ITERATION DETAILS]")
    for rec in report.iterations:
        print(f"\n  === Iteration {rec.iteration} ===")
        print(f"  Status: {rec.status.value}")
        print(f"  Verify passed: {rec.verify_passed}")
        print(f"  Duration: {rec.duration_ms:.2f}ms")

        print(f"\n  Planned actions:")
        for step in rec.plan:
            print(f"    - {step['skill']}.{step['action']}")

        print(f"\n  Executed actions:")
        for step in rec.executed:
            result = step['result']
            status = "[OK]" if result['success'] else "[FAIL]"
            print(f"    {status} {step['skill']}.{step['action']}")
            if not result['success']:
                print(f"         Error: {result['error'][:60]}")

        if rec.issues:
            print(f"\n  Issues detected:")
            for issue in rec.issues:
                print(f"    - {issue}")

        if rec.fix_attempts > 0:
            print(f"\n  Fix attempts made: {rec.fix_attempts}")

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

        print(f"\n  Iteration history:")
        for it in progress['iterations']:
            status_marker = "[PASS]" if it['verify_passed'] else "[FAIL]"
            print(f"    {status_marker} Iteration {it['iteration']}: {it['status']}")

    # Show logs
    print("\n" + "-" * 70)
    print("[AUDIT LOGS]")

    log_dir = Path("logs/simple_demo/")

    # Count log entries
    actions_file = log_dir / "actions.jsonl"
    errors_file = log_dir / "errors.jsonl"
    audit_file = log_dir / "audit.jsonl"

    if actions_file.exists():
        action_count = len(actions_file.read_text().strip().split('\n'))
        print(f"  Actions logged: {action_count}")

        # Show last few actions
        print(f"\n  Recent actions:")
        with open(actions_file) as f:
            lines = f.readlines()
            for line in lines[-5:]:
                entry = json.loads(line)
                print(f"    [{entry['ts'][11:19]}] {entry['skill']}.{entry['action']}")

    if errors_file.exists():
        error_count = len(errors_file.read_text().strip().split('\n')) if errors_file.stat().st_size > 0 else 0
        print(f"\n  Errors logged: {error_count}")

        if error_count > 0:
            print(f"  Recent errors:")
            with open(errors_file) as f:
                for line in f.readlines()[-3:]:
                    entry = json.loads(line)
                    print(f"    [{entry['ts'][11:19]}] {entry['skill']}.{entry['action']}")
                    print(f"      Error: {entry['error'][:60]}")

    if audit_file.exists():
        audit_count = len(audit_file.read_text().strip().split('\n'))
        print(f"\n  Audit events logged: {audit_count}")

    print("\n" + "=" * 70)
    print("  Demo Complete!")
    print("=" * 70)

    print("\nKey Points:")
    print("  1. Each iteration gets a fresh context")
    print("  2. Progress is persisted to JSON after each iteration")
    print("  3. All actions are logged with timing and results")
    print("  4. Loop exits when goal is met or max iterations reached")
    print("  5. Verification checks if actions achieved the goal")

    print("\nView full logs:")
    print(f"  python -c \"import json; [print(json.dumps(json.loads(l), indent=2)) for l in open('{actions_file}')]\"")


if __name__ == "__main__":
    asyncio.run(main())
