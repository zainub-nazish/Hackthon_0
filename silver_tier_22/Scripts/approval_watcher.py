"""
ApprovalWatcher — Silver Tier execution engine.

Watches the Approved/ folder for APPROVAL_*.md files.
When a file appears, parses the embedded APPROVAL_PAYLOAD JSON,
executes the action (email via MCP server, or logs intent for
LinkedIn/WhatsApp which require separate tooling), then archives
the file to Done/ and updates the linked Plan and Dashboard.

Usage:
    python Scripts/approval_watcher.py

Options:
    --poll  INT   Poll interval in seconds (default: 30)
    --once        Process once and exit (useful for cron / testing)
    --dry-run     Parse and log actions without executing them
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── path setup ──────────────────────────────────────────────────────────────
_HERE = Path(__file__).parent
_VAULT_ROOT = _HERE.parent

sys.path.insert(0, str(_HERE))
from mcp_email_client import MCPEmailClient, MCPEmailError  # noqa: E402

# ── constants ───────────────────────────────────────────────────────────────
APPROVED_DIR    = _VAULT_ROOT / "Approved"
REJECTED_DIR    = _VAULT_ROOT / "Rejected"
DONE_DIR        = _VAULT_ROOT / "Done"
PLANS_DIR       = _VAULT_ROOT / "Plans"
LOGS_DIR        = _VAULT_ROOT / "Logs"
DASHBOARD_MD    = _VAULT_ROOT / "Dashboard.md"
ACTIVITY_LOG    = LOGS_DIR / "ActivityLog.md"
WATCHER_LOG     = LOGS_DIR / "ApprovalWatcher.log"

PAYLOAD_START   = "<!-- APPROVAL_PAYLOAD"
PAYLOAD_END     = "-->"

# ── logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(WATCHER_LOG), encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


# ── helpers ──────────────────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

def now_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def now_display() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def extract_payload(text: str) -> dict | None:
    """Parse the <!-- APPROVAL_PAYLOAD ... --> JSON block from an approval file."""
    start = text.find(PAYLOAD_START)
    if start == -1:
        return None
    json_start = start + len(PAYLOAD_START)
    end = text.find(PAYLOAD_END, json_start)
    if end == -1:
        return None
    raw = text[json_start:end].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        log.error("Failed to parse APPROVAL_PAYLOAD JSON: %s", exc)
        return None


def extract_frontmatter_field(text: str, field: str) -> str:
    """Extract a simple scalar field from YAML frontmatter (no parsing library needed)."""
    match = re.search(rf"^{field}:\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def append_activity_log(line: str) -> None:
    ACTIVITY_LOG.parent.mkdir(exist_ok=True)
    with ACTIVITY_LOG.open("a", encoding="utf-8") as f:
        f.write(f"[{now_iso()}] {line}\n")


def update_dashboard(approval_filename: str, action: str, outcome: str) -> None:
    """Append a row to the Recent Activity table in Dashboard.md."""
    if not DASHBOARD_MD.exists():
        return
    content = DASHBOARD_MD.read_text(encoding="utf-8")
    new_row = (
        f"| {now_date()} | SKILL-007: {action} ({approval_filename}) "
        f"| {outcome} | AI (Silver) |"
    )
    # Append after the last table row in Recent Activity section
    marker = "| --- |"
    if marker in content:
        # Insert after the last existing row
        lines = content.splitlines()
        insert_at = len(lines)
        in_table = False
        for i, ln in enumerate(lines):
            if "Recent Activity" in ln:
                in_table = True
            if in_table and ln.startswith("|") and "---" not in ln and ln.count("|") >= 4:
                insert_at = i + 1
        lines.insert(insert_at, new_row)
        DASHBOARD_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        # Append at end as fallback
        with DASHBOARD_MD.open("a", encoding="utf-8") as f:
            f.write(f"\n{new_row}\n")


def mark_plan_action_done(plan_ref: str, approval_filename: str) -> None:
    """In the linked Plan file, update the approval row status to Executed."""
    if not plan_ref:
        return
    plan_path = PLANS_DIR / plan_ref
    if not plan_path.exists():
        log.warning("Plan file not found: %s", plan_path)
        return
    content = plan_path.read_text(encoding="utf-8")
    # Mark the approval checkbox
    updated = content.replace(
        f"- [ ] {approval_filename}",
        f"- [x] {approval_filename} ✓ executed {now_date()}",
    )
    # Also update the Approvals table row
    updated = updated.replace(
        f"| {approval_filename} | ", f"| {approval_filename} | "
    ).replace("| Pending |", "| Executed |", 1)
    plan_path.write_text(updated, encoding="utf-8")


def archive_file(src: Path, outcome: str) -> Path:
    """Move an approval file to Done/ (executed) or Rejected/ (rejected)."""
    dest_dir = DONE_DIR if outcome == "executed" else REJECTED_DIR
    dest_dir.mkdir(exist_ok=True)
    dest = dest_dir / src.name
    shutil.move(str(src), str(dest))
    log.info("Archived %s → %s/", src.name, dest_dir.name)
    return dest


# ── action executors ─────────────────────────────────────────────────────────

def execute_send_email(params: dict, dry_run: bool) -> tuple[bool, str]:
    """Call MCP email server to send an email. Returns (success, message)."""
    to       = params.get("to") or ""
    subject  = params.get("subject") or "(no subject)"
    body     = params.get("body") or ""
    attach   = params.get("attachment")  # may be None

    if not to or not body:
        return False, "Missing 'to' or 'body' in payload params"

    if dry_run:
        log.info("[DRY-RUN] Would send email → to=%s subject=%s", to, subject)
        return True, f"dry-run: email to {to}"

    try:
        client = MCPEmailClient()
        result = client.send_email(to=to, subject=subject, body=body, attachment=attach)
        if result["success"]:
            return True, f"Email sent to {to} | messageId={result.get('messageId', '')}"
        else:
            return False, f"MCP error: {result.get('error', 'unknown')}"
    except MCPEmailError as exc:
        return False, f"MCPEmailError: {exc}"
    except Exception as exc:
        return False, f"Unexpected error: {exc}"


def execute_linkedin_post(params: dict, dry_run: bool) -> tuple[bool, str]:
    """
    Post approved LinkedIn content via Scripts/linkedin_poster.py (Playwright).
    Falls back to a log-and-manual-action message if linkedin_poster.py is missing.
    """
    import subprocess as _sp

    body       = params.get("body", "")
    draft_file = params.get("draft_file", "")

    if not body:
        return False, "Missing 'body' in linkedin_post payload"

    poster_script = _HERE / "linkedin_poster.py"
    if not poster_script.exists():
        log.warning(
            "linkedin_poster.py not found at %s — manual action required.\n"
            "Post content:\n%s", poster_script, body
        )
        return True, "linkedin_poster.py missing — content logged for manual posting"

    cmd = [sys.executable, str(poster_script)]
    if draft_file:
        draft_path = _VAULT_ROOT / draft_file
        if draft_path.exists():
            cmd += ["--draft", str(draft_path)]
        else:
            cmd += ["--content", body]
    else:
        cmd += ["--content", body]

    if dry_run:
        cmd.append("--dry-run")
        log.info("[DRY-RUN] Would run: %s", " ".join(cmd))
        return True, f"dry-run: linkedin_poster.py with {len(body)} chars"

    log.info("Calling linkedin_poster.py (%d chars)…", len(body))
    try:
        result = _sp.run(cmd, capture_output=True, text=True, timeout=180)
        if result.returncode == 0:
            return True, f"LinkedIn post submitted ({len(body)} chars)"
        elif result.returncode == 2:
            msg = "LinkedIn session not active — run linkedin_watcher.py first to log in"
            log.error(msg)
            return False, msg
        else:
            stderr = result.stderr.strip()[-300:]
            log.error("linkedin_poster.py failed (exit %d): %s", result.returncode, stderr)
            return False, f"poster exit {result.returncode}: {stderr}"
    except _sp.TimeoutExpired:
        return False, "linkedin_poster.py timed out after 180s"
    except Exception as exc:
        return False, f"Unexpected error launching poster: {exc}"


def execute_whatsapp_send(params: dict, dry_run: bool) -> tuple[bool, str]:
    """
    WhatsApp sending requires the Playwright watcher (Scripts/whatsapp_watcher.py).
    Log intent; automated send is not implemented in this tier.
    """
    contact = params.get("contact", "unknown")
    body    = params.get("body", "")
    log.info(
        "WhatsApp message approved for %s — automated send not yet implemented.\n"
        "Message content:\n%s", contact, body
    )
    return True, f"WhatsApp approved for {contact} — manual send required (see log)"


ACTION_HANDLERS = {
    "send_email":     execute_send_email,
    "linkedin_post":  execute_linkedin_post,
    "whatsapp_send":  execute_whatsapp_send,
}


# ── core processing ──────────────────────────────────────────────────────────

def process_approval_file(path: Path, dry_run: bool) -> None:
    """Process one APPROVAL_*.md file from Approved/."""
    log.info("Processing: %s", path.name)
    text = path.read_text(encoding="utf-8")

    payload = extract_payload(text)
    if payload is None:
        log.error("No APPROVAL_PAYLOAD found in %s — skipping", path.name)
        return

    action   = payload.get("action", "")
    params   = payload.get("params", {})
    plan_ref = payload.get("plan_ref", "")

    handler = ACTION_HANDLERS.get(action)
    if handler is None:
        log.error("Unknown action '%s' in %s — skipping", action, path.name)
        return

    log.info("Executing action: %s", action)
    success, message = handler(params, dry_run)

    outcome = "executed" if success else "failed"
    log.info("Result: %s — %s", outcome.upper(), message)

    # Update Plan file
    if not dry_run:
        mark_plan_action_done(plan_ref, path.name)

    # Log activity
    append_activity_log(
        f"SKILL-007 | ApprovalWatcher | {path.name} | {action} | {outcome} | {message}"
    )

    # Update Dashboard
    update_dashboard(path.name, action, outcome)

    # Archive file
    if not dry_run:
        archive_file(path, outcome)
    else:
        log.info("[DRY-RUN] Would archive %s → %s/", path.name, outcome)


def scan_approved(dry_run: bool) -> int:
    """Scan Approved/ for APPROVAL_*.md files. Returns count processed."""
    APPROVED_DIR.mkdir(exist_ok=True)
    files = sorted(APPROVED_DIR.glob("APPROVAL_*.md"))
    for f in files:
        try:
            process_approval_file(f, dry_run)
        except Exception as exc:
            log.exception("Unhandled error processing %s: %s", f.name, exc)
    return len(files)


# ── watcher loop ─────────────────────────────────────────────────────────────

class ApprovalWatcher:
    def __init__(self, poll_interval: int = 30, dry_run: bool = False) -> None:
        self.poll_interval = poll_interval
        self.dry_run = dry_run
        self._stop = False
        signal.signal(signal.SIGINT,  self._handle_stop)
        signal.signal(signal.SIGTERM, self._handle_stop)

    def _handle_stop(self, *_) -> None:
        log.info("Stop signal received — shutting down.")
        self._stop = True

    def run_once(self) -> int:
        return scan_approved(self.dry_run)

    def run(self) -> None:
        log.info(
            "ApprovalWatcher started | poll=%ds | dry_run=%s | watching: %s",
            self.poll_interval, self.dry_run, APPROVED_DIR,
        )
        while not self._stop:
            count = scan_approved(self.dry_run)
            if count:
                log.info("Processed %d approval(s) this cycle.", count)
            time.sleep(self.poll_interval)
        log.info("ApprovalWatcher stopped.")


# ── entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Silver Tier Approval Watcher")
    parser.add_argument("--poll",    type=int, default=30,  help="Poll interval seconds")
    parser.add_argument("--once",    action="store_true",   help="Process once and exit")
    parser.add_argument("--dry-run", action="store_true",   help="Log without executing")
    args = parser.parse_args()

    watcher = ApprovalWatcher(poll_interval=args.poll, dry_run=args.dry_run)

    if args.once:
        n = watcher.run_once()
        log.info("--once mode: processed %d approval(s).", n)
    else:
        watcher.run()
