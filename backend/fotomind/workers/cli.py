"""fotomind-worker: runs on the Windows PC. Scans registered folders and reports metadata and
small thumbnails to the FotoMind API on the Pi. Originals never leave this machine."""

import argparse
import contextlib
import logging
import os
import sys
import time
from pathlib import Path

import httpx

from fotomind.workers.api import WorkerApi
from fotomind.workers.client import api_client
from fotomind.workers.config import WorkerSettings, get_worker_settings
from fotomind.workers.scanner import run_scan_job, volume_id_for

logger = logging.getLogger(__name__)


def _echo(msg: str) -> None:
    print(msg, flush=True)


def _worker_id(settings: WorkerSettings) -> str:
    return f"{settings.worker_host}:{os.getpid()}"


def ping() -> int:
    """Check connectivity and portal authentication against the FotoMind API."""
    settings = get_worker_settings()
    print(f"API: {settings.api_url}")
    try:
        with api_client(settings) as client:
            health = client.get("/health")
            print(f"/health -> {health.status_code} {health.text.strip()}")
            me = client.get("/api/v1/me")
            print(f"/api/v1/me -> {me.status_code} {me.text.strip()}")
    except httpx.HTTPError as exc:
        print(f"Connection failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 0 if health.is_success and me.is_success else 1


def roots_add(path: str, label: str | None) -> int:
    settings = get_worker_settings()
    folder = Path(path).expanduser().resolve()
    if not folder.is_dir():
        print(f"Not a folder: {folder}", file=sys.stderr)
        return 2
    with api_client(settings) as client:
        root = WorkerApi(client).register_root(
            settings.worker_host, str(folder), label or folder.name, volume_id_for(folder)
        )
    print(f"Registered {root['label']} ({root['id']}) on {root['host']}: {root['path']}")
    return 0


def roots_list() -> int:
    settings = get_worker_settings()
    with api_client(settings) as client:
        roots = WorkerApi(client).list_roots(settings.worker_host)
    if not roots:
        print(f"No storage roots registered for host {settings.worker_host}.")
    for r in roots:
        print(
            f"{r['label']:<24} {r['availability']:<8} files={r['file_count']:<6} "
            f"missing={r['missing_count']:<4} last_scan={r['last_scan_at'] or '-'}  {r['path']}"
        )
    return 0


def roots_move(selector: str, new_path: str) -> int:
    """The folder moved (drive letter, renamed parent): point the root at its new location.

    The catalogue (ratings, tags, albums) is kept; the next scan re-checks the files.
    """
    settings = get_worker_settings()
    folder = Path(new_path).expanduser().resolve()
    if not folder.is_dir():
        print(f"Not a folder: {folder}", file=sys.stderr)
        return 2
    with api_client(settings) as client:
        api = WorkerApi(client)
        root = _match_root(api.list_roots(settings.worker_host), selector)
        if root is None:
            print(f"Unknown storage root: {selector}", file=sys.stderr)
            return 2
        moved = api.relocate_root(root["id"], str(folder), volume_id_for(folder))
    print(f"Moved {moved['label']}: {root['path']} -> {moved['path']}")
    print(f"Run 'fotomind-worker scan \"{moved['label']}\"' to re-check its files.")
    return 0


def _match_root(roots: list[dict], selector: str) -> dict | None:
    for r in roots:
        if selector in (r["id"], r["label"], r["path"]):
            return r
    return None


def drain(api: WorkerApi, settings: WorkerSettings, worker_id: str) -> int:
    """Run queued jobs for this host until none are left. Returns how many failed."""
    failures = 0
    while (job := api.claim(settings.worker_host, worker_id)) is not None:
        _echo(f"Job {job['id']} ({job['job_type']})")
        if job["job_type"] != "scan_root":
            api.complete(job["id"], worker_id, False, error="Unsupported job type")
            failures += 1
            continue
        try:
            done = run_scan_job(api, settings, worker_id, job, echo=_echo)
        except Exception as exc:
            logger.exception("job.crashed")
            # If even this fails, the API hands the job out again once its heartbeat is stale.
            with contextlib.suppress(httpx.HTTPError):
                api.complete(job["id"], worker_id, False, error=f"{type(exc).__name__}: {exc}")
            failures += 1
            continue
        _echo(f"  -> {done['status']} {done.get('result') or ''} {done.get('error') or ''}")
        failures += done["status"] != "succeeded"
    return failures


def scan(selector: str | None) -> int:
    """Queue a scan for one root (or every root of this host) and run it now."""
    settings = get_worker_settings()
    with api_client(settings) as client:
        api = WorkerApi(client)
        roots = api.list_roots(settings.worker_host)
        if selector:
            root = _match_root(roots, selector)
            if root is None:
                print(f"Unknown storage root: {selector}", file=sys.stderr)
                return 2
            roots = [root]
        if not roots:
            print("No storage roots registered. Use: fotomind-worker roots add <folder>")
            return 2
        for r in roots:
            api.queue_scan(r["id"])
        return 1 if drain(api, settings, _worker_id(settings)) else 0


def run(once: bool) -> int:
    """Poll for jobs queued from the web UI (e.g. "Scan now") and execute them."""
    settings = get_worker_settings()
    worker_id = _worker_id(settings)
    _echo(f"Worker {worker_id} polling {settings.api_url} every {settings.poll_interval_s}s")
    with api_client(settings) as client:
        api = WorkerApi(client)
        while True:
            try:
                drain(api, settings, worker_id)
            except httpx.HTTPError as exc:
                _echo(f"API unavailable ({type(exc).__name__}); retrying")
            if once:
                return 0
            time.sleep(settings.poll_interval_s)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="fotomind-worker", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ping", help="check API connectivity and authentication")

    roots = sub.add_parser("roots", help="manage the folders this PC exposes to FotoMind")
    roots_sub = roots.add_subparsers(dest="roots_command", required=True)
    add = roots_sub.add_parser("add", help="register a folder (read-only) as a storage root")
    add.add_argument("path")
    add.add_argument("--label")
    roots_sub.add_parser("list", help="list the storage roots of this PC")
    move = roots_sub.add_parser("move", help="point a root at the folder's new location")
    move.add_argument("root", help="root id, label or old path")
    move.add_argument("path", help="new folder location")

    scan_p = sub.add_parser("scan", help="scan a storage root now (default: all of this PC)")
    scan_p.add_argument("root", nargs="?", help="root id, label or path")

    run_p = sub.add_parser("run", help="process jobs queued from the web UI")
    run_p.add_argument("--once", action="store_true", help="drain the queue and exit")

    args = parser.parse_args(argv)
    try:
        if args.command == "ping":
            return ping()
        if args.command == "roots":
            if args.roots_command == "add":
                return roots_add(args.path, args.label)
            if args.roots_command == "move":
                return roots_move(args.root, args.path)
            return roots_list()
        if args.command == "scan":
            return scan(args.root)
        if args.command == "run":
            return run(args.once)
    except httpx.HTTPError as exc:
        print(f"API error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    return 1


if __name__ == "__main__":
    sys.exit(main())
