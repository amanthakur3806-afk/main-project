from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import datetime

class RunAgentRequest(BaseModel):
    query: str = Field(..., description="The user query or task prompt", example="Give me a complete summary of customer ABC including recent activity and internal documentation.")
    conversation_id: Optional[str] = Field(None, description="Optional conversation ID for short-term memory", example="conv_001")

class SourceCitation(BaseModel):
    document_name: str
    kb_id: str
    chunk_index: int
    similarity_score: float
    snippet: str

class ExecutionStepResponse(BaseModel):
    step_number: int
    step_name: str
    tool_name: Optional[str] = None
    input_payload: Optional[Dict[str, Any]] = None
    output_payload: Optional[Dict[str, Any]] = None
    duration_ms: float
    status: str
    error_message: Optional[str] = None
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class RunAgentResponse(BaseModel):
    execution_id: str
    agent_id: str
    conversation_id: Optional[str] = None
    answer: str
    sources: List[SourceCitation] = []
    status: str
    duration_ms: float
    prompt_file: Optional[str] = None

class ExecutionTraceResponse(BaseModel):
    execution_id: str
    agent_id: str
    conversation_id: Optional[str] = None
    query: str
    final_answer: Optional[str] = None
    status: str
    duration_ms: float
    prompt_file_path: Optional[str] = None
    created_at: datetime.datetime
    steps: List[ExecutionStepResponse] = []

    class Config:
        from_attributes = True
