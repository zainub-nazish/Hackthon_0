"""
Comprehensive test suite for the Agent Skills system.

Tests:
  - Decorator registration
  - Audit logging
  - Recovery with retry and circuit breaker
  - Ralph Wiggum loop
  - MCP tool schema exposure
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


async def test_skill_registration():
    """Verify all skills are registered and expose MCP schemas."""
    print("\n=== Test 1: Skill Registration ===")

    registered = SkillRegistry.names()
    print(f"[OK] Registered skills: {registered}")

    mcp_tools = SkillRegistry.mcp_tool_list()
    print(f"[OK] MCP tools exposed: {len(mcp_tools)}")

    for tool in mcp_tools[:3]:
        print(f"  - {tool['name']}: {tool['description'][:60]}...")

    assert len(registered) > 0, "No skills registered"
    assert len(mcp_tools) > 0, "No MCP tools exposed"
    print("[PASS] Registration test PASSED")


async def test_audit_logging():
    """Verify comprehensive audit logging."""
    print("\n=== Test 2: Audit Logging ===")

    logger = AuditLogger("test", log_dir="logs/test/")

    # Log various event types
    action_id = logger.log_action("test_skill", "test_action", {"param": "value"}, "success", 123.45)
    print(f"[OK] Action logged: {action_id}")

    decision_id = logger.log_decision("test_context", "chose option A", "because B was slower", ["A", "B"])
    print(f"[OK] Decision logged: {decision_id}")

    error_id = logger.log_error("test_skill", "test_action", Exception("test error"), "ERROR", True)
    print(f"[OK] Error logged: {error_id}")

    logger.log_state_change("test_component", "idle", "running", "test started")
    print("[OK] State change logged")

    # Verify log files exist
    log_dir = Path("logs/test/")
    assert (log_dir / "actions.jsonl").exists(), "Actions log missing"
    assert (log_dir / "errors.jsonl").exists(), "Errors log missing"
    assert (log_dir / "audit.jsonl").exists(), "Audit log missing"

    print("[PASS] Audit logging test PASSED")


async def test_recovery_mechanisms():
    """Test retry, circuit breaker, and fallback."""
    print("\n=== Test 3: Recovery Mechanisms ===")

    recovery = RecoverySkill(max_retries=3, backoff_base=0.1)

    # Test successful execution
    async def success_fn():
        return "success"

    result = await recovery.execute_with_recovery("test", "success", success_fn)
    assert result.success, "Success case failed"
    assert result.attempts == 1, f"Expected 1 attempt, got {result.attempts}"
    print(f"[OK] Success case: {result.attempts} attempt(s)")

    # Test retry with eventual success
    attempt_count = 0
    async def retry_fn():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise Exception("temporary failure")
        return "success after retries"

    result = await recovery.execute_with_recovery("test", "retry", retry_fn)
    assert result.success, "Retry case failed"
    assert result.attempts == 3, f"Expected 3 attempts, got {result.attempts}"
    print(f"[OK] Retry case: {result.attempts} attempt(s)")

    # Test circuit breaker
    async def always_fail():
        raise Exception("permanent failure")

    for i in range(6):
        result = await recovery.execute_with_recovery("test", "circuit", always_fail)

    circuit_status = recovery.circuit_status()
    assert "test.circuit" in circuit_status, "Circuit not tracked"
    print(f"[OK] Circuit breaker: {circuit_status['test.circuit']}")

    # Test fallback
    async def fallback_fn():
        return "fallback result"

    recovery.register_fallback("test.fallback_action", fallback_fn)

    async def fail_fn():
        raise Exception("fail")

    result = await recovery.execute_with_recovery("test", "fallback_action", fail_fn)
    assert result.success, "Fallback not used"
    assert result.fallback_used, "Fallback flag not set"
    print(f"[OK] Fallback: {result.fallback_name}")

    print("[PASS] Recovery mechanisms test PASSED")


async def test_autonomous_agent():
    """Test single task execution and Ralph Wiggum loop."""
    print("\n=== Test 4: Autonomous Agent ===")

    logger = AuditLogger("agent_test", log_dir="logs/test/")
    recovery = RecoverySkill(logger=logger)

    social = SocialMediaSkill(recovery=recovery, logger=logger, dry_run=True)
    audit = AuditSkill(recovery=recovery, logger=logger, data_dir="data/test/")
    pb = PersonalBusinessSkill(recovery=recovery, logger=logger, data_dir="data/test/")

    agent = AutonomousAgent(
        skills=[social, audit, pb],
        recovery=recovery,
        logger=logger,
        data_dir="data/test/",
    )

    # Test single task execution
    task = {
        "skill": "personal_business",
        "action": "cross_domain_analysis",
        "params": {},
        "description": "Test cross-domain analysis",
    }

    result = await agent.execute_task(task)
    assert result["success"], f"Task failed: {result.get('error')}"
    print(f"[OK] Single task execution: {result['skill']}.{result['action']}")

    # Test Ralph Wiggum loop (short run)
    print("\n  Running Ralph Wiggum loop (max 2 iterations)...")
    report = await agent.run_ralph_wiggum_loop(
        task_description="Run daily briefing and check tasks",
        max_iterations=2,
        exit_criteria="",
    )

    print(f"  - Total iterations: {report.total_iterations}")
    print(f"  - Goal achieved: {report.goal_achieved}")
    print(f"  - Final status: {report.final_status}")

    for rec in report.iterations:
        marker = "PASS" if rec.verify_passed else "FAIL"
        actions = [f"{e['skill']}.{e['action']}" for e in rec.executed]
        print(f"  - [{rec.iteration}] {marker} {rec.status} | {', '.join(actions[:2])}")

    assert report.total_iterations > 0, "No iterations executed"
    assert Path(report.progress_file).exists(), "Progress file not created"
    print(f"[OK] Ralph Wiggum loop completed: {report.progress_file}")

    print("[PASS] Autonomous agent test PASSED")


async def test_mcp_integration():
    """Test MCP server tool exposure."""
    print("\n=== Test 5: MCP Integration ===")

    # Test that all decorated skills expose MCP schemas
    tools = SkillRegistry.mcp_tool_list()

    required_fields = ["name", "description", "inputSchema"]
    for tool in tools:
        for field in required_fields:
            assert field in tool, f"Tool {tool.get('name', '?')} missing {field}"

    print(f"[OK] All {len(tools)} tools have valid MCP schemas")

    # Test domain filtering
    business_tools = SkillRegistry.by_domain("business")
    personal_tools = SkillRegistry.by_domain("personal")

    print(f"[OK] Business domain: {len(business_tools)} tools")
    print(f"[OK] Personal domain: {len(personal_tools)} tools")

    print("[PASS] MCP integration test PASSED")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Agent Skills System - Comprehensive Test Suite")
    print("=" * 60)

    try:
        await test_skill_registration()
        await test_audit_logging()
        await test_recovery_mechanisms()
        await test_autonomous_agent()
        await test_mcp_integration()

        print("\n" + "=" * 60)
        print("[SUCCESS] ALL TESTS PASSED")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        raise
    except Exception as e:
        print(f"\n[ERROR] UNEXPECTED ERROR: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
