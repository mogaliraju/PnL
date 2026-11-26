# Current schema (Phase 0)

Written 27 Nov 2026 from the code on tag `pre-redesign-2026` (commit `9dd9dfe`) and checked against production the same day (see "Live schema").

## How data is stored

One storage module, `pnl/utils/storage.py`, serves both back ends:

* **Postgres** when `DATABASE_URL` starts with `postgres://` or `postgresql://` (production on Render).
* **SQLite** at `$DATA_DIR/pnl.sqlite3` otherwise (local development and the test suite).

Projects and versions are **JSON documents in a TEXT column** (`payload`), with a few fields copied into columns for listing. Settings live as JSON blobs in `app_state`. There are no foreign keys and no numeric version numbers.

| Table | Key | What it holds |
|---|---|---|
| `app_state` | `key` | JSON blobs: `global_settings` (rate card, role catalog, business units), `working_data` (last editor state), `custom_fields_<module>`, `column_labels_<module>` |
| `users` | `username` | `password` (werkzeug hash), `role` (`admin`/`user`), `name`, `created_at` |
| `projects` | `pid` (text, e.g. `Benline_20260508_080511`) | `name`, `customer`, `location`, `duration`, `proposal_date`, `saved_at`, `saved_by`, `folder`, `payload` (full project JSON) |
| `project_versions` | (`pid`, `vid`) | `saved_at`, `saved_by`, `label`, `payload` (full snapshot JSON) |
| `funnel_entries` | `id` | Funnel Report rows, typed columns plus `extra_fields` JSON |
| `order_bookings` | `id` | Order Bookings rows, typed columns plus `extra_fields` JSON |

All timestamps are ISO strings in TEXT columns, not `timestamptz`.

### Project payload (JSON in `projects.payload` and `project_versions.payload`)

Top-level keys: `_meta` (`id`, `name`, `folder`, `saved_at`, `saved_by`), `project` (36 descriptive fields: customer, status, stage, discount_pct, travel/infra/third_party cost, people, notes…), `resources` (list of `{group, role, level, hours, id}`), `rate_card`, `role_catalog`, `business_units`, `one_time_costs` (list of `{label, amount, category, exclude_from_margin}`), `target_margin`, `cloud4c_margin`, `ax_margin`, `fx_rate`, `export_filename`, plus unused legacy keys `approvals`, `attachments`, `funding`, `releases`, `pnl_roles`, `export_path`.

**Every saved payload carries its own copy of the rate card.** That means every existing version can already be recalculated with the rates it was saved with. This is what makes the legacy parity check (DESIGN.md 2.6.3) possible.

Rate card entries come in two shapes, and the code reads both:

* flat: `{"level": "L2", "rate": 20}` (all categories share one rate)
* by category: `{"level": "L2", "rates": {"Data Engineering": 20, "Power BI & Analytics": 18}}`

Levels in the backup data: `L1`–`L8` and `Onsite`.

Margins: projects saved before the Cloud4C/AX split have only `target_margin`. `resolve_margin_inputs` treats it as the Cloud4C margin, with AX = 0.

### Which numbers the app shows today

| Screen | Rate card used | Discount | Add-on costs |
|---|---|---|---|
| All Projects list, Dashboard, Version History, Excel export (server) | the payload's stored rate card | Version History only (`revenue = sell × (1 − discount)`) | ignored (list shows them as a separate column) |
| Project editor (browser) | **the current global rate card**: `merge_settings()` replaces the payload's copy when the project loads | ignored | ignored |

So a project opened in the editor can show different numbers from the list whenever the global rate card has changed since it was saved. Pinning rate cards (Phase 5) fixes this.

## Code paths that delete or overwrite data today

These conflict with DESIGN.md section 2.3. Each one gets replaced in the phase shown. Until then, avoid using them on production.

| Code | What it does | Replaced in |
|---|---|---|
| `DELETE /api/projects/<pid>` → `delete_project_record` | Hard-deletes the project **and all its versions** | Phase 4 (archive) |
| `DELETE /api/projects/<pid>/versions/<vid>` → `delete_project_version` | Hard-deletes one version | Phase 6 (versions are never deleted) |
| `save_users` | `DELETE FROM users`, then re-inserts every user (one transaction) | Phase 7 |
| `DELETE /api/users/<username>` | Removes a user, whose name is still referenced by `saved_by` | Phase 7 (deactivate) |
| `save_working_data` (`POST /api/data`) | Copies the on-screen `rate_card`, `role_catalog` and `business_units` **over the global settings** | Phase 5 (versioned rate cards) |
| Role Catalog "remove role / category" | Rewrites `global_settings` without the role | Phase 5 (switch off) |
| `DELETE /api/funnel/<id>`, `DELETE /api/bookings/<id>` | Hard deletes | Phase 3 hides the UI. The routes stay but are unreachable |
| `scripts/migrate_sqlite_to_postgres.py` | Upserts (`ON CONFLICT DO UPDATE`) local SQLite rows into Postgres | Never run against production |
| `migrate_postgres_to_sqlite.py` | Reads Postgres, writes SQLite | Safe for production (read only), but don't use it as a backup: use `scripts/backup_snapshot.py` |

`seed_data.py` only writes when the projects table is empty. It also can't read the files in `data_backup/`, because they start with a UTF-8 BOM and it decodes them as `utf-8`. So in practice it restores nothing.

## Known drift between SQLite and Postgres

`_create_schema` adds `projects.folder`, `project_versions.label`, `order_bookings.billing_team_comments` and `order_bookings.pmo` to **existing SQLite** tables only. If the production Postgres tables were created before those columns existed, they may be missing there. Checked on 27 Nov 2026: production has all of them, so there's nothing to fix.

## Live schema (production copy)

Taken from production on 27 Nov 2026 with `scripts/describe_schema.py`. **No drift:** the production tables have every column the code expects, including `projects.folder`, `project_versions.label`, `order_bookings.billing_team_comments` and `pmo`.

Production holds 39 projects, 118 saved versions, 1 user, and no Funnel or Bookings rows. Stored rate cards are mostly per-category (1,170 entries) with some older flat entries (243). Every payload already has separate Cloud4C and AX margins.

Source: production (Neon Postgres 17.12), read-only, 27 Nov 2026. Same result on the restored local copy.

#### `app_state` (2 rows)

| Column | Type | Nullable | Default | PK |
|---|---|---|---|---|
| key | text | no |  | yes |
| json_value | text | no |  |  |
| updated_at | text | no |  |  |

#### `funnel_entries` (0 rows)

| Column | Type | Nullable | Default | PK |
|---|---|---|---|---|
| id | text | no |  | yes |
| record_id | text | yes |  |  |
| reporting_manager | text | yes |  |  |
| opportunity_owner | text | yes |  |  |
| region | text | yes |  |  |
| account_name | text | yes |  |  |
| description | text | yes |  |  |
| opportunity_name | text | yes |  |  |
| closing_month | text | yes |  |  |
| ageing_days | text | yes |  |  |
| stage | text | yes |  |  |
| fq | text | yes |  |  |
| final_product | text | yes |  |  |
| created_time | text | yes |  |  |
| net_forecasting | text | yes |  |  |
| otc_usd_k | real | yes |  |  |
| tcv_usd | real | yes |  |  |
| mrc_usd_k | real | yes |  |  |
| acv_usd_k | real | yes |  |  |
| updates | text | yes |  |  |
| extra_fields | text | yes |  |  |
| saved_at | text | yes |  |  |
| saved_by | text | yes |  |  |

#### `order_bookings` (0 rows)

| Column | Type | Nullable | Default | PK |
|---|---|---|---|---|
| id | text | no |  | yes |
| booking_type | text | no |  |  |
| opf_number | text | yes |  |  |
| opf_date | text | yes |  |  |
| cdd | text | yes |  |  |
| bu | text | yes |  |  |
| customer_name | text | yes |  |  |
| otc | real | yes |  |  |
| mrc | real | yes |  |  |
| billed_pct | real | yes |  |  |
| milestones | text | yes |  |  |
| c4c_invoice_raised | real | yes |  |  |
| c4c_amount_received | real | yes |  |  |
| c4c_pending_billing | real | yes |  |  |
| ax_invoice_raised | real | yes |  |  |
| ax_amount_received | real | yes |  |  |
| ax_pending_collection | real | yes |  |  |
| updates | text | yes |  |  |
| billing_team_comments | text | yes |  |  |
| pmo | text | yes |  |  |
| extra_fields | text | yes |  |  |
| saved_at | text | yes |  |  |
| saved_by | text | yes |  |  |

#### `project_versions` (118 rows)

| Column | Type | Nullable | Default | PK |
|---|---|---|---|---|
| pid | text | no |  | yes |
| vid | text | no |  | yes |
| saved_at | text | yes |  |  |
| saved_by | text | yes |  |  |
| label | text | yes | ''::text |  |
| payload | text | no |  |  |

#### `projects` (39 rows)

| Column | Type | Nullable | Default | PK |
|---|---|---|---|---|
| pid | text | no |  | yes |
| name | text | no |  |  |
| customer | text | yes |  |  |
| location | text | yes |  |  |
| duration | text | yes |  |  |
| proposal_date | text | yes |  |  |
| saved_at | text | yes |  |  |
| saved_by | text | yes |  |  |
| folder | text | yes | ''::text |  |
| payload | text | no |  |  |

#### `users` (1 rows)

| Column | Type | Nullable | Default | PK |
|---|---|---|---|---|
| username | text | no |  | yes |
| password | text | no |  |  |
| role | text | no |  |  |
| name | text | no |  |  |
| created_at | text | no |  |  |

#### Stored project JSON (157 payloads: projects + versions)

Top-level keys: `_meta` (157), `approvals` (157), `attachments` (157), `ax_margin` (157), `business_units` (157), `cloud4c_margin` (157), `export_filename` (157), `funding` (157), `fx_rate` (157), `one_time_costs` (157), `pnl_roles` (157), `project` (157), `rate_card` (157), `releases` (157), `resources` (157), `role_catalog` (157), `target_margin` (157), `export_path` (6)

`project` keys: `account_manager` (157), `billing_type` (157), `business_unit` (157), `company` (157), `currency` (157), `customer` (157), `customer_first_touch_point` (157), `delivery_manager` (157), `delivery_model` (157), `dependencies` (157), `discount_pct` (157), `duration_months` (157), `expected_end_date` (157), `expected_start_date` (157), `industry` (157), `infra_cost` (157), `internal_notes` (157), `location` (157), `next_action` (157), `next_follow_up_date` (157), `opportunity_id` (157), `partner` (157), `payment_terms` (157), `priority` (157), `project_description` (157), `project_owner` (157), `project_type` (157), `proposal_date` (157), `reference` (157), `risks` (157), `sales_spoc` (157), `stage` (157), `status` (157), `technical_lead` (157), `third_party_cost` (157), `travel_cost` (157)

Rate card entry format: flat rate (243), rates-by-category (1170)

Levels seen: `L1` (157), `L2` (157), `L3` (157), `L4` (157), `L5` (157), `L6` (157), `L7` (157), `L8` (157), `Onsite` (157)

Margin fields: cloud4c+ax (157)

Resource categories seen (5): `Architecture & Leadership`, `Data Engineering`, `Platform`, `Power BI & Analytics`, `Project & Product`

Distinct role names on resource lines: 26


## Proposed Phase 5 migration (not run, for approval)

Adapted from DESIGN.md 8.1 to the real table names. It's additive only: new tables, nullable or defaulted new columns, and indexes. It writes nothing to existing columns.

```sql
BEGIN;

CREATE TABLE IF NOT EXISTS level (
  id serial PRIMARY KEY,
  code text UNIQUE NOT NULL,            -- 'L1' … 'L8', 'Onsite'
  name text NOT NULL,
  sort_order int NOT NULL);

CREATE TABLE IF NOT EXISTS role_category (
  id serial PRIMARY KEY,
  name text UNIQUE NOT NULL,
  sort_order int NOT NULL DEFAULT 0,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now());

CREATE TABLE IF NOT EXISTS role (
  id serial PRIMARY KEY,
  category_id int NOT NULL REFERENCES role_category(id),
  name text NOT NULL,
  default_level_id int REFERENCES level(id),
  active boolean NOT NULL DEFAULT true,
  imported boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (category_id, name));

CREATE TABLE IF NOT EXISTS rate_card (
  id serial PRIMARY KEY,
  version int UNIQUE NOT NULL,
  status text NOT NULL CHECK (status IN ('draft','published','archived')),
  effective_from date,
  note text,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  published_by text,
  published_at timestamptz);
CREATE UNIQUE INDEX IF NOT EXISTS rate_card_one_draft     ON rate_card ((status)) WHERE status = 'draft';
CREATE UNIQUE INDEX IF NOT EXISTS rate_card_one_published ON rate_card ((status)) WHERE status = 'published';

CREATE TABLE IF NOT EXISTS rate_card_rate (
  rate_card_id int NOT NULL REFERENCES rate_card(id),
  category_id  int NOT NULL REFERENCES role_category(id),
  level_id     int NOT NULL REFERENCES level(id),
  rate_usd     numeric(10,2),             -- NULL = category doesn't offer this level
  PRIMARY KEY (rate_card_id, category_id, level_id));

-- New columns on existing tables. All nullable or constant-defaulted: Postgres 11+
-- adds these without rewriting or changing any existing value.
ALTER TABLE projects ADD COLUMN IF NOT EXISTS rate_card_id   int REFERENCES rate_card(id);
ALTER TABLE projects ADD COLUMN IF NOT EXISTS calc_mode      text NOT NULL DEFAULT 'legacy';
ALTER TABLE projects ADD COLUMN IF NOT EXISTS archived_at    timestamptz;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS export_filename text;
ALTER TABLE project_versions ADD COLUMN IF NOT EXISTS version_no   int;   -- backfilled by saved_at order
ALTER TABLE project_versions ADD COLUMN IF NOT EXISTS rate_card_id int REFERENCES rate_card(id);

COMMIT;
```

The migration runner (to be written in Phase 5) wraps this in one transaction, prints row counts before and after, and aborts if any existing table's count drops (DESIGN.md 2.2).

Seeding (DESIGN.md 8.2) then copies from `app_state.global_settings` and from every payload:

1. Levels in the current rate-card order (`L1`…`L8`, `Onsite`).
2. Categories from `role_catalog`, plus any `group` found on a resource line that isn't in the catalog.
3. Roles from `role_catalog`. Role names found only on old resource lines get `active = false, imported = true`.
4. Rate card version 1 (`published`), filled from the global rate card. A flat `rate` fills every category for that level. A `rates` map fills per category.
5. `projects.rate_card_id = v1` for every project. This touches only the new column.
6. `project_versions.version_no` numbered 1…N per project by `saved_at`, `vid`. This also touches only a new column.

`app_state.global_settings` stays exactly as it is. It becomes the frozen backup listed in `DEPRECATED.md`.

### Questions for you before Phase 5

1. **SQLite.** Local development and the 100 existing tests use SQLite, but `serial`, `timestamptz` and partial indexes are Postgres syntax. I recommend running the new tables on Postgres only, with local development against a restored Postgres copy, and keeping SQLite only for the old tests until they're ported. The alternative is maintaining both SQL dialects.
2. **Version numbers.** Versions have text ids, not numbers, so the backfill numbers them by `saved_at`. Two versions with the same `saved_at` are ordered by `vid`. Is that acceptable?
3. **Legacy rates.** Old payloads keep their own rate-card copy, and legacy mode keeps using it, so old numbers never move. A project picks up rate card v1 only when someone presses Update in the rate card banner. Confirm that's the intended behaviour.
