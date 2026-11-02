# API conventions

- **Base path:** `/api/v1`. Breaking changes need a new version prefix. Within a version,
  only additive changes are allowed.
- **Contract:** FastAPI generates the OpenAPI schema (`/api/openapi.json`, interactive docs at
  `/api/docs`). The TypeScript client in `packages/api-client` is generated from the
  committed `openapi.json` (`scripts/generate-api.ps1`). Regenerate it in the same change
  as any route or schema change.
- **Auth:** every `/api/v1` route except `/api/v1/health` depends on `UserDep`. In
  production the identity comes only from Caddy's `Remote-User` / `Remote-Groups` headers.
  Locally, `DEV_USER` stands in. `GET /health` (portal probe) is unauthenticated.
- **Errors:** FastAPI's default `{"detail": ...}` body with a matching HTTP status
  (401 unauthenticated, 403 forbidden, 404 not found, 409 conflict, 422 validation, 503
  dependency unavailable). Clients throw `ApiError(status, body)`.
- **Naming:** JSON fields use `snake_case`, resources are plural nouns
  (`/api/v1/assets/{asset_id}`), and IDs are UUIDs.
- **Pagination (from EPIC 2):** cursor-based, `?limit=` (default 100, max 500) and
  `?cursor=`. The response is `{"items": [...], "next_cursor": "..." | null}`. Sort order is
  stable (for example `captured_at DESC, id DESC`).
- **Timestamps:** ISO 8601 with a timezone (UTC). Capture times keep the original offset
  when it is known.
- **Long-running work** (scan, render, AI) is modelled as jobs (`JobStatus`). Endpoints
  return `202` with a job id and never block on processing.
- **Worker endpoints** will live under `/api/v1/worker/*`, with separate authorization
  (worker token).

## Current endpoints

| Method | Path                    | Auth   | Purpose                                     |
| ------ | ----------------------- | ------ | ------------------------------------------- |
| GET    | `/health`               | none   | Portal/Jenkins probe, 503 if DB unusable    |
| GET    | `/api/v1/health`        | none   | Liveness only                               |
| GET    | `/api/v1/system/status` | portal | Version, environment, DB status and latency |
| GET    | `/api/v1/me`            | portal | Current portal user and groups              |
