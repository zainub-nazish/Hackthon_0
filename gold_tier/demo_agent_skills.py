"""
Quick demo of the Agent Skills system.

Shows:
  - Single task execution
  - Ralph Wiggum loop
  - Circuit breaker and recovery
  - MCP tool discovery
"""

import asyncio
import json
from pathlib import Path

from agent_skills import (
    AuditLogger,
    AutonomousAgent,
    RecoverySkill,
    SkillRegistry,
    SocialMediaSkill,
    AuditSkill,
    PersonalBusinessSkill,
)


async def main():
    print("=" * 70)
    print("Agent Skills System - Quick Demo")
    print("=" * 70)

    # Setup
    logger = AuditLogger("demo", log_dir="logs/demo/")
    recovery = RecoverySkill(logger=logger)

    social = SocialMediaSkill(recovery=recovery, logger=logger, dry_run=True)
    audit = AuditSkill(recovery=recovery, logger=logger, data_dir="data/demo/")
    pb = PersonalBusinessSkill(recovery=recovery, logger=logger, data_dir="data/demo/")

    agent = AutonomousAgent(
        skills=[social, audit, pb],
        recovery=recovery,
        logger=logger,
        data_dir="data/demo/",
    )

    # Seed demo data
    print("\n[1] Seeding demo data...")
    audit.seed_mock_data(30)
    pb.seed_demo_tasks()
    print("    - Created 30 days of mock financial transactions")
    print("    - Created demo tasks across personal and business domains")

    # Show registered skills
    print("\n[2] Registered Skills:")
    for skill_name in SkillRegistry.names()[:5]:
        print(f"    - {skill_name}")
    print(f"    ... and {len(SkillRegistry.names()) - 5} more")

    # Single task execution
    print("\n[3] Single Task Execution:")
    print("    Executing: personal_business.cross_domain_analysis")
    result = await agent.execute_task({
        "skill": "personal_business",
        "action": "cross_domain_analysis",
        "params": {},
    })
    if result["success"]:
        data = result["data"]
        print(f"    - Total tasks: {data.total_tasks}")
        print(f"    - Completion rate: {data.completion_rate:.1f}%")
        print(f"    - Overdue: {data.overdue_count}")
    else:
        print(f"    - Failed: {result['error']}")

    # Ralph Wiggum loop
    print("\n[4] Ralph Wiggum Loop:")
    print("    Task: 'Run daily briefing and analyze tasks'")
    print("    Max iterations: 3")
    report = await agent.run_ralph_wiggum_loop(
        task_description="Run daily briefing and analyze tasks",
        max_iterations=3,
        exit_criteria="",
    )

    print(f"\n    Results:")
    print(f"    - Goal achieved: {report.goal_achieved}")
    print(f"    - Total iterations: {report.total_iterations}")
    print(f"    - Final status: {report.final_status}")
    print(f"\n    Iteration details:")
    for rec in report.iterations:
        marker = "[PASS]" if rec.verify_passed else "[FAIL]"
        actions = [f"{e['skill']}.{e['action']}" for e in rec.executed[:2]]
        print(f"      {marker} Iteration {rec.iteration}: {', '.join(actions)}")
        if rec.issues:
            for issue in rec.issues[:1]:
                print(f"            Issue: {issue[:60]}...")

    # Circuit breaker status
    print("\n[5] Circuit Breaker Status:")
    circuits = recovery.circuit_status()
    if circuits:
        for key, state in list(circuits.items())[:3]:
            print(f"    - {key}: {state}")
    else:
        print("    - All circuits closed (healthy)")

    # MCP tool exposure
    print("\n[6] MCP Tool Exposure:")
    tools = SkillRegistry.mcp_tool_list()
    print(f"    - Total tools exposed: {len(tools)}")
    print(f"    - Business domain: {len(SkillRegistry.by_domain('business'))} tools")
    print(f"    - Personal domain: {len(SkillRegistry.by_domain('personal'))} tools")

    # Show sample MCP tool schema
    sample_tool = tools[0]
    print(f"\n    Sample tool schema:")
    print(f"    {json.dumps(sample_tool, indent=6)[:300]}...")

    # Logs
    print("\n[7] Audit Logs:")
    log_dir = Path("logs/demo/")
    for log_file in ["actions.jsonl", "errors.jsonl", "audit.jsonl"]:
        path = log_dir / log_file
        if path.exists():
            size = path.stat().st_size
            print(f"    - {log_file}: {size} bytes")

    # Progress file
    print("\n[8] Progress Tracking:")
    print(f"    - Progress file: {report.progress_file}")
    if Path(report.progress_file).exists():
        with open(report.progress_file) as f:
            progress = json.load(f)
        print(f"    - Iteration count: {progress['iteration_count']}")
        print(f"    - Started: {progress['started_at'][:19]}")
        print(f"    - Updated: {progress['updated_at'][:19]}")

    print("\n" + "=" * 70)
    print("Demo Complete!")
    print("=" * 70)
    print("\nNext steps:")
    print("  - View logs: tail -f logs/demo/actions.jsonl | jq")
    print("  - Run tests: python test_agent_skills.py")
    print("  - Start MCP server: python -m mcp_servers.social_mcp")
    print("  - Read docs: agent_skills/README.md")


if __name__ == "__main__":
    asyncio.run(main())
