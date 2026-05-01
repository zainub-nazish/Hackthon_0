"""
Demo script for testing the Social Media MCP Server

This script demonstrates how to interact with the MCP server
by sending JSON-RPC requests and receiving responses.

Usage:
    python mcp_servers/demo_mcp_client.py
"""

import asyncio
import json
import subprocess
import sys


class MCPClient:
    """Simple MCP client for testing the server."""

    def __init__(self, server_command):
        self.server_command = server_command
        self.process = None
        self.request_id = 0

    async def start(self):
        """Start the MCP server process."""
        self.process = await asyncio.create_subprocess_exec(
            *self.server_command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        print("[OK] MCP server started")

    async def send_request(self, method, params=None):
        """Send a JSON-RPC request to the server."""
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }

        # Send request
        request_json = json.dumps(request) + "
"
        self.process.stdin.write(request_json.encode())
        await self.process.stdin.drain()

        # Read response
        response_line = await self.process.stdout.readline()
        response = json.loads(response_line.decode())

        return response

    async def stop(self):
        """Stop the MCP server process."""
        if self.process:
            self.process.terminate()
            await self.process.wait()
            print("[OK] MCP server stopped")


async def demo_initialize(client):
    """Demo: Initialize the MCP server."""
    print("
" + "=" * 70)
    print("  Test 1: Initialize Server")
    print("=" * 70)

    response = await client.send_request("initialize")

    if "result" in response:
        result = response["result"]
        print(f"[OK] Protocol Version: {result['protocolVersion']}")
        print(f"[OK] Server Name: {result['serverInfo']['name']}")
        print(f"[OK] Server Version: {result['serverInfo']['version']}")
    else:
        print(f"[FAIL] Error: {response.get('error', 'Unknown error')}")


async def demo_list_tools(client):
    """Demo: List available tools."""
    print("
" + "=" * 70)
    print("  Test 2: List Available Tools")
    print("=" * 70)

    response = await client.send_request("tools/list")

    if "result" in response:
        tools = response["result"]["tools"]
        print(f"[OK] Found {len(tools)} tools:")
        for tool in tools:
            print(f"  - {tool['name']}: {tool['description'][:60]}...")
    else:
        print(f"[FAIL] Error: {response.get('error', 'Unknown error')}")


async def demo_post_twitter(client):
    """Demo: Post to Twitter (dry-run)."""
    print("
" + "=" * 70)
    print("  Test 3: Post to Twitter")
    print("=" * 70)

    response = await client.send_request("tools/call", {
        "name": "post_twitter",
        "arguments": {
            "text": "Testing MCP server integration! 🚀 #AI #Automation"
        }
    })

    if "result" in response:
        content = response["result"]["content"][0]["text"]
        print("[OK] Response:")
        for line in content.split("
"):
            print(f"  {line}")
    else:
        print(f"[FAIL] Error: {response.get('error', 'Unknown error')}")


async def demo_cross_post(client):
    """Demo: Cross-post to multiple platforms."""
    print("
" + "=" * 70)
    print("  Test 4: Cross-Post to Multiple Platforms")
    print("=" * 70)

    response = await client.send_request("tools/call", {
        "name": "cross_post",
        "arguments": {
            "text": "Big announcement! Our MCP server is live. 🎉",
            "platforms": ["twitter", "facebook"]
        }
    })

    if "result" in response:
        content = response["result"]["content"][0]["text"]
        print("[OK] Response:")
        for line in content.split("
"):
            print(f"  {line}")
    else:
        print(f"[FAIL] Error: {response.get('error', 'Unknown error')}")


async def demo_get_summary(client):
    """Demo: Get social media summary."""
    print("
" + "=" * 70)
    print("  Test 5: Get Social Media Summary")
    print("=" * 70)

    response = await client.send_request("tools/call", {
        "name": "get_social_summary",
        "arguments": {
            "platform": "twitter",
            "period_days": 7
        }
    })

    if "result" in response:
        content = response["result"]["content"][0]["text"]
        print("[OK] Response:")
        for line in content.split("
"):
            print(f"  {line}")
    else:
        print(f"[FAIL] Error: {response.get('error', 'Unknown error')}")


async def demo_invalid_tool(client):
    """Demo: Call invalid tool (error handling)."""
    print("
" + "=" * 70)
    print("  Test 6: Error Handling (Invalid Tool)")
    print("=" * 70)

    response = await client.send_request("tools/call", {
        "name": "invalid_tool",
        "arguments": {}
    })

    if "error" in response:
        error = response["error"]
        print(f"[OK] Error caught correctly:")
        print(f"  Code: {error['code']}")
        print(f"  Message: {error['message']}")
    else:
        print(f"[FAIL] Expected error but got success")


async def main():
    print("=" * 70)
    print("  Social Media MCP Server - Demo Client")
    print("=" * 70)
    print("
This demo tests the MCP server by sending JSON-RPC requests.")
    print("Note: Server runs in dry-run mode by default (no real API calls).")

    # Create client
    client = MCPClient([sys.executable, "mcp_servers/social_mcp.py"])

    try:
        # Start server
        await client.start()
        await asyncio.sleep(1)  # Give server time to initialize

        # Run demos
        await demo_initialize(client)
        await demo_list_tools(client)
        await demo_post_twitter(client)
        await demo_cross_post(client)
        await demo_get_summary(client)
        await demo_invalid_tool(client)

        print("
" + "=" * 70)
        print("  All Tests Complete!")
        print("=" * 70)
        print("
Next steps:")
        print("  1. Configure real API credentials in .env")
        print("  2. Set dry_run=False in social_mcp.py for real API calls")
        print("  3. Add to Claude Desktop config to use with Claude")

    except Exception as e:
        print(f"
[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        # Stop server
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
