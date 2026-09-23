"""
CRM MCP Server Implementation
Exposes customer relationship management tools conforming to Model Context Protocol standards.
"""
from typing import Dict, Any, List
import datetime

# Mock CRM Database
CRM_DATABASE: Dict[str, Dict[str, Any]] = {
    "ABC": {
        "customer_id": "ABC",
        "company_name": "ABC Global Logistics & Supply Inc.",
        "tier": "Enterprise Tier 1",
        "industry": "Logistics & Supply Chain",
        "status": "Active",
        "account_executive": "Sarah Jenkins",
        "technical_contact": "Dr. Marcus Vance (marcus.vance@abc-logistics.example.com)",
        "contract_value": "$450,000 / year",
        "contract_start": "2024-01-15",
        "contract_renewal": "2027-01-15",
        "sla_tier": "Platinum Mission-Critical",
        "notes": [
            "Completed global telemetry migration in Q3 2024.",
            "Quarterly billing schedule active."
        ]
    },
    "XYZ": {
        "customer_id": "XYZ",
        "company_name": "XYZ Retail Innovations Ltd.",
        "tier": "Growth Tier 2",
        "industry": "E-Commerce",
        "status": "Active",
        "account_executive": "David Kim",
        "technical_contact": "Elena Rostova (elena.rostova@xyzretail.example.com)",
        "contract_value": "$120,000 / year",
        "contract_start": "2024-06-01",
        "contract_renewal": "2025-06-01",
        "sla_tier": "Gold Standard",
        "notes": [
            "Requested rate limit review for upcoming flash sale."
        ]
    }
}

class CRMMCPServer:
    """In-process and protocol-ready CRM MCP server instance."""

    def __init__(self, server_id: str = "crm_mcp"):
        self.server_id = server_id

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return available tools and schema definitions."""
        return [
            {
                "name": "CRM.get_customer",
                "server_id": self.server_id,
                "description": "Retrieve comprehensive CRM customer profile by unique customer ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {
                            "type": "string",
                            "description": "The unique customer identifier, e.g., 'ABC' or 'XYZ'"
                        }
                    },
                    "required": ["customer_id"]
                }
            },
            {
                "name": "CRM.search_customer",
                "server_id": self.server_id,
                "description": "Search customer directory by company name, contact, or keywords.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search term to match against company name or industry"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "CRM.update_notes",
                "server_id": self.server_id,
                "description": "Append an operational note to a customer CRM record.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {
                            "type": "string",
                            "description": "Unique customer ID"
                        },
                        "note": {
                            "type": "string",
                            "description": "Note content to append"
                        }
                    },
                    "required": ["customer_id", "note"]
                }
            }
        ]

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tool with arguments and return structured result."""
        # Normalize tool name (case-insensitive and prefix-tolerant)
        name_lower = tool_name.lower().replace("crm.", "")

        if name_lower == "get_customer":
            customer_id = arguments.get("customer_id", "").strip().upper()
            if not customer_id:
                raise ValueError("Missing required argument: customer_id")
            
            customer = CRM_DATABASE.get(customer_id)
            if not customer:
                return {
                    "found": False,
                    "customer_id": customer_id,
                    "message": f"Customer '{customer_id}' not found in CRM database."
                }
            return {
                "found": True,
                "customer": customer
            }

        elif name_lower == "search_customer":
            query = arguments.get("query", "").lower()
            matches = [
                cust for cust in CRM_DATABASE.values()
                if query in cust["company_name"].lower() or query in cust["industry"].lower() or query in cust["customer_id"].lower()
            ]
            return {
                "count": len(matches),
                "results": matches
            }

        elif name_lower == "update_notes":
            customer_id = arguments.get("customer_id", "").strip().upper()
            note = arguments.get("note", "").strip()
            if customer_id not in CRM_DATABASE:
                return {"success": False, "error": f"Customer {customer_id} does not exist"}
            
            timestamp = datetime.datetime.utcnow().isoformat()
            CRM_DATABASE[customer_id]["notes"].append(f"[{timestamp}] {note}")
            return {
                "success": True,
                "customer_id": customer_id,
                "notes_count": len(CRM_DATABASE[customer_id]["notes"]),
                "last_note": CRM_DATABASE[customer_id]["notes"][-1]
            }

        else:
            raise NotImplementedError(f"Tool '{tool_name}' not implemented by CRM MCP server.")

crm_server_instance = CRMMCPServer()
