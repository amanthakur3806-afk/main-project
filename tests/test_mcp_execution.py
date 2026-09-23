import pytest
from app.mcp.client_manager import mcp_client_manager, ToolPermissionError

@pytest.mark.asyncio
async def test_mcp_tool_discovery():
    """Verify dynamic discovery across multiple MCP servers."""
    tools = await mcp_client_manager.discover_tools()
    tool_names = [t["name"] for t in tools]
    
    assert "CRM.get_customer" in tool_names
    assert "CRM.search_customer" in tool_names
    assert "Analytics.get_customer_metrics" in tool_names
    assert "Analytics.get_customer_history" in tool_names

@pytest.mark.asyncio
async def test_multi_mcp_execution_success():
    """Verify tool execution across CRM and Analytics servers."""
    allowed = ["CRM.get_customer", "Analytics.get_customer_metrics"]
    
    # 1. CRM tool execution
    crm_res = await mcp_client_manager.execute_tool(
        tool_name="CRM.get_customer",
        arguments={"customer_id": "ABC"},
        allowed_tools=allowed
    )
    assert crm_res["success"] is True
    assert crm_res["result"]["found"] is True
    assert crm_res["result"]["customer"]["company_name"] == "ABC Global Logistics & Supply Inc."

    # 2. Analytics tool execution
    analytics_res = await mcp_client_manager.execute_tool(
        tool_name="Analytics.get_customer_metrics",
        arguments={"customer_id": "ABC"},
        allowed_tools=allowed
    )
    assert analytics_res["success"] is True
    assert analytics_res["result"]["found"] is True
    assert analytics_res["result"]["metrics"]["arr"] == 450000

@pytest.mark.asyncio
async def test_agent_level_tool_permission_enforcement():
    """Verify unauthorized tool execution is blocked by the permission guard."""
    allowed = ["CRM.get_customer"]  # Analytics tools NOT allowed
    
    with pytest.raises(ToolPermissionError):
        await mcp_client_manager.execute_tool(
            tool_name="Analytics.get_customer_metrics",
            arguments={"customer_id": "ABC"},
            allowed_tools=allowed
        )
