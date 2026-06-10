# ═══════════════════════════════════════════════════════════════════════════════
# Smart-Stua Backend — Production Dockerfile (multi-stage)
# ═══════════════════════════════════════════════════════════════════════════════

# ─── Stage 1: Dependency Builder ─────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps needed to compile C extensions (psycopg2 wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# ─── Stage 2: Production Runtime ─────────────────────────────────────────────
FROM python:3.11-slim AS production

# Env hardening
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=smartstua.settings \
    PORT=8000

WORKDIR /app

# Runtime system deps only (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        netcat-openbsd \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    # Non-root user for security
    && groupadd -r appuser \
    && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Install pre-built wheels (no compiler needed in final image)
COPY --from=builder /wheels /wheels
RUN pip install --no-cache /wheels/* && rm -rf /wheels

# Copy application source
COPY . .

# Create directories and set ownership
RUN mkdir -p /app/staticfiles /app/logs \
    && chown -R appuser:appuser /app

# Entrypoint script (migrations, collectstatic, first-boot seed)
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER appuser
EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]

# Default: Gunicorn with 4 workers (override in compose for celery/beat/bridge)
CMD ["gunicorn", "smartstua.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--threads", "2", \
     "--timeout", "120", \
     "--access-logfile", "/app/logs/access.log", \
     "--error-logfile", "/app/logs/error.log"]
