# Backlog

Source: PRD v1.1 §12. Status: ✅ done · 🟡 partial · ⬜ todo.
Topology differences from the PRD are covered in [ADR-0001](adr/0001-hybrid-deployment-topology.md).

## EPIC 0: Decisions and environment

- ⬜ 0.1 Confirm Windows host CPU/GPU/RAM and NVMe cache space
- 🟡 0.2 Record versions (dev: Python 3.13, Node 22, Docker 28; Pi: Debian 12 aarch64)
- ✅ 0.3 Inspect the Pi: Debian 12, PostgreSQL 15 native on **5432**, 8 GB RAM, NVMe
- ✅ 0.4 Validate DB access from the container (`pg_hba` for the Docker subnet) and the firewall
- ✅ 0.5 ADRs for deployment and job execution (ADR-0001 … 0007)

## EPIC 1: Repository and vertical slice

- ✅ 1.1 Monorepo (backend, apps, packages, database, deployment, docs)
- ✅ 1.2 FastAPI health endpoints (`/health`, `/api/v1/health`, `/api/v1/system/status`)
- ✅ 1.3 React web shell (served by the API)
- 🟡 1.4 Tauri desktop shell (scaffolded, needs Rust to build; remote-auth spike in ADR-0003)
- ✅ 1.5 Shared API client/types generated from OpenAPI
- ✅ 1.6 Configuration and secrets (env vars, Jenkins credentials, `.env.example`)
- ✅ 1.7 Structured JSON logs to stdout
- ✅ 1.8 CI pipeline (Jenkinsfile, Docker `test` stage)
- ✅ 1.9 Dev setup docs

## EPIC 2: Database foundation

- ✅ 2.1 Dedicated `fotomind` DB/user on the Pi ([script](../deployment/raspberry-pi/create-database.sql)) +
  dev/test DBs for the `fotomind_dev` role ([script](../deployment/raspberry-pi/create-dev-databases.sql))
- ✅ 2.2 Network policy (`pg_hba`, LAN only)
- ✅ 2.3 SQLAlchemy models + migration `0002_catalog` (storage_root, media_asset, media_file, job; ADR-0002)
- ✅ 2.4 Alembic baseline (`pg_trgm`)
- ✅ 2.5 Health/readiness checks
- ⬜ 2.6 pgvector spike (ADR-0006)
- ⬜ 2.7 Dump/restore rehearsal ([runbook](operations/database-backup-restore.md))
- ✅ Worker authentication (portal login + `X-FotoMind-Worker-Token`) + `/api/v1/worker/*` endpoints

## EPIC 3: Storage and import

- ✅ 3.1 Storage-root registration (`fotomind-worker roots add`)
- ✅ 3.2 Volume identity (Windows volume serial)
- ✅ 3.3 Path normalisation/security (relative POSIX paths, no `..`/drives)
- ✅ 3.4 Scanner (JPEG, PNG, CR2/CR3, ARW, MP4/MOV; incremental by size+mtime)
- ✅ 3.5 Restartable import jobs (queue, claim with `SKIP LOCKED`, heartbeat, stale reclaim, cancel)
- ✅ 3.6 SHA-256 per file
- 🟡 3.7 Duplicates: identical content shares one asset and moves are tracked; RAW+JPEG pairing todo
- ✅ 3.8 EXIF (capture time, camera, lens, dimensions, orientation; video duration/creation time)
- 🟡 3.9 Thumbnails (512 px JPEG uploaded to the Pi data volume); larger previews todo
- ✅ 3.10 Missing-file detection (unseen files → `missing`; offline root → `offline`)

## EPIC 4: Library UX

- ✅ 4.1 Grid
- 🟡 4.2 Viewer (thumbnail only; full resolution needs the PC)
- ✅ 4.3 Metadata panel
- 🟡 4.4 Filters/sort/pagination (type filter, newest first, cursor paging)
- ⬜ 4.5 Ratings/tags · ⬜ 4.6 Albums
- ✅ 4.7 Job progress UI (Sources & jobs)
- ✅ 4.8 LAN/remote web access (photos.borrellofamily.co.uk via the portal)
- ✅ 4.9 Keyboard navigation (←/→/Esc in the viewer)

## EPIC 5: Search

⬜ 5.1 Metadata query API · 5.2 Full-text/trigram · 5.3 Embedding benchmark · 5.4 Embedding worker ·
5.5 Vector storage/search · 5.6 Semantic search UI · 5.7 Reindex strategy

## EPIC 6: RAW and conventional development

⬜ 6.1 CR2/ARW/JPEG samples · 6.2 rawpy/LibRaw · 6.3 RawTherapee spike · 6.4 Quality comparison ·
6.5 Edit-settings schema · 6.6 Preview renderer · 6.7 Edit history · 6.8 JPEG/TIFF export ·
6.9 Lens profiles

## EPIC 7: AI enhancement

⬜ 7.1 Task/provider contracts · 7.2 Local runtime benchmark · 7.3–7.6 Deblur/upscale/denoise/face
restoration benchmarks · 7.7 Closed-eye spike · 7.8 Cloud consent UX · 7.9 Job orchestration ·
7.10 Before/after review · 7.11 Provenance/cost records

## EPIC 8: Backup and operations

⬜ 8.1 Media manifest export · 8.2 DB backup automation · 8.3 Offsite backup · 8.4 Checksum
verification · 8.5 Restore test · 8.6 Backup dashboard · 8.7 Disk health/space reporting

## EPIC 9: People and identity

⬜ 9.1 Domain models · 9.2 Migrations · 9.3 People UI · 9.4 Local face detector · 9.5 Review queue ·
9.6 Embedding benchmark/thresholds · 9.7 Embeddings from confirmed samples · 9.8 Candidate
matching · 9.9 Corrections/deletion · 9.10 Privacy controls/audit · 9.11 Synthetic fixtures
