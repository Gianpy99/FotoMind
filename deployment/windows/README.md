# Windows PC worker

The worker runs on the Windows PC next to the photo disks and GPU
([ADR-0001](../../docs/adr/0001-hybrid-deployment-topology.md)). It talks to the API on
the Pi over HTTPS only. It never connects to PostgreSQL directly and never modifies
originals ([ADR-0007](../../docs/adr/0007-immutable-originals.md)).

## Setup

```powershell
cd C:\Development\FotoMind
.\scripts\setup-dev.ps1          # or: python -m venv .venv; .\.venv\Scripts\pip install -e .
```

Set the worker variables in `.env` (or as user environment variables):

| Variable                | Value                                   |
| ----------------------- | --------------------------------------- |
| `FOTOMIND_API_URL`      | `https://photos.borrellofamily.co.uk`   |
| `FOTOMIND_API_USER`     | portal login user                       |
| `FOTOMIND_API_PASSWORD` | portal login password (never commit it) |
| `FOTOMIND_CACHE_DIR`    | local cache, e.g. `D:\FotoMindCache`    |

Check connectivity and authentication:

```powershell
.\.venv\Scripts\fotomind-worker ping
```

## Status

EPIC 1 only provides `ping`. Planned next:

- EPIC 2/3: register storage roots, scan, extract metadata, generate thumbnails/previews.
- A dedicated worker token instead of portal basic auth.
- Running as a scheduled task or service (`nssm` or Task Scheduler "at logon").
