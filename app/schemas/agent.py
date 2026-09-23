from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import datetime

class AgentToolSchema(BaseModel):
    tool_name: str
    server_id: str
    enabled: bool = True

    class Config:
        from_attributes = True

class AgentCreate(BaseModel):
    agent_id: str
    agent_name: str
    description: Optional[str] = None
    system_prompt: str
    playbook: str
    model: str = "gpt-4o-mini"
    temperature: float = 0.2
    memory_configuration: Dict[str, Any] = Field(default_factory=lambda: {"short_term": True, "long_term": True})
    workflow_configuration: Dict[str, Any] = Field(default_factory=lambda: {"max_iterations": 10, "enable_subagents": True, "rag_enabled": True, "knowledge_base": "customer_docs"})
    allowed_tools: List[str] = Field(default_factory=list)
    enabled: bool = True

class AgentUpdate(BaseModel):
    agent_name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    playbook: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    memory_configuration: Optional[Dict[str, Any]] = None
    workflow_configuration: Optional[Dict[str, Any]] = None
    allowed_tools: Optional[List[str]] = None
    enabled: Optional[bool] = None

class AgentResponse(BaseModel):
    agent_id: str
    agent_name: str
    description: Optional[str]
    system_prompt: str
    playbook: str
    model: str
    temperature: float
    memory_configuration: Dict[str, Any]
    workflow_configuration: Dict[str, Any]
    allowed_tools: List[str] = []
    enabled: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True

class AgentConfigResponse(BaseModel):
    agent_id: str
    model: str
    temperature: float
    memory: Dict[str, Any]
    rag: Dict[str, Any]
    workflow: Dict[str, Any]
    allowed_tools: List[str]
