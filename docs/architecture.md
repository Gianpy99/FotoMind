# Architecture

FotoMind is a **modular monolith** (single FastAPI process) deployed in the Family Portal
hybrid topology ([ADR-0001](adr/0001-hybrid-deployment-topology.md)).

```
 Browser ──HTTPS──> Caddy (Pi, app_portal: basic auth → Remote-User)
                      │
                      ▼ 127.0.0.1:8097
           ┌──────────────────────────────┐        ┌──────────────────────┐
           │ fotomind container (Pi)      │        │ PostgreSQL 15 (Pi)   │
           │  FastAPI /api/v1 + web UI /  │──5432─▶│ database: fotomind   │
           │  volume fotomind-data        │        └──────────────────────┘
           └──────────────────────────────┘
                      ▲ HTTPS (portal auth / worker token)
                      │
           ┌──────────────────────────────┐
           │ fotomind-worker (Windows PC) │── read-only ──▶ photo HDDs (originals)
           │  scan, metadata, RAW, AI     │── GPU
           └──────────────────────────────┘
           Tauri desktop app (PC) uses the same React UI
```

## Backend layers (`backend/fotomind`)

| Package           | Responsibility                                                                                                                                            |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `api/`            | HTTP: routers, auth dependency, SPA serving. No business rules.                                                                                           |
| `application/`    | Cross-module use cases and orchestration.                                                                                                                 |
| `domain/`         | Shared enums and value objects (pure Python).                                                                                                             |
| `modules/<name>/` | Feature modules: library, metadata, storage, video, search, imaging, editing, ai, people, backup. Each one owns its rules, ports and persistence mapping. |
| `infrastructure/` | Database engine/session, migrations, external adapters.                                                                                                   |
| `workers/`        | Windows worker CLI and its HTTP client to the API.                                                                                                        |

Rules:

- Modules communicate through application services or explicit interfaces, never through
  each other's tables.
- Heavy processing (decoding, rendering, AI) only runs in the worker, never in the Pi API.
- Originals are read-only everywhere ([ADR-0007](adr/0007-immutable-originals.md)).

## Data

PostgreSQL is the source of truth for the catalogue ([ADR-0002](adr/0002-storage-model.md)).
Alembic migrations live in `database/migrations` and run at startup. They must be
idempotent and backward compatible with the previous image, because Jenkins can roll back.

## Frontend

React + Vite in `apps/web`, Tauri 2 in `apps/desktop`, and shared code in `packages/ui` and
`packages/api-client` ([ADR-0003](adr/0003-desktop-and-web-clients.md)).

## Build and deploy

A multi-stage `Dockerfile` (web build → web tests → Python tests → slim runtime) runs on the
Pi's Jenkins (`Jenkinsfile`). The `test` target gates every deploy, and the image runs as
uid 1000 with a `HEALTHCHECK`.
