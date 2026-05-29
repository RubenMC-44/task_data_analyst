#!/usr/bin/env python3
"""Replay a session CSV onto a Redis Stream to simulate a live 1 Hz feed.

This is provided as a convenience for the optional realtime bonus. You do NOT
need it for the batch deliverable. If you tackle the bonus, run this producer
and build your own consumer against the contract below.

Contract
--------
- Transport: a single Redis Stream, key `lps:session:{session}` (override with
  --stream). Entries are appended in time order with auto-generated IDs.
- Each entry's fields are the CSV columns for one sample, as strings. Empty CSV
  cells are omitted from the entry (so a missing field == NULL, not "").
- `time_stamp` is always present and is the idempotency key: dedupe / upsert on
  (session, time_stamp). Re-running this producer republishes the same rows with
  new stream IDs, so never key off the stream ID.
- The stream is capped (--maxlen, approximate) so memory stays bounded.

Run
---
    docker run -p 6379:6379 redis:8-alpine          # or any local Redis
    python stream_replay.py --session sessions/session_19423.csv --speed 60
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

import redis


def parse_ts(raw: str) -> datetime:
    """Parse a Postgres timestamptz string, tolerating a `+00` style offset."""
    normalized = raw.strip()
    if len(normalized) >= 3 and normalized[-3] in "+-" and normalized[-2:].isdigit():
        normalized = f"{normalized}:00"
    return datetime.fromisoformat(normalized)


def replay(args: argparse.Namespace) -> int:
    src = Path(args.session)
    if not src.exists():
        raise FileNotFoundError(f"session CSV not found: {src.resolve()}")

    stream = args.stream or f"lps:session:{src.stem.split('_')[-1]}"
    client = redis.Redis(host=args.host, port=args.port, decode_responses=True)

    print(f"replaying {src.name} -> stream '{stream}' at {args.speed}x", file=sys.stderr)

    sent = 0
    prev_ts: datetime | None = None
    with src.open("r", newline="") as fin:
        reader = csv.DictReader(fin)
        if reader.fieldnames is None or "time_stamp" not in reader.fieldnames:
            raise ValueError("CSV missing required `time_stamp` column")

        for row in reader:
            ts = parse_ts(row["time_stamp"])
            if prev_ts is not None and args.speed > 0:
                gap = (ts - prev_ts).total_seconds() / args.speed
                if gap > 0:
                    time.sleep(min(gap, args.max_sleep))
            prev_ts = ts

            fields = {k: v for k, v in row.items() if v != "" and v is not None}
            entry_id = client.xadd(stream, fields, maxlen=args.maxlen, approximate=True)

            sent += 1
            print(f"→ {entry_id}  {ts.isoformat()}  ({len(fields)} fields)  {fields}", flush=True)

            if args.limit and sent >= args.limit:
                break

    print(f"done — {sent} rows replayed to '{stream}'", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Replay a session CSV onto a Redis Stream.")
    p.add_argument("--session", required=True, help="path to a slimmed session CSV")
    p.add_argument("--stream", default=None, help="stream key (default: lps:session:<id>)")
    p.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="time compression: 1.0 = real cadence, 60 = 60x faster (default 1.0)",
    )
    p.add_argument("--max-sleep", type=float, default=5.0, help="cap per-row sleep seconds")
    p.add_argument("--maxlen", type=int, default=100_000, help="approx stream length cap")
    p.add_argument("--limit", type=int, default=0, help="stop after N rows (0 = all)")
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=6379)
    return p


if __name__ == "__main__":
    sys.exit(replay(build_parser().parse_args()))
