"""
LlamaIndex Workflow Orchestrator
Coordinates multi-stage agent execution:
Start -> Load Agent -> Memory & RAG -> Tool Planning -> Permission Guard
-> Multi-MCP Tool Execution -> Sub-Agent Condensation -> Context Management
-> LLM Synthesis -> Final Prompt Audit Logging -> Save State -> Stop
"""
import os
import re
import time
import uuid
from typing import Dict, Any, List, Optional
from pathlib import Path

from llama_index.core.workflow import Workflow, step, StartEvent, StopEvent
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.agent import Agent, AgentTool
from app.models.execution import Execution, ExecutionStep
from app.mcp.client_manager import mcp_client_manager, ToolPermissionError
from app.rag.embeddings import embeddings_provider
from app.rag.vector_store import vector_store
from app.memory.memory_manager import memory_manager
from app.workflow.subagent import TemporaryResearchSubAgent
from app.workflow.llm_provider import llm_provider
from app.workflow.events import (
    AgentLoadedEvent,
    MemoryAndRAGLoadedEvent,
    ToolPlanGeneratedEvent,
    ToolsExecutedEvent,
    ContextCondensedEvent
)

def redact_secrets(text: str) -> str:
    """Scrub sensitive credentials, passwords, or API keys from logs and prompt files."""
    patterns = [
        (r'sk-[a-zA-Z0-9]{20,}', '[REDACTED_OPENAI_KEY]'),
        (r'Bearer\s+[a-zA-Z0-9_\-\.]{20,}', 'Bearer [REDACTED_TOKEN]'),
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'password="[REDACTED]"'),
        (r'secret["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'secret="[REDACTED]"')
    ]
    for pattern, repl in patterns:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    return text

class AgentOrchestratorWorkflow(Workflow):
    """
    Enterprise LlamaIndex Workflow orchestrating dynamic multi-MCP agents.
    """

    @step
    async def step_load_agent(self, ev: StartEvent) -> AgentLoadedEvent:
        """Step 1 & 2: Load agent configuration and permissions from SQL database."""
        t0 = time.time()
        agent_id = ev.get("agent_id")
        query = ev.get("query")
        conversation_id = ev.get("conversation_id")
        execution_id = ev.get("execution_id", f"exec_{uuid.uuid4().hex[:12]}")

        db: Session = SessionLocal()
        try:
            agent = db.query(Agent).filter(Agent.agent_id == agent_id, Agent.enabled == True).first()
            if not agent:
                raise ValueError(f"Agent with ID '{agent_id}' not found or disabled.")

            # Load allowed tools
            allowed_tools = [t.tool_name for t in agent.tools if t.enabled]

            agent_config = {
                "agent_id": agent.agent_id,
                "agent_name": agent.agent_name,
                "description": agent.description,
                "system_prompt": agent.system_prompt,
                "playbook": agent.playbook,
                "model": agent.model,
                "temperature": agent.temperature,
                "memory_configuration": agent.memory_configuration or {},
                "workflow_configuration": agent.workflow_configuration or {},
                "allowed_tools": allowed_tools
            }

            # Create Execution record in DB
            execution_rec = Execution(
                execution_id=execution_id,
                agent_id=agent_id,
                conversation_id=conversation_id,
                query=query,
                status="running"
            )
            db.add(execution_rec)

            # Log Step 1 in trace
            step_rec = ExecutionStep(
                execution_id=execution_id,
                step_number=1,
                step_name="load_agent_configuration",
                input_payload={"agent_id": agent_id},
                output_payload={"agent_name": agent.agent_name, "allowed_tools": allowed_tools},
                duration_ms=round((time.time() - t0) * 1000, 2),
                status="completed"
            )
            db.add(step_rec)
            db.commit()

        finally:
            db.close()

        return AgentLoadedEvent(
            agent_id=agent_id,
            agent_config=agent_config,
            query=query,
            conversation_id=conversation_id,
            execution_id=execution_id
        )

    @step
    async def step_load_memory_and_rag(self, ev: AgentLoadedEvent) -> MemoryAndRAGLoadedEvent:
        """Step 3: Retrieve short-term dialogue, semantic long-term memory, and FAISS RAG context."""
        t0 = time.time()
        agent_cfg = ev.agent_config
        db: Session = SessionLocal()
        retrieved_chunks = []
        short_term_history = []
        long_term_facts = []

        try:
            # 1. Memory loading
            mem_cfg = agent_cfg.get("memory_configuration", {})
            if mem_cfg.get("short_term", True) or mem_cfg.get("long_term", True):
                mem_data = memory_manager.load_memory_context(
                    db=db,
                    conversation_id=ev.conversation_id,
                    query=ev.query,
                    entity_key="customer:ABC"  # Default entity match
                )
                if mem_cfg.get("short_term", True):
                    short_term_history = mem_data["short_term_history"]
                if mem_cfg.get("long_term", True):
                    long_term_facts = mem_data["long_term_facts"]

            # 2. Knowledge Base RAG via FAISS
            wf_cfg = agent_cfg.get("workflow_configuration", {})
            if wf_cfg.get("rag_enabled", True):
                target_kb = wf_cfg.get("knowledge_base", "customer_docs")
                q_vec = embeddings_provider.get_embedding(ev.query)
                retrieved_chunks = vector_store.search(
                    query_vector=q_vec,
                    top_k=3,
                    kb_id=target_kb
                )

            # Record step in trace
            step_rec = ExecutionStep(
                execution_id=ev.execution_id,
                step_number=2,
                step_name="memory_and_rag_retrieval",
                input_payload={"query": ev.query, "kb_id": wf_cfg.get("knowledge_base")},
                output_payload={
                    "short_term_turns": len(short_term_history),
                    "long_term_facts_count": len(long_term_facts),
                    "rag_chunks_retrieved": len(retrieved_chunks),
                    "sources": [c["filename"] for c in retrieved_chunks]
                },
                duration_ms=round((time.time() - t0) * 1000, 2),
                status="completed"
            )
            db.add(step_rec)
            db.commit()

        finally:
            db.close()

        return MemoryAndRAGLoadedEvent(
            agent_id=ev.agent_id,
            agent_config=agent_cfg,
            query=ev.query,
            conversation_id=ev.conversation_id,
            execution_id=ev.execution_id,
            short_term_history=short_term_history,
            long_term_facts=long_term_facts,
            retrieved_chunks=retrieved_chunks
        )

    @step
    async def step_plan_tools(self, ev: MemoryAndRAGLoadedEvent) -> ToolPlanGeneratedEvent:
        """Step 4: Tool Planning across registered MCP servers."""
        t0 = time.time()
        agent_cfg = ev.agent_config
        allowed_tools = agent_cfg.get("allowed_tools", [])

        # Get discovered tools permitted for this agent
        permitted_tools = await mcp_client_manager.get_tools_for_agent(allowed_tools)

        # Generate tool plan
        planned_tools = llm_provider.plan_tools(
            query=ev.query,
            available_tools=permitted_tools,
            knowledge_chunks=ev.retrieved_chunks
        )

        db: Session = SessionLocal()
        try:
            step_rec = ExecutionStep(
                execution_id=ev.execution_id,
                step_number=3,
                step_name="tool_planning",
                input_payload={"available_tools_count": len(permitted_tools)},
                output_payload={"planned_tools": planned_tools},
                duration_ms=round((time.time() - t0) * 1000, 2),
                status="completed"
            )
            db.add(step_rec)
            db.commit()
        finally:
            db.close()

        return ToolPlanGeneratedEvent(
            agent_id=ev.agent_id,
            agent_config=agent_cfg,
            query=ev.query,
            conversation_id=ev.conversation_id,
            execution_id=ev.execution_id,
            short_term_history=ev.short_term_history,
            long_term_facts=ev.long_term_facts,
            retrieved_chunks=ev.retrieved_chunks,
            planned_tools=planned_tools
        )

    @step
    async def step_execute_tools(self, ev: ToolPlanGeneratedEvent) -> ToolsExecutedEvent:
        """Step 5 & 6: Permission Check and Multi-MCP Tool Execution (CRM + Analytics)."""
        agent_cfg = ev.agent_config
        allowed_tools = agent_cfg.get("allowed_tools", [])
        tool_results = []
        db: Session = SessionLocal()

        current_step_num = 4
        try:
            for plan in ev.planned_tools:
                t0 = time.time()
                tool_name = plan["tool_name"]
                arguments = plan.get("arguments", {})

                # Step 5: Explicit Agent-Level Permission Check
                is_permitted = mcp_client_manager.check_tool_permission(tool_name, allowed_tools)
                if not is_permitted:
                    err_msg = f"Permission Denied: Agent '{ev.agent_id}' is not authorized to execute tool '{tool_name}'."
                    step_rec = ExecutionStep(
                        execution_id=ev.execution_id,
                        step_number=current_step_num,
                        step_name=f"permission_check_failed:{tool_name}",
                        tool_name=tool_name,
                        input_payload=arguments,
                        output_payload={"error": err_msg},
                        duration_ms=round((time.time() - t0) * 1000, 2),
                        status="failed",
                        error_message=err_msg
                    )
                    db.add(step_rec)
                    db.commit()
                    current_step_num += 1
                    continue

                # Step 6: Multi-MCP Execution
                res = await mcp_client_manager.execute_tool(
                    tool_name=tool_name,
                    arguments=arguments,
                    allowed_tools=allowed_tools
                )
                tool_results.append(res)

                step_rec = ExecutionStep(
                    execution_id=ev.execution_id,
                    step_number=current_step_num,
                    step_name=f"execute_mcp_tool:{tool_name}",
                    tool_name=tool_name,
                    input_payload=arguments,
                    output_payload=res.get("result", {"error": res.get("error")}),
                    duration_ms=res.get("duration_ms", 0.0),
                    status="completed" if res.get("success") else "failed",
                    error_message=res.get("error")
                )
                db.add(step_rec)
                db.commit()
                current_step_num += 1

        finally:
            db.close()

        return ToolsExecutedEvent(
            agent_id=ev.agent_id,
            agent_config=agent_cfg,
            query=ev.query,
            conversation_id=ev.conversation_id,
            execution_id=ev.execution_id,
            short_term_history=ev.short_term_history,
            long_term_facts=ev.long_term_facts,
            retrieved_chunks=ev.retrieved_chunks,
            tool_results=tool_results
        )

    @step
    async def step_subagent_and_context(self, ev: ToolsExecutedEvent) -> ContextCondensedEvent:
        """Step 7: Temporary Sub-Agent Result Condensation & Context Management."""
        t0 = time.time()
        agent_cfg = ev.agent_config
        wf_cfg = agent_cfg.get("workflow_configuration", {})

        condensed_summary = ""
        if wf_cfg.get("enable_subagents", True):
            subagent = TemporaryResearchSubAgent()
            subagent_res = await subagent.condense_results(
                query=ev.query,
                tool_results=ev.tool_results,
                knowledge_chunks=ev.retrieved_chunks
            )
            condensed_summary = subagent_res["condensed_summary"]
        else:
            # Fallback direct string formatting
            condensed_summary = "\n".join([f"Tool {r['tool_name']}: {r.get('result')}" for r in ev.tool_results])

        db: Session = SessionLocal()
        try:
            # Step in trace
            step_rec = ExecutionStep(
                execution_id=ev.execution_id,
                step_number=6,
                step_name="subagent_context_condensation",
                input_payload={"raw_tools_count": len(ev.tool_results)},
                output_payload={"summary_length": len(condensed_summary)},
                duration_ms=round((time.time() - t0) * 1000, 2),
                status="completed"
            )
            db.add(step_rec)
            db.commit()
        finally:
            db.close()

        return ContextCondensedEvent(
            agent_id=ev.agent_id,
            agent_config=agent_cfg,
            query=ev.query,
            conversation_id=ev.conversation_id,
            execution_id=ev.execution_id,
            short_term_history=ev.short_term_history,
            long_term_facts=ev.long_term_facts,
            retrieved_chunks=ev.retrieved_chunks,
            condensed_tool_summary=condensed_summary,
            raw_tool_results=ev.tool_results
        )

    @step
    async def step_synthesize_and_save(self, ev: ContextCondensedEvent) -> StopEvent:
        """Step 8, 9, 10, 11: LLM Synthesis, final_prompt.txt Audit Logging, DB State Persistence, and StopEvent."""
        t0 = time.time()
        agent_cfg = ev.agent_config

        # 1. Synthesize final answer
        final_answer = llm_provider.synthesize_response(
            agent_name=agent_cfg["agent_name"],
            system_prompt=agent_cfg["system_prompt"],
            playbook=agent_cfg["playbook"],
            query=ev.query,
            short_term_history=ev.short_term_history,
            long_term_facts=ev.long_term_facts,
            condensed_tool_summary=ev.condensed_tool_summary,
            retrieved_chunks=ev.retrieved_chunks,
            model=agent_cfg.get("model", "gpt-4o-mini"),
            temperature=agent_cfg.get("temperature", 0.2)
        )

        # 2. Build and write final_prompt.txt (sanitized audit log)
        prompt_log_file = settings.EXECUTIONS_LOG_DIR / f"{ev.execution_id}_prompt.txt"
        
        prompt_content = f"""================================================================================
ORCHESTRATED MULTI-MCP AGENT EXECUTION AUDIT LOG
Execution ID: {ev.execution_id}
Agent ID:     {ev.agent_id} ({agent_cfg['agent_name']})
Model:        {agent_cfg.get('model', 'gpt-4o-mini')} | Temperature: {agent_cfg.get('temperature', 0.2)}
Timestamp:    {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}
================================================================================

[AGENT SYSTEM PROMPT]
{agent_cfg['system_prompt']}

[AGENT PLAYBOOK]
{agent_cfg['playbook']}

[ALLOWED MCP TOOLS]
{agent_cfg.get('allowed_tools', [])}

[USER QUERY]
{ev.query}

[SHORT-TERM CONVERSATION TURNS]
{ev.short_term_history}

[LONG-TERM RETRIEVED MEMORY FACTS]
{ev.long_term_facts}

[RAG KNOWLEDGE BASE CHUNKS]
{[f"File: {c['filename']} (score: {c['score']})" for c in ev.retrieved_chunks]}

[TOOL CALLS & RESULTS]
{ev.condensed_tool_summary}

[FINAL SYNTHESIZED ANSWER]
{final_answer}
================================================================================
"""
        sanitized_prompt_log = redact_secrets(prompt_content)
        with open(prompt_log_file, "w", encoding="utf-8") as f:
            f.write(sanitized_prompt_log)

        # 3. Update Database Records
        db: Session = SessionLocal()
        total_duration_ms = 0.0
        try:
            # Log final synthesis step
            synth_step = ExecutionStep(
                execution_id=ev.execution_id,
                step_number=7,
                step_name="llm_final_synthesis",
                input_payload={"model": agent_cfg.get("model")},
                output_payload={"answer_preview": final_answer[:150] + "..."},
                duration_ms=round((time.time() - t0) * 1000, 2),
                status="completed"
            )
            db.add(synth_step)

            # Update overall Execution record
            exec_rec = db.query(Execution).filter(Execution.execution_id == ev.execution_id).first()
            if exec_rec:
                exec_rec.final_answer = final_answer
                exec_rec.status = "completed"
                exec_rec.prompt_file_path = str(prompt_log_file)
                # Compute total duration across all steps
                all_steps = db.query(ExecutionStep).filter(ExecutionStep.execution_id == ev.execution_id).all()
                total_duration_ms = sum(s.duration_ms for s in all_steps)
                exec_rec.duration_ms = round(total_duration_ms, 2)

            # Save conversation turn in memory
            if ev.conversation_id:
                memory_manager.save_turn(
                    db=db,
                    conversation_id=ev.conversation_id,
                    agent_id=ev.agent_id,
                    user_query=ev.query,
                    assistant_response=final_answer
                )

            db.commit()

        finally:
            db.close()

        # Format Source Citations
        sources = [
            {
                "document_name": c["filename"],
                "kb_id": c["kb_id"],
                "chunk_index": c["chunk_index"],
                "similarity_score": c["score"],
                "snippet": c["content"][:200] + "..."
            }
            for c in ev.retrieved_chunks
        ]

        return StopEvent(
            result={
                "execution_id": ev.execution_id,
                "agent_id": ev.agent_id,
                "conversation_id": ev.conversation_id,
                "answer": final_answer,
                "sources": sources,
                "status": "completed",
                "duration_ms": round(total_duration_ms, 2),
                "prompt_file": str(prompt_log_file)
            }
        )

# Factory helper
def create_agent_workflow() -> AgentOrchestratorWorkflow:
    return AgentOrchestratorWorkflow(timeout=60.0)
