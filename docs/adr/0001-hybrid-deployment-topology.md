# ADR-0001: Hybrid deployment topology (Pi API + Windows worker)

- Status: Accepted
- Date: 2026-11-02
- Supersedes: PRD §7.1 deployment assumption (API hosted on the Windows PC)

## Context

PRD §7.1 places the whole backend on the Windows PC. All family apps, however, are hosted
on the Raspberry Pi under the Family Portal standard: one Docker container per app, Caddy
reverse proxy with portal auth, the shared native PostgreSQL 15 and Jenkins deploying on
each push to `main`. The photo library (originals) lives on the PC's HDDs, and the PC has
the GPU needed for RAW rendering and AI.

## Decision

FotoMind is a **modular monolith** split across two runtimes:

1. **API + web UI on the Pi.** A single container (`fotomind`, `127.0.0.1:8097` → `8000`)
   behind Caddy (`import app_portal 8097`). It owns the catalogue (PostgreSQL `fotomind`
   database on the Pi, port 5432), auth (`Remote-User`), the job queue and derived assets
   that are small enough for the Pi (thumbnails and previews in the `fotomind-data`
   volume).
2. **Worker on the Windows PC.** `fotomind-worker` reads the originals on the local disks,
   runs scanning, metadata extraction, RAW rendering and AI inference, and reports results
   to the API over HTTPS. It **never connects to PostgreSQL directly** and never uploads
   originals.

Everything else from the portal standard applies: `GET /health`, 401 without `Remote-User`
in production, idempotent migrations at startup, logs to stdout and ARM64 images.

## Consequences

- The PC can be off. The library stays browsable from previews, and processing jobs wait
  in the queue. Asset availability (`Availability` enum) reflects this.
- Worker authentication is needed. It currently uses portal basic auth, and a dedicated
  worker token is planned for EPIC 2.
- Pi resource limits (8 GB RAM, ARM64) rule out heavy processing on the API side.
- pgvector is not available on the Pi's PostgreSQL (see ADR-0006).
- Upload bandwidth from the PC to the Pi is limited to derived files (thumbnails and
  previews). Exports and full-resolution renders stay on the PC.
