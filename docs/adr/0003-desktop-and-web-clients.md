# ADR-0003: Desktop and web clients share one React UI

- Status: Accepted, with an open spike
- Date: 2026-11-02

## Decision

- The UI is built with React and Vite. Shared components live in `packages/ui` and the
  typed client in `packages/api-client`, which is generated from the FastAPI OpenAPI
  schema.
- `apps/web` is built into the API image and served by FastAPI at `/`, so it uses
  same-origin calls and portal auth.
- `apps/desktop` is a Tauri 2 shell around the same UI for the Windows PC. It points at
  `VITE_FOTOMIND_API_URL`, which defaults to the local API (`http://127.0.0.1:8000`).

## Open spike

The desktop app calling `https://photos.borrellofamily.co.uk` hits Caddy basic auth.
Browsers do not send credentials on CORS preflight requests, so `OPTIONS` gets a 401.
Options to evaluate:

1. Route API calls through the Tauri HTTP plugin (Rust side), which avoids browser CORS.
2. Load the remote web UI in the Tauri webview (no CORS, but no offline support).
3. Add a Caddy rule that lets `OPTIONS` through without auth for this host.

Until the spike is done, the desktop app is only supported against a local API.
