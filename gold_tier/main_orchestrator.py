"""
Main Orchestrator - Command Line Interface
Production-ready autonomous agent with CLI for task execution.

Usage:
    python main_orchestrator.py --task "Post daily update and generate summary"
    python main_orchestrator.py --mode continuous
    python main_orchestrator.py --health-check
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from unified_orchestrator import AutonomousDayOrchestrator


async def run_task(task_description: str) -> None:
    """Execute a specific task."""
    print(f"\n{'=' * 70}")
    print(f"EXECUTING TASK: {task_description}")
    print(f"{'=' * 70}\n")

    orchestrator = AutonomousDayOrchestrator()

    try:
        await orchestrator.start()

        # Parse task and execute appropriate action
        task_lower = task_description.lower()

        if "daily update" in task_lower or "post" in task_lower:
            # Post daily update
            result = await orchestrator._post_scheduled_social()
            print(f"\n✅ Social post result: {result}")

        if "summary" in task_lower or "audit" in task_lower:
            # Generate summary/audit
            if "week" in task_lower:
                result = await orchestrator._run_weekly_audit()
                print(f"\n✅ Weekly audit result: {result}")
            else:
                # Run full day cycle
                result = await orchestrator.run_autonomous_day()
                print(f"\n✅ Day summary: {result}")

        if "tasks" in task_lower or "check" in task_lower:
            # Check tasks
            result = await orchestrator._check_pending_tasks()
            print(f"\n✅ Tasks checked: {result}")

    except Exception as e:
        print(f"\n❌ Error executing task: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await orchestrator.shutdown()


async def run_continuous_mode() -> None:
    """Run continuous autonomous operation."""
    print(f"\n{'=' * 70}")
    print("CONTINUOUS AUTONOMOUS MODE")
    print(f"{'=' * 70}\n")

    orchestrator = AutonomousDayOrchestrator()

    try:
        await orchestrator.start()
        await orchestrator.run_continuous(interval_hours=24)
    except KeyboardInterrupt:
        print("\n\nShutdown requested by user")
    except Exception as e:
        print(f"\n❌ Error in continuous mode: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await orchestrator.shutdown()


async def run_health_check() -> None:
    """Run health check on all systems."""
    print(f"\n{'=' * 70}")
    print("SYSTEM HEALTH CHECK")
    print(f"{'=' * 70}\n")

    orchestrator = AutonomousDayOrchestrator()

    try:
        await orchestrator.start()

        # Check MCP servers
        health = await orchestrator.mcp.health_check_all()

        print("MCP Server Status:")
        for server_name, status in health["servers"].items():
            icon = "✅" if status.get("healthy") else "❌"
            tools = status.get("tools_count", 0)
            print(f"  {icon} {server_name.upper()}: {status.get('status')} ({tools} tools)")

        print(f"\nOverall Health: {'✅ HEALTHY' if health['overall_healthy'] else '⚠️ DEGRADED'}")

        # Check error recovery
        recovery = await orchestrator._run_error_recovery()
        print(f"\nError Recovery Status:")
        print(f"  Unhealthy Servers: {recovery.get('unhealthy_servers', 0)}")
        print(f"  Overall Health: {'✅' if recovery.get('overall_health') else '⚠️'}")

    except Exception as e:
        print(f"\n❌ Error during health check: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await orchestrator.shutdown()


async def run_demo() -> None:
    """Run demonstration of all features."""
    print(f"\n{'=' * 70}")
    print("AUTONOMOUS ORCHESTRATOR - FULL DEMO")
    print(f"{'=' * 70}\n")

    orchestrator = AutonomousDayOrchestrator()

    try:
        await orchestrator.start()

        # Run one complete day cycle
        summary = await orchestrator.run_autonomous_day()

        print(f"\n{'=' * 70}")
        print("DEMO COMPLETE - DAY SUMMARY")
        print(f"{'=' * 70}")
        print(f"\nTasks Completed: {summary['tasks_completed']}")
        print(f"Social Posts: {summary['social_posts']}")
        print(f"Audit Run: {summary['audit_run']}")
        print(f"Total Errors: {summary['total_errors']}")
        print(f"\nActivities: {len(summary['activities'])} steps completed")

        if summary['errors']:
            print(f"\nErrors encountered:")
            for error in summary['errors']:
                print(f"  - {error}")

    except Exception as e:
        print(f"\n❌ Error during demo: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await orchestrator.shutdown()


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Autonomous Agent Orchestrator - Production System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Execute a specific task
  python main_orchestrator.py --task "Post daily update and generate summary"

  # Run continuous autonomous mode (24-hour cycles)
  python main_orchestrator.py --mode continuous

  # Run health check
  python main_orchestrator.py --health-check

  # Run demo
  python main_orchestrator.py --demo
        """
    )

    parser.add_argument(
        "--task",
        type=str,
        help="Execute a specific task (e.g., 'Post daily update')"
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["continuous", "once"],
        help="Operation mode: continuous (24h cycles) or once (single cycle)"
    )

    parser.add_argument(
        "--health-check",
        action="store_true",
        help="Run system health check"
    )

    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run full demonstration"
    )

    args = parser.parse_args()

    # Execute based on arguments
    if args.task:
        asyncio.run(run_task(args.task))
    elif args.mode == "continuous":
        asyncio.run(run_continuous_mode())
    elif args.mode == "once":
        asyncio.run(run_demo())
    elif args.health_check:
        asyncio.run(run_health_check())
    elif args.demo:
        asyncio.run(run_demo())
    else:
        # No arguments - show help and run demo
        parser.print_help()
        print("\n" + "=" * 70)
        print("No arguments provided - running demo mode")
        print("=" * 70)
        asyncio.run(run_demo())


if __name__ == "__main__":
    main()
