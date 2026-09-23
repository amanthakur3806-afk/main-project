import datetime
from sqlalchemy import Column, String, Boolean, DateTime, JSON, Text
from app.database import Base

class MCPServer(Base):
    __tablename__ = "mcp_servers"

    server_id = Column(String(64), primary_key=True, index=True)
    server_name = Column(String(128), nullable=False)
    server_url = Column(String(256), nullable=True)  # URL or script path
    transport = Column(String(32), default="inprocess", nullable=False)  # inprocess, stdio, sse
    configuration = Column(JSON, default=dict)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
