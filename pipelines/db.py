import duckdb
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "lps.duckdb"

def get_connection():
    con = duckdb.connect(str(DB_PATH))
    return con

def create_tables(con, df_raw, df_metrics,df_anomalies): 
    con.execute("CREATE TABLE IF NOT EXISTS raw_sessions AS SELECT * FROM df_raw WHERE 1=0")
    con.execute("CREATE TABLE IF NOT EXISTS metrics_per_minute AS SELECT * FROM df_metrics WHERE 1=0")
    con.execute("CREATE TABLE IF NOT EXISTS detect_anomalies AS SELECT * FROM df_anomalies WHERE 1=0")
    
def insert_session (con,df_raw): 
    session_id = df_raw["session_id"].iloc[0]
    con.execute("DELETE FROM raw_sessions WHERE session_id = ?", [session_id])
    con.execute("INSERT INTO raw_sessions SELECT * FROM df_raw")

def insert_metrics(con,df_metrics): 
    session_id = df_metrics["session_id"].iloc[0]
    con.execute("DELETE FROM metrics_per_minute WHERE session_id = ?", [session_id])
    con.execute("INSERT INTO metrics_per_minute SELECT * FROM df_metrics")

def insert_anomalies(con,df_anomalies): 
    session_id = df_anomalies["session_id"].iloc[0]
    con.execute("DELETE FROM detect_anomalies  WHERE session_id = ?", [session_id])
    con.execute("INSERT INTO detect_anomalies SELECT * FROM df_anomalies")