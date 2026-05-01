---
name: Gold Tier Autonomous Employee Scaffold
description: Full project scaffold for the Gold Tier autonomous AI employee system including orchestrator, agent skills, MCP servers, audit, social media, and architecture docs
type: general
stage: general
id: "001"
date: 2026-05-01
surface: agent
model: claude-sonnet-4-6
feature: gold-tier-autonomous-employee
branch: main
user: zainub-nazish
command: "Build Gold Tier Autonomous Employee complete project structure"
labels: ["scaffold", "architecture", "mcp", "social-media", "audit", "ralph-wiggum-loop"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
---

## Prompt

You are building the Gold Tier "Autonomous Employee" system. Create a complete project structure for a highly autonomous AI agent that acts as a full employee. Requirements (Odoo accounting skip):
- Full cross-domain integration (Personal + Business tasks)
- Integrate Facebook & Instagram (post messages + generate summary)
- Integrate X (Twitter) (post messages + generate summary)
- Multiple MCP servers for different action types
- Weekly Business and Accounting Audit with CEO Briefing generation (accounting part without Odoo — use local CSV/SQLite or mock data)
- Error recovery and graceful degradation
- Comprehensive audit logging
- Ralph Wiggum loop for autonomous multi-step task completion
- All AI functionality as modular Agent Skills
- Proper documentation of architecture and lessons learned

## Response Summary

Created complete project scaffold under `D:/hackthon_0_/gold_tier/` with:

**Files created:**
- `main_orchestrator.py` — GoldTierOrchestrator with Ralph Wiggum loop (observe→reason→act→evaluate), APScheduler for weekly audit, full skill dispatch table
- `agent_skills/social.py` — SocialMediaSkill: post_to_twitter, post_to_facebook, post_to_instagram, cross_post, generate_all_summaries
- `agent_skills/audit.py` — AuditSkill: SQLite accounting, weekly audit, CEO briefing generation via Jinja2
- `agent_skills/recovery.py` — RecoverySkill: CircuitBreaker, exponential backoff, fallback registry, with_recovery decorator
- `agent_skills/audit_logger.py` — AuditLogger: rotating JSONL logs (actions/errors/audit), thread-safe singleton
- `agent_skills/personal_business.py` — PersonalBusinessSkill: cross-domain task CRUD, priority scoring, daily briefing
- `mcp_servers/social_mcp.py` — stdio MCP server: 5 social tools
- `mcp_servers/audit_mcp.py` — stdio MCP server: 6 audit/task tools
- `mcp_servers/recovery_mcp.py` — stdio MCP server: 5 circuit/health tools
- `config/credentials.py` — pydantic-settings, SecretStr, .env loading
- `config/settings.yaml` — full app/orchestrator/social/audit/recovery/logging/MCP config
- `docs/ARCHITECTURE.md` — Mermaid diagrams: component map, social flow, audit flow, Ralph Wiggum state machine, error recovery flowchart, lessons learned
- `requirements.txt`, `.env.example`, `.gitignore`

## Files Created/Modified

 - main_orchestrator.py
 - agent_skills/__init__.py
 - agent_skills/social.py
 - agent_skills/audit.py
 - agent_skills/recovery.py
 - agent_skills/audit_logger.py
 - agent_skills/personal_business.py
 - mcp_servers/__init__.py
 - mcp_servers/social_mcp.py
 - mcp_servers/audit_mcp.py
 - mcp_servers/recovery_mcp.py
 - config/__init__.py
 - config/credentials.py
 - config/settings.yaml
 - docs/ARCHITECTURE.md
 - requirements.txt
 - .env.example
 - .gitignore

## Tests Run

 - (none — scaffold only, no test suite yet)
