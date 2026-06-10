#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Smart-Stua Backend — Docker Entrypoint Script
# Runs on every container start. Handles:
#   1. Wait for PostgreSQL + Redis to be healthy
#   2. Apply database migrations
#   3. Collect static files
#   4. First-boot: seed default admin user if none exists
#   5. Hand off to CMD (gunicorn / celery / etc.)
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

POSTGRES_HOST="${POSTGRES_HOST:-db}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
REDIS_HOST="${REDIS_HOST:-redis}"

# ─── Wait for PostgreSQL ──────────────────────────────────────────────────────
echo "⏳  Waiting for PostgreSQL at ${POSTGRES_HOST}:${POSTGRES_PORT}..."
until nc -z "${POSTGRES_HOST}" "${POSTGRES_PORT}"; do
  sleep 1
done
echo "✅  PostgreSQL is ready."

# ─── Wait for Redis ───────────────────────────────────────────────────────────
echo "⏳  Waiting for Redis at ${REDIS_HOST}:6379..."
until nc -z "${REDIS_HOST}" 6379; do
  sleep 1
done
echo "✅  Redis is ready."

# ─── Database Migrations ──────────────────────────────────────────────────────
# Only run migrations from the main backend container, not workers/bridge.
# Workers detect this by checking CMD arg.
FIRST_ARG="${1:-}"
if [[ "${FIRST_ARG}" == "gunicorn" ]]; then

  echo "🔧  Applying database migrations..."
  python manage.py migrate --noinput

  echo "📦  Collecting static files..."
  python manage.py collectstatic --noinput --clear

  # ─── First-Boot: Seed Default Admin ─────────────────────────────────────────
  echo "🔑  Checking for initial admin user..."
  python manage.py shell << 'PYEOF'
from monitoring.models import User
from django.contrib.auth.hashers import make_password
import os, secrets

if not User.objects.filter(role='admin').exists():
    default_pass = os.environ.get('ADMIN_DEFAULT_PASSWORD', 'SmartStua@Change-Me!')
    User.objects.create(
        full_name='System Admin',
        phone_number=os.environ.get('ADMIN_PHONE', '+256000000000'),
        email=os.environ.get('ADMIN_EMAIL', 'admin@smartstua.local'),
        role='admin',
        password_hash=make_password(default_pass),
        is_active=True,
    )
    print(f"✅  Default admin created. Phone: {os.environ.get('ADMIN_PHONE', '+256000000000')}")
    print(f"⚠️   Default password is set. CHANGE IT after first login!")
else:
    print("ℹ️   Admin user already exists — skipping seed.")
PYEOF

fi

echo "🚀  Starting: $*"
exec "$@"
