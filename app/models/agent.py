import datetime
from sqlalchemy import Column, String, Float, Boolean, DateTime, Text, JSON, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Agent(Base):
    __tablename__ = "agents"

    agent_id = Column(String(64), primary_key=True, index=True)
    agent_name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    system_prompt = Column(Text, nullable=False)
    playbook = Column(Text, nullable=False)
    model = Column(String(64), default="gpt-4o-mini", nullable=False)
    temperature = Column(Float, default=0.2, nullable=False)
    memory_configuration = Column(JSON, default=lambda: {"short_term": True, "long_term": True})
    workflow_configuration = Column(JSON, default=lambda: {"max_iterations": 10, "enable_subagents": True, "rag_enabled": True, "knowledge_base": "customer_docs"})
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    tools = relationship("AgentTool", back_populates="agent", cascade="all, delete-orphan")
    executions = relationship("Execution", back_populates="agent", cascade="all, delete-orphan")


class AgentTool(Base):
    __tablename__ = "agent_tools"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String(64), ForeignKey("agents.agent_id", ondelete="CASCADE"), nullable=False, index=True)
    tool_name = Column(String(128), nullable=False, index=True)
    server_id = Column(String(64), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    agent = relationship("Agent", back_populates="tools")
