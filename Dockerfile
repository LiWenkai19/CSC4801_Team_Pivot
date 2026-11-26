# syntax=docker/dockerfile:1
#
# Builds the complete CSC4801 final-project environment in one image:
#   PostgreSQL 15 + FastAPI (uvicorn) + nginx serving the built React app.
#
# Build:  docker build -t csc4801-final .
# Run:    docker run -d --name csc4801 -p 127.0.0.1:8080:80 csc4801-final
# Then:   docker exec -w /app/backend csc4801 python scripts/seed_demo.py
#
# See INSTALL.md ("Docker Build" / "Docker Startup") for the documented flow.

# ---------------------------------------------------------------- stage 1 ---
# Build the React frontend. Node and node_modules stay out of the final image
# except for what the rendering unit test needs (see stage 2).
FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------- stage 2 ---
FROM python:3.12-slim-bookworm

# Only non-sensitive defaults are baked in. Override at run time with -e.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_NAME="CSC4801 Final Project" \
    COOKIE_SECURE=false \
    DATABASE_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/employ" \
    CANDIDATE_TEST_DATABASE_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/postgres" \
    EMPLOYER_TEST_DATABASE_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/postgres"

# System dependencies:
#   postgresql-15 / client  - the database server shipped inside the image
#   nginx                   - static files + /api reverse proxy
#   supervisor              - runs uvicorn and nginx
#   node                    - copied from stage 1 below (no NodeSource download);
#                             required only by tests/unit/test_rendering.py
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        ca-certificates curl \
        postgresql-15 postgresql-client-15 \
        nginx supervisor \
 && rm -rf /var/lib/apt/lists/* \
 && rm -rf /var/lib/postgresql/15/main /etc/postgresql/15/main

# Node runtime for the rendering unit test. The binary is self-contained apart
# from the standard C/C++ runtime libraries the base image already ships.
COPY --from=frontend /usr/local/bin/node /usr/local/bin/node

WORKDIR /app

# Python dependencies first: this layer is cached until the lock file changes.
COPY requirements.txt requirements.lock ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY README.md INSTALL.md ./

# Application sources, tests (needed by the documented test command) and the
# built frontend. node_modules is copied from the build stage because the
# rendering unit test loads the real React component.
COPY backend/ ./backend/
COPY tests/ ./tests/
COPY frontend/ ./frontend/
COPY --from=frontend /build/dist ./frontend/dist
COPY --from=frontend /build/node_modules ./frontend/node_modules
COPY deploy/ /deploy/

RUN chmod +x /deploy/entrypoint.sh \
 && useradd --create-home --uid 10001 appuser \
 && mkdir -p /var/lib/postgresql/data /var/log/csc4801 \
 && chown -R postgres:postgres /var/lib/postgresql \
 && chown -R www-data:www-data /var/log/csc4801

EXPOSE 80

# Healthy means nginx + uvicorn are both answering: an unauthenticated
# /users/me must return 401 (not 502/504).
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
  CMD curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/api/users/me | grep -q 401 || exit 1

ENTRYPOINT ["/deploy/entrypoint.sh"]
