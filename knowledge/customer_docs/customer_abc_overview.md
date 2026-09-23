# Customer ABC - Internal Account Overview & Technical Profile

## Account Metadata
- **Customer ID**: ABC
- **Company Name**: ABC Global Logistics & Supply Inc.
- **Industry**: Logistics, Freight Management, and Supply Chain Tracking
- **Tier**: Enterprise Tier 1
- **Primary Technical Contact**: Dr. Marcus Vance (marcus.vance@abc-logistics.example.com)
- **Account Executive**: Sarah Jenkins
- **Contract Term**: 36-Month Multi-Year Enterprise Agreement (Signed: 2024-01-15)

## Internal Architecture & Integration Details
Customer ABC operates a hybrid microservices infrastructure across AWS (us-east-1) and on-premises sorting warehouses.
Their core systems integrate with our platform via:
1. **Real-time Telemetry Webhooks**: Consuming 45,000 shipment events per hour.
2. **Dedicated Batch SFTP Pipeline**: Daily reconciliation run at 02:00 UTC.
3. **SSO / SAML 2.0**: Okta federated directory with automated SCIM provisioning.

## SLA & Support Requirements
- Customer ABC is covered under the **Platinum Mission-Critical SLA**.
- Required initial response time for Severity 1 incidents is under 15 minutes.
- Dedicated Technical Account Manager (TAM) assigned: Dev Patel.
- Disaster recovery RPO: 5 minutes; RTO: 30 minutes.

## Important Operational Notes & Context
- Customer ABC completed their global migration in Q3 2024.
- During high-volume seasonal spikes (October through December), automated throttling exceptions are pre-authorized for up to 120% baseline capacity.
- Billing is handled on a consolidated quarterly schedule, delivered to accounts.payable@abc-logistics.example.com.
