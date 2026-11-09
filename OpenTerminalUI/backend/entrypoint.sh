#!/usr/bin/env sh
set -e

# Ensure runtime volume directory exists and is owned by appuser
mkdir -p /data
chown -R appuser:appgroup /data /app 2>/dev/null || true
chmod 775 /data 2>/dev/null || true

# SEC-FIX (SEC-05): Step-down privilege pattern.
# Container boots as root to fix volume permissions, then immediately drops to appuser.
if [ "$(id -u)" = "0" ]; then
  exec su -s /bin/sh appuser -c "$0 $*"
fi

if [ "${SKIP_MIGRATIONS:-0}" != "1" ]; then
  alembic -c backend/alembic.ini upgrade head
fi

# Seed an initial admin account on first launch so login works out of the box.
# Idempotent: skips automatically once any user exists or if no password is set.
python scripts/seed_admin.py || true

exec python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
