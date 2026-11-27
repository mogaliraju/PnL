---
name: dataeng-proposal
description: "Generate AutomatonsX or Cloud4C (Part of Capgemini) Data Engineering and Analytics proposals as Word (.docx) documents for Microsoft Fabric and Azure data platforms, data lakes and lakehouses, data warehouses, ETL/ELT, Power BI, and Microsoft Purview governance. Use this skill WHENEVER the user wants to create, draft, or build a data engineering proposal, techno-commercial proposal, SOW response, or scope-of-work document for a data or analytics engagement: greenfield builds, migrations (Synapse to Fabric, on-prem to cloud, vendor transitions), assessment, and Purview setups. Trigger even when the user just says make a proposal for a client, draft a Fabric proposal, data platform SOW, or Purview proposal, or uploads a BRD/SOW to turn into one. Supports two brand formats; if the brand is not stated, ASK whether it is an AutomatonsX or Cloud4C proposal before drafting. Produces a branded doc covering Confidentiality, Intro, Scope, Solution Overview, Timelines, Commercials, and Conclusion."
license: "Proprietary. Internal use."
---

# Data Engineering & Analytics Proposal Generator

Generate polished, client-ready techno-commercial proposals for data engineering and analytics engagements, delivered as Word `.docx` files in one of two house styles: **AutomatonsX** or **Cloud4C ("Part of Capgemini")**.

This skill encodes the structure, tone, standard boilerplate, reusable architecture diagrams, and branding from real proposals. Follow the workflow below. **Do not skip the brand check or the intake interview**; a good proposal depends on getting the brand, engagement type, and inputs right first.

> All `scripts/`, `assets/`, and `references/` paths below are relative to **this skill's directory**.

---

## Workflow at a glance

1. **Pick the brand** (AutomatonsX or Cloud4C). If the request does not say which, **ask before drafting**.
2. **Classify the engagement** (greenfield / migration / assessment-completion / governance-only).
3. **Run the intake interview** based on engagement type. Read the BRD/SOW if provided.
4. **Research** any unfamiliar source systems, target services, or current pricing/SKU facts.
5. **Draft proposal content** section by section using the structure in `references/proposal_structure.md`.
6. **Generate the component-architecture diagram** fresh from the inputs (see `references/diagrams.md`).
7. **Build the `.docx`** using `scripts/build_proposal.js` with the right `brand` (see "Building the document").
8. **Validate**, then present the file.

---

## Step 0 — Pick the brand

Two brand formats are supported. **If the user has not already specified the brand** (in this request or earlier in the chat), **ask which one to use before drafting** — e.g. "Should this go out as an AutomatonsX or a Cloud4C proposal?" Do not assume a default.

- **AutomatonsX** — magenta `#C201B0` + navy `#262262`, Calibri, the AX gradient mark. Uses the AutomatonsX confidentiality/disclaimer and value-proposition boilerplate.
- **Cloud4C ("Part of Capgemini")** — royal-blue/navy palette, Arial, the Cloud4C logo. Uses the full Cloud4C intro, value levers, Gartner recognition, and certifications boilerplate.

The brand drives the cover layout, palette, fonts, logo, header/footer, and which boilerplate set to pull from. It is passed to the builder as `"brand": "automatonsx"` or `"brand": "cloud4c"` in the spec. When both could apply or the user is unsure, surface the choice rather than guessing.

---

## Step 1 — Classify the engagement

Determine which engagement type applies. Each drives a different scope shape, solution narrative, and set of intake questions:

- **Greenfield implementation** — net-new data platform (e.g. "implement a Fabric data lake from scratch"). Needs technologies + a BRD (or a brief if no BRD).
- **Migration** — moving from an existing technology/platform to a new one (e.g. Synapse → Fabric, on-prem DW → cloud, one cloud → another, or a vendor transition). Needs a requirements doc or SOW describing *what* moves *from where* *to where*. **Requires a service-mapping matrix** (existing → target) plus pipeline/object counts.
- **Assessment & completion** — an existing implementation needs review, stabilization, and finishing (the Brother International pattern: vendor handover, incomplete Gold layer, reconciliation gaps). Two-phase: rapid assessment then completion.
- **Governance-only (Purview)** — stand up data governance, cataloging, classification, lineage on an existing estate (the Medcan pattern).

If the user's request is ambiguous, ask which one it is before going further. A request can be a hybrid (e.g. greenfield platform + Purview governance) — in that case combine the relevant intake sets and scope blocks.

---

## Step 2 — Intake interview

**Always ask intake questions before drafting** unless the user has already supplied the answers (in chat or an uploaded BRD/SOW). When a BRD or SOW is attached, read it first and only ask for what's genuinely missing. Use the `ask_user_input_v0` tool for multiple-choice questions where it helps; otherwise ask concisely in prose. Keep it tight — batch related questions, don't interrogate.

### Questions for every engagement
- **Client name** and industry/sector.
- **Brand** — confirm whether this is an **AutomatonsX** or **Cloud4C ("Part of Capgemini")** proposal (this should already be settled in Step 0; carry it forward).
- **Region / data residency** (drives Azure region, e.g. UAE North, and currency — USD/CAD/etc.).
- **Document version** and author name (defaults: V1.0/V0.1, author "Srikar Mogaliraju, Principal Architect – Data Engineering"; reviewer "Amair Soofi, Principal Solution Architect" for AutomatonsX or "Krishna Kumar G, Head of Data & AI" for Cloud4C — confirm or override).
- **Data Governance** — does the engagement include setting up data governance, and **can Microsoft Purview be used** for it? (If yes, include the governance scope block and Purview components; if a different tool is mandated, note it and adapt.)
- **New/extra sections** — any sections to add beyond the standard set, e.g. **Project Governance Structure** (meeting cadence/RACI — the Brother pattern), Risk & Mitigation, Appendices (Purview roles, RACI matrix)?
- **Commercials** — include commercials now, or mark them as a separate annexure / "to follow"? Get OTC figure, any Microsoft/partner funding (AFO), managed-services option, payment milestones, and consumption-borne-by-client note if known.

### Additional questions — Greenfield
- **Target technologies** (e.g. Microsoft Fabric + OneLake + Power BI + Purview; or Azure Synapse, Databricks, etc.).
- **BRD available?** If yes, read it. If **no BRD**, gather a brief:
  - What **data sources** need to be integrated? (systems, e.g. SAP S/4HANA, Oracle, Salesforce, PeopleStrong, REST/SOAP APIs, Excel/flat files, SaaS platforms.)
  - Approx **data volume** (initial + growth) and **object/table counts** per source.
  - **Ingestion cadence** (batch / incremental / CDC / near-real-time; interval e.g. daily, 90-min).
  - **Consumption needs** — number of Power BI dashboards/reports, semantic models, mobile layouts, Copilot, self-service.
  - **Medallion scope** — full Bronze/Silver/Gold, or a Bronze-only/archive foundation with curation deferred (the ANG pattern)?
  - **Timeline** desired for implementation.
  - **Licensing** — who procures Fabric capacity / Power BI / Purview licenses (usually the client).

### Additional questions — Migration
- **Source (existing) technology** and **target technology** (e.g. Azure Synapse Dedicated SQL Pool → Microsoft Fabric Lakehouse).
- **Requirements doc / SOW** describing exactly what must migrate. Read it if provided.
- **Inventory to migrate**: number of **pipelines**, **notebooks**, tables/objects, reports/datasets, stored procedures, linked services.
- Whether a **service-mapping matrix** is needed (it almost always is) — existing service → target service mapping. Build it (see `references/migration.md`).
- **Re-platform vs refactor vs re-architect** stance per component.
- **Cutover / parallel-run** expectations, reconciliation requirements, downtime tolerance.

### Additional questions — Assessment & completion
- What's **already built** vs **incomplete** (per Bronze/Silver/Gold layer).
- Known pain points (performance, reconciliation, vendor support, technical debt).
- Whether Phase 1 is a **rapid time-boxed assessment** with Phase 2 scoped post-assessment.

### Additional questions — Governance-only (Purview)
- The **existing data estate** to govern (e.g. ~N Synapse pipelines, ADLS, SQL Pool medallion layers, Power BI).
- Which **Purview capabilities** are in scope: Data Map/scanning, classification, lineage, business glossary, sensitivity labels, insights.
- **Licensing** dependencies (e.g. M365 E5 / AIP P2 for auto-labelling) and who provides them.

After intake, briefly play back your understanding (engagement type, sources, target, scope highlights, commercials posture) and proceed.

---

## Step 3 — Research

Source-system and target-platform facts go stale. Before drafting, **search the web** for anything you're not current on, especially:
- **Microsoft Fabric SKUs & pricing** (F2…F2048, capacity units, the **F64 free-viewer threshold**, indicative monthly PAYG vs reserved). Always verify current figures rather than quoting from memory; mark commercial numbers as *indicative, subject to confirmation*.
- **Microsoft Purview** capability/licensing specifics (Data Map vs Information Protection, auto-labelling licensing).
- Unfamiliar **source systems** the client named (what they are, how data is typically extracted — APIs, CDC, connectors).
- Official cloud provider docs (`learn.microsoft.com`, Azure pricing) as the authoritative reference for service names and capabilities.

Use accurate, current service names and keep technical claims defensible.

---

## Step 4 — Draft the content

Follow **`references/proposal_structure.md`** for the full section-by-section template, required boilerplate (Confidentiality, Copyright, Intro to Cloud4C), and house writing style. The standard top-level structure is:

1. Cover page (Cloud4C logo "Part of Capgemini", "Technical Proposal" / "Techno-Commercial Proposal", client name + logo if provided, version)
2. Document Control (version table, corporate info, account manager, customer approval)
3. Confidentiality
4. Copyright
5. Introduction to Cloud4C (About us, Value Levers, Analyst Recognition, Why Cloud4C, Certifications, Azure Expertise)
6. Scope of Work → **Executive Summary**, **Objective**, **Scope** (initiation, infrastructure, integration, modelling, governance, out-of-scope, assumptions; migration adds the mapping matrix; assessment uses the two-phase shape)
7. Solution Overview → **Reference Architecture**, **Logical Architecture**, **Component Architecture & Data Flow**
8. Timelines (phased, with RACI legend)
9. Commercials (OTC, funding, optional managed services, payment plan, consumption note)
10. (Optional) Project Governance Structure, Risk & Mitigation, Appendices
11. Conclusion

Pull standard boilerplate text from `references/boilerplate.md`. That file has a **Cloud4C** set (Confidentiality, Copyright, Intro to Cloud4C, value levers, certifications) and an **AutomatonsX** set (Confidentiality & Disclaimer Statement, Value Proposition, corporate-info front matter). **Use the set that matches the chosen brand.** Tailor the Executive Summary, Objective, and Scope to the specific client and inputs — never ship generic filler, and never mix one brand's company boilerplate into the other brand's document.

For migrations, read **`references/migration.md`** for how to build the existing→target service-mapping matrix and inventory tables. For Purview governance, read **`references/purview.md`** for the standard capability blocks, scan-rule-set patterns, and licensing assumptions.

---

## Step 5 — Generate the component-architecture diagram

The **Reference Architecture** and **Logical Architecture** diagrams are standard Cloud4C assets — reuse them as-is from `assets/reference_architecture.png` and `assets/logical_architecture.png`.

The **Component Architecture & Data Flow** diagram must be **generated fresh per project** to reflect the actual sources, ingestion method, medallion layers, target services, and consumption layer from the intake. See **`references/diagrams.md`** for how to produce it (an SVG rendered to PNG) and embed it. Reflect the real source systems (e.g. SAP, Oracle, the named APIs/SaaS), the ingestion mechanism (e.g. AXConnect, Dataflow Gen2, Data Factory), OneLake/Bronze-Silver-Gold (or Bronze-only), and the consumption targets (Power BI, Excel, downstream).

---

## Building the document

Generate the `.docx` with the bundled builder. Assemble a JSON content spec and pass it to `scripts/build_proposal.js`. The builder reads `spec.brand` (`"automatonsx"` or `"cloud4c"`, default `cloud4c`) and applies the matching palette, font, logo, cover layout, header, and footer automatically. It also handles US Letter sizing, the TOC, navy-banded tables, zebra rows, and the full-page brand-coloured border.

```bash
cd {skill-dir}
npm install docx    # if not already available
node scripts/build_proposal.js spec.json /mnt/user-data/outputs/{Client}_Proposal_{vN}.docx
```

Set the brand at the top of the spec, e.g. `{ "brand": "automatonsx", "client": "...", ... }`. Read **`references/builder.md`** for the full JSON spec schema (brand field, sections, tables, images, lists, page breaks) and worked examples before writing the spec. If the builder can't express something, fall back to the docx skill's general approach (build with docx-js directly, or unpack→edit XML→repack) — but prefer the builder for consistency.

**AutomatonsX branding (when `brand: "automatonsx"`):**
- Logo `assets/automatonsx_logo.png` (the AX gradient mark): top-left on the cover, top-right in the page header.
- Thin magenta page border on every page; cover has a magenta band wrapping a light-gray title block (client name in magenta `#C201B0`, subtitle in black), then a centered "Technical Proposal to" + client + "Date: … Version …" line.
- Section headings (H1) in magenta `#C201B0`; sub-headings (H2/H3) in navy `#262262`; navy table header band; light-magenta zebra rows. Default font Calibri.
- Footer: dashed top rule, "Automatonsx | Confidential | {section}" centered, page number bottom-right. Set `"footerSection"` in the spec to control the section label (e.g. "Scope of Work").
- Front matter (built as body blocks): Corporate Information table, Account Manager Details, Prepared By, Document Version table, Confidentiality and Disclaimer Statement (references AutomatonsX), Value Proposition. Pull text from the AutomatonsX set in `references/boilerplate.md`.

**Cloud4C branding (when `brand: "cloud4c"`, the default):**
- Use the **current** logo `assets/cloud4c_logo.png` ("CLOUD4C — Part of Capgemini"). Never use the old "A CtrlS Company" mark.
- Cover title in Cloud4C blue; client logo centered below the title if provided.
- Full-page Cloud4C-blue border (logo royal blue `#0024CA`); blue header rule; navy table header band; footer "Confidential – Cloud4C & {Client}" with a Cloud4C-blue page number. Default font Arial.
- Palette: royal blue `#0024CA` (border, accents), navy `#1F3864` (sub-headings, table header band), heading blue `#0000CC` (H1 and cover title).
- Copyright line "© {year} Cloud4C. All Rights Reserved."

After building, **validate**:
```bash
python /mnt/skills/public/docx/scripts/office/validate.py /mnt/user-data/outputs/{file}.docx
```
If validation fails, unpack → fix XML → repack per the docx skill.

Then present the file with `present_files` and a one-line summary. Don't paste the whole proposal back into chat.

---

## Quality bar

- **Tailored, not templated** — Executive Summary, Objective, and Scope must speak to the specific client, sources, and goals. Reviewers should not see "CUSTOMER" placeholders or another client's name left in.
- **Defensible commercials** — label figures indicative/subject to confirmation; show OTC, any funding deduction, optional managed services, payment milestones, and who bears consumption.
- **Accurate scope boundaries** — every engagement needs explicit Out-of-Scope and Assumptions; migrations need the mapping matrix and object counts; deferred layers (Silver/Gold) must be clearly marked as future/use-case-driven if that's the chosen shape.
- **Consistent house style** — headings, table styling, logo, footer, and tone match the reference proposals.
- **Current facts** — SKUs, pricing, and service names verified via search, not memory.

## Reference files
- `references/proposal_structure.md` — full section-by-section template + writing style.
- `references/boilerplate.md` — reusable Confidentiality, Copyright, Intro to Cloud4C, medallion + solution-approach text.
- `references/builder.md` — JSON spec schema for `build_proposal.js`, with examples.
- `references/diagrams.md` — generating the per-project component-architecture diagram.
- `references/migration.md` — service-mapping matrix + inventory tables for migration engagements.
- `references/purview.md` — Purview governance capability blocks, scan rule sets, licensing assumptions.

## Assets
- `assets/automatonsx_logo.png` — AutomatonsX AX gradient mark (cover + header).
- `assets/cloud4c_logo.png` — current Cloud4C "Part of Capgemini" logo.
- `assets/reference_architecture.png` — standard enterprise data-lake reference architecture.
- `assets/logical_architecture.png` — standard logical architecture (medallion + governance + orchestration).
