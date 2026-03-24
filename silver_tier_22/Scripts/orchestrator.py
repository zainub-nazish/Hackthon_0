"""
Orchestrator — Silver Tier process manager and cron scheduler.

Two modes:
  standalone   Start and supervise all watchers in-process (dev / no pm2).
  cron-only    Skip watchers; run only the cron scheduler loop (use when pm2
               already manages the individual watcher processes).

Usage:
    python Scripts/orchestrator.py                   # standalone (all watchers + cron)
    python Scripts/orchestrator.py --mode cron-only  # cron jobs only
    python Scripts/orchestrator.py --list            # print process registry and exit
    python Scripts/orchestrator.py --generate-pm2    # print ecosystem.config.js and exit

How it works
────────────
ProcessManager
  • Spawns each watcher as a child subprocess.
  • Health-checks every HEALTH_INTERVAL seconds.
  • Restarts crashed processes with exponential backoff (cap 5 min).
  • Propagates SIGINT/SIGTERM → graceful shutdown of all children.

CronScheduler
  • Evaluated every 60 s against the CRON_JOBS table.
  • Each job fires at most once per matching minute.
  • Jobs run in a daemon thread so they do not block the main loop.

Adding a new watcher
────────────────────
Append an entry to WATCHER_REGISTRY below.  Fields:
  name        Unique identifier (used in logs and --list output).
  cmd         Command list passed to subprocess.Popen.
  restart     Whether to auto-restart on non-zero exit (default True).
  backoff     Initial restart delay in seconds (doubles on each failure, cap 300).
  enabled     Set False to skip without removing the entry.

Adding a cron job
─────────────────
Append an entry to CRON_JOBS below.  Fields:
  name        Unique identifier.
  hour, min   UTC time to fire (24-h clock).
  days        List of weekday names to fire on, e.g. ["mon","tue","wed","thu","fri"].
              Use ["*"] for every day.
  fn          Callable (no args) executed in a daemon thread.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import textwrap
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

# ── paths ────────────────────────────────────────────────────────────────────
_HERE       = Path(__file__).parent
_VAULT_ROOT = _HERE.parent
_LOGS_DIR   = _VAULT_ROOT / "Logs"
_LOGS_DIR.mkdir(exist_ok=True)

DASHBOARD_MD  = _VAULT_ROOT / "Dashboard.md"
ACTIVITY_LOG  = _LOGS_DIR / "ActivityLog.md"

# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(_LOGS_DIR / "Orchestrator.log"), encoding="utf-8"),
    ],
)
log = logging.getLogger("orchestrator")

# ── watcher registry ──────────────────────────────────────────────────────────
#
# Edit this table to add, remove, or disable watchers.
# All paths are relative to the vault root; the orchestrator resolves them.
#
WATCHER_REGISTRY: list[dict] = [
    {
        "name":    "filesystem-watcher",
        "cmd":     [sys.executable, str(_VAULT_ROOT / "watchers" / "filesystem_watcher.py")],
        "restart": True,
        "backoff": 5,
        "enabled": True,
    },
    {
        "name":    "gmail-watcher",
        "cmd":     [sys.executable, str(_HERE / "gmail_watcher.py")],
        "restart": True,
        "backoff": 10,
        "enabled": True,
    },
    {
        "name":    "linkedin-watcher",
        "cmd":     [sys.executable, str(_HERE / "linkedin_watcher.py")],
        "restart": True,
        "backoff": 15,
        "enabled": True,
    },
    {
        "name":    "whatsapp-watcher",
        "cmd":     [sys.executable, str(_HERE / "whatsapp_watcher.py")],
        "restart": True,
        "backoff": 15,
        "enabled": True,
    },
    {
        "name":    "approval-watcher",
        "cmd":     [sys.executable, str(_HERE / "approval_watcher.py"), "--poll", "30"],
        "restart": True,
        "backoff": 5,
        "enabled": True,
    },
]


# ── cron job implementations ──────────────────────────────────────────────────

def job_daily_briefing() -> None:
    """
    Daily 8 AM briefing — summarises pending work and sends an email digest.

    Reads:  Needs_Action/, Pending_Approval/, Plans/
    Sends:  Email via MCP server to BRIEFING_RECIPIENT (env var).

    To enable email delivery set BRIEFING_RECIPIENT in ~/ai-secrets/.env
    or pass it as an environment variable when starting the orchestrator.
    """
    log.info("[CRON] daily_briefing — starting")

    needs_action     = sorted((_VAULT_ROOT / "Needs_Action").glob("*.md"))
    pending_approval = sorted((_VAULT_ROOT / "Pending_Approval").glob("APPROVAL_*.md"))
    plans            = sorted((_VAULT_ROOT / "Plans").glob("PLAN_*.md"))

    date_str = datetime.now(timezone.utc).strftime("%A, %d %B %Y")

    lines: list[str] = [
        f"<h2>Good morning — Daily Briefing for {date_str}</h2>",
        "",
        f"<h3>Needs Action ({len(needs_action)} item{'s' if len(needs_action) != 1 else ''})</h3>",
    ]
    if needs_action:
        lines.append("<ul>")
        for f in needs_action:
            lines.append(f"  <li>{f.name}</li>")
        lines.append("</ul>")
    else:
        lines.append("<p>✅ Nothing pending in Needs_Action.</p>")

    lines += [
        "",
        f"<h3>Pending Approvals ({len(pending_approval)})</h3>",
    ]
    if pending_approval:
        lines.append("<ul>")
        for f in pending_approval:
            lines.append(f"  <li>{f.name}</li>")
        lines.append("</ul>")
    else:
        lines.append("<p>✅ No approvals waiting.</p>")

    lines += [
        "",
        f"<h3>Active Plans ({len(plans)})</h3>",
    ]
    if plans:
        lines.append("<ul>")
        for f in plans:
            lines.append(f"  <li>{f.stem}</li>")
        lines.append("</ul>")
    else:
        lines.append("<p>No plans found.</p>")

    lines += [
        "",
        "<hr>",
        "<small>Sent by Silver Tier Orchestrator — AI Employee Vault</small>",
    ]

    html_body = "\n".join(lines)
    subject   = f"[AI Employee] Daily Briefing — {date_str}"
    recipient = os.environ.get("BRIEFING_RECIPIENT", "")

    if not recipient:
        log.warning(
            "[CRON] daily_briefing — BRIEFING_RECIPIENT not set. "
            "Set it in ~/ai-secrets/.env to receive email digests."
        )
        _log_activity(f"CRON | daily_briefing | skipped (no BRIEFING_RECIPIENT)")
        return

    # Send via MCP email client
    try:
        sys.path.insert(0, str(_HERE))
        from mcp_email_client import MCPEmailClient  # noqa: PLC0415

        client = MCPEmailClient()
        result = client.send_email(to=recipient, subject=subject, body=html_body)
        if result["success"]:
            log.info("[CRON] daily_briefing — email sent to %s (id=%s)", recipient, result.get("messageId"))
            _log_activity(f"CRON | daily_briefing | email sent to {recipient}")
        else:
            log.error("[CRON] daily_briefing — MCP error: %s", result.get("error"))
    except Exception as exc:
        log.exception("[CRON] daily_briefing — unexpected error: %s", exc)


def _log_activity(line: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    try:
        with ACTIVITY_LOG.open("a", encoding="utf-8") as f:
            f.write(f"[{ts}] {line}\n")
    except OSError:
        pass


# ── cron job table ────────────────────────────────────────────────────────────
#
# hour, min  : UTC time (24-h).  Both are integers.
# days       : list of lowercase weekday names, or ["*"] for every day.
# fn         : callable with no arguments — runs in a daemon thread.
#
CRON_JOBS: list[dict] = [
    {
        "name": "daily_briefing",
        "hour": 8,
        "min":  0,
        "days": ["mon", "tue", "wed", "thu", "fri"],   # weekdays only
        "fn":   job_daily_briefing,
    },
    # ── add more jobs here ─────────────────────────────────────────────────
    # {
    #     "name": "weekly_report",
    #     "hour": 17,
    #     "min":  0,
    #     "days": ["fri"],
    #     "fn":   job_weekly_report,
    # },
]


# ── CronScheduler ─────────────────────────────────────────────────────────────

class CronScheduler:
    """Simple minute-resolution cron scheduler. Thread-safe, no external deps."""

    _DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

    def __init__(self, jobs: list[dict]) -> None:
        self._jobs     = jobs
        self._fired:   set[str] = set()   # "name:YYYY-MM-DD HH:MM" — dedup per minute
        self._stop_evt = threading.Event()

    def _should_fire(self, job: dict, now: datetime) -> bool:
        day_name = self._DAYS[now.weekday()]
        days     = job.get("days", ["*"])
        if "*" not in days and day_name not in days:
            return False
        if now.hour != job["hour"] or now.minute != job["min"]:
            return False
        key = f"{job['name']}:{now.strftime('%Y-%m-%d %H:%M')}"
        if key in self._fired:
            return False
        self._fired.add(key)
        # Prune old keys (keep only last 10) to avoid unbounded growth
        if len(self._fired) > 100:
            self._fired = set(list(self._fired)[-50:])
        return True

    def tick(self) -> None:
        """Call once per minute to check and fire due jobs."""
        now = datetime.now(timezone.utc)
        for job in self._jobs:
            if self._should_fire(job, now):
                log.info("[CRON] Firing job: %s", job["name"])
                t = threading.Thread(target=job["fn"], name=f"cron-{job['name']}", daemon=True)
                t.start()

    def run(self, stop_event: threading.Event) -> None:
        """Block-run the scheduler until stop_event is set."""
        log.info("CronScheduler started with %d job(s).", len(self._jobs))
        while not stop_event.is_set():
            self.tick()
            stop_event.wait(60)
        log.info("CronScheduler stopped.")


# ── ProcessManager ────────────────────────────────────────────────────────────

class ManagedProcess:
    MAX_BACKOFF = 300  # seconds

    def __init__(self, spec: dict) -> None:
        self.name     = spec["name"]
        self.cmd      = spec["cmd"]
        self.restart  = spec.get("restart", True)
        self.backoff  = spec.get("backoff", 5)
        self._backoff_cur = self.backoff
        self._proc: subprocess.Popen | None = None
        self._restarts = 0
        self._last_exit: int | None = None

    # ── lifecycle ─────────────────────────────────────────────────────────

    def start(self) -> None:
        log.info("[%s] Starting: %s", self.name, " ".join(str(c) for c in self.cmd))
        self._proc = subprocess.Popen(
            self.cmd,
            stdout=open(str(_LOGS_DIR / f"{self.name}.stdout.log"), "a"),
            stderr=open(str(_LOGS_DIR / f"{self.name}.stderr.log"), "a"),
        )
        log.info("[%s] PID %d", self.name, self._proc.pid)

    def stop(self, timeout: int = 10) -> None:
        if self._proc and self._proc.poll() is None:
            log.info("[%s] Sending SIGTERM (PID %d)", self.name, self._proc.pid)
            self._proc.terminate()
            try:
                self._proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                log.warning("[%s] Force-killing after %ds", self.name, timeout)
                self._proc.kill()
                self._proc.wait()

    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    # ── health check / restart ────────────────────────────────────────────

    def check(self) -> None:
        """Called periodically. Restart the process if it has exited."""
        if self.is_alive():
            self._backoff_cur = self.backoff   # reset backoff on sustained health
            return

        exit_code = self._proc.poll() if self._proc else None
        self._last_exit = exit_code

        if not self.restart:
            log.info("[%s] Exited (code %s) — restart disabled.", self.name, exit_code)
            return

        self._restarts += 1
        log.warning(
            "[%s] Exited (code %s) — restarting in %ds (restart #%d)",
            self.name, exit_code, self._backoff_cur, self._restarts,
        )
        time.sleep(self._backoff_cur)
        self._backoff_cur = min(self._backoff_cur * 2, self.MAX_BACKOFF)
        self.start()

    # ── status dict ──────────────────────────────────────────────────────

    def status(self) -> dict:
        return {
            "name":      self.name,
            "pid":       self._proc.pid if self._proc else None,
            "alive":     self.is_alive(),
            "restarts":  self._restarts,
            "last_exit": self._last_exit,
        }


class ProcessManager:
    HEALTH_INTERVAL = 10  # seconds between health checks

    def __init__(self, registry: list[dict]) -> None:
        self._procs: list[ManagedProcess] = [
            ManagedProcess(spec)
            for spec in registry
            if spec.get("enabled", True)
        ]
        self._stop_evt = threading.Event()

    def start_all(self) -> None:
        for p in self._procs:
            p.start()

    def stop_all(self) -> None:
        log.info("Stopping all managed processes…")
        for p in self._procs:
            p.stop()
        log.info("All processes stopped.")

    def run(self, stop_event: threading.Event) -> None:
        log.info("ProcessManager supervising %d process(es).", len(self._procs))
        self.start_all()
        while not stop_event.is_set():
            for p in self._procs:
                p.check()
            stop_event.wait(self.HEALTH_INTERVAL)
        self.stop_all()

    def print_status(self) -> None:
        print(f"\n{'NAME':<25} {'PID':>7} {'ALIVE':<8} {'RESTARTS':>9} {'LAST_EXIT':>10}")
        print("─" * 65)
        for p in self._procs:
            s = p.status()
            alive = "✓" if s["alive"] else "✗"
            print(
                f"{s['name']:<25} {str(s['pid'] or '—'):>7} {alive:<8} "
                f"{s['restarts']:>9} {str(s['last_exit'] or '—'):>10}"
            )
        print()


# ── pm2 config generator ──────────────────────────────────────────────────────

def generate_pm2_config() -> str:
    """Return a ready-to-use ecosystem.config.js content string."""
    apps = []
    for spec in WATCHER_REGISTRY:
        if not spec.get("enabled", True):
            continue
        cmd  = spec["cmd"]
        name = spec["name"]
        # cmd[0] is the interpreter, cmd[1] is the script, rest are args
        interpreter = cmd[0]
        script      = cmd[1] if len(cmd) > 1 else ""
        args        = " ".join(cmd[2:]) if len(cmd) > 2 else ""
        app: dict = {
            "name":          name,
            "script":        script,
            "interpreter":   interpreter,
            "restart_delay": spec.get("backoff", 5) * 1000,
            "max_restarts":  20,
            "watch":         False,
            "autorestart":   spec.get("restart", True),
        }
        if args:
            app["args"] = args
        apps.append(app)

    # Add orchestrator itself in cron-only mode
    apps.append({
        "name":        "orchestrator-cron",
        "script":      str(_HERE / "orchestrator.py"),
        "interpreter": sys.executable,
        "args":        "--mode cron-only",
        "watch":       False,
        "autorestart": True,
        "max_restarts": 20,
    })

    lines = ["module.exports = {", "  apps: ["]
    for i, app in enumerate(apps):
        comma = "," if i < len(apps) - 1 else ""
        lines.append("    {")
        for k, v in app.items():
            if isinstance(v, bool):
                lines.append(f"      {k}: {'true' if v else 'false'},")
            elif isinstance(v, int):
                lines.append(f"      {k}: {v},")
            else:
                lines.append(f"      {k}: {json.dumps(v)},")
        lines.append(f"    }}{comma}")
    lines += ["  ]", "};"]
    return "\n".join(lines)


# ── Orchestrator ──────────────────────────────────────────────────────────────

class Orchestrator:
    def __init__(self, mode: str = "standalone") -> None:
        self.mode      = mode
        self._stop_evt = threading.Event()
        self._pm       = ProcessManager(WATCHER_REGISTRY) if mode == "standalone" else None
        self._cron     = CronScheduler(CRON_JOBS)

        signal.signal(signal.SIGINT,  self._handle_stop)
        signal.signal(signal.SIGTERM, self._handle_stop)

    def _handle_stop(self, *_) -> None:
        log.info("Shutdown signal received.")
        self._stop_evt.set()

    def run(self) -> None:
        log.info("Orchestrator starting | mode=%s", self.mode)

        threads: list[threading.Thread] = []

        # Cron thread (always)
        cron_thread = threading.Thread(
            target=self._cron.run,
            args=(self._stop_evt,),
            name="cron",
            daemon=True,
        )
        threads.append(cron_thread)
        cron_thread.start()

        if self.mode == "standalone" and self._pm:
            # Process manager runs in its own thread
            pm_thread = threading.Thread(
                target=self._pm.run,
                args=(self._stop_evt,),
                name="process-manager",
                daemon=True,
            )
            threads.append(pm_thread)
            pm_thread.start()

        log.info("Orchestrator ready. Press Ctrl+C to stop.")

        # Main thread waits for stop signal
        self._stop_evt.wait()

        # Give threads a moment to finish
        for t in threads:
            t.join(timeout=15)

        log.info("Orchestrator shut down cleanly.")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Silver Tier Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Modes:
              standalone    Start all watchers + cron scheduler (default)
              cron-only     Run cron scheduler only (pair with pm2 for watchers)

            Examples:
              python Scripts/orchestrator.py
              python Scripts/orchestrator.py --mode cron-only
              python Scripts/orchestrator.py --list
              python Scripts/orchestrator.py --generate-pm2 > ecosystem.config.js
        """),
    )
    parser.add_argument(
        "--mode",
        choices=["standalone", "cron-only"],
        default="standalone",
        help="Run mode (default: standalone)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print registered watchers and cron jobs, then exit",
    )
    parser.add_argument(
        "--generate-pm2",
        action="store_true",
        help="Print an ecosystem.config.js for pm2, then exit",
    )
    args = parser.parse_args()

    if args.list:
        print("\nWatcher Registry")
        print("-" * 50)
        for spec in WATCHER_REGISTRY:
            enabled = "[x]" if spec.get("enabled", True) else "[ ]"
            print(f"  {enabled} {spec['name']}")
            print(f"        cmd: {' '.join(str(c) for c in spec['cmd'])}")
        print("\nCron Jobs")
        print("-" * 50)
        for job in CRON_JOBS:
            days = ", ".join(job["days"])
            print(f"  {job['name']:<25}  {job['hour']:02d}:{job['min']:02d} UTC  [{days}]")
        print()
        return

    if args.generate_pm2:
        print(generate_pm2_config())
        return

    Orchestrator(mode=args.mode).run()


if __name__ == "__main__":
    main()
