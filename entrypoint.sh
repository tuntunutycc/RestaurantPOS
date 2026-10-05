#!/bin/sh
set -eu

DB_PATH="${POS_DB_PATH:-/data/db/pos.db}"
TICKET_DIR="${KITCHEN_PRINT_OUTPUT_DIR:-/data/tickets}"
ROOT_USER="${ROOT_USERNAME:-root}"

mkdir -p "$(dirname "$DB_PATH")" "$TICKET_DIR"

if [ ! -f "$DB_PATH" ]; then
  echo "No database at ${DB_PATH}. Creating tables and seeding root user '${ROOT_USER}'."
  python -c "from database import engine; from models import Base; Base.metadata.create_all(bind=engine)"
  if [ -z "${ROOT_PASSWORD:-}" ]; then
    echo "ROOT_PASSWORD is required to seed the first root user." >&2
    rm -f "$DB_PATH"
    exit 1
  fi
  if ! python scripts/seed_root.py --username "$ROOT_USER" --password "$ROOT_PASSWORD"; then
    echo "Root seed failed. Removing the incomplete database so the next start can retry." >&2
    rm -f "$DB_PATH"
    exit 1
  fi
else
  echo "Database found at ${DB_PATH}. Skipping initial seed."
fi

exec uvicorn main:app --host 0.0.0.0 --port 8000
