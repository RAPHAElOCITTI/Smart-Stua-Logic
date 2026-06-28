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
REDIS_PORT=6379

if [[ -n "${DATABASE_URL:-}" ]]; then
  echo "🔍 Parsing DATABASE_URL for healthcheck..."
  POSTGRES_HOST=$(python -c "import os; from urllib.parse import urlparse; print(urlparse(os.environ.get('DATABASE_URL')).hostname or 'db')")
  POSTGRES_PORT=$(python -c "import os; from urllib.parse import urlparse; print(urlparse(os.environ.get('DATABASE_URL')).port or 5432)")
fi

if [[ -n "${REDIS_URL:-}" ]]; then
  echo "🔍 Parsing REDIS_URL for healthcheck..."
  REDIS_HOST=$(python -c "import os; from urllib.parse import urlparse; print(urlparse(os.environ.get('REDIS_URL')).hostname or 'redis')")
  REDIS_PORT=$(python -c "import os; from urllib.parse import urlparse; print(urlparse(os.environ.get('REDIS_URL')).port or 6379)")
fi

# ─── Wait for PostgreSQL ──────────────────────────────────────────────────────
echo "⏳  Waiting for PostgreSQL at ${POSTGRES_HOST}:${POSTGRES_PORT}..."
until nc -z "${POSTGRES_HOST}" "${POSTGRES_PORT}"; do
  sleep 1
done
echo "✅  PostgreSQL is ready."

# ─── Wait for Redis ───────────────────────────────────────────────────────────
echo "⏳  Waiting for Redis at ${REDIS_HOST}:${REDIS_PORT}..."
until nc -z "${REDIS_HOST}" "${REDIS_PORT}"; do
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
import os
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User as DjangoUser

ADMIN_EMAIL    = os.environ.get('ADMIN_EMAIL',    'admin@smartstua.local')
ADMIN_PHONE    = os.environ.get('ADMIN_PHONE',    '+256000000000')
ADMIN_PASSWORD = os.environ.get('ADMIN_DEFAULT_PASSWORD', 'SmartStua@Change-Me!')

# ── 1. Django superuser (for /admin/ panel login) ────────────────────────────
if not DjangoUser.objects.filter(username='admin').exists():
    DjangoUser.objects.create_superuser(
        username='admin',
        email=ADMIN_EMAIL,
        password=ADMIN_PASSWORD,
    )
    print(f"✅  Django superuser created.")
    print(f"    Username: admin")
    print(f"    Password: {ADMIN_PASSWORD}")
    print(f"⚠️  CHANGE THIS PASSWORD after first login at /admin/")
else:
    print("ℹ️   Django superuser already exists — skipping.")

# ── 2. Smart-Stua custom User (for mobile app API login) ─────────────────────
from monitoring.models import User
if not User.objects.filter(role='admin').exists():
    User.objects.create(
        full_name='System Admin',
        phone_number=ADMIN_PHONE,
        email=ADMIN_EMAIL,
        role='admin',
        password_hash=make_password(ADMIN_PASSWORD),
        is_active=True,
    )
    print(f"✅  Smart-Stua app user created.")
    print(f"    Phone:    {ADMIN_PHONE}")
    print(f"    Password: {ADMIN_PASSWORD}")
else:
    print("ℹ️   Smart-Stua app user already exists — skipping.")
PYEOF

fi

# Use $PORT if set by Render.com; fall back to 8000 for local Docker
if [[ "${1:-}" == "gunicorn" ]]; then
  # ─── Free Tier background processes ──────────────────────────────────────────
  echo "🌀 Starting Celery Worker (concurrency=1)..."
  celery -A smartstua worker --loglevel=info --concurrency=1 > /app/logs/celery_worker.log 2>&1 &

  echo "⏰ Starting Celery Beat Scheduler..."
  celery -A smartstua beat --loglevel=info > /app/logs/celery_beat.log 2>&1 &

  echo "🔌 Starting MQTT Bridge Daemon..."
  python manage.py mqtt_bridge > /app/logs/mqtt_bridge.log 2>&1 &

  # ─── Foreground Web Server ────────────────────────────────────────────────────
  echo "🚀 Starting Gunicorn Web Server..."
  exec gunicorn smartstua.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-1}" \
    --threads 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
else
  exec "$@"
fi

