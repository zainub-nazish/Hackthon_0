# Social Media MCP Server

MCP (Model Context Protocol) server that exposes social media posting skills as discoverable tools for AI clients.

## Overview

This MCP server allows any AI client (Claude Desktop, etc.) to discover and use social media posting capabilities through a standardized protocol.

**Protocol:** JSON-RPC 2.0 over stdio  
**Version:** 1.0.0

## Available Tools

### 1. post_twitter
Post a message to X (Twitter) with optional media.

**Input Schema:**
```json
{
  "text": "Tweet content (max 280 chars)",
  "media_path": "Optional path to image/video file"
}
```

**Example:**
```json
{
  "text": "Just launched our new AI system! 🚀 #AI #Automation",
  "media_path": "announcement.jpg"
}
```

### 2. post_facebook
Post a message to a Facebook Page with optional link and image.

**Input Schema:**
```json
{
  "message": "Post content",
  "link": "Optional URL to share",
  "image_path": "Optional path to image file"
}
```

**Example:**
```json
{
  "message": "Check out our latest blog post!",
  "link": "https://example.com/blog"
}
```

### 3. post_instagram
Post a photo with caption to Instagram Business account.

**Input Schema:**
```json
{
  "caption": "Caption text (max 2200 chars)",
  "image_path": "Publicly accessible image URL (required)",
  "is_reel": false
}
```

**Note:** Instagram requires publicly accessible image URLs, not local file paths.

### 4. cross_post
Post the same message across multiple platforms simultaneously.

**Input Schema:**
```json
{
  "text": "Message content",
  "platforms": ["twitter", "facebook", "instagram"],
  "image_path": "Optional image path"
}
```

### 5. get_social_summary
Retrieve engagement summary for a platform.

**Input Schema:**
```json
{
  "platform": "twitter",
  "period_days": 7
}
```

## Setup

### 1. Install Dependencies

```bash
pip install tweepy>=4.14.0 requests>=2.31.0 python-dotenv>=1.0.0
```

### 2. Configure API Credentials

Create a `.env` file in the project root:

```bash
# X (Twitter)
TWITTER_API_KEY=your_api_key
TWITTER_API_SECRET=your_api_secret
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret

# Facebook Page
FACEBOOK_ACCESS_TOKEN=your_page_access_token
FACEBOOK_PAGE_ID=your_page_id

# Instagram Business
INSTAGRAM_ACCESS_TOKEN=your_page_access_token
INSTAGRAM_BUSINESS_ACCOUNT_ID=your_instagram_business_account_id
```

See `docs/SOCIAL_API_SETUP.md` for detailed credential setup instructions.

### 3. Test the Server

```bash
python mcp_servers/social_mcp.py
```

The server will start and listen for JSON-RPC requests on stdin.

## Usage with Claude Desktop

Add to your Claude Desktop configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "social-media": {
      "command": "python",
      "args": ["D:/hackthon_0_/gold_tier/mcp_servers/social_mcp.py"],
      "env": {}
    }
  }
}
```

After restarting Claude Desktop, the social media tools will be available.

## Protocol Details

### Initialize
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {}
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {"tools": {}},
    "serverInfo": {
      "name": "social-media-mcp",
      "version": "1.0.0"
    }
  }
}
```

### List Tools
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      {
        "name": "post_twitter",
        "description": "Post a message to X (Twitter)...",
        "inputSchema": {...}
      },
      ...
    ]
  }
}
```

### Call Tool
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "post_twitter",
    "arguments": {
      "text": "Hello from MCP! 🚀"
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Posted successfully!
Platform: twitter
Post ID: 123456
URL: https://twitter.com/user/status/123456
Engagement expected: high because..."
      }
    ]
  }
}
```

## Error Handling

All errors follow JSON-RPC 2.0 error format:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "error": {
    "code": -32602,
    "message": "Unknown tool: invalid_tool"
  }
}
```

**Error Codes:**
- `-32700`: Parse error (invalid JSON)
- `-32601`: Method not found
- `-32602`: Invalid params (unknown tool)
- `-32603`: Internal error

## Logging

All MCP server activity is logged to:
- `logs/social_mcp/actions.jsonl` - All tool calls
- `logs/social_mcp/errors.jsonl` - All errors
- `logs/social_mcp/audit.jsonl` - State changes

## Security

- API credentials are loaded from environment variables
- Never hardcode credentials in the server code
- Use `.env` file (excluded from git)
- Rotate tokens regularly (Facebook: 60 days)

## Troubleshooting

### Server not starting
- Check Python version (3.10+)
- Verify all dependencies installed
- Check `.env` file exists and has valid credentials

### Tools not appearing in Claude Desktop
- Verify `claude_desktop_config.json` path is correct
- Restart Claude Desktop after config changes
- Check server logs for errors

### API errors
- Verify credentials in `.env` are correct
- Check API rate limits
- Ensure tokens haven't expired

## Development

### Testing the Server Manually

```bash
# Start server
python mcp_servers/social_mcp.py

# In another terminal, send test request
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | python mcp_servers/social_mcp.py
```

### Dry-Run Mode

To test without making real API calls, edit `social_mcp.py`:

```python
self.social = SocialMediaSkill(
    recovery=self.recovery,
    logger=self.logger,
    dry_run=True  # Enable dry-run mode
)
```

## Production Deployment

1. Use process manager (systemd, supervisor)
2. Set up log rotation
3. Monitor error logs
4. Implement token refresh for Facebook
5. Set up alerts for circuit breaker opens

## License

Part of the Agent Skills system.
