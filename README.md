# Data Engineering Take-Home Task

## Context

We operate a fleet of laser-equipped trains and brushcars across multiple transit systems. Each vehicle streams sensor data — lasers, pressure, GPS, system health — roughly once per second. A "session" is one continuous operating run of a vehicle.

This repo includes everything you need:

- Two sample sessions as CSVs in `sessions/`: `session_19423.csv` and `session_20198.csv`
- Schema documentation in [`SCHEMA.md`](SCHEMA.md) — full per-column reference (units, bitmask layouts, enums, and gotchas)

## Task

Build a Python pipeline that ingests the **2 provided session CSVs** and produces:

### 1. Aggregated per-minute metrics

Persisted to a new table or file. The choice of sink is yours — justify it in the README.

### 2. Anomaly flags

Across lasers, pressure, and GPS. There are no labels — you define what "anomalous" means. Document your reasoning.

### 3. A Streamlit dashboard

The dashboard must let a viewer answer the questions below. You choose the chart types.

**Session-understanding questions:**

- Where did the train go, and how fast?
- When were the lasers on / off, and how many at a time?
- Did blower and compressor pressure stay in their operating ranges?
- Were laser and optics temperatures stable, or did any individual laser drift?
- How healthy was the GPS signal (satellites, dilution, dropouts)?
- When did anomalies fire, and what kind?

## What we care about

- **Code structure** — modular, readable, testable
- **Idempotency** — running your pipeline twice does not double-count or corrupt state
- **Query / aggregation quality** — efficient, correct aggregation against whatever sink you choose; keep it readable and indexed for the query patterns the dashboard needs
- **Anomaly definition** — justified, not arbitrary
- **Chart reasoning** — defensible choices for chart type

## Bonus (optional)

The core task above should fit in 8 hours. The items below are where to spend more time if you have it — pick what interests you. None are required.

### Productionization writeup

In your README, describe how you'd run this nightly, handle new sessions arriving continuously, and how you'd extend it to Airflow + dbt.

### Realtime streaming

Handle session data in **realtime** at a rate of roughly **1 data point per second**. Focus on:

- Windowed aggregation that closes minute-buckets correctly
- Anomaly detection on a streaming window
- Idempotent writes on reconnect
- Live update in the Streamlit dashboard

### Provided: a replay producer

You don't need to stand up a real feed — we ship one. `stream_replay.py` reads a
session CSV and replays it onto a Redis Stream, paced by the real `time_stamp`
gaps (so non-uniform cadence and dropouts come through as they happened). Your
job is the **consumer**: read the stream, aggregate, flag anomalies, and update
the dashboard live.

```bash
# 1. start a Redis (any local instance is fine)
docker run -p 6379:6379 redis:8-alpine

# 2. install deps + replay a session (60x faster than real time for demos)
uv sync
uv run stream_replay.py --session sessions/session_19423.csv --speed 60
```

Useful flags: `--speed` (1.0 = real cadence), `--limit N`, `--stream`, `--host/--port`.

**Stream contract**

- One Redis Stream per session, key `lps:session:{id}` (override with `--stream`).
- Each entry's fields are that sample's CSV columns, as strings. Empty cells are
  omitted — a **missing field means NULL**, not `""`. Booleans are `t`/`f`.
- `time_stamp` is always present and is the **idempotency key**: dedupe / upsert
  on `(session, time_stamp)`. Re-running the producer republishes the same rows
  with new stream IDs, so never key off the stream ID.
- Resume after a disconnect by checkpointing the last consumed stream ID and
  `XREAD`-ing from it (Redis Streams retain history; pub/sub channels would not).

Minimal consumer skeleton:

```python
import redis

r = redis.Redis(decode_responses=True)
last = "0-0"  # persist this to resume on reconnect
while True:
    for _, entries in r.xread({"lps:session:19423": last}, block=5000, count=200):
        for entry_id, fields in entries:
            last = entry_id
            handle(fields)  # fields["time_stamp"], fields["gps_speed"], ...
```

Do not let the bonus compromise the batch deliverable.

## Stack

- Python 3.10 or newer
- Free choice on libraries (pandas, polars, duckdb, dbt — whatever fits)
- Source is the provided session CSVs; output sink is your choice (Parquet, SQLite, DuckDB, etc.) — justify it

## Deliverable

A GitHub repo (public or shared private) containing:

- All code
- `README.md` with:
  - How to run
  - Assumptions you made
  - What you cut for time
  - For every chart: the question it answers and why that chart type
  - _(optional)_ How you'd productionize, scale beyond these two sessions, and extend to Airflow + dbt
- A requirements file or lockfile so we can reproduce your environment

We should be able to run your Streamlit app locally and step through your pipeline end-to-end.

## Time

Target **8 hours of focused work** for the core task, spread across up to one week. Bonuses are extra. We do not expect a polished production system. We expect clear thinking, working code, and honest tradeoffs.

If you run over, that's fine — note in the README what you'd do with more time.

## After submission

We'll schedule a **60-minute walkthrough call**. You'll share your screen, walk us through the code, and we'll ask you to:

- Explain key design decisions
- Defend your chart-type choices
- Make a small extension live (e.g. add a new anomaly type, or change a window definition)
- Discuss what would break at 10× scale

The take-home is a starting point. Submit something you can defend and extend, not something you can't explain.

## Questions

Email `omar.sengab@lasertribology.com` with any clarification questions before starting. Asking good questions early is a positive signal.
