-- Proposal generation (design/PROPOSALS.md section 4). New table only; nothing existing changes.
-- One row per generated proposal. Regenerating adds a row; the app never removes rows.
-- The Word file is kept in the row because the server's disk is wiped on every deploy.
CREATE TABLE IF NOT EXISTS proposal (
  id serial PRIMARY KEY,
  project_id text NOT NULL,
  version_id text NOT NULL,             -- project_versions.vid the commercials came from
  version_no int NOT NULL,
  brand text NOT NULL CHECK (brand IN ('automatonsx', 'cloud4c')),
  engagement_type text NOT NULL,
  status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'ready', 'failed')),
  stage text NOT NULL DEFAULT '',       -- progress text shown while running
  intake text NOT NULL,                 -- JSON: the form, with any BRD or SOW text
  commercials text,                     -- JSON: built from the PnL version by code, never by the model
  content text,                         -- JSON: what the model wrote (validated)
  docx bytea,
  filename text,
  model_id text,
  input_tokens int,
  output_tokens int,
  error text,
  created_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz
);
CREATE INDEX IF NOT EXISTS proposal_project_idx ON proposal (project_id, created_at);
CREATE INDEX IF NOT EXISTS proposal_user_idx ON proposal (created_by, created_at);
