# Development guide

## Prerequisites

- Python 3.12+ (3.13 works), Node 22 + npm 10, and SSH key access to the Pi
  (`g99trading@192.168.1.129`).
- Rust (stable) + the WebView2 runtime, only for `npm run dev:desktop` (Tauri).
- **No Docker on the PC.** Everything containerised runs in the Pi development space
  `~/apps/fotomind` (see [Docker checks on the Pi](#docker-checks-on-the-pi)).

## Setup

```powershell
.\scripts\setup-dev.ps1
```

`.env` (copied from `.env.example`) points `DATABASE_URL` at the `fotomind_dev` database on
the Pi's PostgreSQL. The admin creates it once with
[create-dev-databases.sql](../deployment/raspberry-pi/create-dev-databases.sql), using a
separate `fotomind_dev` role so development can't touch production. Fill in the password
in your local `.env`. Leave `DATABASE_URL` empty to run the API without a database;
`/health` still reports ok outside production.

## Run

```powershell
.\.venv\Scripts\fotomind-api     # http://127.0.0.1:8000, docs at /api/docs, migrations on start
npm run dev:web                  # http://localhost:5173, proxies /api and /health to :8000
npm run dev:desktop              # Tauri window (needs Rust)
.\.venv\Scripts\fotomind-worker ping
```

Try the full flow against the local API (dev DB on the Pi; thumbnails go to `.data\thumbnails`):

```powershell
.\.venv\Scripts\fotomind-worker roots add "C:\path\to\some\photos" --label Test
.\.venv\Scripts\fotomind-worker scan     # then open http://localhost:5173
```

See [deployment/windows/README.md](../deployment/windows/README.md) for all worker commands.

Locally you are the `DEV_USER` (default `dev`). To simulate the portal, send
`Remote-User: alice` and `Remote-Groups: family,admins`.

## Docker checks on the Pi

[scripts/pi-check.ps1](../scripts/pi-check.ps1) copies the working tree (tracked and
untracked files that aren't git-ignored) to `~/apps/fotomind/src` on the Pi and runs Docker
there:

```powershell
.\scripts\pi-check.ps1                # docker build --target test (same gate as Jenkins)
.\scripts\pi-check.ps1 -Integration   # + integration tests against fotomind_test
.\scripts\pi-check.ps1 -Run           # + dev container fotomind-dev on the Pi's 127.0.0.1:18097
.\scripts\pi-check.ps1 -Stop          # stop the dev container
ssh -L 18097:127.0.0.1:18097 g99trading@192.168.1.129   # then open http://localhost:18097
```

`-Integration` and `-Run` need `~/apps/fotomind/.env` on the Pi (copy
[dev.env.example](../deployment/raspberry-pi/dev.env.example), `chmod 600`). The script
never touches the production container `fotomind` or the `fotomind:latest` image.

## Checks

| What               | Command                                                                                                         |
| ------------------ | --------------------------------------------------------------------------------------------------------------- |
| Python lint/format | `.\.venv\Scripts\ruff check .` / `ruff format --check .`                                                        |
| Python tests       | `.\.venv\Scripts\pytest`                                                                                        |
| DB integration     | `$env:FOTOMIND_TEST_DATABASE_URL = "<see .env.example>"; pytest -m integration`, or `pi-check.ps1 -Integration` |
| TS types           | `npm run typecheck`                                                                                             |
| Lint / format      | `npm run lint` / `npm run format:check`                                                                         |
| Frontend tests     | `npm test`                                                                                                      |
| Same as Jenkins    | `.\scripts\pi-check.ps1` (runs on the Pi)                                                                       |

## Migrations

```powershell
.\.venv\Scripts\alembic revision --rev-id 0002 -m "short description"   # next sequential id
.\.venv\Scripts\alembic upgrade head
```

Files are named `YYYYMMDD_NNNN_slug.py`; always pass the next `--rev-id`. Never edit a
migration that has reached `main`, because it has already run on the Pi.

## API client

After changing routes or schemas, run `.\scripts\generate-api.ps1` and commit
`packages/api-client/openapi.json` and `src/schema.d.ts`.

## Branching

**Every push to `main` deploys to the Pi.** Work on feature branches and merge only when
`.\scripts\pi-check.ps1` passes.

## Notes

- TypeScript is pinned to `~5.9` because `typescript-eslint` and `openapi-typescript` don't
  support TS 6+ yet.
- The Pi has Docker 20.10 (classic builder, no buildx) and the standalone `docker-compose`
  1.29. There is no `docker compose` plugin, so keep the Dockerfile and
  [docker-compose.yml](../docker-compose.yml) compatible with both.
