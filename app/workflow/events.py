"""
LlamaIndex Workflow Events
Defines event contracts passing state across workflow stages.
"""
from typing import Dict, Any, List, Optional
from llama_index.core.workflow import Event

class AgentLoadedEvent(Event):
    agent_id: str
    agent_config: Dict[str, Any]
    query: str
    conversation_id: Optional[str] = None
    execution_id: str

class MemoryAndRAGLoadedEvent(Event):
    agent_id: str
    agent_config: Dict[str, Any]
    query: str
    conversation_id: Optional[str] = None
    execution_id: str
    short_term_history: List[Dict[str, str]]
    long_term_facts: List[str]
    retrieved_chunks: List[Dict[str, Any]]

class ToolPlanGeneratedEvent(Event):
    agent_id: str
    agent_config: Dict[str, Any]
    query: str
    conversation_id: Optional[str] = None
    execution_id: str
    short_term_history: List[Dict[str, str]]
    long_term_facts: List[str]
    retrieved_chunks: List[Dict[str, Any]]
    planned_tools: List[Dict[str, Any]]

class ToolsExecutedEvent(Event):
    agent_id: str
    agent_config: Dict[str, Any]
    query: str
    conversation_id: Optional[str] = None
    execution_id: str
    short_term_history: List[Dict[str, str]]
    long_term_facts: List[str]
    retrieved_chunks: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]

class ContextCondensedEvent(Event):
    agent_id: str
    agent_config: Dict[str, Any]
    query: str
    conversation_id: Optional[str] = None
    execution_id: str
    short_term_history: List[Dict[str, str]]
    long_term_facts: List[str]
    retrieved_chunks: List[Dict[str, Any]]
    condensed_tool_summary: str
    raw_tool_results: List[Dict[str, Any]]
