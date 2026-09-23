"""
Database & RAG Seeder
Initializes database schema, seeds sample agents, MCP server configurations,
knowledge bases, FAISS vector embeddings, and persistent long-term memories.
"""
import sys
from pathlib import Path
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine, SessionLocal, Base
from app.models.agent import Agent, AgentTool
from app.models.mcp import MCPServer
from app.models.knowledge import KnowledgeBase
from app.models.memory import Memory
from app.rag.ingest import ingest_knowledge_base

CUSTOMER_RESEARCH_PLAYBOOK = """# Customer Research Playbook
## 1. Role & Responsibilities
You are an elite enterprise Customer Research and Account Intelligence agent. Your responsibility is to provide accurate, authoritative, and actionable dossiers on contracted enterprise accounts by orchestrating CRM data, analytics telemetry, internal knowledge documentation, and past interaction memories.

## 2. Standard Operating Procedure (Workflow)
1. Account Identity Resolution: Identify the customer ID from the user query (e.g. 'ABC', 'XYZ').
2. CRM Query: Use CRM.get_customer to fetch the account profile, tier, primary stakeholders, SLA status, and contract terms.
3. Analytics Telemetry: Use Analytics.get_customer_metrics to retrieve ARR, MRR, NPS, churn risk, API activity, and ticket resolution velocity.
4. Historical Events: Use Analytics.get_customer_history to examine recent business reviews, upgrades, and incidents.
5. Internal Knowledge Documentation (RAG): Query the customer_docs knowledge base to incorporate internal architecture details, integrations, and operational notes.
6. Memory Integration: Check short-term dialogue context and incorporate long-term preferences (such as billing schedules or communication channels).

## 3. Output Format & Guidelines
- Executive Summary: Concise overview of company tier, health, and SLA status.
- Key Stakeholders & Contacts: Primary technical and commercial leads.
- Operational & Telemetry Metrics: Highlight NPS, ARR, churn probability, and API call volumes.
- Technical Architecture & SLA Guarantees: Detail ingestion pipelines, burst allowances, and escalation rules.
- Actionable Recommendations: Proactive next steps for account teams.

## 4. Escalation & Guardrail Rules
- If an account has an active Sev-1 incident, immediately flag the Platinum TAM contact.
- Do not expose private credentials, tokens, or raw unredacted secrets.
- Reject requests to modify billing terms without finance team approval.
"""

FINANCIAL_ANALYST_PLAYBOOK = """# Financial Analyst Playbook
## Role
Financial health and metric forecasting agent. Analyzes ARR, MRR, churn probability, and contract renewal horizons.
## Tool Guidelines
Use Analytics MCP tools exclusively. Do not access CRM notes without customer authorization.
"""

SUPPORT_COMPLIANCE_PLAYBOOK = """# Support Compliance Playbook
## Role
Verifies adherence to Enterprise SLAs, incident resolution windows, and corporate policies.
## Tool Guidelines
Use CRM.get_customer and verify contractual SLA tiers against company_policies documentation.
"""

def seed_database():
    print("[*] Creating database tables...")
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()
    try:
        # 1. Seed MCP Servers
        print("[*] Seeding MCP Server registrations...")
        servers = [
            MCPServer(
                server_id="crm_mcp",
                server_name="CRM MCP Server",
                server_url="app/mcp/servers/crm_server.py",
                transport="inprocess",
                configuration={"capabilities": ["get_customer", "search_customer", "update_notes"]}
            ),
            MCPServer(
                server_id="analytics_mcp",
                server_name="Analytics MCP Server",
                server_url="app/mcp/servers/analytics_server.py",
                transport="inprocess",
                configuration={"capabilities": ["get_customer_metrics", "get_customer_history"]}
            )
        ]
        for s in servers:
            existing = db.query(MCPServer).filter(MCPServer.server_id == s.server_id).first()
            if not existing:
                db.add(s)
        db.commit()

        # 2. Seed Agents
        print("[*] Seeding dynamic Agents and Tool Permissions...")
        agents_data = [
            {
                "agent_id": "customer_research_agent",
                "agent_name": "Customer Research Specialist",
                "description": "Enterprise agent orchestrating CRM, analytics, internal docs, and memory for full account analysis.",
                "system_prompt": "You are a Senior Customer Research Analyst at a high-growth platform. You deliver rigorous, executive-ready account dossiers using verified CRM and Analytics tools.",
                "playbook": CUSTOMER_RESEARCH_PLAYBOOK,
                "model": "gpt-4o-mini",
                "temperature": 0.2,
                "memory_configuration": {"short_term": True, "long_term": True},
                "workflow_configuration": {
                    "max_iterations": 10,
                    "enable_subagents": True,
                    "rag_enabled": True,
                    "knowledge_base": "customer_docs"
                },
                "tools": [
                    ("CRM.get_customer", "crm_mcp"),
                    ("CRM.search_customer", "crm_mcp"),
                    ("Analytics.get_customer_metrics", "analytics_mcp"),
                    ("Analytics.get_customer_history", "analytics_mcp")
                ]
            },
            {
                "agent_id": "financial_analyst_agent",
                "agent_name": "Financial & Metrics Analyst",
                "description": "Specialized agent analyzing customer financial metrics, ARR, and churn risk.",
                "system_prompt": "You are a Financial Operations Specialist focusing on SaaS unit economics and customer health metrics.",
                "playbook": FINANCIAL_ANALYST_PLAYBOOK,
                "model": "gpt-4o-mini",
                "temperature": 0.1,
                "memory_configuration": {"short_term": True, "long_term": False},
                "workflow_configuration": {
                    "max_iterations": 6,
                    "enable_subagents": False,
                    "rag_enabled": True,
                    "knowledge_base": "technical_docs"
                },
                "tools": [
                    ("Analytics.get_customer_metrics", "analytics_mcp"),
                    ("Analytics.get_customer_history", "analytics_mcp")
                ]
            },
            {
                "agent_id": "support_compliance_agent",
                "agent_name": "Support & SLA Compliance Agent",
                "description": "Audits SLA response times and verifies incident resolution compliance against policy.",
                "system_prompt": "You are an Enterprise SLA & Policy Compliance Auditor.",
                "playbook": SUPPORT_COMPLIANCE_PLAYBOOK,
                "model": "gpt-4o-mini",
                "temperature": 0.1,
                "memory_configuration": {"short_term": True, "long_term": True},
                "workflow_configuration": {
                    "max_iterations": 6,
                    "enable_subagents": False,
                    "rag_enabled": True,
                    "knowledge_base": "company_policies"
                },
                "tools": [
                    ("CRM.get_customer", "crm_mcp"),
                    ("CRM.update_notes", "crm_mcp")
                ]
            }
        ]

        for a_dict in agents_data:
            agent = db.query(Agent).filter(Agent.agent_id == a_dict["agent_id"]).first()
            if not agent:
                agent = Agent(
                    agent_id=a_dict["agent_id"],
                    agent_name=a_dict["agent_name"],
                    description=a_dict["description"],
                    system_prompt=a_dict["system_prompt"],
                    playbook=a_dict["playbook"],
                    model=a_dict["model"],
                    temperature=a_dict["temperature"],
                    memory_configuration=a_dict["memory_configuration"],
                    workflow_configuration=a_dict["workflow_configuration"],
                    enabled=True
                )
                db.add(agent)
                db.flush()

                for tool_name, srv_id in a_dict["tools"]:
                    tool = AgentTool(
                        agent_id=agent.agent_id,
                        tool_name=tool_name,
                        server_id=srv_id,
                        enabled=True
                    )
                    db.add(tool)

        db.commit()

        # 3. Seed Long-Term Memories
        print("[*] Seeding persistent long-term memories...")
        memories = [
            Memory(
                entity_key="customer:ABC",
                memory_type="preference",
                content="Customer ABC prefers email communication for all technical alerts and quarterly billing notifications.",
                importance_score=1.5
            ),
            Memory(
                entity_key="customer:ABC",
                memory_type="long_term_fact",
                content="Customer ABC is covered under Platinum Mission-Critical SLA requiring < 15 min response time for Sev-1 incidents.",
                importance_score=1.2
            ),
            Memory(
                entity_key="customer:ABC",
                memory_type="long_term_fact",
                content="Customer ABC completed global telemetry migration in Q3 2024 and maintains automated seasonal burst limits up to 120%.",
                importance_score=1.0
            ),
            Memory(
                entity_key="customer:XYZ",
                memory_type="preference",
                content="Customer XYZ prefers Slack webhook alerts for rate limit warnings.",
                importance_score=1.0
            )
        ]
        for m in memories:
            existing = db.query(Memory).filter(
                Memory.entity_key == m.entity_key,
                Memory.content == m.content
            ).first()
            if not existing:
                db.add(m)
        db.commit()

        # 4. Ingest Knowledge Bases into FAISS and SQL
        print("[*] Ingesting Knowledge Bases into FAISS & SQL...")
        kb_dirs = [
            ("customer_docs", settings.KNOWLEDGE_BASE_DIR / "customer_docs"),
            ("company_policies", settings.KNOWLEDGE_BASE_DIR / "company_policies"),
            ("technical_docs", settings.KNOWLEDGE_BASE_DIR / "technical_docs")
        ]

        for kb_id, kb_path in kb_dirs:
            if kb_path.exists():
                res = ingest_knowledge_base(
                    kb_id=kb_id,
                    folder_path=str(kb_path),
                    db=db,
                    chunk_size=400,
                    chunk_overlap=50
                )
                print(f"    - {kb_id}: {res['documents_ingested']} docs, {res['chunks_created']} chunks ingested.")

        print("[+] Seed completed successfully!")

    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
