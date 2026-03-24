"""
Orchestrator — Silver-tier AI Employee Vault

Starts all watchers concurrently in daemon threads:
  - FileSystemWatcher  : Inbox → Needs_Action (file copy + metadata)
  - WhatsAppWatcher    : WhatsApp Web keyword monitor (Playwright)
  - LinkedInWatcher    : Needs_Action LINKEDIN_ file metadata stub

Usage:
    python main.py [--watchers fs,wa,li]

    --watchers  Comma-separated list of watchers to start (default: all).
                  fs = FileSystemWatcher
                  wa = WhatsAppWatcher
                  li = LinkedInWatcher

Press Ctrl+C to stop all watchers.
"""

import argparse
import signal
import sys
import threading
from pathlib import Path

# Ensure watchers/ is on sys.path
_WATCHERS_DIR = Path(__file__).parent / "watchers"
sys.path.insert(0, str(_WATCHERS_DIR))

from filesystem_watcher import FileSystemWatcher   # noqa: E402
from linkedin_watcher import LinkedInWatcher       # noqa: E402
from whatsapp_watcher import WhatsAppWatcher       # noqa: E402

WATCHER_MAP = {
    "fs": FileSystemWatcher,
    "wa": WhatsAppWatcher,
    "li": LinkedInWatcher,
}


def _make_daemon_thread(watcher_instance) -> threading.Thread:
    """Wrap a watcher's run() in a daemon thread."""
    t = threading.Thread(
        target=watcher_instance.run,
        name=type(watcher_instance).__name__,
        daemon=True,
    )
    return t


def main(watcher_keys: list[str]) -> None:
    watchers = []
    threads: list[threading.Thread] = []

    print(f"[orchestrator] Starting watchers: {', '.join(watcher_keys)}")

    for key in watcher_keys:
        cls = WATCHER_MAP[key]
        instance = cls()
        watchers.append(instance)
        t = _make_daemon_thread(instance)
        threads.append(t)
        t.start()
        print(f"[orchestrator] {type(instance).__name__} started (thread: {t.name})")

    def _shutdown(signum, frame):  # noqa: ANN001
        print("\n[orchestrator] Shutdown signal — stopping all watchers…")
        for w in watchers:
            w.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    print("[orchestrator] All watchers running. Press Ctrl+C to stop.")

    # Keep main thread alive while daemon threads run
    for t in threads:
        t.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Employee Vault Orchestrator")
    parser.add_argument(
        "--watchers",
        default="fs,li",  # WhatsApp excluded by default (needs browser/QR)
        help=(
            "Comma-separated watcher IDs to start: "
            "fs=FileSystem, wa=WhatsApp, li=LinkedIn  (default: fs,li)"
        ),
    )
    args = parser.parse_args()

    keys = [k.strip() for k in args.watchers.split(",") if k.strip()]
    unknown = [k for k in keys if k not in WATCHER_MAP]
    if unknown:
        print(f"[orchestrator] Unknown watcher(s): {unknown}. Valid: {list(WATCHER_MAP)}")
        sys.exit(1)

    main(keys)
