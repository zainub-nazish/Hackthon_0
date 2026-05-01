"""
Social Media MCP Server

Exposes social media posting skills as MCP tools via stdio protocol.
Any AI client (Claude, etc.) can discover and call these tools.

Usage:
    python mcp_servers/social_mcp.py

Protocol: JSON-RPC 2.0 over stdio
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

# Add parent directory to path so we can import agent_skills
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_skills import AuditLogger, RecoverySkill, SocialMediaSkill


class MCPServer:
    """MCP protocol server for social media skills."""

    def __init__(self):
        self.logger = AuditLogger("social_mcp", log_dir="logs/social_mcp/")
        self.recovery = RecoverySkill(logger=self.logger)
        self.social = SocialMediaSkill(
            recovery=self.recovery,
            logger=self.logger,
            dry_run=False
        )

        self.tools = {
            "post_twitter": {
                "name": "post_twitter",
                "description": "Post a message to X (Twitter) with optional media. Truncates to 280 characters.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Tweet content (max 280 chars)"},
                        "media_path": {"type": "string", "description": "Optional path to image/video file"}
                    },
                    "required": ["text"]
                }
            },
            "post_facebook": {
                "name": "post_facebook",
                "description": "Post a message to a Facebook Page with optional link and image.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "Post content"},
                        "link": {"type": "string", "description": "Optional URL to share"},
                        "image_path": {"type": "string", "description": "Optional path to image file"}
                    },
                    "required": ["message"]
                }
            },
            "post_instagram": {
                "name": "post_instagram",
                "description": "Post a photo with caption to Instagram Business account. Image must be publicly accessible URL.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "caption": {"type": "string", "description": "Caption text (max 2200 chars)"},
                        "image_path": {"type": "string", "description": "Publicly accessible image URL (required)"},
                        "is_reel": {"type": "boolean", "description": "Post as Reel (video)", "default": False}
                    },
                    "required": ["caption", "image_path"]
                }
            },
            "cross_post": {
                "name": "cross_post",
                "description": "Post the same message across multiple social media platforms simultaneously.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Message content"},
                        "platforms": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["twitter", "facebook", "instagram"]},
                            "description": "Platforms to post to (default: twitter, facebook)"
                        },
                        "image_path": {"type": "string", "description": "Optional image path"}
                    },
                    "required": ["text"]
                }
            },
            "get_social_summary": {
                "name": "get_social_summary",
                "description": "Retrieve engagement summary for a platform over the specified period.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "platform": {
                            "type": "string",
                            "enum": ["twitter", "facebook", "instagram", "all"],
                            "description": "Platform to get summary for"
                        },
                        "period_days": {"type": "integer", "description": "Number of days to look back", "default": 7}
                    },
                    "required": ["platform"]
                }
            }
        }
    async def handle_request(self, request: dict) -> dict:
        """Handle incoming JSON-RPC request."""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        try:
            if method == "initialize":
                return self._make_response(request_id, {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "social-media-mcp", "version": "1.0.0"}
                })
            elif method == "tools/list":
                return self._make_response(request_id, {"tools": list(self.tools.values())})
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                if tool_name not in self.tools:
                    return self._make_error(request_id, -32602, f"Unknown tool: {tool_name}")
                result = await self._execute_tool(tool_name, arguments)
                return self._make_response(request_id, result)
            else:
                return self._make_error(request_id, -32601, f"Method not found: {method}")
        except Exception as e:
            self.logger.log_error("mcp_server", method or "unknown", e, "ERROR", True)
            return self._make_error(request_id, -32603, f"Internal error: {str(e)}")

    async def _execute_tool(self, tool_name: str, arguments: dict) -> dict:
        """Execute a social media skill and return result."""
        try:
            if tool_name == "post_twitter":
                result = await self.social.post_to_twitter(
                    text=arguments["text"], media_path=arguments.get("media_path"))
            elif tool_name == "post_facebook":
                result = await self.social.post_to_facebook(
                    message=arguments["message"], link=arguments.get("link"),
                    image_path=arguments.get("image_path"))
            elif tool_name == "post_instagram":
                result = await self.social.post_to_instagram(
                    caption=arguments["caption"], image_path=arguments["image_path"],
                    is_reel=arguments.get("is_reel", False))
            elif tool_name == "cross_post":
                result = await self.social.cross_post(
                    text=arguments["text"], platforms=arguments.get("platforms"),
                    image_path=arguments.get("image_path"))
            elif tool_name == "get_social_summary":
                result = await self.social.generate_social_summary(
                    platform=arguments["platform"], period_days=arguments.get("period_days", 7))
            else:
                return {"content": [{"type": "text", "text": f"Error: Unknown tool {tool_name}"}], "isError": True}
            return self._format_result(result)
        except Exception as e:
            return {"content": [{"type": "text", "text": f"Error executing {tool_name}: {str(e)}"}], "isError": True}
    def _format_result(self, result) -> dict:
        """Format skill result for MCP response."""
        if hasattr(result, "success"):
            if result.success:
                text = f"Posted successfully!\nPlatform: {result.platform}\nPost ID: {result.post_id}\nURL: {result.url}\n{result.engagement_prediction}"
                return {"content": [{"type": "text", "text": text}]}
            else:
                return {"content": [{"type": "text", "text": f"Failed: {result.error}"}], "isError": True}
        elif isinstance(result, dict):
            text = "Cross-post results:\n\n"
            for platform, post_result in result.items():
                if hasattr(post_result, "data"):
                    post_result = post_result.data
                if post_result.success:
                    text += f"{platform.upper()}\n  Post ID: {post_result.post_id}\n  URL: {post_result.url}\n  {post_result.engagement_prediction}\n\n"
                else:
                    text += f"{platform.upper()}: {post_result.error}\n\n"
            return {"content": [{"type": "text", "text": text}]}
        elif hasattr(result, "platform"):
            text = f"Social Media Summary - {result.platform.upper()}\nPeriod: Last {result.period_days} days\n\n"
            text += f"Total Posts: {result.total_posts}\nTotal Likes: {result.total_likes}\n"
            text += f"Total Comments: {result.total_comments}\nTotal Shares: {result.total_shares}\n"
            text += f"Engagement Rate: {result.engagement_rate:.2%}\n"
            if result.top_post_id:
                text += f"Top Post: {result.top_post_id}\n"
            return {"content": [{"type": "text", "text": text}]}
        return {"content": [{"type": "text", "text": str(result)}]}

    def _make_response(self, request_id, result: dict) -> dict:
        """Create JSON-RPC success response."""
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _make_error(self, request_id, code: int, message: str) -> dict:
        """Create JSON-RPC error response."""
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    async def run(self):
        """Run the MCP server (stdio protocol)."""
        self.logger.log_action("mcp_server", "startup", {"protocol": "stdio"})
        while True:
            try:
                line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
                if not line:
                    break
                request = json.loads(line)
                response = await self.handle_request(request)
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
            except json.JSONDecodeError as e:
                error_response = self._make_error(None, -32700, f"Parse error: {str(e)}")
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()
            except Exception as e:
                self.logger.log_error("mcp_server", "run_loop", e, "ERROR", True)
                error_response = self._make_error(None, -32603, f"Internal error: {str(e)}")
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()


async def main():
    """Entry point for MCP server."""
    server = MCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())