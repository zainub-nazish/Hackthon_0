---
id: 013
title: LinkedIn Post Generator Agent Skill (SKILL-008)
stage: general
date: 2026-03-20
surface: agent
model: claude-sonnet-4-6
feature: linkedin-post
branch: main
user: DANISH LAPTOP
command: /linkedin-post (new agent skill)
labels: ["linkedin","post","playwright","agent-skill","approval-workflow","business-goals"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - .claude/commands/linkedin-post.md
  - Business_Goals.md
  - Scripts/linkedin_poster.py
  - Scripts/approval_watcher.py
  - Dashboard.md
  - AGENT_SKILLS.md
tests:
  - "python -c import linkedin_poster (syntax OK, stubbed playwright)"
  - "python -c import approval_watcher; assert linkedin_poster in handler src"
---

## Prompt

Add Agent Skill: Every day if no urgent tasks, generate business post from Business_Goals.md and use browser MCP (or Playwright) to draft/post on LinkedIn (draft-only, approval required). Update Dashboard.md to show recent LinkedIn posts. All functionality as Agent Skills only.

## Response snapshot

Created SKILL-008 — LinkedIn Post Generator as a complete Agent Skill:

1. `.claude/commands/linkedin-post.md` (9-step slash command):
   - Pre-flight: urgent task check, daily frequency check, Business_Goals.md exists check
   - Reads Business_Goals.md, extracts company/audience/services/tone/CTAs/wins
   - Topic rotation by day of week (Mon=services, Tue=tip, Wed=case study, Thu=process, Fri=question, Sat=observation, Sun=motivational)
   - Generates 150-250 word post: Hook → Value → Proof → CTA → 3-5 hashtags
   - Saves Plans/DRAFT_POST_<date>.md with frontmatter + review checklist
   - Creates Pending_Approval/APPROVAL_<date>_008_linkedin-post.md with APPROVAL_PAYLOAD JSON
   - Updates Dashboard.md: LinkedIn Posts table + Pending Tasks + Recent Activity
   - Logs SKILL-008 entry to ActivityLog.md (prevents duplicate same day)

2. `Business_Goals.md`: structured template with company overview, target audience, services, value props, case studies, tone rules, CTA library, topic rotation, hashtag pool, current priorities

3. `Scripts/linkedin_poster.py` (Playwright implementation):
   - Reuses ~/ai-secrets/linkedin_session/ (shared with linkedin_watcher.py)
   - Multi-selector fallback strategy for LinkedIn's changing HTML
   - Clipboard paste for fast content entry + keyboard.type() fallback
   - extract_post_from_draft() parses DRAFT_POST_*.md ## Post Content section
   - CLI: --content, --draft, --dry-run flags; exit codes 0/1/2/3

4. `Scripts/approval_watcher.py` updated:
   - execute_linkedin_post() now calls linkedin_poster.py via subprocess
   - Falls back to log-and-manual if script missing
   - Handles exit codes 0 (success), 2 (session not active), other (failure)

5. `Dashboard.md`: LinkedIn Posts section added with date/day/topic/preview/status/approval columns

6. `AGENT_SKILLS.md`: updated to v2.2 with full SKILL-008 documentation

## Outcome

- ✅ Impact: Full LinkedIn post lifecycle as Agent Skills only — generate → draft → approve → Playwright post
- 🧪 Tests: linkedin_poster.py syntax OK; approval_watcher linkedin handler verified
- 📁 Files: 6 files created/updated
- 🔁 Next prompts: fill in Business_Goals.md [FILL IN] fields; test /linkedin-post; run approval_watcher --dry-run
- 🧠 Reflection: Used multi-selector fallback arrays since LinkedIn HTML changes frequently; clipboard paste chosen over keyboard.type() for speed and reliable line-break preservation

## Evaluation notes (flywheel)

- Failure modes observed: none at implementation
- Graders run and results (PASS/FAIL): syntax check PASS, handler reference PASS
- Prompt variant (if applicable): none
- Next experiment: add screenshot capture on post success to confirm LinkedIn actually published
