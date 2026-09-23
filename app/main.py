"""
FastAPI Application Entry Point
Orchestrated Multi-MCP AI Agent Platform
"""
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.agents import router as agents_router
from app.api.executions import router as executions_router
from app.api.knowledge import router as knowledge_router
from app.api.mcp import router as mcp_router
from app.seed_data import seed_database

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database and seed data are ready on boot
    seed_database()
    yield

app = FastAPI(
    title="Orchestrated Multi-MCP AI Agent Platform",
    description="""
Enterprise AI agent platform coordinating multiple Model Context Protocol (MCP) servers,
LlamaIndex Workflows, dynamic agent-level permissions, FAISS vector search, and dual-tier memory.
    """,
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for open API usage
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Files
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include API Routers
app.include_router(agents_router)
app.include_router(executions_router)
app.include_router(knowledge_router)
app.include_router(mcp_router)

@app.get("/", include_in_schema=False)
def serve_dashboard():
    """Serve the Web Control Center UI."""
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": "Orchestrated Multi-MCP Agent Platform",
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)

