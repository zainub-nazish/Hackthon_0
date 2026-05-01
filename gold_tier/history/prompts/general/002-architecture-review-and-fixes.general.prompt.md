---
name: Architecture Review and Fixes
description: Full code review of Gold Tier scaffold — identified 8 bugs/gaps and applied all fixes
type: general
stage: general
id: "002"
date: 2026-05-01
surface: agent
model: claude-sonnet-4-6
feature: gold-tier-autonomous-employee
branch: main
user: zainub-nazish
command: "Review architecture for MCP servers, agent skills, Ralph Wiggum loop, and cross-domain integration"
labels: ["review", "bug-fix", "mcp", "ralph-wiggum", "cross-domain"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
---

## Prompt

Review the created architecture. Does it support multiple MCP servers, agent skills pattern, Ralph Wiggum loop, and cross-domain (personal+business) integration? List any missing parts and fix them.

## Findings

### Bugs (runtime errors)
1. `run_stdio()` broken in all 3 MCP servers — `asyncio.BaseProtocol` used as write-pipe factory; crashes at runtime. Fixed to use `sys.stdout.buffer.write()` directly.
2. `LoopStep.index` hardcoded to `0` in `_act()` — never reflected actual step position. Fixed via `step_def["_index"]`.
3. Instagram had no fallback in `_register_fallbacks()` — only Twitter and Facebook had fallbacks. Added `_ig_fallback`.

### Missing pieces
4. No `.claude/settings.json` — MCP servers were unreachable from Claude Code. Created with all 3 server registrations.
5. No `BaseSkill` abstract class — no enforced interface across skills. Created `agent_skills/base.py`.
6. `_reason()` was `@staticmethod` returning `None` when `plan=None` — loop terminated in 1 iteration for goal-driven mode. Converted to instance method with `_goal_to_plan()` keyword matcher and `_GOAL_PLANS` class map.
7. `audit_mcp.py` missing `list_tasks` and `update_task_status` tools — cross-domain task reads/updates unavailable via MCP. Added both tools + dispatch handlers.
8. `agent_skills/logging.py` absent from spec layout. Created as re-export shim for `audit_logger.py`.

## Files Created/Modified

 - agent_skills/__init__.py (added BaseSkill export)
 - agent_skills/base.py (new — BaseSkill ABC)
 - agent_skills/logging.py (new — shim re-exporting AuditLogger)
 - agent_skills/social.py (Instagram fallback added)
 - main_orchestrator.py (_reason instance method, _goal_to_plan, _GOAL_PLANS, LoopStep.index fix)
 - mcp_servers/social_mcp.py (run_stdio fixed)
 - mcp_servers/audit_mcp.py (run_stdio fixed, list_tasks + update_task_status added)
 - mcp_servers/recovery_mcp.py (run_stdio fixed)
 - .claude/settings.json (new — MCP server registrations for Claude Code)

## Tests Run

 - 14/14 Python files parsed clean (ast.parse with UTF-8)
