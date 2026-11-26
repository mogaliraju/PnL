-- Phase 5 (DESIGN.md 8.1): versioned rate cards and the role catalog in their own tables.
-- Postgres only. Additive: new tables, nullable new columns, indexes.
CREATE TABLE IF NOT EXISTS level (
  id serial PRIMARY KEY,
  code text UNIQUE NOT NULL,
  name text NOT NULL,
  sort_order int NOT NULL
);

CREATE TABLE IF NOT EXISTS role_category (
  id serial PRIMARY KEY,
  name text UNIQUE NOT NULL,
  sort_order int NOT NULL DEFAULT 0,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS role (
  id serial PRIMARY KEY,
  category_id int NOT NULL REFERENCES role_category(id),
  name text NOT NULL,
  default_level_id int REFERENCES level(id),
  active boolean NOT NULL DEFAULT true,
  imported boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (category_id, name)
);

CREATE TABLE IF NOT EXISTS rate_card (
  id serial PRIMARY KEY,
  version int UNIQUE NOT NULL,
  status text NOT NULL CHECK (status IN ('draft', 'published', 'archived')),
  effective_from date,
  note text,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  published_by text,
  published_at timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS rate_card_one_draft ON rate_card ((status)) WHERE status = 'draft';
CREATE UNIQUE INDEX IF NOT EXISTS rate_card_one_published ON rate_card ((status)) WHERE status = 'published';

CREATE TABLE IF NOT EXISTS rate_card_rate (
  rate_card_id int NOT NULL REFERENCES rate_card(id),
  category_id int NOT NULL REFERENCES role_category(id),
  level_id int NOT NULL REFERENCES level(id),
  rate_usd numeric(10, 2),                 -- NULL = the category doesn't offer this level
  PRIMARY KEY (rate_card_id, category_id, level_id)
);

ALTER TABLE projects ADD COLUMN IF NOT EXISTS rate_card_id int REFERENCES rate_card(id);
ALTER TABLE project_versions ADD COLUMN IF NOT EXISTS version_no int;
ALTER TABLE project_versions ADD COLUMN IF NOT EXISTS rate_card_id int REFERENCES rate_card(id);
CREATE UNIQUE INDEX IF NOT EXISTS project_versions_pid_version_no ON project_versions (pid, version_no);
