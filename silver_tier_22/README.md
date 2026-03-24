# AI Employee Vault — Silver Tier

Autonomous AI employee system built on an Obsidian vault.
Monitors Gmail, LinkedIn, WhatsApp, and the local filesystem,
reasons about required actions, gates sensitive operations behind
human approval, and executes approved actions via an MCP email server.

---

## Architecture

```
External signals
  Gmail       ──> Scripts/gmail_watcher.py       ─┐
  LinkedIn    ──> Scripts/linkedin_watcher.py     ─┤
  WhatsApp    ──> Scripts/whatsapp_watcher.py     ─┤──> Needs_Action/*.md
  Filesystem  ──> watchers/filesystem_watcher.py  ─┘

Reasoning (Claude Code slash command)
  /silver-reason
    reads  Needs_Action/*.md
    writes Plans/PLAN_xxx.md          (checkboxes)
    writes Pending_Approval/*.md      (sensitive actions only)
    executes safe actions immediately

Human approval
  review  Pending_Approval/*.md
  move to Approved/  (execute) or  Rejected/  (cancel)

Execution
  Scripts/approval_watcher.py         (polls Approved/ every 30 s)
    send_email  ──> Scripts/mcp_email_client.py
                      ──> mcp-email-server/dist/index.js   (Gmail OAuth2)
    linkedin_post, whatsapp_send ──> logged for manual action

Scheduling
  Scripts/orchestrator.py             (cron scheduler + optional process supervisor)
    08:00 UTC weekdays ──> daily briefing email via MCP
```

---

## Folder layout

```
Inbox/              New files arrive here (FileSystemWatcher routes them on)
Needs_Action/       Items requiring reasoning — watchers write here
Pending_Approval/   Sensitive actions waiting for human sign-off
Approved/           Human moves files here → approval_watcher.py executes
Rejected/           Human moves files here → action cancelled
Done/               Archived completed items
Plans/              PLAN_xxx.md files created by /silver-reason
Logs/               Per-watcher logs + ActivityLog.md
Briefings/          Executive summaries (on demand)
Scripts/            Silver-tier watcher and orchestration scripts
watchers/           Bronze-tier filesystem watcher
mcp-email-server/   Node.js MCP server (Gmail OAuth2 send)
```

---

## Quick start

### 1. Credentials

Copy the template and fill in your Gmail OAuth2 values:

```bash
cp mcp-email-server/.env.example ~/ai-secrets/.env
# or create ~/ai-secrets/gmail_credentials.json  (see .env.example for format)
```

Set the daily briefing recipient:

```bash
echo "BRIEFING_RECIPIENT=you@gmail.com" >> ~/ai-secrets/.env
```

### 2. Build the MCP email server

```bash
cd mcp-email-server
npm install
npm run build        # outputs dist/index.js
cd ..
```

### 3. Python environment

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt  # google-auth, playwright, etc.
```

### 4. Run everything (standalone — no pm2)

```bash
python Scripts/orchestrator.py
```

This starts all five watchers as supervised subprocesses **and** runs the
cron scheduler in the same process.  Logs go to `Logs/`.

### 5. Reason about pending work

In Claude Code:

```
/silver-reason
```

Claude reads every file in `Needs_Action/`, creates `Plans/PLAN_xxx.md` with
checkboxes, and puts sensitive actions in `Pending_Approval/` for your review.

---

## Running with pm2

pm2 gives each watcher its own process with persistent logs, restart policies,
and a web dashboard.

### Generate the config

```bash
python Scripts/orchestrator.py --generate-pm2 > ecosystem.config.js
```

The generated file wires up all five watchers **plus** the orchestrator in
`cron-only` mode (so cron jobs still fire without duplicating the watchers).

### Start / manage

```bash
# Start everything
pm2 start ecosystem.config.js

# Live status
pm2 list

# Tail a specific watcher's log
pm2 logs gmail-watcher
pm2 logs approval-watcher

# Restart one watcher
pm2 restart linkedin-watcher

# Stop everything
pm2 stop all

# Save process list so it survives reboots
pm2 save
pm2 startup          # follow the printed command
```

### Disable a watcher temporarily

```bash
pm2 stop whatsapp-watcher
# or set "enabled": False in WATCHER_REGISTRY inside orchestrator.py
# then: pm2 delete whatsapp-watcher && pm2 start ecosystem.config.js
```

---

## Cron scheduling

### Built-in scheduler (orchestrator.py)

The orchestrator includes a minute-resolution cron scheduler.
No external tools required — it runs in a daemon thread.

Current jobs (`Scripts/orchestrator.py → CRON_JOBS`):

| Job | Time (UTC) | Days | Action |
|-----|-----------|------|--------|
| `daily_briefing` | 08:00 | Mon–Fri | Email digest of Needs_Action, Plans, Pending_Approval |

To add a job, append to `CRON_JOBS` in `orchestrator.py`:

```python
CRON_JOBS = [
    {
        "name": "daily_briefing",
        "hour": 8,
        "min":  0,
        "days": ["mon", "tue", "wed", "thu", "fri"],
        "fn":   job_daily_briefing,
    },
    # Weekly Friday 5 PM report (add your own fn):
    {
        "name": "weekly_report",
        "hour": 17,
        "min":  0,
        "days": ["fri"],
        "fn":   job_weekly_report,   # define this function above CRON_JOBS
    },
]
```

### System cron (alternative)

If you prefer system cron instead of the built-in scheduler:

```cron
# Daily 8 AM briefing (UTC) — weekdays
0 8 * * 1-5  cd /home/zainab/silver_tier_22 && \
              .venv/bin/python Scripts/approval_watcher.py --once \
              >> Logs/cron.log 2>&1

# Run silver-reason non-interactively via Claude CLI — weekdays 8:05 AM
5 8 * * 1-5  claude --print "/silver-reason" \
              >> Logs/cron-silver-reason.log 2>&1
```

Add with `crontab -e`.

### pm2 cron (alternative to system cron)

pm2 can trigger a script on a cron schedule without system cron:

```javascript
// Add to apps[] in ecosystem.config.js
{
  name: "daily-briefing",
  script: "Scripts/orchestrator.py",
  interpreter: ".venv/bin/python",
  args: "--mode cron-only",
  cron_restart: "0 8 * * 1-5",   // restart = trigger at 8 AM Mon-Fri
  autorestart: false,
  watch: false,
}
```

---

## Approval workflow (step-by-step)

1. Run `/silver-reason` in Claude Code.
2. Claude writes `Pending_Approval/APPROVAL_<date>_<plan>_<slug>.md`.
3. Open the file — read the proposed action and the **Details** section.
4. To approve: move the file to `Approved/`.
5. `approval_watcher.py` detects the file within 30 seconds.
6. It parses the embedded `APPROVAL_PAYLOAD` JSON block and calls the correct handler:
   - `send_email` → `MCPEmailClient` → MCP server → Gmail
   - `linkedin_post` / `whatsapp_send` → logged for manual action (autonomous posting disabled)
7. The approval file is moved to `Done/`.
8. The checkbox in the linked `Plans/PLAN_xxx.md` is ticked.
9. `Logs/ActivityLog.md` is updated.

To reject instead: move the file to `Rejected/` — no action is taken.

---

## MCP email server

The email server (`mcp-email-server/`) is a Node.js MCP (Model Context Protocol)
server that exposes one tool:

**`send_email`**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `to` | string (email) | yes | Recipient |
| `subject` | string | yes | Subject line |
| `body` | string | yes | HTML or plain text |
| `attachment` | string (path) | no | Absolute path to file |

### Claude Code mcp.json entry

```json
{
  "mcpServers": {
    "email": {
      "command": "node",
      "args": ["/home/zainab/mcp-email-server/dist/index.js"],
      "env": { "GMAIL_CREDENTIALS": "/home/zainab/ai-secrets/gmail_credentials.json" }
    }
  }
}
```

### Test the MCP client from Python

```bash
python Scripts/mcp_email_client.py \
  --to test@example.com \
  --subject "MCP test" \
  --body "<p>Hello from the vault</p>"
```

---

## Watcher reference

| Watcher | Script | Poll | Output |
|---------|--------|------|--------|
| Filesystem | `watchers/filesystem_watcher.py` | 10 s | `Needs_Action/FILE_*.md` |
| Gmail | `Scripts/gmail_watcher.py` | 60 s | `Needs_Action/EMAIL_*.md` |
| LinkedIn | `Scripts/linkedin_watcher.py` | 60 s | `Needs_Action/LINKEDIN_*.md` |
| WhatsApp | `Scripts/whatsapp_watcher.py` | 30 s | `Needs_Action/WHATSAPP_*.md` |
| Approval | `Scripts/approval_watcher.py` | 30 s | Executes `Approved/APPROVAL_*.md` |

---

## Credentials setup

All secrets live in `~/ai-secrets/` — never committed to git.

```
~/ai-secrets/
  gmail_credentials.json    # Gmail OAuth2 (client_id, client_secret, refresh_token, user)
  token.json                # auto-refreshed by gmail_watcher.py
  linkedin_session/         # Playwright persistent browser session
  whatsapp_session/         # Playwright persistent browser session
  .env                      # BRIEFING_RECIPIENT and fallback env vars
```

`gmail_credentials.json` format:

```json
{
  "client_id":     "your-id.apps.googleusercontent.com",
  "client_secret": "GOCSPX-...",
  "refresh_token": "1//...",
  "user":          "you@gmail.com"
}
```

How to get a refresh token: open the OAuth Playground at
`https://developers.google.com/oauthplayground`, tick "Use your own OAuth
credentials", authorise `https://mail.google.com/`, then copy the Refresh Token.

---

## Adding a new Agent Skill

1. Create `.claude/commands/<skill-name>.md` with step-by-step instructions.
2. Document it in `AGENT_SKILLS.md`.
3. If it needs a background process, add an entry to `WATCHER_REGISTRY` in
   `orchestrator.py` and regenerate `ecosystem.config.js`.

---

*Silver Tier — AI Employee Vault | See AGENT_SKILLS.md and Company_Handbook.md*
