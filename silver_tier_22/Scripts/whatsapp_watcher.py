"""
WhatsAppWatcher — Silver-tier WhatsApp Web monitor using Playwright.

Behavior:
  - Opens WhatsApp Web in a persistent browser context (avoids re-scanning QR each run).
  - Polls for new messages every POLL_INTERVAL seconds.
  - Filters messages for keywords: urgent, invoice, payment, order, pricing
  - Creates a WHATSAPP_<timestamp>.md in Needs_Action/ for each keyword match.
  - Logs all activity to Logs/WhatsAppWatcher.log

Usage:
    python Scripts/whatsapp_watcher.py

First run:
    A browser window will open — scan the WhatsApp Web QR code once.
    Subsequent runs reuse the saved session from ~/ai-secrets/whatsapp_session/.
"""

import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, sync_playwright

# Allow running from project root or from Scripts/ directly
_HERE = Path(__file__).parent
_VAULT_ROOT = _HERE.parent

sys.path.insert(0, str(_HERE))
from base_watcher import BaseWatcher  # noqa: E402


VAULT_ROOT = _VAULT_ROOT
NEEDS_ACTION_DIR = VAULT_ROOT / "Needs_Action"
LOG_DIR = VAULT_ROOT / "Logs"
SESSION_DIR = Path.home() / "ai-secrets" / "whatsapp_session"
POLL_INTERVAL = 30  # seconds

KEYWORDS: frozenset[str] = frozenset({"urgent", "invoice", "payment", "order", "pricing"})
WHATSAPP_WEB_URL = "https://web.whatsapp.com"


class WhatsAppWatcher(BaseWatcher):
    """
    Watches WhatsApp Web for messages containing trigger keywords.

    Uses Playwright with a persistent browser context so the WhatsApp session
    survives restarts (QR scan required only on first run).

    Keyword triggers: urgent, invoice, payment, order, pricing
    Session stored at: ~/ai-secrets/whatsapp_session/
    """

    def __init__(self) -> None:
        super().__init__(
            watch_dir=NEEDS_ACTION_DIR,
            interval=POLL_INTERVAL,
            log_dir=LOG_DIR,
        )
        NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)
        SESSION_DIR.mkdir(parents=True, exist_ok=True)

        self._pw = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._seen: set[str] = set()  # dedup key → message already processed

        self.logger.info("Vault root   : %s", VAULT_ROOT)
        self.logger.info("Destination  : %s", NEEDS_ACTION_DIR)
        self.logger.info("Session dir  : %s", SESSION_DIR)
        self.logger.info("Keywords     : %s", sorted(KEYWORDS))
        self.logger.info("Poll interval: %ds", POLL_INTERVAL)

    # ------------------------------------------------------------------
    # BaseWatcher — file hook (unused; browser-based watcher)
    # ------------------------------------------------------------------

    def process_file(self, file_path: Path) -> None:
        """Not used — WhatsAppWatcher is browser-based, not file-based."""

    # ------------------------------------------------------------------
    # Browser lifecycle
    # ------------------------------------------------------------------

    def _launch(self) -> None:
        """Start Playwright and open a persistent Chromium context."""
        self.logger.info("Launching Chromium (persistent context)…")
        self._pw = sync_playwright().start()
        self._context = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=False,  # WhatsApp Web requires a real viewport for QR login
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        self._page = (
            self._context.pages[0]
            if self._context.pages
            else self._context.new_page()
        )
        self.logger.info("Browser launched.")

    def _navigate(self) -> None:
        """Open WhatsApp Web and wait for the chat list panel."""
        self.logger.info("Navigating to %s…", WHATSAPP_WEB_URL)
        self._page.goto(WHATSAPP_WEB_URL, wait_until="domcontentloaded", timeout=60_000)
        try:
            self._page.wait_for_selector('[data-testid="chat-list"]', timeout=90_000)
            self.logger.info("WhatsApp Web ready (chat list visible).")
        except Exception:
            self.logger.warning(
                "Chat list not visible within timeout — "
                "QR scan may be required. Check the browser window."
            )

    def _close(self) -> None:
        """Gracefully close browser and Playwright."""
        try:
            if self._context:
                self._context.close()
            if self._pw:
                self._pw.stop()
        except Exception as exc:
            self.logger.debug("Error during browser close: %s", exc)

    # ------------------------------------------------------------------
    # Chat scraping
    # ------------------------------------------------------------------

    def _unread_chats(self) -> list[dict]:
        """
        Return list of {contact, preview, element} for chats with unread badges.
        """
        chats: list[dict] = []
        try:
            cells = self._page.query_selector_all(
                '[data-testid="chat-list"] [data-testid="cell-frame-container"]'
            )
            for cell in cells:
                if cell.query_selector('[data-testid="icon-unread-count"]') is None:
                    continue
                contact_el = cell.query_selector('[data-testid="cell-frame-title"]')
                preview_el = cell.query_selector(
                    '[data-testid="cell-frame-primary-detail"]'
                )
                chats.append(
                    {
                        "contact": contact_el.inner_text() if contact_el else "Unknown",
                        "preview": preview_el.inner_text() if preview_el else "",
                        "element": cell,
                    }
                )
        except Exception as exc:
            self.logger.error("Error reading chat list: %s", exc)
        return chats

    def _messages_in_open_chat(self) -> list[dict]:
        """
        After a chat is open, return the last 20 incoming messages as
        {text, timestamp} dicts.
        """
        messages: list[dict] = []
        try:
            self._page.wait_for_selector(
                '[data-testid="msg-container"]', timeout=10_000
            )
            containers = self._page.query_selector_all(
                '[data-testid="msg-container"]'
            )[-20:]
            for container in containers:
                # Skip outgoing messages (they have the "tail-out" CSS class)
                if container.query_selector(".tail-out") is not None:
                    continue
                text_el = container.query_selector('[data-testid="msg-text"]')
                time_el = container.query_selector('[data-testid="msg-meta"] span')
                text = text_el.inner_text() if text_el else ""
                ts = time_el.inner_text() if time_el else ""
                if text:
                    messages.append({"text": text, "timestamp": ts})
        except Exception as exc:
            self.logger.debug("Error reading messages: %s", exc)
        return messages

    # ------------------------------------------------------------------
    # Keyword matching + note creation
    # ------------------------------------------------------------------

    def _matched_keywords(self, text: str) -> list[str]:
        """Return sorted list of keywords found in text (case-insensitive)."""
        lower = text.lower()
        return sorted(kw for kw in KEYWORDS if kw in lower)

    def _dedup_key(self, contact: str, text: str) -> str:
        return f"{contact}::{text[:100]}"

    def _write_note(self, contact: str, text: str, matched: list[str]) -> None:
        """Write WHATSAPP_<timestamp>.md to Needs_Action/."""
        now = datetime.now(timezone.utc)
        slug = now.strftime("%Y%m%d_%H%M%S")
        note_name = f"WHATSAPP_{slug}.md"
        note_path = NEEDS_ACTION_DIR / note_name

        content = f"""\
---
source: whatsapp
contact: "{contact}"
detected_at: {now.strftime("%Y-%m-%d %H:%M:%S UTC")}
keywords: [{", ".join(matched)}]
status: needs_action
---

# WhatsApp Message — {contact}

| Field        | Value                                   |
|--------------|-----------------------------------------|
| Contact      | {contact}                               |
| Detected At  | {now.strftime("%Y-%m-%d %H:%M:%S UTC")} |
| Keywords     | {", ".join(f"`{kw}`" for kw in matched)} |
| Status       | needs_action                            |

## Message Content

> {text}

## Action Required

Review the message from **{contact}** — triggered by keyword(s): {", ".join(f"`{kw}`" for kw in matched)}.

- [ ] Reply
- [ ] Delegate
- [ ] Escalate
- [ ] Archive / close

---
*Auto-generated by WhatsAppWatcher on {now.strftime("%Y-%m-%d")}.*
"""
        try:
            note_path.write_text(content, encoding="utf-8")
            self.logger.info("Note created -> %s  (keywords: %s)", note_name, matched)
        except OSError as exc:
            self.logger.error("Failed to write note %s: %s", note_name, exc)

    # ------------------------------------------------------------------
    # Poll cycle
    # ------------------------------------------------------------------

    def _scan(self) -> None:
        """One poll cycle: check unread chats, read messages, filter keywords."""
        unread = self._unread_chats()
        if not unread:
            self.logger.debug("No unread chats.")
            return

        self.logger.info("Found %d unread chat(s).", len(unread))
        for chat in unread:
            contact = chat["contact"]
            chat["element"].click()

            for msg in self._messages_in_open_chat():
                key = self._dedup_key(contact, msg["text"])
                if key in self._seen:
                    continue
                self._seen.add(key)
                matched = self._matched_keywords(msg["text"])
                if matched:
                    self._write_note(contact, msg["text"], matched)

    # ------------------------------------------------------------------
    # Run loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Launch browser, navigate to WhatsApp Web, then poll indefinitely."""
        self._running = True
        self.logger.info("WhatsAppWatcher starting…")
        try:
            self._launch()
            self._navigate()
            self.logger.info(
                "Polling every %ds for keywords %s. Press Ctrl+C to stop.",
                self.interval,
                sorted(KEYWORDS),
            )
            while self._running:
                self.logger.debug("--- Poll cycle ---")
                self._scan()
                self._sleep()
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt — stopping.")
        finally:
            self._close()
            self.logger.info("WhatsAppWatcher stopped.")


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def _handle_signal(signum, frame):  # noqa: ANN001
    print("\n[whatsapp_watcher] Signal received, shutting down…")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    watcher = WhatsAppWatcher()
    watcher.run()
