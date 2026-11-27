# Migration Engagements

For migration proposals, the differentiator is a clear **existing → target** picture: a service-mapping matrix, an inventory of what moves, and a per-component migration stance.

## 1. Service-Mapping Matrix (required)
Map every existing service/component to its target. This is the core artifact reviewers look for. Build it as a table:

| Existing Service / Component | Current Technology | Target Service | Target Technology | Migration Stance | Notes |
|---|---|---|---|---|---|
| Ingestion / ETL | Azure Synapse Pipelines | Data Factory in Fabric | Microsoft Fabric | Replatform | ~N pipelines re-pointed; Copy/Dataflow Gen2 |
| Raw storage | ADLS Gen2 | OneLake (Bronze) | Microsoft Fabric | Replatform | Delta format |
| Bronze/Silver/Gold | Dedicated SQL Pool | Lakehouse / Warehouse | Microsoft Fabric | Refactor | medallion preserved |
| Transformations | SQL stored procs / Spark | PySpark/SQL Notebooks | Microsoft Fabric | Refactor | reconstruct logic |
| Semantic / reporting | Power BI on Synapse | Power BI on Fabric semantic models | Microsoft Fabric | Replatform | re-point datasets |
| Governance | (none / manual) | Microsoft Purview | Purview | New | catalog/lineage |
| Secrets | Key Vault | Azure Key Vault | Azure | Rehost | unchanged |
| Monitoring | Azure Monitor | Azure Monitor / Fabric Monitor | Azure/Fabric | Rehost | unchanged |

Adapt rows to the actual source/target named in intake. Stances: **Rehost** (lift-and-shift), **Replatform** (minor changes), **Refactor** (rework logic), **Re-architect** (redesign).

## 2. Inventory tables
Quantify what migrates — this anchors effort and commercials. Capture from the SOW/requirements doc or ask:

| Artifact | Count | Complexity (L/M/H) | Approach |
|---|---|---|---|
| Pipelines | | | |
| Notebooks | | | |
| Tables / objects | | | |
| Stored procedures | | | |
| Reports / datasets | | | |
| Linked services / connections | | | |

If counts are uncertain, use the ANG "bounded baseline" pattern: state per-source object/volume baselines, note they're confirmed at a Discovery gate, and re-baseline commercials transparently if Discovery reveals material variance.

## 3. Migration scope sub-sections
- **Assessment & Discovery** — inventory validation, dependency mapping, complexity scoring, target-design confirmation, Discovery gate to freeze scope.
- **Target environment setup** — Fabric capacity, workspaces (Dev/UAT/Prod), Entra ID RBAC, networking, Key Vault, CI/CD.
- **Migration build** — per service-mapping row; pipeline/notebook re-platform/refactor; data movement into OneLake; semantic-model re-point.
- **Reconciliation & validation** — row counts/control totals, parallel-run comparison source-vs-target, exception handling, business sign-off.
- **Cutover** — go-live plan, fallback, hypercare.
- **Out of Scope / Assumptions** — source-system remediation, net-new features, license procurement, etc.

## 4. Timeline shape
Phased: Discovery & Setup → Migration Build → Reconciliation & UAT → Cutover & Closure, with RACI cells.

## 5. Solution narrative
In Solution Overview, contrast the AS-IS (existing platform from intake) with the TO-BE (target). The Component Architecture diagram should show the target-state flow; optionally include an AS-IS diagram too if the user wants both.
