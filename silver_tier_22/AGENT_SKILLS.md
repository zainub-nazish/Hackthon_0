---
title: Agent Skills
version: 2.0
last_updated: 2026-03-20
tier: Silver
status: active
---

# Agent Skills

All skills available to the Bronze Tier AI Employee. Each skill has a defined trigger, process, and output.

---

## Skill 001 — Read Needs_Action and Create Plan

**Skill ID:** SKILL-001
**Description:** Reads all items in the `Needs_Action` folder and generates a structured `Plan.md` file in the `Plans` folder based on what needs to be done.

**When to Use:**
- At the start of each work session.
- When new items have been moved into `Needs_Action`.
- When the current plan is stale or missing.

**Step-by-Step Process:**

1. Open the `Needs_Action` folder and list all files.
2. For each file, extract: task title, owner, due date (if present), and priority.
3. Sort tasks by priority: High → Medium → Low.
4. Create or overwrite `Plans/Plan.md` with the structured task list.
5. Add a timestamp to the plan header.
6. Update `Dashboard.md` to reflect that the plan was refreshed (see Skill 003).
7. Log the action in `Logs` with format: `[DATE] SKILL-001 executed — Plan.md updated.`

---

## Skill 002 — Move Completed Tasks to Done

**Skill ID:** SKILL-002
**Description:** Moves task files from `Approved` (or `Needs_Action`) into the `Done` folder once a task is confirmed complete.

**When to Use:**
- After a task has been approved and fully executed.
- When a user explicitly marks a task as complete.
- During end-of-day cleanup.

**Step-by-Step Process:**

1. Identify the task file to be closed (confirm it is in `Approved` or `Needs_Action`).
2. Verify the task is actually complete — do not move if work is still pending.
3. Add a completion note to the bottom of the task file:
   > Completed: [DATE] | Authorized by: [NAME]
4. Move the file from its current folder to `Done/`.
5. Update `Dashboard.md` Recent Activity table (see Skill 003).
6. Log the action in `Logs` with format: `[DATE] SKILL-002 — [filename] moved to Done.`

---

## Skill 003 — Update Dashboard After Every Action

**Skill ID:** SKILL-003
**Description:** Keeps `Dashboard.md` current by updating the Recent Activity table and Pending Tasks checklist after any significant action is taken.

**When to Use:**
- After every skill execution (001, 002, 004).
- After any file is created, moved, or modified.
- At the start and end of each work session.

**Step-by-Step Process:**

1. Open `Dashboard.md`.
2. Add a new row to the **Recent Activity** table:

   | [DATE] | [Action taken] | [Status] | [Authorized by] |

3. Review the **Pending Tasks** checklist — check off any completed items.
4. Review the **Next Actions** list — update or add items based on current state.
5. Save `Dashboard.md`.
6. Log the dashboard update in `Logs` with format: `[DATE] SKILL-003 — Dashboard.md updated.`

> Note: This skill runs automatically as a final step of every other skill.

---

## Skill 004 — Create Approval Request for Sensitive Actions

**Skill ID:** SKILL-004
**Description:** Generates a structured approval request and places it in `Pending_Approval` when a sensitive action is detected (e.g., payments over $100, data deletion, external sharing).

**When to Use:**
- Any payment or expense over $100.
- Any action involving deletion of files or records.
- Any action that shares internal data externally.
- Any action outside the normal task lifecycle.

**Step-by-Step Process:**

1. Stop all execution immediately — do not proceed with the sensitive action.
2. Create a new file in `Pending_Approval/` named: `APPROVAL-[DATE]-[short-description].md`
3. Populate the file using this format:

   ```
   APPROVAL REQUEST
   Date: [DATE]
   Requested by: AI Employee (Bronze Tier)
   Action: [describe the action clearly]
   Amount (if payment): $[X]
   Reason: [why this action is needed]
   Risk level: [Low / Medium / High]
   Awaiting approval from: [NAME or ROLE]
   ```

4. Flag the request in `Dashboard.md` Pending Tasks checklist.
5. Update `Dashboard.md` Recent Activity table (Skill 003).
6. Log in `Logs`: `[DATE] SKILL-004 — Approval request created: [filename].`
7. Do not retry the action until explicit human approval is received and documented.

---

---

## Skill 005 — LinkedIn Business Opportunity Monitor

**Skill ID:** SKILL-005
**Description:** Runs the Playwright-based LinkedIn watcher to scrape notifications
and unread messages, identify business opportunities by keyword, and create
action notes in `Needs_Action/` for human review.

**When to Use:**
- Automatically (continuous): `Scripts/linkedin_watcher.py` runs as a pm2 process.
- Manually: when the pm2 process is not running and a LinkedIn check is needed.

**Trigger — a note is created in `Needs_Action/` when:**
- An unread LinkedIn message is detected (all unread DMs are captured).
- A LinkedIn notification contains any of these keywords:
  `partnership`, `opportunity`, `collaboration`, `project`, `proposal`,
  `hire`, `contract`, `consulting`, `deal`, `interested`, `services`,
  `quote`, `offer`, `work together`, `reach out`.
- A connection request is received (always captured).

**Step-by-Step Process:**

1. `LinkedInWatcher` launches a persistent Chromium browser using the session
   saved at `~/ai-secrets/linkedin_session/`.
2. If no session exists, a browser window opens — log in manually once.
3. Every 60 seconds the watcher:
   a. Navigates to `https://www.linkedin.com/notifications/` and scrapes cards.
   b. Navigates to `https://www.linkedin.com/messaging/` and reads unread conversations.
   c. For each item: dedup check → keyword match → write note if matched.
4. Note format: `LINKEDIN_<YYYYMMDD_HHMMSS>.md` in `Needs_Action/` with YAML
   frontmatter (source, actor, keywords, status) and an action checklist.
5. Execute Skill 003 (Update Dashboard) after any note is created.
6. Log in `Logs/LinkedInWatcher.log`: `[DATE] SKILL-005 — LINKEDIN_<id>.md created.`

**Constraints:**
- Read-only: never send messages, accept/reject connections, or post autonomously.
- Do not post or interact with LinkedIn without explicit human approval.
- Deduplication is in-memory per session; restart clears the seen set.

**Output:** `Needs_Action/LINKEDIN_<timestamp>.md`

---

## Skill 006 — Generate Business Post When Inbox Is Clear

**Skill ID:** SKILL-006
**Description:** When `Needs_Action/` contains no urgent items, proactively draft
a professional business post promoting the company's services. Save the draft
for human review and approval before any posting occurs.

**When to Use:**
- Automatically triggered by the monitoring loop when `Needs_Action/` is empty
  or contains no files with urgent status.
- Manually: when the owner wants a fresh LinkedIn/WhatsApp post drafted.

**Trigger condition (ALL must be true):**
1. `Needs_Action/` has zero `.md` files with `status: needs_action` in frontmatter.
2. No file in `Needs_Action/` has `urgent`, `invoice`, `payment`, `order`, or
   `pricing` in its filename or frontmatter.
3. `Logs/` does NOT contain a `SKILL-006` entry for today's date (max once/day).

**Step-by-Step Process:**

1. Scan `Needs_Action/` — confirm all trigger conditions are met. If not, skip.
2. Check `Logs/` for today's SKILL-006 entry — skip if found.
3. Draft a business post with the following structure:

   ```
   Hook (1–2 sentences): attention-grabbing opening relevant to target audience.
   Value (2–3 sentences): specific insight, tip, or service highlight.
   Proof (1 sentence): brief social proof or outcome (e.g., "helped 3 clients...").
   CTA (1 sentence): clear, low-friction call-to-action.
   ```

4. Post rules:
   - Tone: helpful, expert, non-salesy.
   - Length: 150–250 words.
   - Platform-ready for LinkedIn or WhatsApp broadcast.
   - Rotate the topic each day (services, tips, case study, insight).
5. Save draft to: `Plans/DRAFT_POST_<YYYY-MM-DD>.md`
   YAML frontmatter: `type: draft_post | date | status: pending_review | platform: linkedin`
6. Create approval request in `Pending_Approval/` using Skill 004 format:
   - Action: "Post business content to LinkedIn/WhatsApp"
   - Risk level: Low
   - Awaiting approval from: Owner
7. Update Dashboard (Skill 003).
8. Log: `[DATE] SKILL-006 — Business post draft created: Plans/DRAFT_POST_<date>.md`

**Constraints:**
- Never post autonomously. Draft + approval only.
- One draft per calendar day maximum.
- Do not generate a post if any urgent task exists in `Needs_Action/`.

**Output:**
- `Plans/DRAFT_POST_<YYYY-MM-DD>.md` — the post draft
- `Pending_Approval/APPROVAL-<DATE>-business-post.md` — approval request

---

---

## Skill 007 — Silver Tier Reasoning Pipeline

**Skill ID:** SKILL-007
**Slash Command:** `/silver-reason`
**Description:** End-to-end reasoning pipeline for Silver Tier. Reads every file in
`Needs_Action/`, reasons about required actions, creates structured `Plans/PLAN_xxx.md`
files with checkboxes, and gates all sensitive actions (email, LinkedIn, WhatsApp) behind
`Pending_Approval/` files. After human approval, `Scripts/approval_watcher.py` executes
actions via the MCP email server.

**When to Use:**
- At the start of every work session.
- After any watcher (Gmail, LinkedIn, WhatsApp, Filesystem) drops a new file in `Needs_Action/`.
- Whenever you want to know what needs to happen and why.

**Trigger:**
```
/silver-reason
```
(Implemented in `.claude/commands/silver-reason.md`)

**Step-by-Step Process:**

1. Scan `Needs_Action/` — list all files.
2. Determine next PLAN ID (count existing `Plans/PLAN_*.md` + 1).
3. For each file: read content, classify every required action as SAFE or SENSITIVE.
4. Create `Plans/PLAN_<ID>.md` with full context, checkbox action lists, and approval refs.
5. For each SENSITIVE action: create `Pending_Approval/APPROVAL_<date>_<ID>_<slug>.md`
   with full action details and an embedded `APPROVAL_PAYLOAD` JSON block.
6. Execute all SAFE actions immediately (log, update Dashboard, etc.).
7. Update `Dashboard.md` (Recent Activity + Pending Tasks for each approval).
8. Print a summary report.

**Sensitivity Rules:**

| Action | Classification |
|--------|---------------|
| Read / summarise / log | SAFE |
| Create internal document | SAFE |
| Move file within vault | SAFE |
| Send email (any outbound) | **SENSITIVE** |
| LinkedIn post (any length) | **SENSITIVE** |
| Reply to LinkedIn / WhatsApp | **SENSITIVE** |
| Payment > $100 | **SENSITIVE** |
| Delete any file or record | **SENSITIVE** |

**Approval Execution — `Scripts/approval_watcher.py`:**

After the human moves an `APPROVAL_*.md` from `Pending_Approval/` → `Approved/`:

1. `approval_watcher.py` detects the file (polls every 30 s).
2. Parses the `APPROVAL_PAYLOAD` JSON block from the file.
3. Dispatches to the correct handler:
   - `send_email` → `Scripts/mcp_email_client.py` → MCP email server (`mcp-email-server/dist/index.js`)
   - `linkedin_post` → logs content for manual posting (autonomous posting disabled per policy)
   - `whatsapp_send` → logs content for manual send
4. Archives the approval file to `Done/`.
5. Marks the checkbox in the linked `Plans/PLAN_<ID>.md` as done.
6. Logs to `Logs/ActivityLog.md` and updates `Dashboard.md`.

**Run the watcher:**
```bash
# Continuous (background)
python Scripts/approval_watcher.py

# One-shot (for cron or testing)
python Scripts/approval_watcher.py --once

# Dry-run (no execution, just logging)
python Scripts/approval_watcher.py --dry-run --once
```

**Supporting files:**

| File | Role |
|------|------|
| `.claude/commands/silver-reason.md` | Slash command prompt — the reasoning brain |
| `Scripts/approval_watcher.py` | Polls `Approved/`, executes actions |
| `Scripts/mcp_email_client.py` | Thin Python MCP client for the email server |
| `mcp-email-server/dist/index.js` | Node.js MCP server (Gmail OAuth2) |

**Constraints:**
- Never send email, post to LinkedIn, or send WhatsApp autonomously.
- All outbound actions must pass through `Pending_Approval/` → human approval → `Approved/`.
- The `APPROVAL_PAYLOAD` JSON in each approval file is the single source of truth for what gets executed.

---

---

## Skill 008 — LinkedIn Post Generator

**Skill ID:** SKILL-008
**Slash Command:** `/linkedin-post`
**Description:** Reads `Business_Goals.md`, generates a platform-ready LinkedIn
post (150–250 words) matching today's topic rotation, saves the draft to
`Plans/DRAFT_POST_<date>.md`, and creates a `Pending_Approval/` file for human
review. After approval, `approval_watcher.py` calls `Scripts/linkedin_poster.py`
(Playwright) to submit the post to LinkedIn via the saved browser session.
**Always draft-only — never posts without explicit human approval.**

**When to Use:**
- Daily (automated by orchestrator or cron when `Needs_Action/` is clear).
- Manually whenever a fresh LinkedIn post draft is needed.
- Run `/linkedin-post` in Claude Code to trigger the skill.

**Pre-flight checks (all three must pass or skill stops):**
1. No urgent files in `Needs_Action/` (urgent = High priority / invoice / payment).
2. No `SKILL-008` entry in `Logs/ActivityLog.md` for today (max one post per day).
3. `Business_Goals.md` exists in the vault root.

**Step-by-Step Process:**

1. Run pre-flight checks — stop with a clear message if any fail.
2. Read `Business_Goals.md` — extract company overview, services, audience, tone, CTAs.
3. Choose today's topic angle from the Topic Rotation table (day-of-week based).
4. Generate the post: Hook → Value → Proof → CTA → Hashtags (150–250 words).
5. Save `Plans/DRAFT_POST_<YYYY-MM-DD>.md` with frontmatter + review checklist.
6. Create `Pending_Approval/APPROVAL_<date>_008_linkedin-post.md` with:
   - Full post preview
   - Embedded `APPROVAL_PAYLOAD` JSON (action: `linkedin_post`)
7. Update `Dashboard.md`:
   - Add row to **LinkedIn Posts** table (newest first)
   - Add to **Pending Tasks** checklist
   - Add to **Recent Activity** table
8. Append to `Logs/ActivityLog.md`.
9. Print summary report.

**Topic Rotation (day of week):**

| Day | Angle |
|-----|-------|
| Monday | Services spotlight |
| Tuesday | Tip / quick insight |
| Wednesday | Case study / outcome |
| Thursday | Process / behind-the-scenes |
| Friday | Question for engagement |
| Saturday | Industry observation |
| Sunday | Motivational / culture |

**Post format:**
```
Hook (1–2 lines)

Value (2–4 short paragraphs)

Proof (1 line — specific outcome or number)

CTA (1 low-friction ask from CTA library)

3–5 hashtags
```

**Execution after approval — `Scripts/linkedin_poster.py`:**

When the human moves the approval file to `Approved/`:

1. `approval_watcher.py` detects the file and parses the `APPROVAL_PAYLOAD`.
2. Calls `Scripts/linkedin_poster.py --draft Plans/DRAFT_POST_<date>.md`.
3. `linkedin_poster.py`:
   - Launches Chromium with persistent session (`~/ai-secrets/linkedin_session/`).
   - Navigates to `https://www.linkedin.com/feed/`.
   - Clicks "Start a post", pastes content via clipboard API.
   - Clicks the "Post" button.
   - Logs result to `Logs/LinkedInPoster.log` and `Logs/ActivityLog.md`.
4. Approval file archived to `Done/`.
5. Draft plan checkbox ticked.

**Supporting files:**

| File | Role |
|------|------|
| `.claude/commands/linkedin-post.md` | Slash command — generates draft + approval |
| `Business_Goals.md` | Source of truth: company, audience, services, tone |
| `Scripts/linkedin_poster.py` | Playwright poster — called after approval |
| `Scripts/approval_watcher.py` | Dispatches `linkedin_post` action |

**Constraints:**
- Never post autonomously — always requires human to move file to `Approved/`.
- One post draft per calendar day maximum.
- Post must be 150–250 words; never more than 5 hashtags.
- Content must reference real details from `Business_Goals.md` — no generic filler.
- If `Business_Goals.md` has unfilled `[FILL IN]` placeholders in critical fields,
  note them in the draft and prompt the human to complete before approving.

**Output files:**
- `Plans/DRAFT_POST_<YYYY-MM-DD>.md` — the post draft with review checklist
- `Pending_Approval/APPROVAL_<date>_008_linkedin-post.md` — approval request with payload

---

*Silver Tier — Agent Skills v2.2 | See [[Company_Handbook]] for Rules of Engagement.*
