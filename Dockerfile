# syntax=docker/dockerfile:1
# FotoMind API + web UI for the Family Portal (ARM64 Raspberry Pi and x86 both work).
#   docker build --target test .   -> web typecheck/lint/tests + backend lint/tests (used by Jenkins)
#   docker build .                 -> runtime image (FastAPI serving the built web UI on :8000)

# ---- Web UI -----------------------------------------------------------------
FROM node:22-alpine AS web
WORKDIR /src
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/
COPY apps/desktop/package.json apps/desktop/
COPY packages/api-client/package.json packages/api-client/
COPY packages/ui/package.json packages/ui/
RUN npm ci --no-audit --no-fund
COPY tsconfig.base.json eslint.config.js vitest.config.ts .prettierrc.json .prettierignore ./
COPY packages packages
COPY apps/web apps/web
COPY apps/desktop/package.json apps/desktop/tsconfig.json apps/desktop/vite.config.ts apps/desktop/index.html apps/desktop/
COPY apps/desktop/src apps/desktop/src
RUN npm run build

FROM web AS web-test
RUN npm run typecheck && npm run lint && npm test && touch /tmp/web-tests-passed

# ---- Backend ----------------------------------------------------------------
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/backend
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY pyproject.toml alembic.ini ./
COPY backend backend
COPY database database

FROM base AS test
# Pulls in the web-test stage so `--target test` also runs the frontend checks.
COPY --from=web-test /tmp/web-tests-passed /tmp/web-tests-passed
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
COPY tests tests
RUN ruff check backend tests && ruff format --check backend tests && pytest -q

FROM base AS runtime
COPY --from=web /src/apps/web/dist /app/web
RUN useradd --create-home --uid 1000 app && mkdir -p /app/data && chown app:app /app/data
USER app
ENV APP_ENV=production \
    HOST=0.0.0.0 \
    PORT=8000 \
    DATA_DIR=/app/data \
    WEB_DIST_DIR=/app/web \
    LOG_FORMAT=json
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=4).status == 200 else 1)"
# Alembic migrations run in the app lifespan on every start (idempotent).
CMD ["python", "-m", "uvicorn", "fotomind.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
