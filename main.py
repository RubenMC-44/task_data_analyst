from pipelines.ingest import load_session
from pipelines.db import get_connection, create_tables, insert_session, insert_metrics,insert_anomalies
from pipelines.aggregate import aggregate_by_minute
from pipelines.anomalies import detect_anomalies 
from pathlib import Path

ROOT = Path(__file__).parent

session_1 = load_session(ROOT / "sessions" / "session_19423.csv")
session_2 = load_session(ROOT / "sessions" / "session_20198.csv")

#Conecting duckdb
con = get_connection()
#DF_metrics where i add the groups by minutes
df_metrics_1= aggregate_by_minute(session_1)
df_metrics_2=aggregate_by_minute(session_2)
#df calling the anomalies
df_anomalies_1 = detect_anomalies(session_1)
df_anomalies_2 = detect_anomalies(session_2)
#Creating tables in duckdb
create_tables(con,session_1,df_metrics_1,df_anomalies_1)
#adding the sessions
insert_session(con,session_1)
insert_session(con,session_2)
#adding the metrics
insert_metrics(con,df_metrics_1)
insert_metrics(con,df_metrics_2)
#adding the anomalies
insert_anomalies(con,df_anomalies_1)
insert_anomalies(con,df_anomalies_2)

print(session_2["laser_n1_main_status"].value_counts())