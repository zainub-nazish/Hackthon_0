---
id: "007"
title: WhatsApp and LinkedIn Watcher Creation
stage: general
date: 2026-03-18
surface: agent
model: claude-sonnet-4-6
feature: none
branch: main
user: zainub-nazish
command: resume
labels: ["whatsapp", "playwright", "linkedin", "watcher", "orchestrator"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - watchers/whatsapp_watcher.py
  - watchers/linkedin_watcher.py
  - watchers/__init__.py
  - main.py
tests:
  - none
---

## Prompt

I have base_watcher.py and gmail_watcher.py already. Now create whatsapp_watcher.py exactly as per the hackathon document (Playwright, keywords: urgent, invoice, payment, help). Also create a simple LinkedInWatcher stub that watches /Needs_Action for any LINKEDIN_ file. Make sure both watchers create .md files in Needs_Action with proper frontmatter. Update orchestrator logic if needed.

## Response snapshot

Created four files:
1. `watchers/whatsapp_watcher.py` — Playwright-based WhatsApp Web monitor. Uses persistent browser context (session saved to Logs/whatsapp_session/), polls unread chats every 30s, filters messages for keywords: urgent, invoice, payment, help, writes WHATSAPP_<timestamp>.md to Needs_Action/ with YAML frontmatter.
2. `watchers/linkedin_watcher.py` — Polling stub. Watches Needs_Action/ every 15s for LINKEDIN_-prefixed files, creates companion LINKEDIN_<stem>.meta.md notes with YAML frontmatter.
3. `watchers/__init__.py` — Updated to export all three concrete watchers.
4. `main.py` — Rewritten as a proper orchestrator. Starts selected watchers as daemon threads. Default: `fs,li`. WhatsApp (`wa`) opt-in via `--watchers fs,wa,li` (requires browser/QR). Handles SIGINT/SIGTERM for graceful shutdown.

## Outcome

- ✅ Impact: Silver-tier gains WhatsApp keyword monitoring and LinkedIn stub, both integrated into the orchestrator
- 🧪 Tests: none — manual testing via `python main.py` or individual watcher scripts
- 📁 Files: watchers/whatsapp_watcher.py, watchers/linkedin_watcher.py, watchers/__init__.py, main.py
- 🔁 Next prompts: implement full LinkedIn Playwright scraper; add gmail_watcher.py if not yet created; write integration tests
- 🧠 Reflection: WhatsApp uses persistent context to avoid repeated QR scans; LinkedIn stub follows same polling pattern as FileSystemWatcher for consistency

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): none
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): add Gmail watcher with same BaseWatcher pattern
