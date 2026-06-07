# LPS Data Analyst — Take-Home Task

## How to run

**Requirements:** Python 3.12+, [uv](https://docs.astral.sh/uv/)

```bash
# 1. Install dependencies
uv sync

# 2. Run the pipeline (reads CSVs and stores results in the database)
uv run main.py

# 3. Launch the dashboard
uv run streamlit run dashboard/dashboard.py
```

Just drop the session CSV files into the `sessions/` folder and run the pipeline. It picks them up automatically. You can run it as many times as you want — it won't create duplicate data (more on this below).

---

## Project structure

```
├── sessions/           # Raw session CSV files (input)
├── data/               # Database file (output)
├── pipelines/
│   ├── ingest.py       # Reads and parses the CSVs
│   ├── aggregate.py    # Summarises data by minute
│   ├── anomalies.py    # Detects anomalies
│   └── db.py           # Handles database reads/writes
├── dashboard/
│   └── dashboard.py    # The Streamlit dashboard
└── main.py             # Where it all starts
```

---

## Why DuckDB?

I chose DuckDB as the database for a few practical reasons:

- **No setup needed** — it's just a single file on disk. Anyone can clone the repo and run the pipeline without installing a database server.
- **Fast for analytics** — it's built for the kind of queries a dashboard makes: aggregating many columns at once over large tables. Running summaries over 30,000+ rows per session is noticeably faster than SQLite.
- **Works naturally with pandas** — any query returns a DataFrame directly, so the pipeline code stays clean and readable.
- **Scales well enough for this task** — with two sessions of ~35k rows each, DuckDB is more than sufficient. It would still handle 10× that without any changes.

---

## Re-running the pipeline is safe

The pipeline can be run multiple times without creating duplicate data. Before writing anything, it deletes the existing records for that session first:

```python
con.execute("DELETE FROM raw_sessions WHERE session_id = ?", [session_id])
con.execute("INSERT INTO raw_sessions SELECT * FROM df_raw")
```

This applies to all three tables. Whether you run it once or ten times, the result is always the same.

---

## Assumptions

- Both sessions come from the same vehicle and equipment type, but they are analyzed **independently** — each session has its own measurements and values, and there is no cross-session aggregation.
- `fpga_state = 4` is the active cleaning mode. Pressure and temperature baselines are calculated only during this state, since startup, shutdown, and idle modes have different expected values.
- `gps_n_satellites` always shows `0` in both sessions — the sensor simply isn't reporting in this hardware setup. So GPS health is assessed using DOP (a standard measure of GPS signal accuracy — lower is better) and fix quality (`gps_quality`) instead. A quality value above 0 means the receiver was computing a valid position.
- Temperatures below 0°C on the power unit sensors are physically impossible for hardware that's running, so these are treated as sensor faults rather than real readings.
- `temp_s1_top_pw` returns the exact same value (91.05°C) in every record across both sessions — this sensor is stuck or defective.

---

## What I left out

- **Tests** — there's no test suite. The core functions are written in a way that would make them straightforward to test with synthetic data. Given more time, I'd add pytest tests covering each anomaly type and edge cases like empty sessions or columns that are entirely missing.
- **Multi-session comparison in the dashboard** — the dashboard shows one session at a time. A view comparing signal quality, pressure stability, or anomaly counts across sessions would be useful for fleet-level monitoring.
- **Production setup** — no Airflow or dbt configuration was implemented (see the production notes at the end).
---

## Dashboard: why each chart

### Section 1 — Route and Speed

**Question:** Where did the train go, and how fast?

| Chart | Why |
|---|---|
| Map (GPS coordinates) | The most direct way to answer "where". Start and end points are marked so you can immediately orient yourself. |
| Speed over time (line chart) | Continuous data like speed is clearest as a line — you can see where the train accelerated, slowed down, or stopped. |

### Section 2 — Laser usage

**Question:** When were the lasers on and off, and how many were running at once?

| Chart | Why |
|---|---|
| Timeline (Gantt-style) | Shows each laser's on/off periods as horizontal bars. N1 and S1 are on separate rows for easy comparison. |
| Active laser count over time (line chart) | A single line showing 0, 1, or 2 active lasers is more direct than reading two timelines at the same time. |
| Summary numbers | Total minutes with both on / one on / both off — a quick session-level summary. |

### Section 3 — Pressure monitoring

**Question:** Did blower and compressor pressure stay within normal operating ranges?

| Chart | Why |
|---|---|
| Pressure over time with a shaded band | The shaded band shows the expected range, calculated from the session's own cleaning-state data. Anything outside the band stands out immediately. |

Blower and compressor are shown in separate charts because they use different units (mbar vs bar) — combining them on the same axis would be misleading.

### Section 4 — Laser and optics temperatures

**Question:** Were temperatures stable, or did any laser drift?

| Chart | Why |
|---|---|
| N1 vs S1 temperatures (line chart) | Overlaying North and South laser readings on the same chart makes any divergence obvious. If both lines move together, the system is balanced; if they split, one laser is drifting. |
| Stability metric | A single number (max − min over the session) tells you how stable the temperature was without having to read the chart carefully. |

Three separate charts (lens box / power unit / chiller) to avoid mixing sensors with different operating ranges on the same axis.

### Section 5 — GPS health

**Question:** How reliable was the GPS signal throughout the session?

| Chart | Why |
|---|---|
| DOP over time with coloured bands | DOP (Dilution of Precision) measures GPS signal quality — lower is better. Three coloured zones (green below 2 / orange 2–5 / red above 5) let anyone assess signal quality at a glance, even without knowing what DOP means. |
| GPS fix quality over time | Shows whether the receiver had a valid fix at each moment. The red zone at 0 highlights periods where GPS was unavailable. Labels explain each value: No fix / GPS / DGPS / PPS. |
| Summary numbers | Average DOP, worst DOP, average fix quality, and total minutes without a fix. |

**Note:** Satellite count (`gps_n_satellites`) is always 0 in both sessions — the sensor isn't reporting in this hardware configuration. This is a known limitation.

### Section 6 — Anomalies

**Question:** When did anomalies occur, and what type were they?

| Chart | Why |
|---|---|
| Bar chart (count by type) | Answers "what kind" and "how many". Sorted by frequency so the most common issues stand out. |
| Scatter timeline | Each anomaly is plotted as a dot at the exact time it happened, coloured by type. Shows whether anomalies are isolated events or concentrated in a specific period. Hovering shows the detail for each one. |

---

## Anomaly definitions

Each type is defined in [pipelines/anomalies.py](pipelines/anomalies.py):

| Anomaly type | What triggers it | Why |
|---|---|---|
| `n1_laser_alarm` / `s1_laser_alarm` | Hardware alarm bit is set in the laser status field | Direct hardware flag — no inference needed. |
| `chiller_n1_alarm` / `chiller_s1_alarm` | Chiller alarm field is True | Hardware-reported fault. Direct flag. |
| `laser_n1_humidity` / `laser_s1_humidity` | Humidity reading is exactly 0 | A real humidity value is never exactly 0 — this means the sensor isn't responding. |
| `blower_pressure` / `compressor_pressure` | Outside the normal range (mean ± 3 standard deviations) during active cleaning | A standard threshold for statistical outlier detection. The baseline is calculated per session, using only the active cleaning state (`fpga_state = 4`). |
| `GPS_moderate_signal` | DOP between 2 and 5 | Standard GPS thresholds. Usable but degraded precision. |
| `GPS_poor_signal` | DOP above 5 | Position data is unreliable at this level. |
| `high_cpu_usage` | CPU above mean + 3 standard deviations | Only the upper end is flagged — low CPU is not a concern. |
| `impossible_temperature` | Any temperature sensor below 0°C | Physically impossible for running hardware. Must be a sensor fault. |
| `stuck_sensor` | A temperature sensor returns the exact same value for the entire session | Real sensors always show some variation. A constant value means the sensor has failed. |
| `subsystem_offline` | The key measurement column for a subsystem has missing values | Missing data means the subsystem wasn't reporting during that period. |

---

## Taking this to production

If this pipeline needed to run automatically in a real environment:

**Airflow (task scheduler):**
- One task per step: ingest → aggregate → detect anomalies → save to database
- Triggered when new files arrive or on a nightly schedule
- Each step is safe to retry if something fails

**dbt (data transformations):**
- The raw session table becomes a source
- The aggregation and anomaly tables become SQL models
- Built-in tests can replace some of the manual anomaly logic

**At larger scale:**
- DuckDB handles hundreds of millions of rows on a single machine — no immediate change needed
- For thousands of sessions per day across a fleet, the next step would be DuckDB on cloud storage (MotherDuck) or a warehouse like BigQuery or Snowflake — the SQL logic stays the same
- The dashboard would query the warehouse instead of a local file

**For continuous incoming data:**
- A file watcher or cloud storage event triggers the pipeline whenever a new session arrives
- The delete-before-insert approach handles re-processing safely

