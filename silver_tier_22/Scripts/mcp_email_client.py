"""
MCPEmailClient — thin Python client for the stdio-based MCP email server.

Protocol: newline-delimited JSON-RPC 2.0 (MCP stdio transport).
Handshake: initialize → notifications/initialized → tools/call → close.

Usage:
    from mcp_email_client import MCPEmailClient

    client = MCPEmailClient()
    result = client.send_email(
        to="user@example.com",
        subject="Hello",
        body="<p>Hi there</p>",
        attachment="/absolute/path/to/file.pdf",  # optional
    )
    print(result)  # {"messageId": "...", "success": True}
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)

# Resolve paths relative to this file
_HERE = Path(__file__).parent
_VAULT_ROOT = _HERE.parent
_SERVER_JS = _VAULT_ROOT / "mcp-email-server" / "dist" / "index.js"
_DEFAULT_CREDS = Path.home() / "ai-secrets" / "gmail_credentials.json"


class MCPEmailError(RuntimeError):
    """Raised when the MCP server returns an error or the process fails."""


class MCPEmailClient:
    """Spawn the MCP email server as a child process and call send_email."""

    def __init__(
        self,
        server_js: str | Path = _SERVER_JS,
        credentials_json: str | Path = _DEFAULT_CREDS,
    ) -> None:
        self.server_js = Path(server_js)
        self.credentials_json = Path(credentials_json)

        if not self.server_js.exists():
            raise FileNotFoundError(
                f"MCP server not built: {self.server_js}\n"
                "Run: cd mcp-email-server && npm run build"
            )
        if not self.credentials_json.exists():
            raise FileNotFoundError(
                f"Gmail credentials not found: {self.credentials_json}\n"
                "See .env.example for setup instructions."
            )

    # ── internal helpers ────────────────────────────────────────────────────

    def _build_env(self) -> dict:
        env = os.environ.copy()
        env["GMAIL_CREDENTIALS"] = str(self.credentials_json)
        return env

    @staticmethod
    def _write(proc: subprocess.Popen, msg: dict) -> None:
        line = json.dumps(msg) + "\n"
        proc.stdin.write(line.encode())
        proc.stdin.flush()
        log.debug("→ MCP: %s", json.dumps(msg)[:120])

    @staticmethod
    def _read(proc: subprocess.Popen) -> dict:
        raw = proc.stdout.readline()
        if not raw:
            stderr = proc.stderr.read().decode(errors="replace")
            raise MCPEmailError(f"MCP server closed stdout unexpectedly.\nstderr: {stderr}")
        msg = json.loads(raw.decode().strip())
        log.debug("← MCP: %s", json.dumps(msg)[:120])
        return msg

    # ── public API ──────────────────────────────────────────────────────────

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        attachment: str | None = None,
    ) -> dict:
        """
        Send an email via the MCP server.

        Returns a dict with keys:
          - success: bool
          - messageId: str (on success)
          - error: str (on failure)
        """
        proc = subprocess.Popen(
            ["node", str(self.server_js)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self._build_env(),
        )

        try:
            # ── 1. Initialize handshake ─────────────────────────────────
            self._write(proc, {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "approval-watcher", "version": "1.0"},
                },
            })
            init_resp = self._read(proc)
            if "error" in init_resp:
                raise MCPEmailError(f"Initialize failed: {init_resp['error']}")

            # ── 2. Initialized notification ─────────────────────────────
            self._write(proc, {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            })

            # ── 3. Call send_email tool ─────────────────────────────────
            args: dict = {"to": to, "subject": subject, "body": body}
            if attachment:
                args["attachment"] = attachment

            self._write(proc, {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "send_email", "arguments": args},
            })
            tool_resp = self._read(proc)

            # ── 4. Parse result ─────────────────────────────────────────
            if "error" in tool_resp:
                return {"success": False, "error": str(tool_resp["error"])}

            result = tool_resp.get("result", {})
            content = result.get("content", [])
            text = content[0].get("text", "") if content else ""

            if result.get("isError"):
                return {"success": False, "error": text}

            # Extract Message-ID from the success text
            message_id = ""
            for part in text.split("\n"):
                if part.startswith("Message-ID:"):
                    message_id = part.split(":", 1)[1].strip()

            return {"success": True, "messageId": message_id, "text": text}

        finally:
            proc.stdin.close()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


# ── CLI smoke test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.DEBUG)
    parser = argparse.ArgumentParser(description="Send a test email via MCP server")
    parser.add_argument("--to", required=True)
    parser.add_argument("--subject", default="MCP Test")
    parser.add_argument("--body", default="<p>Test from MCPEmailClient</p>")
    parser.add_argument("--attachment", default=None)
    args = parser.parse_args()

    client = MCPEmailClient()
    result = client.send_email(args.to, args.subject, args.body, args.attachment)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["success"] else 1)
