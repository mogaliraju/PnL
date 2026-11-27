# Go-live runbook: redesign 2026

Everything below is on branch `redesign-2026`. Production (Render + Neon) still runs `master` (tag `pre-redesign-2026`) and its database has none of the new tables yet. Follow these steps in order. Each step can be undone as described in BACKUP_AND_ROLLBACK.md.

## 0. Try it locally first (optional, recommended)

A copy of production with every migration applied (`pnl_try`) runs with:

```bash
DATABASE_URL=postgresql://localhost/pnl_try DATA_DIR=/tmp/pnl-try SECRET_KEY=local PNL_ASSISTANT_FAKE=1 \
  .venv/bin/python -m flask --app app run --port 5050
```

Sign in at http://127.0.0.1:5050 with your normal production username and password. `PNL_ASSISTANT_FAKE=1` gives a demo assistant that shows raw tool results without calling a model.

## 1. Fresh backup (5 minutes)

1. In the Neon console, create a branch named `pre-redesign-golive` (a server-side snapshot).
2. On this machine: `scripts/backup_production.sh` (dump, JSON copy, baseline figures, verified restore).

## 2. Prepare Bedrock for the assistant (can be done later; the app works without it)

1. In the AWS console, Amazon Bedrock, region **Asia Pacific (Mumbai) `ap-south-1`**: enable model access for **gpt-oss-120b**.
2. Create a Bedrock API key (long-term, or a short-term key for a trial).
3. Optional but recommended: create a SELECT-only Postgres role in Neon for the assistant's tools, and grant it `INSERT` on the assistant tables only:

   ```sql
   CREATE ROLE pnl_assistant LOGIN PASSWORD '<choose one>';
   GRANT SELECT ON ALL TABLES IN SCHEMA public TO pnl_assistant;
   ```

   (Run this yourself in the Neon SQL editor. The app's own migrations never create roles.)

## 3. Migrate the production database (2 minutes, additive only)

The runner refuses non-local databases unless you confirm the name. It applies migrations 0001–0005 in one transaction and rolls everything back if any existing row would change.

```bash
read -s DATABASE_URL && export DATABASE_URL        # paste the Neon URL
.venv/bin/python scripts/migrate.py --database-url "$DATABASE_URL" --production --dry-run
PNL_MIGRATE_CONFIRM=neondb .venv/bin/python scripts/migrate.py --database-url "$DATABASE_URL" --production
unset DATABASE_URL
```

The old app keeps working after this step: it ignores the new tables and columns.

## 4. Configure Render

In the Render dashboard for `pnl-automatonsx`, Environment:

| Variable | Value |
|---|---|
| `PNL_ENV` | `production` |
| `AWS_BEARER_TOKEN_BEDROCK` | the Bedrock API key (step 2) |
| `AWS_REGION` | `ap-south-1` |
| `BEDROCK_MODEL_ID` | `openai.gpt-oss-120b-1:0` |
| `ASSISTANT_DATABASE_URL` | the SELECT-only role's URL (step 2.3), optional |
| `PNL_BOOTSTRAP_ADMIN_PASSWORD` | leave empty unless the users table is empty |

Start command (also in `render.yaml`): `gunicorn --worker-class gthread --threads 8 --timeout 120 app:app`.

## 5. Deploy

Merge `redesign-2026` into `master` (a pull request is recommended) and let Render deploy. Then:

1. Sign in, open Projects, Dashboard, Rates and roles, Users and one project.
2. Run `verify_data.py` against a fresh dump of production (step 1 tooling) to confirm nothing changed.
3. Ask the assistant "Which open projects are below the AX target?".

## Rolling back

* Code: redeploy the previous Render deploy, or deploy tag `pre-redesign-2026`. No data change is needed: the old code ignores everything the migrations added.
* Data: restore the Neon branch or the dump into a new database and point `DATABASE_URL` at it (BACKUP_AND_ROLLBACK.md section 4).
