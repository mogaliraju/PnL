-- Phase 4 (DESIGN.md 2.3.1, 5.2): archive instead of delete, per-user list preferences.
-- Additive only: two nullable columns, one index, one new table.
ALTER TABLE projects ADD COLUMN IF NOT EXISTS archived_at timestamptz;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS archived_by text;
CREATE INDEX IF NOT EXISTS projects_archived_at_idx ON projects (archived_at);

CREATE TABLE IF NOT EXISTS user_pref (
  username   text        NOT NULL,
  pref_key   text        NOT NULL,
  value      text        NOT NULL,          -- JSON document
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (username, pref_key)
);
