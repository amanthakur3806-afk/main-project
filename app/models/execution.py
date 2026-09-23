import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Execution(Base):
    __tablename__ = "executions"

    execution_id = Column(String(64), primary_key=True, index=True)
    agent_id = Column(String(64), ForeignKey("agents.agent_id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(String(64), nullable=True, index=True)
    query = Column(Text, nullable=False)
    final_answer = Column(Text, nullable=True)
    status = Column(String(32), default="running", nullable=False)  # running, completed, failed
    duration_ms = Column(Float, default=0.0, nullable=False)
    prompt_file_path = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    agent = relationship("Agent", back_populates="executions")
    steps = relationship("ExecutionStep", back_populates="execution", cascade="all, delete-orphan", order_by="ExecutionStep.step_number")


class ExecutionStep(Base):
    __tablename__ = "execution_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_id = Column(String(64), ForeignKey("executions.execution_id", ondelete="CASCADE"), nullable=False, index=True)
    step_number = Column(Integer, nullable=False)
    step_name = Column(String(128), nullable=False)  # e.g., "load_configuration", "knowledge_search", "crm.get_customer"
    tool_name = Column(String(128), nullable=True)
    input_payload = Column(JSON, nullable=True)
    output_payload = Column(JSON, nullable=True)
    duration_ms = Column(Float, default=0.0, nullable=False)
    status = Column(String(32), default="completed", nullable=False)  # completed, failed, skipped
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    execution = relationship("Execution", back_populates="steps")
