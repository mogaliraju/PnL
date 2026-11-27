-- Phase 8 (DESIGN.md 9.5): PnL assistant chat history, tool-call audit and one-time export links.
-- New tables only. The assistant never writes project, version or rate data.
CREATE TABLE IF NOT EXISTS assistant_session (
  id text PRIMARY KEY,
  username text NOT NULL,
  title text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS assistant_session_user_idx ON assistant_session (username, updated_at);

CREATE TABLE IF NOT EXISTS assistant_message (
  id serial PRIMARY KEY,
  session_id text NOT NULL REFERENCES assistant_session(id),
  role text NOT NULL CHECK (role IN ('user', 'assistant')),
  content text NOT NULL,                -- JSON: the API content blocks, kept unchanged for replay
  display text NOT NULL DEFAULT '',     -- JSON: what the drawer shows (text, sources, files)
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS assistant_message_session_idx ON assistant_message (session_id, id);

CREATE TABLE IF NOT EXISTS assistant_tool_call (
  id serial PRIMARY KEY,
  session_id text NOT NULL REFERENCES assistant_session(id),
  username text NOT NULL,
  tool text NOT NULL,
  input text NOT NULL,                  -- JSON
  ms int NOT NULL,
  ok boolean NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS export_token (
  token text PRIMARY KEY,
  username text NOT NULL,
  project_id text NOT NULL,
  version_id text,
  overrides text NOT NULL DEFAULT '{}', -- JSON scenario overrides, never saved to the project
  filename text NOT NULL,
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
