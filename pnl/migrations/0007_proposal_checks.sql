-- Results of the automatic checks run on each generated proposal (pnl/proposal_checks.py).
-- One new nullable column; nothing existing changes.
ALTER TABLE proposal ADD COLUMN IF NOT EXISTS checks text;   -- JSON list of {id, label, ok, detail}
