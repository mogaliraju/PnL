# Backup and rollback runbook

Use this before the redesign starts (Phase 0) and whenever you need to go back. All scripts in `scripts/` open the database read-only, except `restore_snapshot.py`, which only writes into a new, empty database.

Setup once (Python 3.10+ is required. The repo has a `.venv` with Python 3.12):

```bash
cd "PnL"
/opt/homebrew/bin/python3.12 -m venv .venv      # skip if .venv exists
.venv/bin/pip install -r requirements.txt pytest
```

## 1. Back up production (do this first, before any phase)

Production `DATABASE_URL` is set in the Render dashboard. `render.yaml` notes that it points at a Neon or Supabase database, so the "manual backup" happens in whichever provider hosts that URL.

1. **Provider backup.** In the provider's dashboard (Render Postgres, Neon or Supabase), take a manual backup or snapshot. Neon calls this a branch, Supabase calls it a backup. Note its name and time.
2. **pg_dump from your machine.** Paste the URL at a hidden prompt so it doesn't land in your shell history:

   ```bash
   mkdir -p ~/pnl-backups && cd ~/pnl-backups
   read -s DATABASE_URL && export DATABASE_URL        # paste the production URL, press Enter
   /opt/homebrew/opt/postgresql@17/bin/pg_dump --format=custom --no-owner "$DATABASE_URL" \
     > pnl_backup_$(date +%Y%m%d).dump
   /opt/homebrew/opt/postgresql@17/bin/pg_restore --list pnl_backup_$(date +%Y%m%d).dump | head   # sanity check
   ```

3. **JSON snapshot (second copy, includes rate card and role catalog as separate files).** This runs read-only against production:

   ```bash
   cd "<repo>/PnL"
   .venv/bin/python scripts/backup_snapshot.py --out ~/pnl-backups/prod_snapshot_$(date +%Y%m%d)
   unset DATABASE_URL
   ```

   This writes `rate_card.json` and `role_catalog.json` alongside every table (DESIGN.md 2.1.3).

Keep `~/pnl-backups` outside the repo. Copy it to a second place too, such as OneDrive or an external drive.

## 2. Make the development copy (never develop against production)

```bash
/opt/homebrew/opt/postgresql@17/bin/createdb pnl_prod_copy
/opt/homebrew/opt/postgresql@17/bin/pg_restore --no-owner --dbname=pnl_prod_copy ~/pnl-backups/pnl_backup_YYYYMMDD.dump
export DATABASE_URL=postgresql://localhost/pnl_prod_copy      # only ever the local copy
```

Then record the baseline:

```bash
.venv/bin/python scripts/count_rows.py --out design/baseline_counts.txt          # commit this file
.venv/bin/python scripts/describe_schema.py > ~/pnl-backups/live_schema.md        # paste into CURRENT_SCHEMA.md
.venv/bin/python scripts/capture_baseline.py --out ~/pnl-backups/baseline_YYYYMMDD # figures stay outside the repo
.venv/bin/python scripts/verify_data.py --baseline-figures ~/pnl-backups/baseline_YYYYMMDD/baseline_figures.json
```

`capture_baseline.py` must run with the **pre-redesign code**: tag `pre-redesign-2026`, or Phase 0 of `redesign-2026`, which doesn't change any app code. It records each project's and version's figures and three sample Excel exports. Every later phase is checked against them.

## 3. Verify after every phase

```bash
DATABASE_URL=postgresql://localhost/pnl_prod_copy \
  .venv/bin/python scripts/verify_data.py --baseline-figures ~/pnl-backups/baseline_YYYYMMDD/baseline_figures.json
```

`VERIFY PASSED` is required before merging a phase. The script checks row counts (Bookings and Funnel must match exactly), that no project or version is missing, that every payload loads, calculation parity within USD 1, and Excel parity.

## 4. Rolling back

The redesign is built so that **rolling back code never needs a data change**. Migrations only add tables and columns, which the old code ignores.

### Roll back code

* Production deploys from `master`. Redesign work lives on `redesign-2026`, one pull request per phase. Nothing reaches production until a phase is merged.
* To undo a merged phase: in Render, go to **Deploys**, pick the last good deploy and click **Redeploy**. Or `git revert` the phase's merge commit and push.
* The last state before the redesign is tag **`pre-redesign-2026`** (commit `9dd9dfe`). To return to it completely without rewriting history: in Render, deploy that commit (Manual Deploy, then "Deploy a specific commit"). In git, `git revert` the redesign merge commits on `master`, so history stays intact.

What the old code sees after a rollback:

* New tables (`rate_card`, `role`, …): ignored.
* `projects.archived_at`: ignored, so archived projects show up again in the old list. Nothing is lost.
* `calc_mode`: ignored, so the old code computes every project the legacy way, which is what it always did.

### Roll back data

Restore into a **new** database, check it, then point the app at it. Never restore over the live database.

```bash
# from the pg_dump file
createdb pnl_restore_YYYYMMDD
pg_restore --no-owner --dbname=pnl_restore_YYYYMMDD ~/pnl-backups/pnl_backup_YYYYMMDD.dump

# or from the JSON snapshot
.venv/bin/python scripts/restore_snapshot.py --snapshot ~/pnl-backups/prod_snapshot_YYYYMMDD \
  --database-url postgresql://localhost/pnl_restore_YYYYMMDD

# check it against the baseline
DATABASE_URL=postgresql://localhost/pnl_restore_YYYYMMDD .venv/bin/python scripts/verify_data.py \
  --baseline-figures ~/pnl-backups/baseline_YYYYMMDD/baseline_figures.json
```

For production, restore into a new database at the provider (a new Neon branch, a Supabase or Render database restored from the backup) and change `DATABASE_URL` in Render to point at it. The old database stays untouched until you decide what to do with it.

## 5. Guardrails in the repo

* `.claude/settings.json` denies `dropdb`, `rm -rf`, `git push --force` and `git reset --hard` for Claude Code.
* `CLAUDE.md` tells Claude Code never to run SQL with DROP, TRUNCATE or DELETE, never to touch the production `DATABASE_URL`, and to ask before any command that writes to a database.
