# Smart-Stua — Safe Database Import Instructions

> **SAFE TO RUN:** `loaddata` uses INSERT OR REPLACE semantics.
> Existing production records are updated, not deleted.
> Records only in production (not in the fixture) are left untouched.

## Option A — Render.com (via one-off job or Shell)

In your Render dashboard → smartstua-backend → Shell:

```bash
# Upload fixture files first (scp / git commit / Render CLI)
# Then run in the Render shell:
python manage.py loaddata fixtures/auth_users.json
python manage.py loaddata fixtures/users.json
python manage.py loaddata fixtures/sensor_nodes.json
python manage.py loaddata fixtures/thresholds.json
python manage.py loaddata fixtures/alert_logs.json
```

## Option B — pg_dump / pg_restore (Structural Clone)

```bash
# Dump local Docker PostgreSQL (zero-data-loss append):
docker exec smartstua_db pg_dump \
  -U smartstua -d smartstua_db \
  --data-only --column-inserts \
  --on-conflict-do-nothing \
  -f /tmp/smartstua_data.sql

# Copy dump out of container:
docker cp smartstua_db:/tmp/smartstua_data.sql ./smartstua_data.sql

# Apply to Render PostgreSQL (get URL from Render dashboard):
psql $RENDER_DATABASE_URL < smartstua_data.sql
```

## Exported Models

| Model | Records | Status |
|---|---|---|
| `monitoring.user` | 3 | ✅ |
| `monitoring.sensornode` | 2 | ✅ |
| `monitoring.threshold` | 2 | ✅ |
| `monitoring.alertlog` | 908 | ✅ |
| `monitoring.reading` | skipped | ⏭️ |
| `auth.user` | 4 | ✅ |
| `authtoken.token` | 3 | ✅ |