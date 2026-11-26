#!/usr/bin/env bash
# Phase 0: back up production and build the local development copy.
#
# Reads production ONLY (pg_dump and read-only connections). Writes only to
# ~/pnl-backups/<timestamp>/ and to a NEW local database pnl_prod_copy_<timestamp>.
#
# The production URL is read from ~/pnl-backups/.prod_url (chmod 600), never from
# the command line, so it stays out of shell history and logs.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PY="$REPO/.venv/bin/python"
PGBIN="${PGBIN:-/opt/homebrew/opt/postgresql@17/bin}"
URL_FILE="${URL_FILE:-$HOME/pnl-backups/.prod_url}"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_ROOT="${BACKUP_ROOT:-$HOME/pnl-backups}"
OUT="$BACKUP_ROOT/prod_$STAMP"
COPY_DB="${COPY_PREFIX:-pnl_prod_copy}_$STAMP"

[ -f "$URL_FILE" ] || { echo "Put the production DATABASE_URL in $URL_FILE (chmod 600) first."; exit 1; }
PROD_URL="$(tr -d '[:space:]' < "$URL_FILE")"
PROD_URL="${PROD_URL/#postgres:\/\//postgresql://}"
mkdir -p "$OUT"
chmod 700 "$BACKUP_ROOT" "$OUT"
log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$OUT/backup.log"; }

log "Backup folder: $OUT"

# 1. Server and client versions (pg_dump must be the same major version or newer)
SERVER_VER="$(PGOPTIONS='-c default_transaction_read_only=on' "$PGBIN/psql" "$PROD_URL" -Atc 'SHOW server_version')"
log "Production server version: $SERVER_VER; pg_dump: $("$PGBIN/pg_dump" --version)"

# 2. Row counts on production (read-only)
log "Row counts on production"
"$PY" "$REPO/scripts/count_rows.py" --database-url "$PROD_URL" --out "$OUT/prod_counts.txt" | sed 's/^/    /' | tee -a "$OUT/backup.log" >/dev/null

# 3. pg_dump: custom format (for pg_restore) and plain SQL (readable, restorable with psql)
log "pg_dump (custom format)"
"$PGBIN/pg_dump" --format=custom --no-owner --no-privileges "$PROD_URL" > "$OUT/pnl_backup_$STAMP.dump"
log "pg_dump (plain SQL)"
"$PGBIN/pg_dump" --format=plain --no-owner --no-privileges "$PROD_URL" > "$OUT/pnl_backup_$STAMP.sql"
"$PGBIN/pg_restore" --list "$OUT/pnl_backup_$STAMP.dump" > "$OUT/dump_contents.txt"
log "Dump OK: $(grep -c 'TABLE DATA' "$OUT/dump_contents.txt") table data sections"

# 4. JSON snapshot, including rate card and role catalog as separate files (read-only)
log "JSON snapshot"
"$PY" "$REPO/scripts/backup_snapshot.py" --database-url "$PROD_URL" --out "$OUT/json_snapshot" | sed 's/^/    /' | tee -a "$OUT/backup.log" >/dev/null

# 5. Live schema (read-only)
"$PY" "$REPO/scripts/describe_schema.py" --database-url "$PROD_URL" > "$OUT/live_schema.md"

# 6. Restore the dump into a NEW local database and prove it matches production
log "Restoring into new local database $COPY_DB"
"$PGBIN/createdb" "$COPY_DB"
"$PGBIN/pg_restore" --no-owner --no-privileges --dbname="$COPY_DB" "$OUT/pnl_backup_$STAMP.dump"
"$PY" "$REPO/scripts/count_rows.py" --database-url "postgresql://localhost/$COPY_DB" --out "$OUT/copy_counts.txt" >/dev/null
if diff <(grep -v '^#' "$OUT/prod_counts.txt") <(grep -v '^#' "$OUT/copy_counts.txt") >/dev/null; then
  log "Local copy row counts match production"
else
  log "WARNING: local copy row counts differ from production (rows may have been saved during the dump)"
  diff <(grep -v '^#' "$OUT/prod_counts.txt") <(grep -v '^#' "$OUT/copy_counts.txt") | tee -a "$OUT/backup.log" || true
fi

# 7. Baseline figures from the local copy, with the pre-redesign code
log "Capturing baseline figures and Excel samples"
"$PY" "$REPO/scripts/capture_baseline.py" --database-url "postgresql://localhost/$COPY_DB" --out "$OUT/baseline" | sed 's/^/    /' | tee -a "$OUT/backup.log" >/dev/null
"$PY" "$REPO/scripts/verify_data.py" --database-url "postgresql://localhost/$COPY_DB" \
  --baseline-counts "$OUT/copy_counts.txt" --baseline-figures "$OUT/baseline/baseline_figures.json" | tee -a "$OUT/backup.log"

echo "$COPY_DB" > "$OUT/LOCAL_COPY_DB"
log "Done. Local copy: postgresql://localhost/$COPY_DB"

# 8. Checksums for everything in the backup folder (last, so no file changes afterwards)
(cd "$OUT" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 shasum -a 256 > SHA256SUMS)
chmod -R go-rwx "$OUT"
echo "Checksums: $OUT/SHA256SUMS"
