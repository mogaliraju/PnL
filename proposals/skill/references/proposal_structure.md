# Proposal Structure & Writing Style

This is the canonical section order and content guidance for a Data Engineering & Analytics proposal. Adapt depth to engagement type; keep the order.

**Brand note:** the section order below is shared by both brands. The cover, front matter, palette, fonts, logo, and company boilerplate differ — see Step 0 in `SKILL.md` and the matching set in `boilerplate.md`. For **Cloud4C**, sections 1–5 read as written below. For **AutomatonsX**, the cover follows the AX layout (magenta band + light-gray title block + "Technical Proposal to") and the front matter is the AutomatonsX set (Corporate Information, Account Manager, Prepared By, Document Version, Confidentiality & Disclaimer, Value Proposition); use AutomatonsX boilerplate wherever "Cloud4C" appears in 1–5.

## House writing style
- **Tone:** confident, consultative, technical-but-readable. First person plural ("Cloud4C will…", "We propose…"). Address the client by name throughout — never leave "CUSTOMER" or another client's name in.
- **Structure:** numbered headings (1, 2, 3 … with sub-levels 4.1, 4.3.1). Bullet lists for scope items, assumptions, deliverables. Tables for BoQ, commercials, timelines, mapping matrices.
- **Bold** key phrases at the start of bullets ("**Historical Data Retention & Audit Compliance** – …").
- Keep claims defensible; mark commercials and SKU sizing as *indicative, subject to confirmation following solution workshops*.
- Keep typography clean and consistent within the chosen brand.

---

## 1. Cover page
- Cloud4C logo ("Part of Capgemini") top-left.
- Large title in Cloud4C blue: **"Technical Proposal"** or **"Techno-Commercial Proposal"** (use Techno-Commercial when commercials are included).
- Client name (blue, large) + sub-title describing the engagement (e.g. "Enterprise Data Platform — Data Archival, Retention & Modernization", or "DataLake Implementation in Fabric").
- Client logo centered below the title if provided by the user.
- "Commercial Proposal | V<version>" or date line.

## 2. Document Control
- **Version table:** Version | Date | Prepared By | Designation | Reviewed By | Designation | Comments.
- **Corporate Information:** Company name (Cloud4C Services entity for the region), office address, website www.cloud4c.com.
- **Account Manager / Director Details:** name, designation, email, mobile.
- **Customer Approval and Signature** table (Customer Name | Position | Signature).

## 3. Confidentiality
Use the standard text in `boilerplate.md` (§Confidentiality), substituting the client name. Two variants exist: the ANG named-party version and the Sobha/Medcan disclaimer-statement version — either is acceptable; default to the disclaimer-statement version.

## 4. Copyright
Use `boilerplate.md` (§Copyright).

## 5. Introduction to Cloud4C
Pull from `boilerplate.md` (§Intro). Sub-sections:
- **About us** — born-in-cloud, global footprint, employee/COE stats.
- **Cloud4C Value Levers** — premier partnerships, full-lifecycle support, proven track record, proprietary AIOps (SHOP™), etc.
- **Analyst Recognition** — Gartner Visionary for Public Cloud IT Transformation Services.
- **Why choose Cloud4C** — Azure Expert MSP, AI-driven automation, hybrid/multi-cloud, business-centric SLAs.
- **Certifications, Compliance & Centre of Excellence** — ISO 27001/9001/20000-1/22301/27017/27018, PCI DSS, SOC-1/2, HIPAA/GDPR.
- **Azure Expertise** — seamless integration, single point of accountability.
- Optionally **Cloud4C Data Analytics Services Offering Overview** (Data Consulting, Data Platform Modernization, Data Engineering, Data Ops).

## 6. Scope of Work

### 6.1 Executive Summary
2–4 paragraphs, fully tailored. State the client's situation, the platform being built (target tech), the consolidation of named sources into a single foundation, the primary business driver (e.g. retention/audit, self-service analytics, governance), and the intended phasing. If using a Bronze-only/archive foundation with deferred curation, say so explicitly.

### 6.2 Objective
Bulleted list of 5–8 tailored objectives, each bolded-lead + explanation (integrate sources, establish governed lakehouse/OneLake, enable self-service analytics, governance & lineage, training, validation/monitoring, foundation for future modernization).

### 6.3 Scope
Lead sentence describing end-to-end coverage. Then sub-sections (use the set relevant to the engagement):
- **Project Initiation & Planning** — workshops, success criteria, system inventory, project plan, risks.
- **Infrastructure** — Azure subscriptions, Fabric capacity (SKU recommendation), Entra ID RBAC, networking/private endpoints, Key Vault, lake landing structure, encryption, CI/CD, audit logging.
- **Data Integration (& Archival)** — per-source ingestion approach (API, CDC, file-drop), Bronze landing, full extracts for sunsetting apps, table/field mapping repository.
- **Data Lake & Modelling** — medallion layers; if Bronze-only, mark Silver/Gold as deferred.
- **Governance & Compliance** — Purview catalog/glossary/lineage, classification, RBAC, data-quality rules, retention/legal-hold (see `purview.md`).
- **Power BI / Consumption** (greenfield BI engagements) — number of dashboards, reusable datasets, RLS, drill-through, branding, Copilot, mobile layouts.
- **Training & Knowledge Transfer** — duration, topics.
- **(Migration)** — service-mapping matrix + inventory (see `migration.md`).
- **(Assessment)** — Phase 1 assessment areas + deliverables, Phase 2 completion activities.
- **Indicative Azure BoQ** — service category | type | region | description | indicative price (USD).
- **Out of Scope** — explicit exclusions.
- **Assumptions** — client obligations, access/credentials, environments (Dev/UAT/Prod), refresh cadence, licensing procurement, CR process.
- **(Optional) Scope Basis & Extraction Boundaries** — the ANG "value-first, bounded baseline" narrative with a per-source object/volume table; good for large/uncertain estates.

## 7. Solution Overview
Lead with the **Solution Approach** paragraph + the guiding-principles table (Quality, Scalability, Maintainability, Performance, Flexibility, Robustness, Rapid Development) from `boilerplate.md`.

### 7.1 Reference Architecture
Embed `assets/reference_architecture.png`. Follow with the medallion-layer descriptions (Raw/Bronze, Integrated/Silver, Use-case/Gold, Data delivery, Job Orchestration, Traceability & reconciliation, Constraint checks, Runtime audits, Housekeeping) from `boilerplate.md`.

### 7.2 Logical Architecture
Embed `assets/logical_architecture.png`. Describe the layers tailored to this client: Data Sources, Ingestion Layer, Data Lakehouse (Storage & Transformation), Governance & Metadata Layer, Orchestration & Monitoring Layer.

### 7.3 Component Architecture & Data Flow
Embed the **freshly generated** component diagram (see `diagrams.md`). Walk through the numbered flow (Source Integration & Ingestion → OneLake → Bronze/Archive → Silver/Gold → Consumption → Security/Governance → Monitoring). Close with the architecture-layers table (Architecture Layer | Description | Components).

## 8. Timelines
Phased tables. Either a single table (Stage # | Activity | Client | Cloud4C | High-Level Timeline) or multi-phase (Discovery & Setup / Integration & Archival / Governance & Closure). Use RACI cells (R/A/C/I) and include the legend:
- R = Responsible (does the work)
- A = Accountable (owns the outcome and decision)
- C = Consulted (provides input)
- I = Informed (kept in the loop)

## 9. Commercials
- **One Time Cost (OTC)** table: Sr.No | Component | Cost Type | Cost (USD). Include any **Microsoft Funding / AFO** deducted from OTC and the net total.
- **MRC / Consumption** table when relevant (Fabric capacity SKU, Power BI Pro licenses, Purview Data Map/Scanning/Storage, VNet, Private Endpoints, Key Vault, Azure Monitor). Note consumption is borne by the client.
- **Optional Managed Services** table (monthly + 1-year total).
- **Payment Plan** (Advance % / milestone % / UAT % / closure %) and **Payment Terms** (funding note, managed-services note, invoice due days).
- Note: figures exclude local VAT/TAX unless stated.

## 10. Optional sections
- **Project Governance Structure** — meeting cadence table (Daily Huddle / Weekly Status / Bi-weekly Steering / Monthly Leadership / SOS) with duration, stakeholders, agenda.
- **Risk and Mitigation** — risk | impact | mitigation table.
- **Appendices** — Purview roles & permissions, full RACI matrix.

## 11. Conclusion
Short, warm close: thank the client, restate Cloud4C's Azure Expert MSP credentials and confidence, invite questions, sign-off (e.g. "Vice President – Sales", website). End with the standard company one-paragraph blurb and "© <year> Cloud4C. All Rights Reserved."
