#!/bin/sh
set -eu

# Optional: run DB migrations once on container start, then exec the given command.
#
# Notes
# -----
# We intentionally keep migrations optional (controlled via RUN_MIGRATIONS_ON_STARTUP),
# because in production migrations are usually executed as a separate deploy step/job.
# For local dev/test tasks you may enable it to make `docker compose up` self-contained.

if [ "${RUN_MIGRATIONS_ON_STARTUP:-false}" = "true" ]; then
  echo "[entrypoint] running alembic migrations (RUN_MIGRATIONS_ON_STARTUP=true)..."
  python - <<'PY'
from app.core.migrations import run_migrations_once

run_migrations_once()
PY
else
  echo "[entrypoint] skipping migrations (RUN_MIGRATIONS_ON_STARTUP=false)"
fi

echo "[entrypoint] starting app: $*"
exec "$@"
