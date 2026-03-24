---
id: "009"
title: LinkedIn Watcher and Agent Skills
stage: general
date: 2026-03-20
surface: agent
model: claude-sonnet-4-6
feature: silver-tier-linkedin-watcher
branch: main
user: danish
command: create Scripts/linkedin_watcher.py, update Company_Handbook.md and AGENT_SKILLS.md
labels: ["linkedin","playwright","watcher","agent-skills","business-post","silver-tier"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - Scripts/linkedin_watcher.py
  - Scripts/README.md
  - Company_Handbook.md
  - AGENT_SKILLS.md
tests:
  - manual: first run opens Chromium, login saves session to ~/ai-secrets/linkedin_session/
  - manual: notification with keyword "proposal" produces LINKEDIN_<timestamp>.md in Needs_Action/
  - manual: all unread messages produce notes regardless of keywords
  - manual: empty Needs_Action triggers SKILL-006 business post draft in Plans/
---

## Prompt

Create /Scripts/linkedin_watcher.py using Playwright (similar to WhatsApp). Monitor LinkedIn notifications/messages for business opportunities. Also add logic in Company_Handbook.md: "If no urgent tasks in Needs_Action, generate a helpful business post about my services and prepare it for posting." Save everything as Agent Skill.

## Response snapshot

1. Created `Scripts/linkedin_watcher.py`:
   - Full Playwright implementation (not stub) using persistent Chromium context
   - Session at `~/ai-secrets/linkedin_session/`; manual login once, reused thereafter
   - Polls `/notifications/` and `/messaging/` every 60s
   - Opportunity keywords: partnership, opportunity, collaboration, project, proposal, hire, contract, consulting, deal, interested, services, quote, offer, work together, reach out
   - Always captures: all unread DMs, connection requests, InMail
   - Creates `LINKEDIN_<timestamp>.md` in Needs_Action/ with YAML frontmatter + action checklist
   - In-memory dedup via `_seen` set

2. Updated `Company_Handbook.md` (v2.0→v3.0, Bronze→Silver):
   - Added "Proactive Engagement Rules" section with full trigger condition and SKILL-006 process
   - Added "Channel Monitoring Rules" table (Gmail/WhatsApp/LinkedIn watchers)

3. Updated `AGENT_SKILLS.md` (v1.0→v2.0, Bronze→Silver):
   - Added SKILL-005: LinkedIn Business Opportunity Monitor (full spec with trigger, process, constraints)
   - Added SKILL-006: Generate Business Post When Inbox Is Clear (trigger conditions, post structure, draft-only + approval flow)

4. Updated `Scripts/README.md`: LinkedIn watcher entry, session setup, pm2 start command, log file table.

## Outcome

- Impact: LinkedIn is now a monitored channel; business opportunities surface automatically in Needs_Action/. Idle-time proactive content generation is now an official agent behavior.
- Tests: manual verification required (login flow + note creation + SKILL-006 trigger)
- Files: Scripts/linkedin_watcher.py, Company_Handbook.md, AGENT_SKILLS.md, Scripts/README.md
- Next prompts: test LinkedIn login, verify note format, implement SKILL-006 automation script
- Reflection: Designed SKILL-006 with strict guard rails (draft-only, max once/day, approval required) to keep the agent safely within autonomous boundaries.

## Evaluation notes (flywheel)

- Failure modes observed: LinkedIn DOM selectors may need updating if LinkedIn changes markup
- Graders run and results (PASS/FAIL): pending manual test
- Prompt variant (if applicable): none
- Next experiment: add persistent seen-IDs file for LinkedIn (cross-restart dedup)
