/**
 * email-mcp — MCP server for sending emails via Gmail API
 *
 * Exposes tool: send_email
 *   Inputs : to, subject, body (plain-text), cc? (optional)
 *   Auth   : OAuth2 credentials loaded from .env
 *
 * Protocol: Model Context Protocol (stdio transport)
 *
 * Usage:
 *   node index.js
 *
 * Required .env keys:
 *   GMAIL_CLIENT_ID
 *   GMAIL_CLIENT_SECRET
 *   GMAIL_REDIRECT_URI   (e.g. http://localhost)
 *   GMAIL_REFRESH_TOKEN
 *   GMAIL_FROM           (sender address, must match the authorised account)
 */

import "dotenv/config";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { google } from "googleapis";

// ---------------------------------------------------------------------------
// Gmail OAuth2 client
// ---------------------------------------------------------------------------

function buildGmailClient() {
  const { GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REDIRECT_URI, GMAIL_REFRESH_TOKEN } =
    process.env;

  const missing = ["GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REDIRECT_URI", "GMAIL_REFRESH_TOKEN"].filter(
    (k) => !process.env[k]
  );
  if (missing.length) {
    throw new Error(`Missing required env vars: ${missing.join(", ")}`);
  }

  const oauth2Client = new google.auth.OAuth2(
    GMAIL_CLIENT_ID,
    GMAIL_CLIENT_SECRET,
    GMAIL_REDIRECT_URI
  );
  oauth2Client.setCredentials({ refresh_token: GMAIL_REFRESH_TOKEN });
  return google.gmail({ version: "v1", auth: oauth2Client });
}

// ---------------------------------------------------------------------------
// Email helper — RFC 2822 → base64url
// ---------------------------------------------------------------------------

function buildRawMessage({ from, to, cc, subject, body }) {
  const lines = [
    `From: ${from}`,
    `To: ${to}`,
    ...(cc ? [`Cc: ${cc}`] : []),
    `Subject: ${subject}`,
    "MIME-Version: 1.0",
    "Content-Type: text/plain; charset=utf-8",
    "",
    body,
  ];
  const raw = lines.join("\r\n");
  // base64url encoding (Gmail API requirement)
  return Buffer.from(raw)
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

async function sendEmail({ to, subject, body, cc }) {
  const gmail = buildGmailClient();
  const from = process.env.GMAIL_FROM;
  if (!from) throw new Error("GMAIL_FROM env var is required");

  const raw = buildRawMessage({ from, to, cc, subject, body });

  const res = await gmail.users.messages.send({
    userId: "me",
    requestBody: { raw },
  });

  return {
    messageId: res.data.id,
    threadId: res.data.threadId,
    labelIds: res.data.labelIds ?? [],
  };
}

// ---------------------------------------------------------------------------
// Tool schema
// ---------------------------------------------------------------------------

const SEND_EMAIL_TOOL = {
  name: "send_email",
  description:
    "Send an email via Gmail API. Returns the Gmail message ID on success.",
  inputSchema: {
    type: "object",
    properties: {
      to: {
        type: "string",
        description: "Recipient email address (or comma-separated list).",
      },
      subject: {
        type: "string",
        description: "Email subject line.",
      },
      body: {
        type: "string",
        description: "Plain-text email body.",
      },
      cc: {
        type: "string",
        description: "Optional CC address (or comma-separated list).",
      },
    },
    required: ["to", "subject", "body"],
  },
};

// ---------------------------------------------------------------------------
// MCP Server
// ---------------------------------------------------------------------------

const server = new Server(
  { name: "email-mcp", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

// List available tools
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [SEND_EMAIL_TOOL],
}));

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  if (name !== "send_email") {
    return {
      content: [{ type: "text", text: `Unknown tool: ${name}` }],
      isError: true,
    };
  }

  const { to, subject, body, cc } = args ?? {};

  // Validate required fields
  if (!to || !subject || !body) {
    return {
      content: [
        {
          type: "text",
          text: "Missing required arguments: to, subject, body are all required.",
        },
      ],
      isError: true,
    };
  }

  try {
    const result = await sendEmail({ to, subject, body, cc });
    return {
      content: [
        {
          type: "text",
          text: `Email sent successfully.\nMessage ID : ${result.messageId}\nThread ID  : ${result.threadId}`,
        },
      ],
    };
  } catch (err) {
    return {
      content: [
        {
          type: "text",
          text: `Failed to send email: ${err.message}`,
        },
      ],
      isError: true,
    };
  }
});

// ---------------------------------------------------------------------------
// Start (stdio transport — required by Claude Code MCP)
// ---------------------------------------------------------------------------

const transport = new StdioServerTransport();
await server.connect(transport);
// Server is now running; logs to stderr so stdout stays clean for MCP protocol
console.error("[email-mcp] Server ready — listening on stdio.");
