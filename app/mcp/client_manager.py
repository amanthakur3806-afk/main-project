"""
Multi-MCP Client Manager
Manages server registries, dynamic tool discovery, agent-level permission enforcement,
and resilient tool execution across multiple MCP servers.
"""
import asyncio
import time
import logging
from typing import Dict, Any, List, Optional
from app.mcp.servers.crm_server import crm_server_instance
from app.mcp.servers.analytics_server import analytics_server_instance

logger = logging.getLogger("mcp_manager")

class ToolPermissionError(Exception):
    """Raised when an agent attempts to execute an unauthorized tool."""
    pass

class MCPClientManager:
    """Coordinates multiple MCP servers, tool discovery, permissions, and tool execution."""

    def __init__(self):
        # Server registry mapping server_id to server handler
        self._servers: Dict[str, Any] = {
            "crm_mcp": crm_server_instance,
            "analytics_mcp": analytics_server_instance
        }

    def register_server(self, server_id: str, server_instance: Any):
        """Register an active MCP server instance."""
        self._servers[server_id] = server_instance

    def list_servers(self) -> List[Dict[str, Any]]:
        """List metadata of all connected MCP servers."""
        return [
            {
                "server_id": "crm_mcp",
                "server_name": "CRM MCP Server",
                "transport": "inprocess",
                "status": "connected"
            },
            {
                "server_id": "analytics_mcp",
                "server_name": "Analytics MCP Server",
                "transport": "inprocess",
                "status": "connected"
            }
        ]

    async def discover_tools(self) -> List[Dict[str, Any]]:
        """Discover tools dynamically across all connected MCP servers."""
        all_tools = []
        for server_id, server in self._servers.items():
            try:
                tools = server.list_tools()
                for tool in tools:
                    all_tools.append(tool)
            except Exception as e:
                logger.error(f"Error discovering tools from server {server_id}: {e}")
        return all_tools

    async def get_tools_for_agent(self, allowed_tools: List[str]) -> List[Dict[str, Any]]:
        """Filter discovered tools by agent-specific tool permissions."""
        all_tools = await self.discover_tools()
        if not allowed_tools:
            return []

        # Normalize allowed tool names (case-insensitive and whitespace stripped)
        allowed_normalized = {t.strip().lower() for t in allowed_tools}
        
        filtered = []
        for tool in all_tools:
            name = tool["name"].lower()
            # Check direct match or without prefix (e.g. 'crm.get_customer' or 'get_customer')
            matches = any(
                name == allowed or name.endswith(f".{allowed}") or allowed.endswith(f".{name}")
                for allowed in allowed_normalized
            )
            if matches:
                filtered.append(tool)
        return filtered

    def check_tool_permission(self, tool_name: str, allowed_tools: List[str]) -> bool:
        """Validate if a specific tool is authorized for the given agent."""
        tool_name_norm = tool_name.strip().lower()
        allowed_normalized = {t.strip().lower() for t in allowed_tools}

        return any(
            tool_name_norm == allowed or 
            tool_name_norm.endswith(f".{allowed}") or 
            allowed.endswith(f".{tool_name_norm}")
            for allowed in allowed_normalized
        )

    def _resolve_server(self, tool_name: str) -> Optional[Any]:
        """Find the corresponding MCP server for a tool."""
        tool_upper = tool_name.upper()
        if tool_upper.startswith("CRM"):
            return self._servers.get("crm_mcp")
        elif tool_upper.startswith("ANALYTICS"):
            return self._servers.get("analytics_mcp")
        
        # Fallback: scan all servers for the tool
        for server in self._servers.values():
            tools = server.list_tools()
            for t in tools:
                if t["name"].lower() == tool_name.lower():
                    return server
        return None

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        allowed_tools: List[str],
        timeout_seconds: float = 10.0,
        max_retries: int = 1
    ) -> Dict[str, Any]:
        """
        Execute an MCP tool with explicit permission checking, timeout, and retry handling.
        Returns execution result dictionary with timing and status.
        """
        start_time = time.time()
        
        # 1. Permission check
        if not self.check_tool_permission(tool_name, allowed_tools):
            duration_ms = round((time.time() - start_time) * 1000, 2)
            raise ToolPermissionError(
                f"Tool '{tool_name}' is not in the allowed tools list for this agent: {allowed_tools}"
            )

        # 2. Resolve target MCP server
        server = self._resolve_server(tool_name)
        if not server:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            return {
                "success": False,
                "tool_name": tool_name,
                "error": f"No connected MCP server found for tool '{tool_name}'",
                "duration_ms": duration_ms
            }

        # 3. Resilient execution with retries and timeout
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    server.call_tool(tool_name, arguments),
                    timeout=timeout_seconds
                )
                duration_ms = round((time.time() - start_time) * 1000, 2)
                return {
                    "success": True,
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "result": result,
                    "duration_ms": duration_ms,
                    "attempts": attempt + 1
                }
            except asyncio.TimeoutError:
                last_error = f"Tool execution timed out after {timeout_seconds}s"
            except Exception as e:
                last_error = str(e)
            
            # Brief delay before retry
            if attempt < max_retries:
                await asyncio.sleep(0.2)

        duration_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "success": False,
            "tool_name": tool_name,
            "arguments": arguments,
            "error": last_error,
            "duration_ms": duration_ms,
            "attempts": max_retries + 1
        }

# Global singleton
mcp_client_manager = MCPClientManager()
