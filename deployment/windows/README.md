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
| `FOTOMIND_WORKER_TOKEN` | shared worker token (see below)         |
| `FOTOMIND_WORKER_HOST`  | optional, defaults to the computer name |

The worker token is generated on the Pi by `deployment/raspberry-pi/jenkins-setup.sh`
(`~/apps/fotomind/secrets/worker-token`) and passed to the production container by Jenkins
(credential `fotomind-worker-token`). Copy it into `.env` without echoing it:

```powershell
$t = ssh g99trading@192.168.1.129 "cat ~/apps/fotomind/secrets/worker-token"
Add-Content .env "FOTOMIND_WORKER_TOKEN=$($t.Trim())"
```

A local development API without `WORKER_TOKEN` accepts the worker without a token.

Check connectivity and authentication:

```powershell
.\.venv\Scripts\fotomind-worker ping
```

## Usage

```powershell
# Register a folder once (the label is what the web UI shows)
.\.venv\Scripts\fotomind-worker roots add "D:\Photos" --label Photos
.\.venv\Scripts\fotomind-worker roots list

# Scan now: queues a scan job for every root on this PC (or one root by label/ID) and runs it
.\.venv\Scripts\fotomind-worker scan
.\.venv\Scripts\fotomind-worker scan Photos

# The folder moved (new disk, new parent folder)? Point the root at the new location.
# Ratings, tags and albums are kept; run a scan afterwards.
.\.venv\Scripts\fotomind-worker roots move Photos "E:\Archive\Photos"

# Long-running mode: picks up "Scan now" requests made in the web UI
.\.venv\Scripts\fotomind-worker run
```

What a scan does:

- Walks the root (read-only), skipping hidden/system folders, symlinks and junctions.
- Supported: JPEG, PNG, TIFF, CR2, CR3, ARW, MP4, MOV.
- Exclusion patterns (set per root in the web UI under **Sources & jobs**) skip matching
  folders/files, e.g. `Exports`, `*.tmp` or `2019/Scans/*`. A pattern without `/` matches
  any folder or file name; one with `/` matches from the root. Matching is
  case-insensitive. Files already catalogued that become excluded are removed from the
  library on the next scan (the originals are untouched).
- New or changed files (by size + mtime) are hashed (SHA-256). EXIF/video metadata is
  extracted and a 512 px JPEG thumbnail is uploaded to the Pi. Originals never leave the
  PC.
- Unchanged files are only confirmed, so re-scans are fast.
- Files that disappeared are marked `missing`. If the whole root is unreachable (e.g. a
  disconnected disk), it is marked `offline` and nothing is deleted.
- Jobs report progress every few seconds and can be cancelled from the web UI. A job
  whose worker stops sending heartbeats is handed out again after 15 minutes.

Install the media libraries once with `pip install -r requirements-worker.txt` (Pillow,
rawpy/LibRaw, ExifRead and PyAV; all ship wheels for Windows).

## Planned

- RAW+JPEG pairing, larger previews and full-resolution viewing served from the PC.
- Running as a scheduled task or service (`nssm` or Task Scheduler "at logon").
