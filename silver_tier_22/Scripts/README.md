# Silver Tier Scripts

Watchers for the AI Employee Vault. Each script polls an external source and drops Obsidian notes into `Needs_Action/` for review.

---

## Scripts

| Script | What it does |
|---|---|
| `base_watcher.py` | Abstract base class; all watchers inherit from it |
| `gmail_watcher.py` | Polls Gmail for unread+important emails; creates `.md` notes in `Needs_Action/` |
| `whatsapp_watcher.py` | Playwright-based WhatsApp Web monitor; creates `.md` notes for messages matching keywords |
| `linkedin_watcher.py` | Playwright-based LinkedIn monitor; captures business opportunity notifications and unread messages |

---

## Prerequisites

### Python dependencies

```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

Or if you use the project's virtual environment:

```bash
cd <vault-root>
uv sync   # or: pip install -r requirements.txt
```

### Gmail credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create an **OAuth 2.0 Client ID** (Desktop app type).
2. Download the JSON file and save it to:
   ```
   ~/ai-secrets/gmail_credentials.json
   ```
3. On first run a browser window will open for consent. After granting access, the token is saved to `~/ai-secrets/token.json` and reused automatically.

### WhatsApp session

No credentials file needed. On first run a browser window opens WhatsApp Web — scan the QR code once. The session is persisted to `~/ai-secrets/whatsapp_session/` and reused on all subsequent runs.

### LinkedIn session

No credentials file needed. On first run a browser window opens LinkedIn — log in manually once. The session is persisted to `~/ai-secrets/linkedin_session/` and reused on all subsequent runs.

```bash
pip install playwright
playwright install chromium
```

---

## Running manually

From the vault root:

```bash
# Gmail watcher
python Scripts/gmail_watcher.py

# WhatsApp watcher
python Scripts/whatsapp_watcher.py

# LinkedIn watcher
python Scripts/linkedin_watcher.py
```

---

## Running with pm2

pm2 keeps the watchers alive, auto-restarts on crash, and persists across reboots.

### 1. Install pm2

```bash
npm install -g pm2
```

### 2. Start the watchers

```bash
pm2 start Scripts/gmail_watcher.py \
    --name gmail-watcher \
    --interpreter python \
    --cwd "D:/Hackthon_0/silver_tier_22"

pm2 start Scripts/whatsapp_watcher.py \
    --name whatsapp-watcher \
    --interpreter python \
    --cwd "D:/Hackthon_0/silver_tier_22"

pm2 start Scripts/linkedin_watcher.py \
    --name linkedin-watcher \
    --interpreter python \
    --cwd "D:/Hackthon_0/silver_tier_22"
```

> **Note:** `whatsapp-watcher` and `linkedin-watcher` open visible Chromium windows. Run them in a session where a display is available. First run: scan WhatsApp QR code / log in to LinkedIn manually. Subsequent restarts reuse the saved session.

### 3. Save the process list (survives reboot)

```bash
pm2 save
pm2 startup   # follow the printed command to register the startup hook
```

### 4. Common pm2 commands

```bash
pm2 list                              # show all processes
pm2 logs gmail-watcher                # tail Gmail watcher logs
pm2 logs whatsapp-watcher             # tail WhatsApp watcher logs
pm2 logs linkedin-watcher             # tail LinkedIn watcher logs
pm2 logs linkedin-watcher --lines 100
pm2 restart linkedin-watcher          # restart
pm2 stop linkedin-watcher             # stop
pm2 delete linkedin-watcher           # remove from pm2
```

---

## Log files

| File | Description |
|---|---|
| `Logs/GmailWatcher.log` | Full debug log from the Gmail watcher |
| `Logs/gmail_seen_ids.txt` | Message IDs already processed (prevents duplicates on restart) |
| `Logs/WhatsAppWatcher.log` | Full debug log from the WhatsApp watcher |
| `Logs/LinkedInWatcher.log` | Full debug log from the LinkedIn watcher |
| `~/ai-secrets/whatsapp_session/` | Persistent Chromium profile (WhatsApp QR session) |
| `~/ai-secrets/linkedin_session/` | Persistent Chromium profile (LinkedIn login session) |

---

## Notes

- **Gmail:** marks emails as read after creating a note; deduplication also via `gmail_seen_ids.txt`.
- **WhatsApp:** deduplication is in-memory (resets on restart); messages already visible before the watcher starts will be re-evaluated but only trigger notes if they contain keywords.
- Poll intervals: Gmail = 60 s, WhatsApp = 30 s. Both configurable via `POLL_INTERVAL` in the respective script.
- WhatsApp keywords: `invoice`, `order`, `payment`, `pricing`, `urgent`.
