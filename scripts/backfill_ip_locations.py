"""Backfill historical IP geolocation into normalized analysis tables."""

from __future__ import annotations

import argparse
import json

from core.database import SessionLocal, ensure_schema_ready
from modules.ip_geo.backfill import backfill_missing_ip_locations


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill missing IP geolocation fields")
    parser.add_argument("--batch-size", type=int, default=200, help="Distinct public IPs to resolve per batch")
    parser.add_argument("--limit", type=int, default=None, help="Maximum distinct IPs to resolve in this run")
    parser.add_argument("--task-id", type=str, default=None, help="Only backfill rows for a specific task")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    ensure_schema_ready()

    with SessionLocal() as db:
        result = backfill_missing_ip_locations(
            db,
            batch_size=args.batch_size,
            limit=args.limit,
            task_id=args.task_id,
        )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
