"""fotomind-worker command line. Job execution (import, thumbnails, RAW, AI) comes in EPIC 3+."""

import argparse
import sys

import httpx

from fotomind.workers.client import api_client
from fotomind.workers.config import get_worker_settings


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fotomind-worker", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ping", help="check API connectivity and authentication")
    args = parser.parse_args(argv)
    if args.command == "ping":
        return ping()
    return 1


if __name__ == "__main__":
    sys.exit(main())
