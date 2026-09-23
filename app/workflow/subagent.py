"""
Temporary Sub-Agent
Handles focused sub-tasks like tool result condensation, metric analysis,
and intermediate synthesis without polluting the main agent's context budget.
"""
from typing import List, Dict, Any

class TemporaryResearchSubAgent:
    """Ephemeral sub-agent spawned for tool result condensation and anomaly analysis."""

    def __init__(self, subagent_id: str = "temp_research_subagent"):
        self.subagent_id = subagent_id

    async def condense_results(
        self,
        query: str,
        tool_results: List[Dict[str, Any]],
        knowledge_chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Condenses raw JSON tool outputs and knowledge snippets into a high-signal brief.
        """
        extracted_facts = []
        crm_summary = None
        analytics_summary = None

        for item in tool_results:
            tool_name = item.get("tool_name", "")
            res = item.get("result", {})

            if "crm" in tool_name.lower():
                if res.get("found"):
                    cust = res.get("customer", {})
                    crm_summary = (
                        f"Customer: {cust.get('company_name')} (ID: {cust.get('customer_id')}) | "
                        f"Tier: {cust.get('tier')} | SLA: {cust.get('sla_tier')} | "
                        f"Account Exec: {cust.get('account_executive')} | Contact: {cust.get('technical_contact')} | "
                        f"Contract: {cust.get('contract_value')} (Renewal: {cust.get('contract_renewal')})"
                    )
                    extracted_facts.append(crm_summary)

            elif "analytics" in tool_name.lower():
                if "metrics" in tool_name.lower() and res.get("found"):
                    metrics = res.get("metrics", {})
                    analytics_summary = (
                        f"ARR: ${metrics.get('arr'):,} | MRR: ${metrics.get('monthly_recurring_revenue'):,} | "
                        f"NPS: {metrics.get('nps_score')} | Churn Risk: {metrics.get('churn_risk_score')} (Low) | "
                        f"Active Users: {metrics.get('active_users')} | SLA Compliance: {metrics.get('sla_compliance_rate')}"
                    )
                    extracted_facts.append(analytics_summary)

                elif "history" in tool_name.lower():
                    timeline = res.get("timeline", [])
                    events_str = "; ".join([
                        f"[{e.get('date')}] {e.get('event_type')}: {e.get('details')}"
                        for e in timeline[:3]
                    ])
                    extracted_facts.append(f"Recent Timeline: {events_str}")

        condensed_text = "\n".join([f"- {fact}" for fact in extracted_facts]) if extracted_facts else "No active tool data returned."

        return {
            "subagent": self.subagent_id,
            "status": "condensed",
            "extracted_facts_count": len(extracted_facts),
            "condensed_summary": condensed_text
        }
