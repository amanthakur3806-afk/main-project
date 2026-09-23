import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_list_agents():
    response = client.get("/agents")
    assert response.status_code == 200
    agents = response.json()
    assert len(agents) >= 3
    ids = [a["agent_id"] for a in agents]
    assert "customer_research_agent" in ids

def test_get_agent_config():
    response = client.get("/agents/customer_research_agent/config")
    assert response.status_code == 200
    data = response.json()
    assert data["agent_id"] == "customer_research_agent"
    assert "CRM.get_customer" in data["allowed_tools"]
    assert "Analytics.get_customer_metrics" in data["allowed_tools"]

def test_update_agent_config():
    # Update temperature
    response = client.put(
        "/agents/customer_research_agent/config",
        json={"temperature": 0.25}
    )
    assert response.status_code == 200
    assert response.json()["temperature"] == 0.25

def test_mcp_endpoints():
    # Servers
    res_servers = client.get("/mcp/servers")
    assert res_servers.status_code == 200
    assert len(res_servers.json()) >= 2

    # Tools
    res_tools = client.get("/mcp/tools")
    assert res_tools.status_code == 200
    tool_names = [t["tool_name"] for t in res_tools.json()]
    assert "CRM.get_customer" in tool_names

def test_run_agent_api():
    response = client.post(
        "/agents/customer_research_agent/run",
        json={
            "query": "Give me a complete summary of customer ABC including recent activity and internal documentation.",
            "conversation_id": "api_test_conv"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert "execution_id" in data
    assert len(data["answer"]) > 50

    # Test trace retrieval
    exec_id = data["execution_id"]
    trace_res = client.get(f"/executions/{exec_id}/trace")
    assert trace_res.status_code == 200
    assert len(trace_res.json()["trace"]) >= 5

    # Test prompt retrieval
    prompt_res = client.get(f"/executions/{exec_id}/prompt")
    assert prompt_res.status_code == 200
    assert "ORCHESTRATED MULTI-MCP AGENT EXECUTION AUDIT LOG" in prompt_res.text
