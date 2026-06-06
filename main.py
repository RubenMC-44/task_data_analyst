from pipelines.ingest import load_session
from pipelines.db import get_connection, create_tables, insert_session, insert_metrics,insert_anomalies
from pipelines.aggregate import aggregate_by_minute
from pipelines.anomalies import anomaly_flags 
from pathlib import Path

ROOT = Path(__file__).parent

if __name__ == "__main__":
    # Load all session CSVs from the sessions folder automatically
    sessions_path = ROOT / "sessions"
    sessions = [load_session(p) for p in sessions_path.glob("*.csv")]

    if not sessions:
        raise FileNotFoundError(f"No CSV files found in {sessions_path}")

    # Connect to DuckDB database
    con = get_connection()

    # Calculate per-minute metrics and anomalies for each session
    metrics = [aggregate_by_minute(s) for s in sessions]
    anomalies = [anomaly_flags(s) for s in sessions]

    # Create tables in DuckDB using the first session as structure reference
    create_tables(con, sessions[0], metrics[0], anomalies[0])

    # Insert data for each session — delete first to avoid duplicates (idempotency)
    for s, m, a in zip(sessions, metrics, anomalies):
        insert_session(con, s)
        insert_metrics(con, m)
        insert_anomalies(con, a)

    # Close the database connection
    con.close()
