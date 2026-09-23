import os
from pathlib import Path
import pytest
from app.workflow.agent_workflow import create_agent_workflow
from app.database import SessionLocal
from app.models.execution import Execution

@pytest.mark.asyncio
async def test_end_to_end_agent_workflow():
    """Verify full LlamaIndex workflow execution for customer_research_agent."""
    workflow = create_agent_workflow()
    
    result = await workflow.run(
        agent_id="customer_research_agent",
        query="Give me a complete summary of customer ABC including recent activity and internal documentation.",
        conversation_id="test_conv_abc"
    )

    assert result["status"] == "completed"
    assert result["agent_id"] == "customer_research_agent"
    assert len(result["answer"]) > 100
    assert len(result["sources"]) > 0
    assert result["duration_ms"] > 0

    # Verify prompt.txt / final_prompt.txt was created on disk
    prompt_file = Path(result["prompt_file"])
    assert prompt_file.exists()
    content = prompt_file.read_text(encoding="utf-8")
    assert "customer_research_agent" in content
    assert "ABC Global Logistics" in content or "Customer Research Playbook" in content

    # Verify execution record in database
    db = SessionLocal()
    try:
        exec_rec = db.query(Execution).filter(Execution.execution_id == result["execution_id"]).first()
        assert exec_rec is not None
        assert exec_rec.status == "completed"
        assert len(exec_rec.steps) >= 5
    finally:
        db.close()
