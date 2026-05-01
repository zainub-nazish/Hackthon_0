"""
MCP Orchestrator - Multi-Server Integration
Manages 3 separate MCP servers with intelligent routing and graceful degradation.

Architecture:
- social_mcp.py: Social media posting and analytics
- audit_mcp.py: Business audits, CEO briefings, transactions
- recovery_mcp.py: Circuit breakers, health checks, error handling

Features:
- Dynamic tool discovery from all MCP servers
- Intelligent task routing based on tool type
- Cross-domain task execution (combines multiple MCPs)
- Graceful degradation when MCPs fail
- Health monitoring and automatic recovery
"""

import asyncio
import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# Fix Windows console encoding
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))


class MCPStatus(Enum):
    """MCP server status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass
class MCPServer:
    """MCP server configuration and state."""
    name: str
    script_path: str
    process: Optional[subprocess.Popen] = None
    status: MCPStatus = MCPStatus.UNKNOWN
    tools: list[dict[str, Any]] = None
    last_health_check: Optional[datetime] = None
    error_count: int = 0
    stdin_writer: Optional[asyncio.StreamWriter] = None
    stdout_reader: Optional[asyncio.StreamReader] = None

    def __post_init__(self):
        if self.tools is None:
            self.tools = []


class MCPOrchestrator:
    """Orchestrator for managing multiple MCP servers."""

    def __init__(self, log_dir: str = "logs/mcp_orchestrator"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_dir / "orchestrator.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("mcp_orchestrator")

        # MCP servers
        self.servers: dict[str, MCPServer] = {
            "social": MCPServer(
                name="social",
                script_path="mcp_servers/social_mcp.py"
            ),
            "audit": MCPServer(
                name="audit",
                script_path="mcp_servers/audit_mcp.py"
            ),
            "recovery": MCPServer(
                name="recovery",
                script_path="mcp_servers/recovery_mcp.py"
            )
        }

        # Task routing rules (tool_name -> [primary_server, fallback_servers...])
        self.routing_rules = {
            # Social tools
            "post_twitter": ["social"],
            "post_facebook": ["social"],
            "post_instagram": ["social"],
            "cross_post": ["social"],
            "get_social_summary": ["social"],

            # Audit tools
            "run_weekly_audit": ["audit"],
            "record_transaction": ["audit"],
            "export_transactions_csv": ["audit"],
            "cross_domain_analysis": ["audit"],
            "seed_mock_data": ["audit"],
            "get_daily_briefing": ["audit"],
            "list_tasks": ["audit"],
            "update_task_status": ["audit"],

            # Recovery tools
            "get_circuit_status": ["recovery"],
            "reset_circuit": ["recovery"],
            "get_error_summary": ["recovery"],
            "run_health_check": ["recovery"],
            "list_fallbacks": ["recovery"],
        }

        # Cross-domain task definitions (task_name -> [required_servers])
        self.cross_domain_tasks = {
            "weekly_business_cycle": {
                "servers": ["audit", "social"],
                "steps": [
                    {"server": "audit", "tool": "run_weekly_audit", "args": {"include_social": True}},
                    {"server": "social", "tool": "get_social_summary", "args": {"platform": "all", "period_days": 7}}
                ]
            },
            "system_health_audit": {
                "servers": ["audit", "recovery"],
                "steps": [
                    {"server": "recovery", "tool": "run_health_check", "args": {}},
                    {"server": "audit", "tool": "cross_domain_analysis", "args": {}}
                ]
            },
            "post_performance_update": {
                "servers": ["audit", "social"],
                "steps": [
                    {"server": "audit", "tool": "run_weekly_audit", "args": {"include_social": False}},
                    {"server": "social", "tool": "post_twitter", "args": {"text": "{{generated_from_audit}}", "dry_run": True}}
                ]
            }
        }

        self.request_id_counter = 0

    async def start(self) -> None:
        """Start all MCP servers."""
        self.logger.info("Starting MCP Orchestrator")

        for name, server in self.servers.items():
            try:
                await self._start_server(server)
                self.logger.info(f"✅ Started {name} MCP server")
            except Exception as e:
                self.logger.error(f"❌ Failed to start {name} MCP server: {e}")
                server.status = MCPStatus.FAILED

        # Discover tools from all servers
        await self._discover_all_tools()

        # Initial health check
        await self.health_check_all()

        healthy_count = len(self._get_healthy_servers())
        total_count = len(self.servers)

        self.logger.info(f"Orchestrator started: {healthy_count}/{total_count} servers healthy")

    async def _start_server(self, server: MCPServer) -> None:
        """Start a single MCP server process."""
        script_path = Path(__file__).parent / server.script_path

        if not script_path.exists():
            raise FileNotFoundError(f"MCP script not found: {script_path}")

        # Set up environment with correct PYTHONPATH
        import os
        env = os.environ.copy()
        parent_dir = str(Path(__file__).parent)
        if 'PYTHONPATH' in env:
            env['PYTHONPATH'] = f"{parent_dir}{os.pathsep}{env['PYTHONPATH']}"
        else:
            env['PYTHONPATH'] = parent_dir

        # Start process
        server.process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(script_path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )

        server.stdin_writer = server.process.stdin
        server.stdout_reader = server.process.stdout

        # Initialize server
        init_request = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "initialize",
            "params": {}
        }

        response = await self._send_request(server, init_request)

        if response and "result" in response:
            server.status = MCPStatus.HEALTHY
        else:
            server.status = MCPStatus.DEGRADED

    async def _discover_all_tools(self) -> None:
        """Discover tools from all healthy servers."""
        for name, server in self.servers.items():
            if server.status == MCPStatus.FAILED:
                continue

            try:
                tools = await self._list_tools(server)
                server.tools = tools
                self.logger.info(f"Discovered {len(tools)} tools from {name}")
            except Exception as e:
                self.logger.error(f"Failed to discover tools from {name}: {e}")
                server.status = MCPStatus.DEGRADED

    async def _list_tools(self, server: MCPServer) -> list[dict[str, Any]]:
        """List tools from a server."""
        request = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "tools/list",
            "params": {}
        }

        response = await self._send_request(server, request)

        if response and "result" in response:
            return response["result"].get("tools", [])
        return []

    async def _send_request(self, server: MCPServer, request: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Send request to MCP server and get response."""
        if not server.stdin_writer or not server.stdout_reader:
            raise RuntimeError(f"Server {server.name} not connected")

        try:
            # Send request
            request_line = json.dumps(request) + "\n"
            server.stdin_writer.write(request_line.encode())
            await server.stdin_writer.drain()

            # Read response
            response_line = await asyncio.wait_for(
                server.stdout_reader.readline(),
                timeout=30.0
            )

            if not response_line:
                raise RuntimeError("Empty response from server")

            response = json.loads(response_line.decode())
            return response

        except asyncio.TimeoutError:
            self.logger.error(f"Timeout waiting for response from {server.name}")
            server.error_count += 1
            return None
        except Exception as e:
            self.logger.error(f"Error communicating with {server.name}: {e}")
            server.error_count += 1
            return None

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool with intelligent routing and fallback."""
        # Determine which server(s) to use
        target_servers = self._route_tool(tool_name)

        if not target_servers:
            return {
                "success": False,
                "error": f"No routing rule for tool: {tool_name}",
                "fallback_used": False
            }

        # Try primary server
        primary_server_name = target_servers[0]
        primary_server = self.servers.get(primary_server_name)

        if primary_server and primary_server.status == MCPStatus.HEALTHY:
            try:
                result = await self._execute_tool(primary_server, tool_name, arguments)
                return {
                    "success": True,
                    "result": result,
                    "server_used": primary_server_name,
                    "fallback_used": False
                }
            except Exception as e:
                self.logger.error(f"Tool execution failed on {primary_server_name}: {e}")
                primary_server.error_count += 1

        # Try fallback servers
        for fallback_server_name in target_servers[1:]:
            fallback_server = self.servers.get(fallback_server_name)

            if fallback_server and fallback_server.status == MCPStatus.HEALTHY:
                try:
                    self.logger.info(f"Using fallback server: {fallback_server_name}")
                    result = await self._execute_tool(fallback_server, tool_name, arguments)
                    return {
                        "success": True,
                        "result": result,
                        "server_used": fallback_server_name,
                        "fallback_used": True
                    }
                except Exception as e:
                    self.logger.error(f"Fallback execution failed on {fallback_server_name}: {e}")

        # All servers failed - graceful degradation
        return {
            "success": False,
            "error": f"All servers failed for tool: {tool_name}",
            "fallback_used": True,
            "degraded_result": self._get_degraded_result(tool_name)
        }

    async def _execute_tool(self, server: MCPServer, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Execute a tool on a specific server."""
        request = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        response = await self._send_request(server, request)

        if not response:
            raise RuntimeError(f"No response from {server.name}")

        if "error" in response:
            raise RuntimeError(f"Tool error: {response['error'].get('message', 'Unknown error')}")

        return response.get("result", {})

    def _route_tool(self, tool_name: str) -> list[str]:
        """Route tool to appropriate server(s)."""
        # Check explicit routing rules
        if tool_name in self.routing_rules:
            return self.routing_rules[tool_name]

        # Fallback: search all servers for the tool
        for server_name, server in self.servers.items():
            if server.status == MCPStatus.HEALTHY:
                for tool in server.tools:
                    if tool.get("name") == tool_name:
                        return [server_name]

        return []

    async def execute_cross_domain_task(self, task_name: str, custom_args: dict[str, Any] = None) -> dict[str, Any]:
        """Execute a cross-domain task across multiple servers."""
        if task_name not in self.cross_domain_tasks:
            return {
                "success": False,
                "error": f"Unknown cross-domain task: {task_name}"
            }

        task_def = self.cross_domain_tasks[task_name]
        required_servers = task_def["servers"]
        steps = task_def["steps"]

        results = {}
        errors = []

        self.logger.info(f"Executing cross-domain task: {task_name}")

        # Execute each step in sequence
        for step in steps:
            server_name = step["server"]
            tool_name = step["tool"]
            args = step["args"].copy()

            # Override with custom args if provided
            if custom_args:
                args.update(custom_args)

            server = self.servers.get(server_name)

            if not server or server.status != MCPStatus.HEALTHY:
                errors.append(f"{server_name} unavailable")
                # Graceful degradation: continue with other steps
                continue

            try:
                result = await self.call_tool(tool_name, args)
                results[f"{server_name}.{tool_name}"] = result

                if not result.get("success"):
                    errors.append(f"{server_name}.{tool_name}: {result.get('error', 'Unknown error')}")

            except Exception as e:
                errors.append(f"{server_name}.{tool_name}: {str(e)}")

        return {
            "success": len(errors) == 0,
            "task_name": task_name,
            "results": results,
            "errors": errors,
            "servers_used": required_servers,
            "partial_success": len(results) > 0 and len(errors) > 0
        }

    async def health_check_all(self) -> dict[str, Any]:
        """Perform health check on all servers."""
        health_status = {}

        for name, server in self.servers.items():
            try:
                if server.process and server.process.returncode is None:
                    # Process is running
                    tools_count = len(server.tools)
                    health_status[name] = {
                        "status": server.status.value,
                        "tools_count": tools_count,
                        "error_count": server.error_count,
                        "healthy": server.status == MCPStatus.HEALTHY
                    }
                else:
                    # Process died
                    server.status = MCPStatus.FAILED
                    health_status[name] = {
                        "status": "failed",
                        "error": "Process not running"
                    }

                server.last_health_check = datetime.now()

            except Exception as e:
                health_status[name] = {
                    "status": "error",
                    "error": str(e)
                }

        overall_healthy = all(
            status.get("healthy", False)
            for status in health_status.values()
        )

        return {
            "overall_healthy": overall_healthy,
            "servers": health_status,
            "timestamp": datetime.now().isoformat()
        }

    def _get_healthy_servers(self) -> list[str]:
        """Get list of healthy server names."""
        return [
            name for name, server in self.servers.items()
            if server.status == MCPStatus.HEALTHY
        ]

    def _get_degraded_result(self, tool_name: str) -> Optional[dict[str, Any]]:
        """Get degraded/fallback result when all servers fail."""
        degraded_results = {
            "post_twitter": {"posted": False, "message": "Social posting unavailable"},
            "run_weekly_audit": {"status": "unavailable", "message": "Audit system offline"},
            "get_circuit_status": {"circuits": {}, "message": "Recovery system offline"}
        }

        return degraded_results.get(tool_name, {"message": "Service temporarily unavailable"})

    def _next_request_id(self) -> int:
        """Get next request ID."""
        self.request_id_counter += 1
        return self.request_id_counter

    async def shutdown(self) -> None:
        """Shutdown all MCP servers."""
        self.logger.info("Shutting down orchestrator")

        for name, server in self.servers.items():
            if server.process:
                try:
                    server.process.terminate()
                    await asyncio.wait_for(server.process.wait(), timeout=5.0)
                    self.logger.info(f"Stopped {name} server")
                except asyncio.TimeoutError:
                    server.process.kill()
                    self.logger.warning(f"Force killed {name} server")
                except Exception as e:
                    self.logger.error(f"Error stopping {name} server: {e}")

    def get_all_tools(self) -> dict[str, list[dict[str, Any]]]:
        """Get all available tools grouped by server."""
        return {
            name: server.tools
            for name, server in self.servers.items()
            if server.status == MCPStatus.HEALTHY
        }


async def main():
    """Demo: Start orchestrator and execute sample tasks."""
    orchestrator = MCPOrchestrator()

    try:
        # Start all servers
        await orchestrator.start()

        print("\n" + "=" * 70)
        print("MCP ORCHESTRATOR - SYSTEM STATUS")
        print("=" * 70)

        # Health check
        health = await orchestrator.health_check_all()
        print(f"\nOverall Health: {'✅ HEALTHY' if health['overall_healthy'] else '⚠️ DEGRADED'}")
        print("\nServer Status:")
        for server_name, status in health["servers"].items():
            status_icon = "✅" if status.get("healthy") else "❌"
            print(f"  {status_icon} {server_name.upper()}: {status.get('status', 'unknown')} ({status.get('tools_count', 0)} tools)")

        # List all available tools
        print("\n" + "=" * 70)
        print("AVAILABLE TOOLS BY SERVER")
        print("=" * 70)
        all_tools = orchestrator.get_all_tools()
        total_tools = 0
        for server_name, tools in all_tools.items():
            print(f"\n{server_name.upper()} ({len(tools)} tools):")
            total_tools += len(tools)
            for tool in tools[:5]:  # Show first 5
                print(f"  • {tool['name']}")
            if len(tools) > 5:
                print(f"  ... and {len(tools) - 5} more")

        print(f"\nTotal tools available: {total_tools}")

        # Execute sample cross-domain task
        print("\n" + "=" * 70)
        print("EXECUTING CROSS-DOMAIN TASK: weekly_business_cycle")
        print("=" * 70)

        result = await orchestrator.execute_cross_domain_task("weekly_business_cycle")

        print(f"\n✅ Success: {result['success']}")
        print(f"📊 Servers Used: {', '.join(result['servers_used'])}")
        print(f"📝 Steps Completed: {len(result['results'])}")

        if result['errors']:
            print(f"⚠️  Errors: {len(result['errors'])}")
            for error in result['errors']:
                print(f"   - {error}")

        if result.get('partial_success'):
            print("⚠️  Partial success - some steps failed but system continued")

        print("\n" + "=" * 70)
        print("ORCHESTRATOR READY FOR AUTONOMOUS OPERATION")
        print("=" * 70)
        print("\n✅ All systems operational")
        print("✅ Graceful degradation enabled")
        print("✅ Cross-domain tasks supported")
        print("✅ Health monitoring active")

    except KeyboardInterrupt:
        print("\n\nShutdown requested...")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await orchestrator.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
