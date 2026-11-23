#!/usr/bin/env bash
#
# Container startup:
#   1. initialise the PostgreSQL data directory on first boot
#   2. start PostgreSQL and wait until it accepts connections
#   3. create the application database if missing
#   4. run Alembic migrations
#   5. hand over to supervisord (uvicorn + nginx)
#
# Idempotent: restarting the container reuses the existing cluster and only
# applies migrations that are still pending.
set -euo pipefail

PGBIN=/usr/lib/postgresql/15/bin
PGDATA=/var/lib/postgresql/data
PGLOG=/var/log/csc4801/postgres.log

DB_NAME="${POSTGRES_DB:-employ}"
DB_USER="${POSTGRES_USER:-postgres}"
DB_PASSWORD="${POSTGRES_PASSWORD:-postgres}"

log() { printf '[entrypoint] %s\n' "$*"; }

mkdir -p "$PGDATA" /var/log/csc4801
chown -R postgres:postgres "$PGDATA" /var/log/csc4801

if [ ! -s "$PGDATA/PG_VERSION" ]; then
    log "initialising PostgreSQL cluster in $PGDATA"
    printf '%s' "$DB_PASSWORD" > /tmp/pgpass
    chown postgres:postgres /tmp/pgpass
    chmod 600 /tmp/pgpass
    su postgres -s /bin/bash -c \
        "$PGBIN/initdb -D '$PGDATA' -U '$DB_USER' --pwfile=/tmp/pgpass \
         --auth=scram-sha-256 --encoding=UTF8 --locale=C.UTF-8"
    rm -f /tmp/pgpass

    cat >> "$PGDATA/postgresql.conf" <<'EOF'

# --- managed by the container entrypoint ---
listen_addresses = '127.0.0.1'
port = 5432
unix_socket_directories = '/tmp'
EOF
fi

log "starting PostgreSQL"
su postgres -s /bin/bash -c \
    "$PGBIN/pg_ctl -D '$PGDATA' -l '$PGLOG' -w start" || {
        log "pg_ctl failed; last log lines:"
        tail -n 40 "$PGLOG" || true
        exit 1
    }

for _ in $(seq 1 60); do
    if "$PGBIN/pg_isready" -h 127.0.0.1 -p 5432 -q; then
        break
    fi
    sleep 1
done
if ! "$PGBIN/pg_isready" -h 127.0.0.1 -p 5432 -q; then
    log "PostgreSQL did not become ready in 60s; last log lines:"
    tail -n 40 "$PGLOG" || true
    exit 1
fi

if ! PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -U "$DB_USER" -tAc \
        "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1; then
    log "creating database $DB_NAME"
    PGPASSWORD="$DB_PASSWORD" createdb -h 127.0.0.1 -U "$DB_USER" "$DB_NAME"
fi

cd /app/backend
log "applying Alembic migrations"
python -m alembic upgrade head

log "starting supervisord (uvicorn on 127.0.0.1:8000, nginx on :80)"
exec /usr/bin/supervisord -c /deploy/supervisord.conf
