# Orchestrated Multi-MCP AI Agent Platform

A production-grade AI agent platform that coordinates multiple **Model Context Protocol (MCP)** servers, executes tools from different servers in the same workflow, loads dynamic agent playbooks from a SQL database, retrieves domain-specific knowledge via **FAISS vector search (RAG)**, and manages both short-term and long-term memory.

Built with **FastAPI**, **LlamaIndex Workflows**, **FAISS**, and **SQLite / SQLAlchemy**.

---

## What This Platform Does (5-Minute Explanation)

Imagine you have an AI assistant that needs to answer: *"Give me a full profile of customer ABC."*

To answer well, it needs to:
1. Look up the customer in the CRM system
2. Pull their analytics metrics
3. Search internal documentation
4. Remember previous conversations
5. Combine everything into a structured report

This platform automates all of that. You send one API request, and the platform:
- Loads the agent's configuration from a database
- Connects to two MCP servers (CRM and Analytics)
- Runs a multi-step LlamaIndex Workflow
- Searches the FAISS knowledge base for relevant documents
- Passes everything through an LLM to generate the final answer
- Saves the execution trace and writes a sanitized `final_prompt.txt` audit log

---

## Architecture

```
User / Browser / Swagger
        |
        v
FastAPI REST API  (agents, executions, knowledge, mcp)
        |
        v
Agent Orchestrator  <-- loads config from SQL database
        |
        +---> LlamaIndex Workflow (10 sequential steps)
        |           |
        |           +---> MCPClientManager
        |           |         +---> CRM MCP Server  (get_customer, search_customer)
        |           |         +---> Analytics MCP Server (get_metrics, get_history)
        |           |
        |           +---> RAG Pipeline (FAISS vector search)
        |           |
        |           +---> Memory Manager (short-term + long-term)
        |           |
        |           +---> Sub-Agent (context condensation)
        |           |
        |           +---> LLM Provider (Groq or offline engine)
        |
        +---> Execution Trace  (saved to SQL)
        +---> final_prompt.txt (saved to disk, sanitized)
```

### Workflow Steps (LlamaIndex)

| Step | Action |
|------|--------|
| 1 | Load agent configuration and allowed tools from SQL |
| 2 | Load short-term memory (recent conversation turns) |
| 3 | Load long-term memory (persistent customer facts) |
| 4 | Search FAISS knowledge base (RAG retrieval) |
| 5 | Plan which MCP tools to call |
| 6 | Permission check (agent can only use allowed tools) |
| 7 | Execute tools on CRM MCP Server and Analytics MCP Server |
| 8 | Sub-agent condenses raw tool results to save LLM tokens |
| 9 | LLM synthesizes final response with all context |
| 10 | Save execution trace + write final_prompt.txt |

---

## SQL Database Schema

| Table | Purpose |
|-------|---------|
| `agents` | Agent definitions: system prompt, playbook, model, temperature, memory/workflow config |
| `agent_tools` | Allowed tools per agent (foreign key → agents) |
| `mcp_servers` | Registered MCP server metadata: URL, transport, capabilities |
| `knowledge_bases` | Knowledge base partitions with chunking configuration |
| `documents` | Ingested source files with content hash for deduplication |
| `document_chunks` | Text chunks with FAISS vector ID mapping |
| `conversations` | Dialogue sessions (foreign key → agents) |
| `messages` | Individual message turns: role, content, token count |
| `memories` | Long-term semantic facts with importance scores |
| `executions` | Top-level run records: query, answer, status, duration |
| `execution_steps` | Granular step-by-step trace: tool name, input, output, timing |

**Key relationships:**
- `agents` 1 → many `agent_tools`
- `agents` 1 → many `executions`
- `executions` 1 → many `execution_steps`
- `knowledge_bases` 1 → many `documents` → many `document_chunks`
- `document_chunks.vector_id` → FAISS index position

---

## Project Structure

```
main-project-main/
├── app/
│   ├── api/
│   │   ├── agents.py          # Agent CRUD + /run endpoint
│   │   ├── executions.py      # Execution trace + prompt audit endpoints
│   │   ├── knowledge.py       # Knowledge base upload + reindex
│   │   └── mcp.py             # MCP server and tool discovery endpoints
│   ├── mcp/
│   │   ├── client_manager.py  # Multi-server orchestration + permission guard
│   │   └── servers/
│   │       ├── crm_server.py       # Mock CRM MCP server
│   │       └── analytics_server.py # Mock Analytics MCP server
│   ├── memory/
│   │   ├── memory_manager.py  # Short-term + long-term memory coordinator
│   │   └── store.py           # SQL CRUD for conversations, messages, memories
│   ├── models/                # SQLAlchemy ORM table definitions
│   ├── rag/
│   │   ├── embeddings.py      # Local hash-based embeddings (384-dim)
│   │   ├── ingest.py          # File extraction, chunking, vectorization pipeline
│   │   └── vector_store.py    # FAISS IndexFlatIP with NumPy fallback
│   ├── schemas/               # Pydantic request/response models
│   ├── static/                # Web dashboard (HTML + CSS + JS)
│   ├── workflow/
│   │   ├── agent_workflow.py  # LlamaIndex 10-step orchestration workflow
│   │   ├── events.py          # Typed workflow event contracts
│   │   ├── llm_provider.py    # Groq or offline synthesis engine
│   │   └── subagent.py        # Ephemeral context-condensation sub-agent
│   ├── config.py              # Settings loaded from .env
│   ├── database.py            # SQLAlchemy engine + session factory
│   ├── main.py                # FastAPI application factory + CORS + routers
│   └── seed_data.py           # Database and FAISS initialization
├── knowledge/
│   ├── customer_docs/         # Customer profiles (agent: customer_research_agent)
│   ├── company_policies/      # SLA and policy documents (agent: support_compliance_agent)
│   └── technical_docs/        # API integration guides (agent: financial_analyst_agent)
├── logs/
│   └── executions/            # final_prompt.txt audit logs (generated at runtime)
├── vector_store/              # FAISS index + metadata (generated at runtime)
├── tests/
│   ├── test_api_endpoints.py  # REST API tests
│   ├── test_mcp_execution.py  # MCP tool discovery + execution tests
│   ├── test_rag_retrieval.py  # FAISS vector search + KB isolation tests
│   └── test_workflow_run.py   # End-to-end LlamaIndex workflow test
├── .env                       # Your configuration (not committed to git)
├── .env.example               # Template — copy to .env
├── requirements.txt
├── run.py                     # Application entry point
└── pytest.ini
```

---

## Setup and Installation

### Prerequisites

- Python 3.10 or newer (tested on Python 3.12)
- Windows, macOS, or Linux

### Step 1: Install Dependencies

```bash
py -3.12 -m pip install -r requirements.txt
```

### Step 2: Configure Environment

The application works fully offline without any API keys. To enable live Groq completions, edit `.env`:

```bash
# .env is already created for you. Edit if you want Groq:
GROQ_API_KEY=gsk_...your-key-here...
GROQ_MODEL=openai/gpt-oss-20b
```

### Step 3: Start the Server

```bash
py -3.12 run.py
```

This single command will:
1. Create the SQLite database (`agent_platform.db`)
2. Seed three example agents, two MCP servers, and long-term memories
3. Ingest all documents in `knowledge/` into the FAISS index
4. Start the FastAPI server at `http://localhost:8000`

### Step 4: Open the Interfaces

| Interface | URL |
|-----------|-----|
| Web Dashboard | http://localhost:8000/ |
| Swagger API Docs | http://localhost:8000/docs |
| Health Check | http://localhost:8000/health |

---

## Pre-Configured Agents

| Agent ID | Name | MCP Tools | Knowledge Base |
|----------|------|-----------|----------------|
| `customer_research_agent` | Customer Research Specialist | CRM.get_customer, CRM.search_customer, Analytics.get_customer_metrics, Analytics.get_customer_history | customer_docs |
| `financial_analyst_agent` | Financial & Metrics Analyst | Analytics.get_customer_metrics, Analytics.get_customer_history | technical_docs |
| `support_compliance_agent` | Support & SLA Compliance Agent | CRM.get_customer, CRM.update_notes | company_policies |

---

## REST API Quick Reference

### Run an Agent

```bash
curl -X POST "http://localhost:8080/agents/customer_research_agent/run" \
  -H "Content-Type: application/json" \
  -d '{"query": "Give me a complete summary of customer ABC.", "conversation_id": "demo_01"}'
```

### Get Execution Trace

```bash
curl "http://localhost:8080/executions/{execution_id}/trace"
```

### Get Prompt Audit Log

```bash
curl "http://localhost:8080/executions/{execution_id}/prompt"
```

### Update Agent Configuration (No Code Changes)

```bash
curl -X PUT "http://localhost:8080/agents/customer_research_agent/config" \
  -H "Content-Type: application/json" \
  -d '{"temperature": 0.3, "allowed_tools": ["CRM.get_customer", "Analytics.get_customer_metrics"]}'
```

### Upload a Document to Knowledge Base

```bash
curl -X POST "http://localhost:8080/knowledge/upload" \
  -F "kb_id=customer_docs" \
  -F "file=@my_document.md"
```

### Load CRM or Analytics Data

The in-process CRM and Analytics servers load `data/crm_data.json` and
`data/analytics_data.json` automatically when present. They also accept JSON
requests or UTF-8 CSV uploads at runtime. CRM CSV needs `customer_id`; analytics
CSV needs `customer_id` and `record_type` (`metrics` or `history`).

```bash
curl -X POST "http://localhost:8080/crm/data" \
  -F "file=@crm_data.csv"

curl -X POST "http://localhost:8080/analytics/data" \
  -H "Content-Type: application/json" \
  -d '{"metrics":{"LUNA":{"arr":125000,"churn_risk_score":0.72}}}'
```

---

## Running Tests

```bash
py -3.12 -m pytest -v
```

| Test File | What it Verifies |
|-----------|-----------------|
| `test_mcp_execution.py` | Tool discovery, multi-server execution (CRM + Analytics), permission guard |
| `test_rag_retrieval.py` | Chunking, embedding generation, FAISS search, KB isolation |
| `test_workflow_run.py` | End-to-end LlamaIndex workflow, final_prompt.txt, database records |
| `test_api_endpoints.py` | All REST API endpoints |

---

## Key Design Decisions

### Why LlamaIndex Workflows?
Each workflow step is an independent, typed function that receives a typed event and emits a new typed event. This means:
- Steps can be understood and debugged in isolation
- State passing is explicit (no hidden global state)
- Adding a new step does not break existing steps
- `max_iterations` prevents infinite tool-calling loops

### Why FAISS with Inner Product?
`IndexFlatIP` on L2-normalized vectors is mathematically identical to cosine similarity. This gives exact nearest-neighbor results without approximation, which is important for small-to-medium knowledge bases (< 1 million chunks).

### Why SQLite as the Default?
Zero setup, zero infrastructure — anyone can clone and run. The codebase is compatible with PostgreSQL and MySQL by changing the `DATABASE_URL` in `.env`.

### How Context is Managed
1. Short-term memory: only the last 6 turns are loaded (sliding window)
2. Long-term memory: only facts semantically relevant to the query are loaded
3. RAG: only the top-3 most similar chunks are included
4. Sub-agent condensation: raw JSON tool outputs are compressed into a concise bullet-point summary before being sent to the main LLM

### How Secrets are Protected
- All secrets are loaded from `.env` (never hard-coded)
- `final_prompt.txt` is regex-scrubbed before writing to disk (`[REDACTED_API_KEY]`, `[REDACTED_TOKEN]`)
- SQL injection is prevented by SQLAlchemy's parameterized ORM queries
- File uploads are sanitized with `Path(filename).name` to prevent path traversal
