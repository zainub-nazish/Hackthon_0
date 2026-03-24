---
id: "008"
title: WhatsApp Watcher Silver Tier
stage: general
date: 2026-03-20
surface: agent
model: claude-sonnet-4-6
feature: silver-tier-whatsapp-watcher
branch: main
user: danish
command: create Scripts/whatsapp_watcher.py with Playwright template
labels: ["whatsapp","playwright","watcher","silver-tier","obsidian"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - Scripts/whatsapp_watcher.py
  - Scripts/README.md
tests:
  - manual: first run opens Chromium, QR scan saves session to ~/ai-secrets/whatsapp_session/
  - manual: message with keyword "invoice" produces WHATSAPP_<timestamp>.md in Needs_Action/
  - manual: restart reuses session without re-scanning QR
---

## Prompt

Create /Scripts/whatsapp_watcher.py exactly like the Playwright template in hackathon doc. Use session_path = "~/ai-secrets/whatsapp_session". Keywords add karo: urgent, invoice, payment, order, pricing. It should create action files in /Needs_Action for WhatsApp messages.

## Response snapshot

Created `Scripts/whatsapp_watcher.py` following the exact Playwright template from `silver_tier/watchers/whatsapp_watcher.py`:

- `SESSION_DIR = Path.home() / "ai-secrets" / "whatsapp_session"` (persistent Chromium profile)
- `KEYWORDS = frozenset({"urgent", "invoice", "payment", "order", "pricing"})` (replaces original `help` with `order` + `pricing`)
- Inherits `BaseWatcher`; `process_file` is a no-op (browser-based watcher)
- `_launch()` → persistent Chromium context (headless=False for QR)
- `_navigate()` → waits for `[data-testid="chat-list"]` up to 90s
- `_scan()` → finds unread-badge chats, clicks each, reads last 20 incoming messages, matches keywords
- `_write_note()` → `WHATSAPP_<timestamp>.md` in `Needs_Action/` with YAML frontmatter + action checklist
- In-memory dedup via `_seen` set
- Also updated `Scripts/README.md` with WhatsApp section (session setup, pm2 start, log file table)

## Outcome

- Impact: WhatsApp messages containing business-critical keywords land as Obsidian notes in Needs_Action/ automatically.
- Tests: manual verification required (QR flow + keyword match)
- Files: Scripts/whatsapp_watcher.py, Scripts/README.md (updated)
- Next prompts: run first QR scan, verify note format, optionally add persistent dedup file
- Reflection: Followed hackathon template exactly; only changed SESSION_DIR and KEYWORDS as requested.

## Evaluation notes (flywheel)

- Failure modes observed: none yet
- Graders run and results (PASS/FAIL): pending manual test
- Prompt variant (if applicable): none
- Next experiment: add persistent seen-IDs file (like gmail_seen_ids.txt) for cross-restart dedup
