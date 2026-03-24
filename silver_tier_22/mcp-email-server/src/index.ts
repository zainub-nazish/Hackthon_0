import dotenv from "dotenv";
import path from "path";
import os from "os";
import fs from "fs";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio";
import { z } from "zod";
import nodemailer, { SendMailOptions } from "nodemailer";
import { google } from "googleapis";

// ── Credential resolution (priority order) ──────────────────────────────────
// 1. GMAIL_CREDENTIALS env var → path to a JSON file
// 2. Individual env vars (GMAIL_CLIENT_ID / SECRET / REFRESH_TOKEN / USER)
// 3. Fallback: dotenv from ~/ai-secrets/.env then re-check individual vars

interface GmailCreds {
  client_id: string;
  client_secret: string;
  refresh_token: string;
  user: string;
}

function loadCreds(): GmailCreds {
  // 1. JSON credentials file
  const credsPath = process.env.GMAIL_CREDENTIALS;
  if (credsPath) {
    if (!fs.existsSync(credsPath)) {
      console.error(`GMAIL_CREDENTIALS path not found: ${credsPath}`);
      process.exit(1);
    }
    const raw = JSON.parse(fs.readFileSync(credsPath, "utf8"));
    // Support both flat { client_id, ... } and Google's nested { installed: { ... } }
    const flat = raw.installed ?? raw.web ?? raw;
    const creds: GmailCreds = {
      client_id: flat.client_id,
      client_secret: flat.client_secret,
      refresh_token: flat.refresh_token,
      user: flat.user ?? flat.email ?? process.env.GMAIL_USER ?? "",
    };
    if (!creds.client_id || !creds.client_secret || !creds.refresh_token || !creds.user) {
      console.error(
        `gmail_credentials.json must contain: client_id, client_secret, refresh_token, user\nFile: ${credsPath}`
      );
      process.exit(1);
    }
    return creds;
  }

  // 2 & 3. Individual env vars, with dotenv fallback
  dotenv.config({ path: path.join(os.homedir(), "ai-secrets", ".env") });

  const { GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN, GMAIL_USER } = process.env;
  if (!GMAIL_CLIENT_ID || !GMAIL_CLIENT_SECRET || !GMAIL_REFRESH_TOKEN || !GMAIL_USER) {
    console.error(
      "Provide credentials via one of:\n" +
        "  • GMAIL_CREDENTIALS=/path/to/gmail_credentials.json\n" +
        "  • GMAIL_CLIENT_ID + GMAIL_CLIENT_SECRET + GMAIL_REFRESH_TOKEN + GMAIL_USER env vars\n" +
        "  • ~/ai-secrets/.env file with the above vars"
    );
    process.exit(1);
  }

  return {
    client_id: GMAIL_CLIENT_ID,
    client_secret: GMAIL_CLIENT_SECRET,
    refresh_token: GMAIL_REFRESH_TOKEN,
    user: GMAIL_USER,
  };
}

const creds = loadCreds();

// ── Gmail OAuth2 transporter ─────────────────────────────────────────────────
async function createTransporter(): Promise<nodemailer.Transporter> {
  const oauth2Client = new google.auth.OAuth2(
    creds.client_id,
    creds.client_secret,
    "https://developers.google.com/oauthplayground"
  );
  oauth2Client.setCredentials({ refresh_token: creds.refresh_token });

  const { token: accessToken } = await oauth2Client.getAccessToken();

  return nodemailer.createTransport({
    service: "gmail",
    auth: {
      type: "OAuth2",
      user: creds.user,
      clientId: creds.client_id,
      clientSecret: creds.client_secret,
      refreshToken: creds.refresh_token,
      accessToken: accessToken ?? undefined,
    },
  });
}

// ── MCP server ───────────────────────────────────────────────────────────────
const server = new McpServer({ name: "mcp-email-server", version: "1.0.0" });

server.tool(
  "send_email",
  "Send an email via Gmail OAuth2. Body can be plain text or HTML. Attachment is an optional absolute file path.",
  {
    to: z.string().email().describe("Recipient email address"),
    subject: z.string().min(1).describe("Email subject line"),
    body: z.string().min(1).describe("Email body — plain text or HTML"),
    attachment: z.string().optional().describe("Absolute path to a file to attach (optional)"),
  },
  async ({ to, subject, body, attachment }) => {
    if (attachment && !fs.existsSync(attachment)) {
      return {
        content: [{ type: "text" as const, text: `Error: attachment not found: ${attachment}` }],
        isError: true,
      };
    }

    const transporter = await createTransporter();

    const mailOptions: SendMailOptions = {
      from: creds.user,
      to,
      subject,
      html: body,
      attachments: attachment ? [{ filename: path.basename(attachment), path: attachment }] : [],
    };

    const info = await transporter.sendMail(mailOptions);

    return {
      content: [
        {
          type: "text" as const,
          text: `Email sent.\nTo: ${to}\nSubject: ${subject}\nMessage-ID: ${info.messageId}`,
        },
      ],
    };
  }
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("MCP Email Server started (stdio)");
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});
