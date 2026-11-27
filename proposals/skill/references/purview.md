# Microsoft Purview Data Governance

Use these blocks when the engagement includes data governance and Purview is the chosen tool (confirmed in intake). Tailor counts and layers to the client's estate.

## Capability blocks (in-scope services)
Organize Purview scope into **Cataloging Services** (business-facing) and **Supporting Governance Services** (foundation).

### Cataloging Services
- **Business Glossary** — shared business vocabulary; formally defined terms (description, acronym, examples, related terms), term templates, acronym registry, domain hierarchy. State a target term count (e.g. 200+) as a planning target contingent on client SME input.
- **Manual Classification & Catalog Curation (Managed Attributes)** — structured mechanism for Data Stewards/Domain Owners to apply governed classification, descriptions, and tags to assets automated scanners can't interpret (opaque column names, legacy flat files, composite fields).
- **Catalog Discovery & Searchable Inventory** — assets discoverable by name, type, classification, sensitivity label, or glossary term.

### Supporting Governance Services
- **Data Map — Source Registration & Scanning** — register all sources with scan rule sets. Table: Source | Method | Configuration | Frequency. Use MSI integration; least-privilege grants (db_datareader etc.). Distinguish native time-based scheduling (full weekly / incremental daily) from custom "on-pipeline-completion" triggers (= custom orchestration via scan API, treated as custom effort).
- **Automated Data Classification** — built-in + custom rule sets (PII, Financial, Health/PHI, custom business terms) applied at scan time; tag + sensitivity-label assignment.
- **End-to-End Data Lineage** — pipeline lineage (native integration emits per-run events), SQL stored-proc/script lineage (table-level; custom lineage API where parsing unavailable), Power BI lineage (dataset→view/table; partial column-level). Be explicit about lineage limitations for Data Flows, Spark/notebook activities, and SPs.
- **Sensitivity Labels** — taxonomy (Public, Internal, Confidential, Highly Confidential); auto-labelling rules; Power BI label inheritance & export restriction. **Licensing dependency:** auto-labelling requires M365 E5 / E5 Compliance / AIP P2, per user. Client confirms licenses. If not provisioned, deliver the equivalent via classification & tagging (visibility without active enforcement) — note active enforcement would be a CR.
- **Insights & Data Estate Reporting** — Asset, Classification, Glossary, Lineage, Scan insights dashboards.

## Scan rule sets (per layer) — pattern
- **Bronze:** include all tables in [bronze] schema; exclude system tables; classify all columns; capture view definitions.
- **Silver:** include [silver] tables & views; map view lineage to bronze; classify; capture SP definition text.
- **Gold:** include [gold] schema & reporting views; max classification sensitivity; auto-assign glossary terms where column names match synonyms.
- Exclude `dbo.sysdiagrams`, `sys.*`.

## Technical implementation architecture
- **Account:** Microsoft Purview (unified governance portal), same region as data sources.
- **Identity:** system-assigned Managed Identity (Purview MSI) for source auth; no stored credentials.
- **Connectivity:** Managed VNet IR or Self-Hosted IR (one pattern per source), confirmed in foundation phase.
- **Auth/RBAC table:** Source | Permission | How to Grant | Principal (least privilege).

## Standard assumptions & dependencies
- Sources in same Entra ID tenant; Synapse supports native Purview integration.
- SQL Pool running during scan windows (paused pool fails scans).
- Client provisions RBAC, SQL grants, Power BI admin consent, app registrations timely.
- Power BI workspaces on Premium / PPU and reachable via read-only admin APIs.
- Greenfield Purview (no pre-existing config to rationalize) unless stated.
- Client provides custom classification inputs (regex, exclusions) and approved glossary content.
- E5/AIP P2 licensing confirmed before enabling auto-labelling.

## Out of Scope (typical)
Access-control/RLS implementation, sensitivity-label enforcement beyond licensing, remediation of source data quality, custom connector development beyond stated APIs.

## Appendices to offer
- **Appendix A — Purview Roles & Minimum Permissions Summary**
- **Appendix B — RACI Matrix**
