---
id: "007"
title: Gmail Watcher Silver Tier
stage: general
date: 2026-03-20
surface: agent
model: claude-sonnet-4-6
feature: silver-tier-gmail-watcher
branch: main
user: danish
command: create Scripts/base_watcher.py and Scripts/gmail_watcher.py
labels: ["gmail","watcher","silver-tier","obsidian","pm2"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - Scripts/base_watcher.py
  - Scripts/gmail_watcher.py
  - Scripts/README.md
tests:
  - manual: first-run OAuth2 flow opens browser, token saved to ~/ai-secrets/token.json
  - manual: unread+important email produces .md note in Needs_Action/
  - manual: restarting watcher does not duplicate notes (seen-IDs file)
---

## Prompt

I am building Silver Tier Personal AI Employee in Obsidian vault. Create /Scripts/base_watcher.py exactly with the BaseWatcher class from hackathon doc. Then create /Scripts/gmail_watcher.py using GmailWatcher class (use credentials from ~/ai-secrets/gmail_credentials.json and token.json flow). Make it create .md files in /Needs_Action for unread important emails. Also create a simple README.md in /Scripts explaining how to run with pm2.

## Response snapshot

Created three files under Scripts/:

1. `Scripts/base_watcher.py` — exact copy of the BaseWatcher abstract class from `watchers/base_watcher.py` (setup_logging, __init__, process_file, run, stop, _sleep).
2. `Scripts/gmail_watcher.py` — GmailWatcher subclass using Google OAuth2 (credentials from ~/ai-secrets/gmail_credentials.json, token at ~/ai-secrets/token.json). Polls Gmail every 60s for `is:unread is:important`, creates Obsidian .md notes in Needs_Action/, marks emails as read, deduplicates via Logs/gmail_seen_ids.txt.
3. `Scripts/README.md` — setup guide covering pip install, credential setup, manual run, pm2 start/save/startup, and common pm2 commands.

## Outcome

- Impact: Silver-tier Gmail monitoring is now wired up; unread important emails land in Needs_Action/ as Obsidian-ready notes.
- Tests: OAuth flow + note creation require manual verification on first run.
- Files: Scripts/base_watcher.py, Scripts/gmail_watcher.py, Scripts/README.md
- Next prompts: install deps, run first auth flow, verify note format in vault.
- Reflection: Followed BaseWatcher pattern exactly from existing watchers/; kept deduplication via flat text file to avoid extra dependencies.

## Evaluation notes (flywheel)

- Failure modes observed: none yet
- Graders run and results (PASS/FAIL): pending manual test
- Prompt variant (if applicable): none
- Next experiment: add IMAP fallback if Gmail API quota is hit
