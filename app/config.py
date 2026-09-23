import os
from pathlib import Path
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseModel):
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))

    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")
    
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/agent_platform.db")
    
    # LLM Settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    
    # Storage Paths
    VECTOR_STORE_DIR: Path = BASE_DIR / "vector_store"
    KNOWLEDGE_BASE_DIR: Path = BASE_DIR / "knowledge"
    LOGS_DIR: Path = BASE_DIR / "logs"
    EXECUTIONS_LOG_DIR: Path = BASE_DIR / "logs" / "executions"
    
    class Config:
        arbitrary_types_allowed = True

settings = Settings()

# Ensure directories exist
settings.VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
settings.KNOWLEDGE_BASE_DIR.mkdir(parents=True, exist_ok=True)
settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)
settings.EXECUTIONS_LOG_DIR.mkdir(parents=True, exist_ok=True)
