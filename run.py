"""
Application Runner
Entry point for starting the Orchestrated Multi-MCP AI Agent Platform.
Usage:
    python run.py
"""
import sys
import os

# Enable UTF-8 for console output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import uvicorn
from app.config import settings
from app.seed_data import seed_database

def main():
    print("=" * 75)
    print("  [+] ORCHESTRATED MULTI-MCP AI AGENT PLATFORM")
    print("=" * 75)
    print("[*] Initializing SQLite database & FAISS index...")
    seed_database()
    
    print("\n[+] System ready! Access the interfaces below:")
    print(f"    - Web Control Center UI : http://localhost:{settings.PORT}/")
    print(f"    - Swagger / OpenAPI Docs: http://localhost:{settings.PORT}/docs")
    print(f"    - Health Check Endpoint : http://localhost:{settings.PORT}/health\n")
    print("=" * 75)
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False
    )

if __name__ == "__main__":
    main()
