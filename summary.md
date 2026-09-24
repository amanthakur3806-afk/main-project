# Project Guide: Orchestrated Multi-MCP AI Agent Platform

This guide explains the project for someone new to the codebase. It describes what the application does, how a request moves through it, what the main files are responsible for, and how the libraries fit together. Read it alongside `README.md`: the README is the quick start and API reference; this file is the project map.

> **Maintenance rule:** whenever a substantial code change adds, removes, or changes a component or its connections, update this guide in the same change. Examples include a new API route, workflow stage, MCP server/tool, storage system, major dependency, or UI-to-API behavior. Small typo fixes and internal refactors that do not change the project map usually do not need an update.

## 1. What the project does

This application serves a web dashboard and REST API for specialized enterprise customer-operations agents. A user asks an agent a question. Depending on the agent and question, the application can retrieve customer or analytics records, search internal documents, load relevant conversation memory, and ask Groq to turn those results into a response. If no Groq key is configured or a Groq call fails, a deterministic local response path is available.

The project includes three example agents:

| Agent | Main purpose | Allowed data/tools | Knowledge base |
|---|---|---|---|
| `customer_research_agent` | Build a customer account summary | CRM customer/search and analytics metrics/history | `customer_docs` |
| `financial_analyst_agent` | Explain customer financial and usage health | Analytics metrics/history | `technical_docs` |
| `support_compliance_agent` | Review support, service levels, and policy | CRM customer and notes tools | `company_policies` |

These agents are configured in the database, so prompts, tool permissions, and workflow options can be changed without editing workflow code. The built-in prompts restrict agents to their customer-operations domains.

## 2. Big picture: how the pieces connect

```text
Browser (app/static) or API client
                 |
                 v
          FastAPI (app/main.py)
       /       |        |        \
   agents   knowledge  MCP     CRM/analytics data
       |
       v
 LlamaIndex agent workflow
       |
       +--> SQL database: agent config, memory, executions, traces
       +--> FAISS: relevant chunks from a selected knowledge base
       +--> MCP manager --> in-process CRM and Analytics tools
       +--> context condensation sub-agent
       +--> Groq LLM or deterministic local response engine
       |
       +--> final answer, source citations, trace, sanitized prompt log
```

There are two different kinds of data to keep in mind:

1. **Application configuration and history** live in SQLite by default: agents, permissions, knowledge-base metadata, document/chunk records, conversations, memories, and executions.
2. **Search vectors** live in the FAISS index and its metadata files under `vector_store/`. The original knowledge files live under `knowledge/`. CRM/analytics data is held by the in-process server objects, optionally loaded from files in `data/` or through the runtime data endpoints.

## 3. What happens when a user asks a question

The main execution path starts at `POST /agents/{agent_id}/run` in `app/api/agents.py` and proceeds through `app/workflow/agent_workflow.py`:

1. **Load the agent.** Read its prompt, playbook, model, memory/RAG options, and allowed tools from SQLite. A disabled or missing agent is rejected.
2. **Load context.** Load recent turns for the conversation, relevant long-term memory for a detected customer, and up to three matching chunks from the agent's configured knowledge base.
3. **Plan tools.** `llm_provider.plan_tools` maps the question to eligible CRM or analytics tool calls. The selected tools must also be permitted for this agent.
4. **Check permissions and execute.** The MCP client manager checks each planned tool against the agent's allowed-tool list, then invokes the appropriate in-process CRM or Analytics server.
5. **Condense results.** The temporary research sub-agent formats tool output into a compact summary to keep the final model context manageable.
6. **Synthesize the answer.** The response layer combines the system prompt, playbook, question, conversation history, memories, tool results, and retrieved document passages. It uses Groq when configured; otherwise it uses the local synthesis implementation. The response layer also rejects requests outside the supported customer-operations scope.
7. **Save observability and memory.** The workflow stores the answer and step-by-step execution trace in SQLite, saves the conversation turn when a conversation ID was supplied, and writes a sanitized prompt audit file under `logs/executions/`.
8. **Return the result.** The API returns the answer, execution ID, duration, status, and source citations. The execution endpoints can then show the detailed trace or prompt audit.

LlamaIndex Workflows is used to represent this as small asynchronous steps connected by typed events. The event classes in `app/workflow/events.py` define the information passed from one stage to the next.

## 3A. Detailed runtime pipeline

This section follows one request from the browser all the way to the saved response. The names below refer to the current implementation in `app/workflow/agent_workflow.py` and `app/api/`.

### Before a request: application and index startup

1. `run.py` loads `settings`, calls `seed_database()`, then starts Uvicorn with `app.main:app`.
2. Importing `app.main` creates the FastAPI application, mounts static files and registers API routers. Its lifespan also calls `seed_database()` when the server starts. In the current entry-point arrangement, running `run.py` therefore runs the seeder before Uvicorn and FastAPI lifespan runs it again.
3. `seed_database()` calls `Base.metadata.create_all()` to ensure SQL tables exist, adds any missing sample agents/MCP registrations/memories/knowledge-base records, then clears the vector index and document/chunk rows and rebuilds them from the files under `knowledge/`.
4. `ingest_knowledge_base()` extracts each supported source file, skips empty/unreadable content and unchanged content hashes, chunks text, creates local embeddings, adds vectors to FAISS, and links vector IDs back to SQL chunk records.
5. Once startup completes, the browser can load `/`, while `/docs` offers interactive API documentation. The MCP manager and the in-process CRM/Analytics server objects are available for workflow calls.

> **Startup data behavior:** the current seed routine rebuilds the indexed document/chunk data and FAISS index from `knowledge/` each time it runs. Keep source documents there (or in the registered KB folders); do not rely on the generated vector index as the only copy. The `run.py` plus FastAPI lifespan currently invokes seeding twice per normal `run.py` launch, which can add startup time because the index rebuild happens twice.

### Request path, stage by stage

```text
Browser form
   |  POST /agents/{agent_id}/run {query, conversation_id?}
   v
FastAPI validation + enabled-agent check
   v
1 Load config and create Execution record
   v AgentLoadedEvent
2 Load conversation memory + retrieve KB chunks
   v MemoryAndRAGLoadedEvent
3 Discover allowed tools + plan calls
   v ToolPlanGeneratedEvent
4 Check permissions + call CRM/Analytics tools
   v ToolsExecutedEvent
5 Condense results for context
   v ContextCondensedEvent
6 Enforce scope + assemble prompt + call Groq or local fallback
   v
7 Write sanitized prompt log + save answer/trace/conversation
   v StopEvent -> API response -> Browser renders answer and sources
```

| Stage | What happens and what data moves forward | Main implementation |
|---|---|---|
| **A. Browser submission** | `app.js` sends the selected `agent_id`, question text, and optional conversation ID as JSON. The page may also make preliminary requests to load agents and health status. | `app/static/app.js`, `app/static/index.html` |
| **B. API validation** | FastAPI parses the request into `RunAgentRequest`. The route checks that the selected agent exists and is enabled, creates a workflow, and passes the ID/question/conversation ID into it. Invalid payloads are rejected by Pydantic; missing or disabled agents produce an HTTP error. | `app/api/agents.py`, `app/schemas/execution.py` |
| **1. Load agent and begin execution** | `step_load_agent` reads the agent and enabled `AgentTool` records from SQLite. It builds a plain config dictionary containing prompt, playbook, model, temperature, memory/RAG settings, and allowed tools. It creates an `Execution` row with `running` status and records the first `ExecutionStep`. It emits an `AgentLoadedEvent` containing that config and request identifiers. | `agent_workflow.py`, `models/agent.py`, `models/execution.py`, `workflow/events.py` |
| **2a. Load short-term conversation** | If enabled and a conversation ID was supplied, `memory_manager` retrieves recent turns from SQL. This allows the current request to use recent dialogue, subject to the manager's context limit. Without an ID, there is no conversation-specific history to load. | `memory_manager.py`, `memory/store.py`, `models/memory.py` |
| **2b. Load long-term customer facts** | `extract_customer_id()` looks for an account/customer identifier in the question. When found, the workflow asks memory storage for facts associated with `customer:{ID}`; memory configuration can disable long-term memory. | `customer_identity.py`, `memory_manager.py`, `memory/store.py` |
| **2c. Retrieve document evidence (RAG)** | If RAG is enabled, the workflow reads the agent's configured `knowledge_base`, embeds the question locally, then asks the vector store for up to three similar chunks filtered to that KB. It records retrieved filenames/count in the execution trace. The resulting chunk list travels with the workflow event. | `agent_workflow.py`, `rag/embeddings.py`, `rag/vector_store.py`, `models/knowledge.py` |
| **3. Discover and plan tool calls** | The MCP manager discovers available tools and limits the list to tools allowed for this agent. `plan_tools()` inspects the query and available tools, then creates zero or more tool plans such as `CRM.get_customer` or `Analytics.get_customer_metrics`, with arguments like `customer_id`. The plan is recorded in an execution step. This planner is deterministic keyword/identity logic in the current implementation, not an LLM tool-calling loop. | `agent_workflow.py`, `llm_provider.py`, `mcp/client_manager.py` |
| **4a. Permission guard** | Before every call, the workflow checks that its exact tool name is in the agent's allowed-tool list. A disallowed call is logged as a failed trace step and is skipped. The manager repeats the permission check during execution as a second guard. | `agent_workflow.py`, `mcp/client_manager.py`, `models/agent.py` |
| **4b. Execute tool** | The manager routes CRM-prefixed tool names to the CRM server and Analytics-prefixed names to the analytics server. It applies a timeout and retry policy, then returns a structured success/error result and duration. Results are stored in execution steps and passed forward. | `mcp/client_manager.py`, `mcp/servers/crm_server.py`, `mcp/servers/analytics_server.py` |
| **5. Condense context** | If enabled for this agent, `TemporaryResearchSubAgent` turns raw tool results and knowledge chunks into concise facts. If disabled, the workflow formats the tool results directly. Both the raw results and condensed summary continue to the final stage; the raw results support local synthesis. | `workflow/subagent.py`, `workflow/agent_workflow.py` |
| **6a. Apply supported-scope rule** | `synthesize_response()` first applies `_is_supported_request()`. Out-of-scope questions receive a fixed redirect response and do not get sent to Groq or the local dossier generator. The current check is keyword-based, so its recognized customer-operations vocabulary is defined in `llm_provider.py`. | `workflow/llm_provider.py` |
| **6b. Build final model context** | For an in-scope question, the provider assembles the selected agent's system prompt and playbook, recent turns, question, relevant long-term facts, condensed tool findings, and retrieved document chunks. The model choice and temperature come from the active agent configuration (with the configured Groq model used for missing/legacy model values). | `workflow/llm_provider.py`, `models/agent.py` |
| **6c. Generate answer** | If `GROQ_API_KEY` is configured, the OpenAI SDK client sends a chat completion to Groq's OpenAI-compatible API endpoint using `GROQ_MODEL` or the selected agent model. If the key is absent or the request fails, the provider calls `_local_synthesize()` to build a deterministic answer from returned tool records, history, memory, and sources. | `workflow/llm_provider.py`, `config.py` |
| **7a. Write audit prompt** | The workflow composes an audit text containing the agent prompt/playbook, allowed tools, query, loaded context summaries, sources, tool summary, and final answer. `redact_secrets()` masks recognized credential patterns before the file is written. | `agent_workflow.py`, `config.py` |
| **7b. Persist result and conversation** | The final answer and overall status update the `Execution`; a final `ExecutionStep` is added. If a conversation ID exists, the user question and assistant response are saved for later short-term history. The workflow calculates duration and commits the transaction. | `agent_workflow.py`, `memory_manager.py`, `models/execution.py`, `models/memory.py` |
| **8. Return and display** | The workflow returns a `StopEvent` result containing answer, execution ID, status, duration, prompt-log path, and citations for retrieved chunks. The API maps this to `RunAgentResponse`; browser JavaScript renders the answer and sources. | `agent_workflow.py`, `app/api/agents.py`, `schemas/execution.py`, `app/static/app.js` |

### Knowledge document pipeline (separate from a question run)

Documents are indexed ahead of query time, rather than being converted to vectors during every question:

```text
Existing file / POST /knowledge/upload
        -> save under the selected KB folder
        -> extract text (PDF via pypdf; Markdown/text directly; DOCX XML extraction)
        -> hash text and skip unchanged document
        -> split into overlapping text chunks
        -> generate local embedding for each chunk
        -> store document/chunk metadata in SQL
        -> add vectors + source metadata to FAISS
        -> at query time, embed question and retrieve matching chunks from chosen KB
```

Supported ingestion extensions are `.md`, `.txt`, `.pdf`, and `.docx`. Although the data-loading endpoints support CSV, CSV is for CRM/analytics records; it is not included in the knowledge ingestion extension allowlist. The vector store normalizes embeddings and uses inner-product similarity (equivalent to cosine similarity for normalized vectors). SQL holds the chunk text and its vector ID; FAISS holds vectors and its metadata map supports source attribution.

### CRM and Analytics data pipeline

At startup, each in-process server attempts to load supported data files from `data/`; otherwise it uses the bundled sample records. A runtime upload/request to `/crm/data` or `/analytics/data` validates and replaces that server's active in-memory data. Later workflow calls reach these same server objects through `MCPClientManager`. These endpoint-loaded values are not automatically written to SQLite or persisted to disk by the endpoint, so restart behavior depends on the files/defaults configured for startup.

### Failure and fallback behavior

- **Unknown/disabled agent:** the API rejects the run before workflow execution.
- **No relevant tool planned:** the workflow continues with memory and retrieved documents; synthesis may report that structured CRM/analytics data was not returned.
- **Tool permission failure:** that tool call is recorded as failed and skipped; the workflow can continue with other context.
- **Tool timeout/runtime error:** the manager retries according to its small retry policy, returns a structured error, and the workflow records it.
- **No Groq key or Groq request error:** local deterministic synthesis is used.
- **Out-of-scope request:** the provider returns a redirect response before making an LLM call.
- **Unreadable/empty document:** ingestion skips it; an unreadable PDF returns no extracted text instead of indexing binary bytes.
- **Prompt audit:** the log is sanitized with regex rules, but the database trace and other application logs should still be treated as private operational data.

## 4. Project files and their responsibilities

### Root files and folders

| Path | Role and connections |
|---|---|
| `run.py` | Friendly development entry point. Seeds the database/index, prints local URLs, then starts Uvicorn. |
| `README.md` | Quick start, endpoint examples, setup notes, and abbreviated architecture. |
| `summary.md` | This deeper guide. Update it when substantial changes alter components or their connections. |
| `requirements.txt` | Pip dependency list, including runtime and development/test packages. |
| `pyproject.toml` | Python package metadata and dependency/dev configuration. Some dependency declarations also appear here; keep the two dependency lists aligned when changing packages. |
| `pytest.ini` | Pytest configuration for the repository. |
| `.env.example` | Safe template showing environment variable names. Copy to `.env` for local configuration; never share a real `.env` or API key. |
| `.env` | Local secrets and overrides (if present); loaded by `app/config.py`. It should remain private and out of source control. |
| `knowledge/` | Original documents that are ingested into the search index. Its three subfolders map to the sample agents' knowledge bases. |
| `vector_store/` | Generated FAISS index and metadata. It is derived from `knowledge/`; it can be rebuilt by seeding/re-ingesting. |
| `logs/executions/` | Generated sanitized prompt audit logs, one per execution. These are useful for debugging; treat them as application data. |
| `tests/` | Automated tests for the API, workflow, MCP execution, and RAG. |
| `data/` | Optional runtime CRM/analytics data files. The servers use supported files here when present; sample fallback data is used otherwise. |

### Application startup and configuration

| File | Role and connections |
|---|---|
| `app/main.py` | Creates the FastAPI app, initializes seed data during lifespan startup, configures CORS/static files, and mounts all API routers. `/` serves the dashboard; `/health` reports service health. |
| `app/config.py` | Reads environment variables and `.env` into the shared `settings` object. Defines host/port, database URL, Groq model/key, and storage paths; creates required storage directories. |
| `app/database.py` | Builds the SQLAlchemy engine, session factory, ORM base class, and request-scoped database dependency. Defaults to SQLite. |
| `app/seed_data.py` | Creates tables and seeds example MCP servers, agents, permissions, memories, and knowledge bases. It rebuilds document/vector data from the configured knowledge folders at startup. |

### API routes: `app/api/`

| File | Routes and responsibility |
|---|---|
| `app/api/agents.py` | Create/list/read/update agents and run an agent workflow. Calls the workflow after checking that the requested agent exists and is enabled. |
| `app/api/executions.py` | Read saved execution records, detailed step traces, and sanitized prompt audit text. |
| `app/api/knowledge.py` | List/create knowledge bases, upload supported files, and re-index a knowledge-base folder. Uploads are written under the configured KB folder and passed to the ingestion pipeline. |
| `app/api/mcp.py` | List registered MCP servers and discover their tools through the MCP manager. |
| `app/api/data.py` | Replace in-memory CRM or analytics data using JSON bodies or JSON/CSV file uploads. Exposes `POST /crm/data` and `POST /analytics/data`. |
| `app/api/__init__.py` | Marks the API folder as a Python package. |

### Agent workflow: `app/workflow/`

| File | Role and connections |
|---|---|
| `app/workflow/agent_workflow.py` | Main orchestrator. Coordinates SQL config, memory, RAG, MCP planning/execution, sub-agent condensation, answer generation, prompt logging, and execution persistence. |
| `app/workflow/events.py` | Typed LlamaIndex events carrying the agent configuration, query, context, tool plans/results, and execution ID between workflow steps. |
| `app/workflow/llm_provider.py` | Plans CRM/analytics tool calls, enforces a basic supported-request scope check, calls Groq using the OpenAI-compatible client interface, and supplies local deterministic synthesis as fallback. |
| `app/workflow/customer_identity.py` | Extracts an explicitly mentioned customer/account identifier for CRM planning and customer-specific memory lookup. |
| `app/workflow/subagent.py` | Temporary helper that condenses CRM/analytics results and document context before final synthesis. It does not persist as a separate agent. |
| `app/workflow/__init__.py` | Marks the workflow folder as a Python package. |

### MCP tools and servers: `app/mcp/`

| File | Role and connections |
|---|---|
| `app/mcp/client_manager.py` | Discovers available tools, routes tool calls to the correct server, and enforces each agent's allowed-tool permissions. |
| `app/mcp/servers/crm_server.py` | In-process CRM implementation: customer lookup/search and notes-related tools. Loads optional JSON/CSV data or uses bundled defaults. |
| `app/mcp/servers/analytics_server.py` | In-process analytics implementation: customer metrics and history tools. Loads optional JSON/CSV data or uses bundled defaults. |
| `app/mcp/__init__.py` | Marks MCP components as a Python package. |

**MCP** (Model Context Protocol) is a standard way to expose tools to an AI application. Here the CRM and Analytics servers run inside the same Python application, but the manager provides a common discovery, permission, and execution interface.

### Retrieval augmented generation: `app/rag/`

| File | Role and connections |
|---|---|
| `app/rag/ingest.py` | Reads supported text/Markdown/PDF documents, extracts text, splits it into overlapping chunks, computes embeddings, and saves chunk metadata/vectors. Called during seeding, upload, and re-indexing. |
| `app/rag/embeddings.py` | Produces local numeric vectors for text. This project does not need a remote embedding API for its current retrieval pipeline. |
| `app/rag/vector_store.py` | Adds, persists, clears, and searches vectors using FAISS where available, with a NumPy fallback. Retrieval is isolated by knowledge-base ID. |
| `app/rag/__init__.py` | Marks RAG components as a Python package. |

**RAG** means retrieval augmented generation: find relevant passages first, then include them in the model context. It helps answer questions from uploaded company documents. A document is stored as a file, indexed as chunks, matched by vector similarity at query time, and returned as a citation/source in the run response.

### Conversation memory: `app/memory/`

| File | Role and connections |
|---|---|
| `app/memory/memory_manager.py` | Chooses which recent conversation turns and long-term facts to load and coordinates saving new turns. |
| `app/memory/store.py` | Low-level SQL operations for conversations, messages, and stored memory facts. |
| `app/memory/__init__.py` | Marks memory components as a Python package. |

Short-term memory is recent dialogue associated with a conversation ID. Long-term memory contains facts/preferences that can be associated with an entity such as `customer:ABC`. The workflow loads only the context enabled in the agent's database configuration.

### Database models: `app/models/`

These files define SQLAlchemy ORM classes (Python representations of database tables). `app/seed_data.py` creates their tables through the shared `Base` in `app/database.py`.

| File | Main records |
|---|---|
| `app/models/agent.py` | `Agent` configuration and `AgentTool` permissions. |
| `app/models/mcp.py` | MCP server registration and transport/configuration metadata. |
| `app/models/knowledge.py` | Knowledge bases, source documents, and text chunks linked to vector IDs. |
| `app/models/memory.py` | Conversations, messages, and long-term memory facts. |
| `app/models/execution.py` | Overall workflow executions and individual execution steps/traces. |
| `app/models/__init__.py` | Package initializer for model definitions. |

### Request/response validation: `app/schemas/`

Pydantic models validate incoming JSON/form-derived data and shape API responses. They are separate from SQLAlchemy models: schemas describe the API contract; ORM models describe persisted tables.

| File | API data shapes |
|---|---|
| `app/schemas/agent.py` | Agent create/update/list/configuration payloads. |
| `app/schemas/execution.py` | Agent run requests, answers, citations, and execution traces. |
| `app/schemas/knowledge.py` | Knowledge-base creation, document, and ingestion responses. |
| `app/schemas/mcp.py` | MCP server and discovered-tool metadata. |
| `app/schemas/__init__.py` | Package initializer. |

### Browser interface: `app/static/`

| File | Role and connections |
|---|---|
| `app/static/index.html` | Dashboard page structure: agent picker, question form, document upload, result/source areas, and trace views. |
| `app/static/style.css` | Visual styling and responsive layout. |
| `app/static/app.js` | Browser behavior. Calls the FastAPI routes to load agents, submit questions, upload knowledge files, and display answers, sources, and execution details. |

The browser does not execute the agent itself. It calls the same REST API available to other clients. FastAPI serves these static files from `app/main.py`.

### Tests

| File | Main area covered |
|---|---|
| `tests/test_api_endpoints.py` | API routes and expected responses. |
| `tests/test_workflow_run.py` | End-to-end orchestration and persisted result behavior. |
| `tests/test_mcp_execution.py` | Tool discovery, dispatch, execution, and permission checks. |
| `tests/test_rag_retrieval.py` | Document chunking, embeddings, vector search, and knowledge-base separation. |
| `tests/__init__.py` | Marks the tests folder as a package. |

## 5. Main libraries and why they are used

The minimum versions are declared in `requirements.txt` (and most runtime dependencies are repeated in `pyproject.toml`).

| Library | Use in this project |
|---|---|
| **FastAPI** | Defines HTTP routes and application lifecycle; integrates request validation and OpenAPI/Swagger docs. |
| **Uvicorn** | ASGI web server that runs the FastAPI app. |
| **Pydantic** | Validates settings and API request/response data. `pydantic-settings` is listed for settings-related support, though the current `Settings` object reads environment variables directly. |
| **SQLAlchemy** | ORM and database sessions for SQLite-backed configuration, memory, document metadata, and execution traces. |
| **LlamaIndex Core / Workflows** | Provides the event-driven workflow structure and typed workflow steps. |
| **FAISS CPU** | Efficient vector similarity search over locally generated document embeddings. |
| **NumPy** | Numeric vector operations and fallback vector-search support. |
| **MCP** | Protocol/tool ecosystem dependency. The included CRM and Analytics implementations are in-process and are dispatched by the project's own manager. |
| **OpenAI Python SDK** (`openai`) | Used as an OpenAI-compatible HTTP client for Groq's API endpoint. It does not mean this app sends requests to OpenAI when configured for Groq. |
| **python-dotenv** | Loads local `.env` values during configuration startup. |
| **pypdf** | Extracts text from PDF files during document ingestion. |
| **python-multipart** | Parses file uploads and form fields in FastAPI routes. |
| **httpx** | HTTP client dependency used by the app ecosystem and tests. |
| **pytest / pytest-asyncio** | Test runner and async test support. These are for development/testing rather than serving user requests. |

The web interface uses plain HTML, CSS, and JavaScript; it has no separate frontend framework or frontend package manager.

## 6. Local setup and first run

1. Install Python 3.10 or newer (the README examples use Python 3.12).
2. Install packages: `py -3.12 -m pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` if needed. Set `GROQ_API_KEY` to enable live Groq responses; keep the key private. `GROQ_MODEL` defaults to `openai/gpt-oss-20b`. Without a key, the local response path is used.
4. Start the app with `py -3.12 run.py`.
5. Open the dashboard at the host/port printed in the terminal (defaults are `http://127.0.0.1:8080/`), Swagger docs at `/docs`, and health status at `/health`.

The startup seeder initializes database tables and sample records and rebuilds the document/vector index from files under `knowledge/`. Do not treat `vector_store/` as the original source of document content; keep the source files in `knowledge/`.

## 7. Useful API routes

| Route | Purpose |
|---|---|
| `GET /agents` | List configured agents. |
| `GET /agents/{agent_id}` | Read a particular agent's configuration. |
| `PUT /agents/{agent_id}/config` | Update agent prompt, playbook, model, memory/RAG settings, or allowed tools. |
| `POST /agents/{agent_id}/run` | Run an agent for a question; accepts `query` and optional `conversation_id`. |
| `GET /executions/{execution_id}` | Read the result and detailed step records. |
| `GET /executions/{execution_id}/trace` | Read a compact workflow timeline. |
| `GET /executions/{execution_id}/prompt` | Read the sanitized prompt audit log. |
| `GET /knowledge/bases` | List configured knowledge bases. |
| `POST /knowledge/upload` | Upload and index a document into a selected KB. |
| `POST /knowledge/reindex` | Re-index files in a knowledge-base folder. |
| `GET /mcp/servers`, `GET /mcp/tools` | Inspect server registrations and discovered tools. |
| `POST /crm/data`, `POST /analytics/data` | Load replacement CRM/analytics data as JSON or supported CSV/JSON file uploads. |

Swagger at `/docs` lets a newcomer inspect schemas and try these endpoints in a browser.

## 8. Where to make common changes

- **Change an agent's scope or behavior:** update the seeded prompt/playbook in `app/seed_data.py`, or update a live agent with the agent configuration API. Existing database records are not all overwritten on each startup; seed migrations intentionally update only known legacy prompts.
- **Add an HTTP endpoint:** add a route in the appropriate `app/api/` module (or create a new router), define/adjust its Pydantic schema if needed, and include the router in `app/main.py`.
- **Add a CRM or analytics capability:** implement a tool in its server module, make it discoverable through the MCP manager, plan it in `llm_provider.py`, and grant it to the relevant agents in their `AgentTool` configuration/seeding.
- **Change how questions choose tools:** edit `LLMProvider.plan_tools` in `app/workflow/llm_provider.py` and ensure the result is still constrained by the permission check in `agent_workflow.py` / `client_manager.py`.
- **Change document formats or extraction:** edit `app/rag/ingest.py`; keep uploads and re-indexing connected to that ingestion function.
- **Change retrieval behavior:** edit `app/rag/embeddings.py` or `app/rag/vector_store.py`, and keep vector metadata consistent with `DocumentChunk.vector_id` in SQLite.
- **Change what gets remembered:** edit `app/memory/memory_manager.py` and `app/memory/store.py`; database record definitions live in `app/models/memory.py`.
- **Change dashboard behavior or appearance:** edit `app/static/app.js`, `app/static/style.css`, or `app/static/index.html`.
- **Change environment configuration:** update `app/config.py` and document new variable names in `.env.example` and this guide.
- **Add/remove a major library:** update `requirements.txt`, `pyproject.toml`, and this guide's library table.

After a substantial change, update the relevant file descriptions, architecture diagram, request pipeline, API/library tables, and setup notes here so they continue to match the code.

## 9. A few implementation details to know

- **The system prompt is not the only behavior control.** The workflow also has deterministic tool-planning and supported-scope logic in `llm_provider.py`, plus tool permissions in the MCP manager. When changing agent scope, review all of these layers.
- **Prompts and permissions are data.** The database stores the active values. Editing a seed constant affects new installations and explicit legacy migrations; an administrator may have a customized value in an existing database.
- **RAG and analytics are separate.** RAG searches document passages. CRM and Analytics MCP tools return structured records. The final answer can combine both, but one does not replace the other.
- **MCP servers here are local implementations.** They are not automatically connected to a company's live CRM. Defaults are sample data; use the data endpoints or provide supported data files to replace them.
- **Execution traces are useful for debugging.** If an answer looks wrong, inspect the execution steps to see which documents were retrieved and which tools ran, then review the prompt log with care.
- **The local fallback is deterministic.** It is a safety net for development and missing/failed Groq calls, not a general language model with the same breadth as Groq.

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