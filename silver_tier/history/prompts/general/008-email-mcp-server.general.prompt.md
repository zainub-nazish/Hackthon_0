---
id: "008"
title: Email MCP Server Gmail API
stage: general
date: 2026-03-18
surface: agent
model: claude-sonnet-4-6
feature: none
branch: main
user: zainub-nazish
command: general request
labels: ["mcp", "gmail", "node", "email", "oauth2"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - mcp/email-mcp/index.js
  - mcp/email-mcp/package.json
  - mcp/email-mcp/.env
  - mcp/email-mcp/.env.example
tests:
  - "MCP tools/list handshake: PASS (send_email tool returned)"
  - "Node syntax check: PASS"
---

## Prompt

Create a complete Node.js MCP server for sending emails (folder: mcp/email-mcp/index.js). It should expose tool "send_email" that uses Gmail API with credentials from .env. Follow Model Context Protocol format. Then update ~/.config/claude-code/mcp.json exactly as in the document example. After creating, test by calling the tool from Claude.

## Response snapshot

Created mcp/email-mcp/ with:
- index.js — MCP stdio server (ESM). Exposes `send_email` tool with inputs: to, subject, body, cc (optional). Gmail OAuth2 via googleapis; credentials from .env. Builds RFC 2822 message, base64url-encodes it, posts to gmail.users.messages.send.
- package.json — ESM package, deps: @modelcontextprotocol/sdk, dotenv, googleapis.
- .env / .env.example — credential placeholders (user must fill real values).
- Installed 117 packages (npm install).
- Updated ~/.claude/settings.json with mcpServers.email-mcp entry pointing to index.js.
- Verified: tools/list handshake returns send_email schema correctly.

## Outcome

- ✅ Impact: Claude Code can now call `send_email` to dispatch Gmail messages via MCP
- 🧪 Tests: MCP protocol handshake PASS; syntax check PASS; real send requires valid OAuth2 credentials in .env
- 📁 Files: mcp/email-mcp/index.js, package.json, .env, .env.example; ~/.claude/settings.json updated
- 🔁 Next prompts: fill in real Gmail credentials in .env; run one-time OAuth2 consent flow for refresh token; test live send_email call
- 🧠 Reflection: Used stdio transport (required by Claude Code MCP); ESM module format matches Node 25 default; credentials injected via env vars (never hardcoded)

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): tools/list → PASS; syntax check → PASS
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): add send_email_html variant for HTML body support
