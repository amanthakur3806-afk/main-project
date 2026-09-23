"""
MCP Server & Tool Discovery API Endpoints
"""
from typing import List, Dict, Any
from fastapi import APIRouter
from app.mcp.client_manager import mcp_client_manager
from app.schemas.mcp import MCPServerResponse, ToolMetadataResponse

router = APIRouter(prefix="/mcp", tags=["Model Context Protocol (MCP)"])

@router.get("/servers", summary="List connected MCP servers and connection status")
def list_mcp_servers():
    servers = mcp_client_manager.list_servers()
    return servers

@router.get("/tools", response_model=List[ToolMetadataResponse], summary="Discover all available tools dynamically across MCP servers")
async def list_mcp_tools():
    tools = await mcp_client_manager.discover_tools()
    results = []
    for t in tools:
        results.append(ToolMetadataResponse(
            tool_name=t["name"],
            server_id=t.get("server_id", "unknown"),
            description=t.get("description", ""),
            parameters=t.get("parameters", {}),
            enabled=True
        ))
    return results
