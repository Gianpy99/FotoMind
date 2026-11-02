# FotoMind

A local-first personal photo and video library with non-destructive RAW development and
AI-assisted organisation and enhancement. Originals are never modified (ADR-0007).

Product requirements: [docs/product/FotoMind_PRD_v1.1.docx](docs/product/FotoMind_PRD_v1.1.docx).
Current release target: **MVP-0 / EPIC 1 (foundation)**. See [docs/backlog.md](docs/backlog.md).

## Topology (Family Portal hybrid)

| Component     | Runs on                         | Notes                                                           |
| ------------- | ------------------------------- | --------------------------------------------------------------- |
| API + web UI  | Raspberry Pi (Docker container) | Served by Caddy at `photos.borrellofamily.co.uk`, portal auth   |
| PostgreSQL 15 | Raspberry Pi (native, `:5432`)  | Dedicated `fotomind` database and role                          |
| Worker        | Windows PC                      | Next to the photo HDDs and GPU; talks to the API only via HTTPS |
| Desktop app   | Windows PC (Tauri)              | Same React UI as the web app                                    |

Rationale and trade-offs: [ADR-0001](docs/adr/0001-hybrid-deployment-topology.md).

### Family Portal contract

| Item           | Value                                                      |
| -------------- | ---------------------------------------------------------- |
| App id         | `fotomind`                                                 |
| Public URL     | https://photos.borrellofamily.co.uk/                       |
| Host port      | `127.0.0.1:8097` → container `8000`                        |
| Health         | `GET /health` (no login; 200 only when the DB is usable)   |
| Auth           | `portal` (Caddy `app_portal`, `Remote-User` header)        |
| Data volume    | `fotomind-data` → `/app/data`                              |
| Jenkins secret | `fotomind-database-url`                                    |
| Deploy         | Every push to `main` (Jenkins on the Pi polls every 3 min) |

Admin onboarding steps: [docs/operations/family-portal-onboarding.md](docs/operations/family-portal-onboarding.md).

## Repository layout

```
backend/fotomind/      FastAPI modular monolith (api, domain, modules, infrastructure, workers)
database/migrations/   Alembic migrations (run automatically at startup)
apps/web/              React + Vite web UI (served by the API in production)
apps/desktop/          Tauri 2 desktop shell around the same UI
packages/api-client/   Typed API client generated from the OpenAPI schema
packages/ui/           Shared React components
tests/                 Backend unit + integration tests
deployment/            Local, Raspberry Pi and Windows worker assets
docs/                  ADRs, architecture, API conventions, operations, backlog
```

## Development quick start

Prerequisites: Python 3.12+, Node 22 and SSH access to the Pi. **No Docker on the PC.**
Docker checks run in the Pi development space `~/apps/fotomind` through
`scripts/pi-check.ps1`. Rust is only needed for the desktop app. Full guide:
[docs/development.md](docs/development.md).

```powershell
.\scripts\setup-dev.ps1                 # venv + pip install + npm ci + .env
.\.venv\Scripts\fotomind-api            # API on http://127.0.0.1:8000 (/api/docs), DB fotomind_dev on the Pi
npm run dev:web                         # UI on http://localhost:5173
```

Checks:

```powershell
.\.venv\Scripts\ruff check . ; .\.venv\Scripts\ruff format --check .
.\.venv\Scripts\pytest
npm run typecheck ; npm run lint ; npm test ; npm run build
.\scripts\pi-check.ps1                  # docker build --target test on the Pi (same gate as Jenkins)
```

After changing API routes, regenerate the client: `.\scripts\generate-api.ps1`.
