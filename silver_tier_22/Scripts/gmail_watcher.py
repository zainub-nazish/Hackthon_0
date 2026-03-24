"""
GmailWatcher — Silver-tier Gmail monitor.

Behavior:
  - Polls Gmail every 60 seconds for unread important emails.
  - Uses OAuth2 credentials from ~/ai-secrets/gmail_credentials.json.
  - Stores/refreshes the access token at ~/ai-secrets/token.json.
  - On new unread+important email: creates a .md note in Needs_Action/.
  - Deduplicates via a local seen-IDs file (Logs/gmail_seen_ids.txt).
  - Marks processed emails as read in Gmail.
  - All activity logged to console + Logs/GmailWatcher.log

Usage:
    python Scripts/gmail_watcher.py

First run:
    A browser window will open for OAuth2 consent.
    Grant access; the token is saved to ~/ai-secrets/token.json.
"""

import base64
import json
import re
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Allow running from project root or from Scripts/ directly
_HERE = Path(__file__).parent
_VAULT_ROOT = _HERE.parent

sys.path.insert(0, str(_HERE))
from base_watcher import BaseWatcher  # noqa: E402


# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------

VAULT_ROOT = _VAULT_ROOT
NEEDS_ACTION_DIR = VAULT_ROOT / "Needs_Action"
LOG_DIR = VAULT_ROOT / "Logs"
SEEN_IDS_FILE = LOG_DIR / "gmail_seen_ids.txt"

SECRETS_DIR = Path.home() / "ai-secrets"
CREDENTIALS_FILE = SECRETS_DIR / "gmail_credentials.json"
TOKEN_FILE = SECRETS_DIR / "token.json"

# ------------------------------------------------------------------
# Gmail API scopes
# ------------------------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",   # needed to mark as read
]

POLL_INTERVAL = 60  # seconds


# ------------------------------------------------------------------
# Auth helper
# ------------------------------------------------------------------

def _build_gmail_service():
    """Return an authenticated Gmail API service object."""
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"Gmail credentials not found at {CREDENTIALS_FILE}. "
                    "Download OAuth2 credentials from Google Cloud Console and "
                    f"save them to {CREDENTIALS_FILE}."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Persist refreshed / new token
        SECRETS_DIR.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=creds)


# ------------------------------------------------------------------
# GmailWatcher
# ------------------------------------------------------------------

class GmailWatcher(BaseWatcher):
    """
    Polls Gmail for unread important emails and writes Obsidian notes
    to Needs_Action/ for each one.

    Deduplication: message IDs are stored in Logs/gmail_seen_ids.txt so
    the watcher is safe to restart without creating duplicate notes.
    """

    def __init__(self) -> None:
        # BaseWatcher needs a watch_dir; we point it at Needs_Action
        # even though we're not watching the filesystem here.
        super().__init__(
            watch_dir=NEEDS_ACTION_DIR,
            interval=POLL_INTERVAL,
            log_dir=LOG_DIR,
        )
        NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        self._seen_ids: set[str] = self._load_seen_ids()
        self._service = None  # lazy-init on first poll

        self.logger.info("Vault root      : %s", VAULT_ROOT)
        self.logger.info("Needs_Action dir: %s", NEEDS_ACTION_DIR)
        self.logger.info("Credentials     : %s", CREDENTIALS_FILE)
        self.logger.info("Token           : %s", TOKEN_FILE)
        self.logger.info("Poll interval   : %ds", POLL_INTERVAL)

    # ------------------------------------------------------------------
    # Seen-IDs persistence
    # ------------------------------------------------------------------

    def _load_seen_ids(self) -> set[str]:
        if SEEN_IDS_FILE.exists():
            ids = {line.strip() for line in SEEN_IDS_FILE.read_text(encoding="utf-8").splitlines() if line.strip()}
            self.logger.debug("Loaded %d seen message IDs.", len(ids))
            return ids
        return set()

    def _save_seen_id(self, msg_id: str) -> None:
        self._seen_ids.add(msg_id)
        with SEEN_IDS_FILE.open("a", encoding="utf-8") as fh:
            fh.write(f"{msg_id}\n")

    # ------------------------------------------------------------------
    # BaseWatcher: process_file (unused — we override the poll logic)
    # ------------------------------------------------------------------

    def process_file(self, file_path: Path) -> None:
        """Not used by GmailWatcher; Gmail items are fetched via API."""
        pass

    # ------------------------------------------------------------------
    # Gmail helpers
    # ------------------------------------------------------------------

    def _ensure_service(self):
        if self._service is None:
            self.logger.info("Authenticating with Gmail API…")
            self._service = _build_gmail_service()
            self.logger.info("Gmail API ready.")

    def _fetch_unread_important(self) -> list[dict]:
        """Return list of message stubs (id, threadId) for unread+important emails."""
        try:
            result = (
                self._service.users()
                .messages()
                .list(
                    userId="me",
                    q="is:unread is:important",
                    maxResults=50,
                )
                .execute()
            )
            return result.get("messages", [])
        except HttpError as exc:
            self.logger.error("Gmail API list error: %s", exc)
            return []

    def _get_message(self, msg_id: str) -> dict | None:
        """Fetch full message payload."""
        try:
            return (
                self._service.users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute()
            )
        except HttpError as exc:
            self.logger.error("Failed to fetch message %s: %s", msg_id, exc)
            return None

    def _mark_as_read(self, msg_id: str) -> None:
        """Remove UNREAD label so the email won't be fetched again."""
        try:
            self._service.users().messages().modify(
                userId="me",
                id=msg_id,
                body={"removeLabelIds": ["UNREAD"]},
            ).execute()
        except HttpError as exc:
            self.logger.warning("Could not mark %s as read: %s", msg_id, exc)

    # ------------------------------------------------------------------
    # Header / body extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _get_header(headers: list[dict], name: str) -> str:
        for h in headers:
            if h["name"].lower() == name.lower():
                return h["value"]
        return ""

    @staticmethod
    def _extract_body(payload: dict) -> str:
        """Best-effort plain-text body extraction."""
        mime = payload.get("mimeType", "")

        if mime == "text/plain":
            data = payload.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

        if mime.startswith("multipart/"):
            for part in payload.get("parts", []):
                if part.get("mimeType") == "text/plain":
                    data = part.get("body", {}).get("data", "")
                    if data:
                        return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            # Fallback: first part regardless of type
            for part in payload.get("parts", []):
                text = GmailWatcher._extract_body(part)
                if text:
                    return text

        return "(No plain-text body)"

    # ------------------------------------------------------------------
    # Note creation
    # ------------------------------------------------------------------

    def _safe_filename(self, text: str) -> str:
        """Sanitise a string for use in a filename."""
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s]+", "_", text.strip())
        return text[:60] or "no_subject"

    def _write_note(self, msg: dict) -> None:
        """Create an Obsidian note in Needs_Action/ for the email."""
        headers = msg.get("payload", {}).get("headers", [])
        subject = self._get_header(headers, "Subject") or "(no subject)"
        sender  = self._get_header(headers, "From")    or "(unknown sender)"
        date_str = self._get_header(headers, "Date")   or ""
        snippet  = msg.get("snippet", "")
        msg_id   = msg["id"]

        body = self._extract_body(msg.get("payload", {}))
        # Truncate very long bodies in the note
        if len(body) > 2000:
            body = body[:2000] + "\n\n… *(truncated — open Gmail for full message)*"

        now = datetime.now(timezone.utc)
        slug = self._safe_filename(subject)
        note_name = f"EMAIL_{now.strftime('%Y%m%d_%H%M%S')}_{slug}.md"
        note_path = NEEDS_ACTION_DIR / note_name

        content = f"""\
---
type: email
source: gmail
gmail_id: {msg_id}
subject: "{subject}"
from: "{sender}"
email_date: "{date_str}"
detected_at: {now.strftime("%Y-%m-%d %H:%M:%S UTC")}
status: needs_action
labels: [email, important, unread]
---

# {subject}

**From:** {sender}
**Date:** {date_str}
**Gmail ID:** `{msg_id}`

## Snippet

> {snippet}

## Body

{body}

---

## Action Required

Review this email and decide:
- [ ] Reply
- [ ] Delegate
- [ ] Archive / close

---
*Auto-generated by GmailWatcher on {now.strftime("%Y-%m-%d %H:%M:%S UTC")}.*
"""
        try:
            note_path.write_text(content, encoding="utf-8")
            self.logger.info("Note created -> %s", note_name)
        except OSError as exc:
            self.logger.error("Failed to write note for %s: %s", msg_id, exc)

    # ------------------------------------------------------------------
    # Poll cycle
    # ------------------------------------------------------------------

    def _scan(self) -> None:
        """Single poll: fetch unread+important, create notes for new ones."""
        self._ensure_service()
        messages = self._fetch_unread_important()

        if not messages:
            self.logger.debug("No unread important emails found.")
            return

        new_count = 0
        for stub in messages:
            msg_id = stub["id"]
            if msg_id in self._seen_ids:
                self.logger.debug("Already processed: %s", msg_id)
                continue

            msg = self._get_message(msg_id)
            if msg is None:
                continue

            self._write_note(msg)
            self._mark_as_read(msg_id)
            self._save_seen_id(msg_id)
            new_count += 1

        if new_count:
            self.logger.info("Processed %d new email(s).", new_count)

    # ------------------------------------------------------------------
    # Run loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the polling loop. Runs until stopped (Ctrl+C or SIGTERM)."""
        self._running = True
        self.logger.info("GmailWatcher started. Press Ctrl+C to stop.")

        while self._running:
            self.logger.debug("--- Poll cycle ---")
            try:
                self._scan()
            except Exception as exc:  # noqa: BLE001
                self.logger.exception("Unexpected error during scan: %s", exc)
            self._sleep()

        self.logger.info("GmailWatcher stopped.")


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def _handle_signal(signum, frame):  # noqa: ANN001
    print("\n[gmail_watcher] Signal received, shutting down…")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    watcher = GmailWatcher()
    watcher.run()
