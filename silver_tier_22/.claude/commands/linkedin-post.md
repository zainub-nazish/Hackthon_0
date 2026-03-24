# SKILL-008 — LinkedIn Post Generator

You are the Silver Tier AI Employee executing the LinkedIn post generation pipeline.
Follow every step below in order. Do not ask clarifying questions — proceed autonomously.
Record every decision in the output so the human can review before approving.

---

## STEP 1 — Pre-flight checks (run all three; stop if any fails)

### 1a. Urgent task check

List all `.md` files in `Needs_Action/`.

A file counts as **urgent** if ANY of the following are true:
- Its filename contains: `urgent`, `invoice`, `payment`, `order`, `pricing`
- Its YAML frontmatter contains `priority: High` or `status: urgent`

If **any urgent file exists**, print:

> "SKILL-008 skipped — urgent items in Needs_Action/ must be resolved first:
> [list filenames]"

Then stop.

### 1b. Daily frequency check

Read `Logs/ActivityLog.md`. Search for a line matching:
`SKILL-008` AND today's date (format `YYYY-MM-DD`).

If found, print:

> "SKILL-008 skipped — LinkedIn post already generated today ([matched line])."

Then stop.

### 1c. Business goals check

Check that `Business_Goals.md` exists in the vault root.

If it does not exist, print:

> "SKILL-008 blocked — Business_Goals.md not found.
> Create it at the vault root with your company overview, services, and tone guidelines."

Then stop.

---

## STEP 2 — Read source material

Read `Business_Goals.md` in full. Extract and note:

- **Company overview** (what the company does and who it serves)
- **Target audience** and their top pain points
- **Core services** (all rows from the Services table)
- **Value propositions** (all bullet points)
- **Recent wins** (all rows from the Case Studies table)
- **Tone & voice rules** (exact phrases to avoid, style notes)
- **CTA library** (all available CTAs)
- **Current priorities** (Q-level focus and monthly topic pushes)

---

## STEP 3 — Choose today's topic

Determine today's day of week (from the current date in context).

Use the Topic Rotation table from `Business_Goals.md`:

| Day | Angle |
|-----|-------|
| Monday | Services spotlight |
| Tuesday | Tip / quick insight |
| Wednesday | Case study / outcome |
| Thursday | Process / behind-the-scenes |
| Friday | Question for engagement |
| Saturday | Industry observation |
| Sunday | Motivational / culture |

If `Business_Goals.md` has a "Topics to push this month" section with items,
**weight the topic toward those** while still matching the day's angle.

Print: `Topic angle selected: <angle> (<day>)`

---

## STEP 4 — Generate the LinkedIn post

Write the post following the exact format from `Business_Goals.md`. If the
format section is missing, use this default:

```
[Hook — 1–2 lines, bold claim or question that stops scrolling]

[Value — 2–4 short paragraphs of insight, tip, or story]

[Proof — 1 line: specific outcome, number, or credibility signal]

[CTA — 1 low-friction ask from the CTA library]

[3–5 hashtags from the approved hashtag pool]
```

**Hard rules (enforce every time):**
- Length: 150–250 words (count carefully)
- No buzzwords from the "Avoid" list in Business_Goals.md
- One CTA only — pick from the CTA library, pick one not used recently
- Hashtags at the very end only, 3–5 maximum
- Blank line between each section (LinkedIn line-break rendering)
- Content must reference at least one real detail from Business_Goals.md
  (service name, pain point, or client outcome) — no generic filler

After writing, print:
```
Word count: <N>
Topic: <angle>
CTA used: "<cta text>"
Hashtags: <list>
```

---

## STEP 5 — Determine next Plan/Draft ID

List files in `Plans/` matching `DRAFT_POST_*.md`.
Next ID = today's date (`YYYY-MM-DD`) — filename: `DRAFT_POST_<date>.md`.

If `Plans/DRAFT_POST_<today>.md` already exists, append `_v2`, `_v3`, etc.

---

## STEP 6 — Save draft to Plans/

Create `Plans/DRAFT_POST_<date>.md` using this template exactly:

```markdown
---
type: draft_post
platform: linkedin
date: <YYYY-MM-DD>
day: <Monday|Tuesday|...>
topic_angle: <angle>
word_count: <N>
status: pending_review
approval_file: <will be filled in Step 7>
---

# LinkedIn Draft — <date> (<day>: <angle>)

## Post Content

<full post text — exactly as generated in Step 4>

## Generation Notes

- Source: Business_Goals.md
- Topic angle: <angle>
- CTA: "<cta text>"
- Hashtags: <list>
- Generated: <YYYY-MM-DDThh:mm:ss UTC>

## Review Checklist

- [ ] Content is accurate and reflects current services
- [ ] Tone matches Business_Goals.md guidelines
- [ ] Word count is 150–250
- [ ] CTA is low-friction
- [ ] No sensitive business details exposed
- [ ] Approve: move Pending_Approval file → Approved/
```

---

## STEP 7 — Create Pending_Approval file

Filename: `APPROVAL_<date>_008_linkedin-post.md`

If that file already exists today, use `APPROVAL_<date>_008_linkedin-post-v2.md`, etc.

Create `Pending_Approval/<filename>` using this template exactly:

```markdown
---
approval_id: APPROVAL_<date>_008_linkedin-post
plan_ref: DRAFT_POST_<date>.md
action_type: linkedin_post
sensitivity: MEDIUM
created: <YYYY-MM-DDThh:mm:ss UTC>
status: PENDING
---

# APPROVAL — LinkedIn Post (<date>)

**Draft:** `Plans/DRAFT_POST_<date>.md`
**Created:** <date>
**Action type:** `linkedin_post`
**Sensitivity:** MEDIUM
**Platform:** LinkedIn

## Proposed Action

Post the following content to LinkedIn using the Playwright poster
(`Scripts/linkedin_poster.py`). The post will be published to the company's
LinkedIn profile using the saved browser session.

## Post Preview

---

<full post text — identical to what is in the draft file>

---

## Details

- **Platform:** LinkedIn
- **Character count:** <N> characters / <N> words
- **Topic angle:** <angle>
- **Day of week:** <day>
- **Draft file:** `Plans/DRAFT_POST_<date>.md`

## Why Approval is Required

LinkedIn posts are public and external-facing. All content must be reviewed
by the account owner before publishing. This is enforced by SKILL-008 policy.

## Decision

Move this file to `/Approved/` to **post to LinkedIn**, or `/Rejected/` to **discard**.

After approval, `Scripts/approval_watcher.py` will call `Scripts/linkedin_poster.py`
which opens the saved LinkedIn session (Chromium) and submits the post.

---

<!-- APPROVAL_PAYLOAD
{
  "action": "linkedin_post",
  "plan_ref": "DRAFT_POST_<date>.md",
  "params": {
    "to": null,
    "subject": null,
    "body": "<full post text — escape newlines as \\n, escape quotes>",
    "attachment": null,
    "platform": "linkedin",
    "contact": null,
    "draft_file": "Plans/DRAFT_POST_<date>.md",
    "char_count": <N>,
    "word_count": <N>
  }
}
-->
```

> **JSON payload rules (enforce strictly):**
> - `body` = full post text with `\n` for newlines, `\"` for double-quotes
> - All other unused fields = JSON `null` (not the string "null")
> - `char_count` and `word_count` = integers, not strings
> - `<!-- APPROVAL_PAYLOAD` and `-->` must each be alone on their own line

After creating the file, go back and fill in `approval_file:` in the draft's frontmatter.

---

## STEP 8 — Update Dashboard.md

Open `Dashboard.md`.

### 8a. Add/update the LinkedIn Posts section

Find the section `## LinkedIn Posts` in Dashboard.md.
If it does not exist, add it **before** the final `---` footer line.

Add a new row to the LinkedIn Posts table:

```markdown
## LinkedIn Posts

| Date | Day | Topic | Preview | Status | Approval |
|------|-----|-------|---------|--------|----------|
| <date> | <day> | <angle> | <first 60 chars of hook>... | Pending Approval | `APPROVAL_<date>_008_linkedin-post.md` |
```

If the table already exists, prepend the new row at the top (newest first).
Keep at most 10 rows (remove oldest if needed).

### 8b. Update Pending Tasks

Add to the Pending Tasks checklist:
```
- [ ] Review and approve LinkedIn post: Pending_Approval/APPROVAL_<date>_008_linkedin-post.md
```

### 8c. Update Recent Activity

Add to Recent Activity table:
```
| <date> | SKILL-008: LinkedIn draft generated (<angle>) | Pending Approval | AI (Silver) |
```

---

## STEP 9 — Log and report

Append to `Logs/ActivityLog.md`:
```
[<YYYY-MM-DDThh:mm:ss>] SKILL-008 | linkedin-post | DRAFT_POST_<date>.md created | Pending approval: APPROVAL_<date>_008_linkedin-post.md
```

Print the final summary:

```
## SKILL-008 Complete — LinkedIn Post Draft Created

Draft:    Plans/DRAFT_POST_<date>.md
Approval: Pending_Approval/APPROVAL_<date>_008_linkedin-post.md
Topic:    <angle> (<day>)
Words:    <N>

Post preview (first 100 chars):
  <first 100 characters of the hook>...

Next step:
  1. Open Pending_Approval/APPROVAL_<date>_008_linkedin-post.md and review the post.
  2. Move it to Approved/ to publish via Playwright, or Rejected/ to discard.
  3. After approving, approval_watcher.py will call Scripts/linkedin_poster.py
     to post using the saved LinkedIn browser session.
```

---

## HARD CONSTRAINTS (never violate)

- Never post to LinkedIn autonomously — always stop at Pending_Approval.
- Never invent business facts not present in Business_Goals.md.
- Never exceed 250 words or go below 150 words.
- Never use more than 5 hashtags.
- Only one LinkedIn post draft per calendar day (enforced by Step 1b).
- If Business_Goals.md has `[FILL IN]` placeholders in critical fields
  (company name, services, audience), note them in the draft and ask the
  human to fill them in before approving.
