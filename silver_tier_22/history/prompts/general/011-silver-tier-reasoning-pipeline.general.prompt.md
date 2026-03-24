---
id: 011
title: Silver Tier Reasoning Pipeline Agent Skill
stage: general
date: 2026-03-20
surface: agent
model: claude-sonnet-4-6
feature: silver-reasoning
branch: main
user: DANISH LAPTOP
command: /silver-reason (new agent skill)
labels: ["silver-tier","reasoning","approval-workflow","mcp","email","agent-skill"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - .claude/commands/silver-reason.md
  - Scripts/mcp_email_client.py
  - Scripts/approval_watcher.py
  - AGENT_SKILLS.md
tests:
  - "python Scripts/approval_watcher.py --dry-run --once (no errors)"
  - "python Scripts/mcp_email_client.py --to x@x.com (builds without import error)"
---

## Prompt

Implement Silver Tier reasoning: When /Needs_Action has files, read them, create /Plans/PLAN_xxx.md with checkboxes. For sensitive actions (email send, LinkedIn post > certain limit), create /Pending_Approval/ file instead of direct action. Use email MCP for sending after approval. Make this an Agent Skill.

## Response snapshot

Created full Silver Tier reasoning pipeline (SKILL-007):

1. `.claude/commands/silver-reason.md` — 8-step Claude Code slash command that:
   - Scans Needs_Action/, determines next PLAN ID
   - Classifies every action as SAFE or SENSITIVE (email/LinkedIn/WhatsApp/payment all SENSITIVE)
   - Creates Plans/PLAN_xxx.md with YAML frontmatter, checkbox action lists, approval refs
   - Creates Pending_Approval/APPROVAL_<date>_<ID>_<slug>.md with embedded APPROVAL_PAYLOAD JSON
   - Executes safe actions immediately, updates Dashboard

2. `Scripts/mcp_email_client.py` — thin Python MCP client:
   - Spawns node mcp-email-server/dist/index.js as child process
   - Implements MCP stdio protocol: initialize → notifications/initialized → tools/call
   - Returns {success, messageId, error} dict

3. `Scripts/approval_watcher.py` — background execution engine:
   - Polls Approved/ every 30s (--poll N, --once, --dry-run flags)
   - Extracts APPROVAL_PAYLOAD JSON from approved files
   - Dispatches: send_email → MCP client, linkedin_post/whatsapp_send → logged for manual action
   - Archives to Done/, marks Plan checkbox, updates Dashboard and ActivityLog

4. `AGENT_SKILLS.md` — updated to v2.1 with SKILL-007 fully documented

## Outcome

- ✅ Impact: Complete human-in-the-loop reasoning pipeline — AI reasons and plans, human approves, MCP executes
- 🧪 Tests: mcp_email_client.py imports clean; approval_watcher.py --dry-run logic verified
- 📁 Files: 4 files created/updated
- 🔁 Next prompts: run /silver-reason on a real Needs_Action file; start approval_watcher.py as pm2 process
- 🧠 Reflection: LinkedIn/WhatsApp set to log-and-manual since autonomous posting is disabled per SKILL-005 policy; MCP protocol confirmed as newline-delimited JSON (not LSP Content-Length framing)

## Evaluation notes (flywheel)

- Failure modes observed: none at implementation time
- Graders run and results (PASS/FAIL): static review PASS
- Prompt variant (if applicable): none
- Next experiment: wire approval_watcher.py into pm2 alongside other watchers
