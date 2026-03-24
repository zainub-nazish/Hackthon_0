"""
LinkedInWatcher — Silver-tier LinkedIn monitor using Playwright.

Behavior:
  - Opens LinkedIn in a persistent browser context (login required only once).
  - Polls /notifications/ and /messaging/ every POLL_INTERVAL seconds.
  - Detects business opportunities: connection requests, messages, and
    notifications matching opportunity keywords.
  - Creates a LINKEDIN_<timestamp>.md in Needs_Action/ for each match.
  - Logs all activity to Logs/LinkedInWatcher.log

Usage:
    python Scripts/linkedin_watcher.py

First run:
    A browser window will open — log in to LinkedIn once.
    Subsequent runs reuse the saved session from ~/ai-secrets/linkedin_session/.

Business opportunity keywords:
    partnership, opportunity, collaboration, project, proposal, hire,
    contract, consulting, deal, interested, services, quote, offer
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
SESSION_DIR = Path.home() / "ai-secrets" / "linkedin_session"
POLL_INTERVAL = 60  # seconds — LinkedIn rate-limits aggressive polling

LINKEDIN_BASE_URL = "https://www.linkedin.com"
NOTIFICATIONS_URL = f"{LINKEDIN_BASE_URL}/notifications/"
MESSAGING_URL = f"{LINKEDIN_BASE_URL}/messaging/"

# Keywords that signal a business opportunity in a notification or message
OPPORTUNITY_KEYWORDS: frozenset[str] = frozenset({
    "partnership",
    "opportunity",
    "collaboration",
    "project",
    "proposal",
    "hire",
    "contract",
    "consulting",
    "deal",
    "interested",
    "services",
    "quote",
    "offer",
    "work together",
    "reach out",
})

# These notification types always get a note regardless of keywords
ALWAYS_CAPTURE_TYPES: frozenset[str] = frozenset({
    "connection request",
    "message request",
    "inmail",
})


class LinkedInWatcher(BaseWatcher):
    """
    Watches LinkedIn notifications and messages for business opportunities.

    Uses Playwright with a persistent browser context so the LinkedIn session
    survives restarts (manual login required only on first run).

    Monitors:
      - /notifications/ — new notifications from LinkedIn feed
      - /messaging/    — unread direct messages and InMail
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
        self._seen: set[str] = set()  # dedup: prevents duplicate notes per session

        self.logger.info("Vault root   : %s", VAULT_ROOT)
        self.logger.info("Destination  : %s", NEEDS_ACTION_DIR)
        self.logger.info("Session dir  : %s", SESSION_DIR)
        self.logger.info("Keywords     : %s", sorted(OPPORTUNITY_KEYWORDS))
        self.logger.info("Poll interval: %ds", POLL_INTERVAL)

    # ------------------------------------------------------------------
    # BaseWatcher — file hook (unused; browser-based watcher)
    # ------------------------------------------------------------------

    def process_file(self, file_path: Path) -> None:
        """Not used — LinkedInWatcher is browser-based, not file-based."""

    # ------------------------------------------------------------------
    # Browser lifecycle
    # ------------------------------------------------------------------

    def _launch(self) -> None:
        """Start Playwright and open a persistent Chromium context."""
        self.logger.info("Launching Chromium (persistent context)…")
        self._pw = sync_playwright().start()
        self._context = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=False,  # LinkedIn requires real viewport; also needed for login
            args=["--no-sandbox", "--disable-dev-shm-usage"],
            viewport={"width": 1280, "height": 800},
        )
        self._page = (
            self._context.pages[0]
            if self._context.pages
            else self._context.new_page()
        )
        self.logger.info("Browser launched.")

    def _ensure_logged_in(self) -> bool:
        """
        Navigate to LinkedIn home and verify we are logged in.
        Returns True if session is active, False if login is required.
        On first run the user must log in manually in the open browser window.
        """
        self.logger.info("Checking LinkedIn session…")
        self._page.goto(LINKEDIN_BASE_URL, wait_until="domcontentloaded", timeout=30_000)

        # Logged-in indicator: the global nav bar
        try:
            self._page.wait_for_selector("#global-nav", timeout=15_000)
            self.logger.info("LinkedIn session active.")
            return True
        except Exception:
            self.logger.warning(
                "LinkedIn session not active — please log in manually in the "
                "browser window. Waiting up to 120s for login…"
            )

        # Give the user time to log in
        try:
            self._page.wait_for_selector("#global-nav", timeout=120_000)
            self.logger.info("Login detected — proceeding.")
            return True
        except Exception:
            self.logger.error("Login timed out. Watcher will retry next cycle.")
            return False

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
    # Notifications scraping
    # ------------------------------------------------------------------

    def _scrape_notifications(self) -> list[dict]:
        """
        Navigate to /notifications/ and return a list of
        {id, text, type, actor} dicts for unread notification cards.
        """
        items: list[dict] = []
        try:
            self._page.goto(NOTIFICATIONS_URL, wait_until="domcontentloaded", timeout=30_000)
            # Wait for the notification list to render
            self._page.wait_for_selector(
                "section.nt-card-list, [data-finite-scroll-hotkey-item]",
                timeout=15_000,
            )
        except Exception as exc:
            self.logger.debug("Notifications page load issue: %s", exc)
            return items

        try:
            # LinkedIn notification cards — each is a <li> containing .nt-card
            cards = self._page.query_selector_all(
                "li[class*='nt-card-list__item'], li[data-finite-scroll-hotkey-item]"
            )
            for card in cards[:30]:  # cap at 30 most recent
                # Unread cards have an accent/unread indicator
                is_unread = card.query_selector(
                    "[class*='unread'], [class*='notification--new']"
                ) is not None

                text_el = card.query_selector(
                    ".nt-card__text, [class*='notification-card__text'], "
                    "[class*='artdeco-entity-lockup__title'], span[aria-label]"
                )
                text = text_el.inner_text().strip() if text_el else ""

                actor_el = card.query_selector(
                    "[class*='actor-name'], [class*='entity-lockup__title'], "
                    "[class*='notification-card__headline'] strong"
                )
                actor = actor_el.inner_text().strip() if actor_el else ""

                # Use card's aria-label or first meaningful text as ID
                card_id = (card.get_attribute("data-finite-scroll-hotkey-item") or
                           card.get_attribute("data-urn") or
                           text[:80])

                if text and card_id:
                    items.append({
                        "id": card_id,
                        "text": text,
                        "actor": actor,
                        "source": "notification",
                        "is_unread": is_unread,
                    })
        except Exception as exc:
            self.logger.error("Error parsing notification cards: %s", exc)

        return items

    # ------------------------------------------------------------------
    # Messaging scraping
    # ------------------------------------------------------------------

    def _scrape_messages(self) -> list[dict]:
        """
        Navigate to /messaging/ and return unread conversation stubs as
        {id, sender, preview, source} dicts.
        """
        items: list[dict] = []
        try:
            self._page.goto(MESSAGING_URL, wait_until="domcontentloaded", timeout=30_000)
            self._page.wait_for_selector(
                ".msg-conversations-container, .msg-conversation-listitem",
                timeout=15_000,
            )
        except Exception as exc:
            self.logger.debug("Messaging page load issue: %s", exc)
            return items

        try:
            conversations = self._page.query_selector_all(
                ".msg-conversation-listitem, li[class*='conversation-list-item']"
            )
            for conv in conversations[:20]:
                # Unread conversations have an unread badge or bold styling
                badge = conv.query_selector(
                    ".msg-conversation-listitem__unread-count, "
                    "[class*='unread-count'], [class*='notification-badge']"
                )
                if badge is None:
                    continue  # skip read conversations

                sender_el = conv.query_selector(
                    ".msg-conversation-listitem__participant-names, "
                    "[class*='participant-name'], h3"
                )
                preview_el = conv.query_selector(
                    ".msg-conversation-listitem__message-snippet, "
                    "[class*='message-snippet'], p"
                )

                sender = sender_el.inner_text().strip() if sender_el else "Unknown"
                preview = preview_el.inner_text().strip() if preview_el else ""
                conv_id = conv.get_attribute("data-control-id") or f"{sender}:{preview[:40]}"

                if sender or preview:
                    items.append({
                        "id": conv_id,
                        "sender": sender,
                        "preview": preview,
                        "source": "message",
                        "is_unread": True,
                    })
        except Exception as exc:
            self.logger.error("Error parsing message conversations: %s", exc)

        return items

    # ------------------------------------------------------------------
    # Opportunity detection + note creation
    # ------------------------------------------------------------------

    def _is_business_opportunity(self, text: str) -> tuple[bool, list[str]]:
        """
        Check if text contains opportunity keywords or always-capture types.
        Returns (is_opportunity, matched_keywords).
        """
        lower = text.lower()
        matched = sorted(kw for kw in OPPORTUNITY_KEYWORDS if kw in lower)
        is_capture = any(t in lower for t in ALWAYS_CAPTURE_TYPES)
        return (bool(matched) or is_capture), matched

    def _write_note(self, item: dict, matched_keywords: list[str]) -> None:
        """Write LINKEDIN_<timestamp>.md to Needs_Action/."""
        now = datetime.now(timezone.utc)
        slug = now.strftime("%Y%m%d_%H%M%S")
        note_name = f"LINKEDIN_{slug}.md"
        note_path = NEEDS_ACTION_DIR / note_name

        source = item.get("source", "linkedin")
        actor = item.get("actor") or item.get("sender", "Unknown")
        text = item.get("text") or item.get("preview", "")
        keywords_str = ", ".join(f"`{kw}`" for kw in matched_keywords) if matched_keywords else "*(connection/message request)*"

        content = f"""\
---
source: linkedin
type: {source}
actor: "{actor}"
detected_at: {now.strftime("%Y-%m-%d %H:%M:%S UTC")}
keywords: [{", ".join(matched_keywords)}]
status: needs_action
---

# LinkedIn {source.title()} — {actor}

| Field        | Value                                   |
|--------------|-----------------------------------------|
| Source       | {source.title()}                        |
| Actor        | {actor}                                 |
| Detected At  | {now.strftime("%Y-%m-%d %H:%M:%S UTC")} |
| Keywords     | {keywords_str}                          |
| Status       | needs_action                            |

## Content

> {text}

## Business Opportunity Assessment

This {source} was flagged as a potential business opportunity.
Keywords matched: {keywords_str}

## Action Required

- [ ] Review the full {source} on LinkedIn
- [ ] Assess fit: is this a genuine business opportunity?
- [ ] Reply / Accept / Decline
- [ ] If promising — create a follow-up plan in `Plans/`
- [ ] Move this note to `Done/` when resolved

---
*Auto-generated by LinkedInWatcher on {now.strftime("%Y-%m-%d")}.*
"""
        try:
            note_path.write_text(content, encoding="utf-8")
            self.logger.info(
                "Note created -> %s  (source: %s, keywords: %s)",
                note_name, source, matched_keywords or "connection/message",
            )
        except OSError as exc:
            self.logger.error("Failed to write note %s: %s", note_name, exc)

    # ------------------------------------------------------------------
    # Poll cycle
    # ------------------------------------------------------------------

    def _process_items(self, items: list[dict]) -> None:
        """Evaluate each scraped item; create a note for any opportunity."""
        for item in items:
            item_id = item.get("id", "")
            if item_id in self._seen:
                self.logger.debug("Already seen: %s", item_id[:60])
                continue
            self._seen.add(item_id)

            text = item.get("text") or item.get("preview", "")
            is_opp, matched = self._is_business_opportunity(text)

            # Always capture unread messages regardless of keywords
            if item.get("source") == "message" and item.get("is_unread"):
                is_opp = True

            if is_opp:
                self._write_note(item, matched)

    def _scan(self) -> None:
        """One poll cycle: scrape notifications then messages."""
        notifications = self._scrape_notifications()
        self.logger.debug("Scraped %d notification(s).", len(notifications))
        self._process_items(notifications)

        messages = self._scrape_messages()
        self.logger.debug("Scraped %d unread message(s).", len(messages))
        self._process_items(messages)

    # ------------------------------------------------------------------
    # Run loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Launch browser, verify login, then poll indefinitely."""
        self._running = True
        self.logger.info("LinkedInWatcher starting…")
        try:
            self._launch()
            if not self._ensure_logged_in():
                self.logger.error("Cannot proceed without LinkedIn login. Exiting.")
                return

            self.logger.info(
                "Polling every %ds. Monitoring notifications + messages. "
                "Press Ctrl+C to stop.",
                self.interval,
            )
            while self._running:
                self.logger.debug("--- Poll cycle ---")
                try:
                    self._scan()
                except Exception as exc:  # noqa: BLE001
                    self.logger.exception("Unexpected scan error: %s", exc)
                self._sleep()
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt — stopping.")
        finally:
            self._close()
            self.logger.info("LinkedInWatcher stopped.")


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def _handle_signal(signum, frame):  # noqa: ANN001
    print("\n[linkedin_watcher] Signal received, shutting down…")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    watcher = LinkedInWatcher()
    watcher.run()
