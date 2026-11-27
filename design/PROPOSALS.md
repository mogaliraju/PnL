# Presales PnL: proposal generation spec (PROPOSALS.md)

Version 1.0, 27 Nov 2026. Owner: Srikar Mogaliraju, AutomatonsX.

This file is the build spec for adding proposal generation to the PnL application. It is written for Claude Code in VS Code. Put it at `design/PROPOSALS.md` and add one line to `CLAUDE.md`:

```
Before working on proposal generation, read design/PROPOSALS.md. Section 2 of design/DESIGN.md (data safety) still overrides everything.
```

---

## 1. What we are building

A user opens a saved project version, clicks **Generate proposal**, fills a short form and gets a branded Word proposal (AutomatonsX or Cloud4C) a minute or two later. The proposal's commercials match that PnL version exactly.

The intelligence comes from the `dataeng-proposal` Claude skill, bundled in `proposals/skill/` unchanged. Claude Opus 4.6 on Amazon Bedrock writes the client-specific content. Everything else (boilerplate, front matter, commercials, layout) is produced by code so it is identical every time.

```
Form (intake) ──┐
                ├─> generator.py ──Bedrock Converse──> Opus 4.6 ──> content JSON (validated)
PnL version ────┤                                                        │
                │                                                        v
                └─> commercials_from_pnl() ──> commercials JSON ──> assemble.py ──> spec JSON
                                                                         │
                                         gen_component_diagram.py <──────┤
                                                                         v
                                                     node build_proposal.js ──> .docx
```

### Division of work (do not change this)

| Part of the document | Written by |
|---|---|
| Cover, document control tables, confidentiality, copyright, Cloud4C intro or AX value proposition | `boilerplate.json` via `assemble.py` |
| Guiding principles, reference and logical architecture images, layer descriptions | `boilerplate.json` + `skill/assets` |
| Executive summary, objectives, scope, out of scope, assumptions, mapping matrix, inventory, logical architecture text, data flow, timeline, risks, governance cadence, conclusion | Model (Opus 4.6) |
| Component architecture diagram | Model picks the boxes, `gen_component_diagram.py` draws it |
| Commercials (OTC, funding, managed services, payment plan, terms) | `commercials_from_pnl()` from `pnl/engine.py` |

The model never sees or writes a price. The schema in `proposals/content_schema.json` has no field for one.

---

## 2. What is in this bundle

```
proposals/
  __init__.py
  skill/                      dataeng-proposal skill, verbatim (SKILL.md, references, scripts, assets incl. both logos)
  boilerplate.json            AX and Cloud4C boilerplate extracted from skill/references/boilerplate.md
  content_schema.json         JSON schema for model output (also the Bedrock tool input schema)
  prompts/system_prompt.md    SKILL.md rewritten for an API model (no tool, file or ask-the-user steps)
  generator.py                Bedrock Converse call, forced tool output, jsonschema validation, one retry
  assemble.py                 boilerplate + content + commercials -> builder spec; renders diagram and docx
  samples/
    automatonsx/              Crestline Realty (fictional), greenfield Fabric + Purview, 16 weeks
    cloud4c/                  Meridian Logistics (fictional), Synapse to Fabric migration, 20 weeks
      intake.json             what the form sends
      commercials.json        what commercials_from_pnl() must return
      content.json            a model output that passes the schema
      spec.json               assembled builder spec
      component_arch.png      generated diagram
      *_Proposal_V0.1.docx    final document (open these to see the target result)
tests/test_proposals.py       offline tests (schema, house style, both samples build)
Dockerfile                    Python 3.12 + Node + cairo, for Render
package.json                  pins docx 9.8.1 for the builder
requirements-proposals.txt    lines to append to requirements.txt
```

Run `python -m proposals.assemble proposals/samples/automatonsx` from the repo root to rebuild a sample. It works offline.

---

## 3. Render setup

1. Open the Render shell for `pnl-automatonsx` and run `node --version`. If Node is missing (expected on the native Python runtime), switch the service to Docker using the bundled `Dockerfile`. Keep the existing start command in its `CMD`.
2. Append `requirements-proposals.txt` to `requirements.txt`. Add `package.json` to the repo root.
3. Environment variables (Render > Environment, never in code):

| Variable | Value |
|---|---|
| `AWS_BEARER_TOKEN_BEDROCK` | existing Bedrock API key |
| `AWS_REGION` | `ap-south-1` |
| `BEDROCK_PROPOSAL_MODEL_ID` | Opus 4.6 model id or APAC/global inference profile id, copied from the Bedrock console |
| `BEDROCK_CHAT_MODEL_ID` | Sonnet 4.5 id for the PnL assistant (see DESIGN.md section 9) |

4. Confirm model access for Opus 4.6 in Bedrock > Model access before the first run.

---

## 4. Data model (additive only)

Follow DESIGN.md section 2: backup first, Alembic migration that only creates, no change to existing tables.

```
proposal(
  id               serial primary key,
  project_id       int not null references project(id),
  version_no       int not null,
  brand            text not null check (brand in ('automatonsx','cloud4c')),
  engagement_type  text not null,
  status           text not null default 'queued',   -- queued | running | ready | failed
  intake           jsonb not null,
  commercials      jsonb,
  content          jsonb,
  spec             jsonb,
  docx             bytea,                             -- Render disk is ephemeral, keep the file in Postgres
  filename         text,
  model_id         text,
  input_tokens     int,
  output_tokens    int,
  error            text,
  created_by       int references "user"(id),
  created_at       timestamptz default now(),
  finished_at      timestamptz
)
index on (project_id, version_no, created_at desc)
```

Generated proposals are never deleted by the app. Regenerating creates a new row.

---

## 5. Backend

### 5.1 `commercials_from_pnl(project_id, version_no) -> dict`

New function in `pnl/proposal_commercials.py`. It loads the saved version, runs `pnl/engine.py` and returns exactly the shape in `samples/*/commercials.json`:

- `currency`, `source` (project, version_no, rate card)
- `duration_weeks` and `team` (role, count, allocation) from the resource plan. These go to the model as context so the timeline matches the PnL.
- `otc_items`: one line per workstream or phase if the PnL has them, otherwise one line "Project Implementation Cost" with the contract value. Amounts are customer prices after margins and discount, never internal cost.
- `funding`: Microsoft or partner funding if recorded on the version, else empty
- `managed_services`: monthly price and months if the version has a managed services line, else null
- `payment_plan`: default template per brand (30/30/30/10 for AX, 20/20/40/20 for Cloud4C), editable in the form
- `consumption_note`, `payment_terms`, `tax_note`: defaults per brand, editable in the form

Add a unit test that the net OTC in the returned dict equals the PnL engine's contract value for the version.

### 5.2 Endpoints

| Method and path | Purpose |
|---|---|
| `POST /api/projects/<id>/versions/<v>/proposals` | multipart: intake JSON + optional BRD/SOW file. Creates a `queued` row, starts the job, returns `202 {proposal_id}` |
| `GET /api/proposals/<id>` | status, error, `open_questions`, token usage |
| `GET /api/proposals/<id>/download` | streams the docx (same permission check as the project) |
| `GET /api/projects/<id>/proposals` | list for the Proposals tab |

Uploaded BRD/SOW: extract text with `pypdf` or `python-docx`, store it in `intake.document_text`, discard the file.

### 5.3 Job

Use an in-process `ThreadPoolExecutor(max_workers=2)` (no new infrastructure). The job:

1. status `running`
2. `commercials = commercials_from_pnl(project_id, version_no)`
3. `content, usage = generator.generate_content(intake, pnl_context=commercials_without_amounts)` where `pnl_context` keeps `duration_weeks` and `team` and drops all amounts
4. `png = assemble.render_diagram(content["component_diagram"], tmp/component_arch.png)`
5. `spec = assemble.build_spec(intake, content, commercials, png)`
6. `assemble.render_docx(spec, tmp/out.docx)`, read bytes into `docx`
7. status `ready` with tokens and `finished_at`; on any exception status `failed` with the message

On app start, mark rows stuck in `running` for more than 15 minutes as `failed` (a deploy killed them).

Rate limit: 10 proposals per user per hour.

---

## 6. UI (fits the DESIGN.md workspace)

Add a **Proposals** tab to the project workspace and a **Generate proposal** button in the version header.

**Generate dialog**, prefilled from the project where possible:

- Brand: AutomatonsX or Cloud4C (required, no default, same rule as the skill)
- Engagement type: Greenfield, Migration, Assessment and completion, Governance only
- Document type: Technical Proposal or Techno-Commercial Proposal
- Client name, short name, industry, region / data residency
- Target technologies (chips: Fabric, OneLake, Power BI, Purview, Databricks, Synapse)
- Sources (repeatable rows: name, ingestion notes, object count)
- Volume, ingestion cadence, consumption needs, medallion scope
- Migration block (shown for Migration): source platform, target platform, inventory counts, stance, cutover expectation
- Governance: included yes/no, Purview allowed yes/no, notes
- Extra sections: Project Governance Structure, Risk and Mitigation
- Include commercials yes/no, payment plan and terms (prefilled per brand)
- Brief (free text) and optional BRD/SOW upload
- People: prepared by (default Srikar Mogaliraju, Principal Architect - Data Engineering), reviewed by (default Amair Soofi for AX, Krishna Kumar G for Cloud4C), account manager

**Proposals tab**: list of generated proposals (brand, version, status, created by, date). A ready row shows Download and the model's `open_questions` as a checklist titled "Close these before sending". A failed row shows the error and Retry.

While running, show progress text from the status endpoint ("Writing content", "Drawing architecture", "Building document").

---

## 7. Rules for Claude Code

- Do not edit anything under `proposals/skill/`. If the builder needs a change, raise it first.
- Do not let the model write boilerplate or numbers. If a new section needs fixed text, add it to `boilerplate.json`.
- Changing `content_schema.json` means updating both sample `content.json` files and `assemble.py` in the same commit, then running the tests.
- House style (no em or en dashes, no comma before or after "and") is enforced twice: in the system prompt and by `assemble.house_style()` on every string. Keep both.
- Keys only in Render env vars. Never log the intake BRD text or the generated content at INFO level.

---

## 8. Testing

1. `pytest tests/test_proposals.py` passes (offline).
2. Unit test for `commercials_from_pnl` against two real saved versions (read-only).
3. Endpoint test with `generator.generate_content` mocked to return `samples/automatonsx/content.json`; the downloaded docx opens in Word.
4. Live smoke test script `scripts/proposal_smoke.py` that sends the AX sample intake to Bedrock and builds the document. Run it manually once after deploy. Check: content passes the schema, timeline fits `duration_weeks`, no prices in the model text, no dashes.
5. Open both generated docs in Word, update the table of contents (Word asks on open), compare against the sample docx files.

---

## 9. Later (not in this release)

- PnL assistant tool `generate_proposal` that starts a job from the chat drawer.
- Editing the generated content in the app and rebuilding the docx without calling the model again.
- Client logo upload on the cover (`intake.client_logo_path` is already supported by the builder).

---

## 10. As built (27 Nov 2026)

What differs from sections 1 to 9, and why.

| Spec | Built | Why |
|---|---|---|
| Alembic migration, `project_id int`, `created_by int` | `pnl/migrations/0006_proposals.sql` and `0007_proposal_checks.sql`, `project_id text` (= `projects.pid`), `version_id text` (= `project_versions.vid`), `created_by` username | The app's own additive runner; projects and users are keyed by text |
| `cairosvg` (and Docker for cairo) | `assemble.render_diagram` loads the skill's own `build_svg` and renders it with `resvg-py` and the bundled Liberation Sans (`proposals/fonts`, SIL OFL) | No system libraries needed; output matches the cairo render. The skill folder is untouched |
| `BEDROCK_PROPOSAL_MODEL_ID` required | Defaults to `global.anthropic.claude-opus-4-6-v1`; `BEDROCK_PROPOSAL_FALLBACK_MODEL_ID` (default Sonnet 4.5) is tried when the Opus call fails | Same model policy as the assistant |
| One OTC line or one per workstream | One line per resource category, one per margin-bearing one-time cost and add-on (all priced after margins and discount), one per pass-through item at cost. Rounding is spread so the lines add up to the rounded contract value | Checked against all 120 saved versions of the production copy |
| Funding and managed services "if recorded on the version" | Entered in the form (the PnL has no such fields) and shown as a deduction or an optional table | |
| Smoke-test checks (section 8.4) | `pnl/proposal_checks.py` runs on every proposal and stores the results: commercials match the PnL, no prices in model text, timeline fits the plan, client named, no placeholders, no other brand, required sections present, inventory counts come from the inputs, house style | This is the verification half of the agent |
| Dockerfile | Kept as `Dockerfile.proposals`, only needed if the Render native runtime has no Node | Render's build command is `pip install -r requirements.txt && npm ci --omit=dev` |

Other notes:
- The Proposals tab only appears for saved projects. It lists setup problems (no Node, no docx package, no Bedrock key) before anyone tries to generate.
- The model gets the intake (minus people, corporate info and file paths) and `{duration_weeks, team}`. It never gets an amount; a test asserts this.
- "Try again" on a failed row reopens the form filled with the earlier answers, including the uploaded BRD text.
- `PNL_PROPOSALS_FAKE=1` uses the bundled sample content (refused in production). Tests use a scripted fake Bedrock client and build real Word files with Node.
- Data residency: Opus and Sonnet are reached through the global cross-Region profile, so BRD text may be processed outside India.
