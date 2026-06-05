import duckdb
import streamlit  as st
from pathlib import Path
import pydeck
import pandas as pd
import plotly.express as px

DB_PATH = Path(__file__).parent.parent / "data" / "lps.duckdb"


st.set_page_config(
    page_title = "LPS data",
    page_icon= "",
    layout= "wide",
    initial_sidebar_state="expanded"
)

con = duckdb.connect(str(DB_PATH), read_only = True)

sessions = con.execute("SELECT DISTINCT session_id FROM raw_sessions").df()
id_session = st.selectbox("Session", sessions["session_id"])
df = con.execute("SELECT * FROM raw_sessions WHERE session_id = ?", [id_session]).df()
df_map = con.execute("""SELECT gps_lat, gps_lon FROM raw_sessions WHERE session_id = ? ORDER BY time_stamp""", [id_session]).df()
df_per_minute = con.execute("SELECT * FROM metrics_per_minute WHERE session_id = ?",[id_session]).df()

st.title(f"Data session: {id_session}")

with st.expander("Raw data"):
    st.dataframe(df)

st.header("Section 1 — Route and Speed", divider=True)
mean_lat = df_map["gps_lat"].mean()
mean_lon = df_map["gps_lon"].mean()
df_start = df_map.iloc[[0]]
df_finish = df_map.iloc[[-1]]

layer = pydeck.Layer(
    'ScatterplotLayer',
    df_map,
    get_position=['gps_lon', 'gps_lat'],
    get_radius= 50,
    get_fill_color=[0, 250, 0]
    )
layer_start = pydeck.Layer(
    "ScatterplotLayer",
    df_start,
    get_position =["gps_lon", "gps_lat"],
    get_radius = 500,
    get_fill_color = [0,128,255]
)
layer_finish = pydeck.Layer(
    "ScatterplotLayer",
    df_finish,
    get_position =["gps_lon", "gps_lat"],
    get_radius = 500,
    get_fill_color = [255,0,0]
)

viewstate= pydeck.ViewState(
    latitude=mean_lat, 
    longitude=mean_lon, 
    zoom=9
)
st.subheader(f"Route of session {id_session}")
st.pydeck_chart(pydeck.Deck(layers=[layer,layer_start,layer_finish], initial_view_state=viewstate))
st.markdown("🔵 Start &nbsp;&nbsp; 🔴 Finish &nbsp;&nbsp; 🟢 Route")

st.subheader("Speed over time")
df_per_minute["gps_avg_speed"] = df_per_minute["gps_avg_speed"].round(1)
fig_speed = px.line(
    df_per_minute, x="minute", y="gps_avg_speed",
    labels={"minute": "Time (min)", "gps_avg_speed": "Speed (m/h)"},
    color_discrete_sequence=["#ff7f0e"],
)
fig_speed.update_layout(showlegend=False)
st.plotly_chart(fig_speed, use_container_width=True)


st.header("Section 2 — Laser usage", divider=True)
df_lasers =con.execute (
        """SELECT 
        minute,
        CASE WHEN laser_n1_avg_power > 0 THEN 1 ELSE 0 END AS laser_n1_on,
        CASE WHEN laser_s1_avg_power > 0 THEN 1 ELSE 0 END AS laser_s1_on,
    FROM metrics_per_minute
    WHERE session_id = ?
    ORDER BY minute""",[id_session]).df()
df_lasers["period_n1"] = (df_lasers["laser_n1_on"] != df_lasers["laser_n1_on"].shift()).cumsum()
df_lasers["period_s1"] = (df_lasers["laser_s1_on"] != df_lasers["laser_s1_on"].shift()).cumsum()

active_n1 = df_lasers[df_lasers["laser_n1_on"] == 1].groupby("period_n1").agg(
    start=("minute", "min"),
    end=("minute", "max")
)
active_s1 = df_lasers[df_lasers["laser_s1_on"] == 1].groupby("period_s1").agg(
    start=("minute", "min"),
    end=("minute", "max")
)
active_n1["laser"] = "North Laser"
active_s1["laser"] = "South Laser"
df_timeline = pd.concat([active_n1, active_s1]).reset_index(drop=True)
df_lasers["lasers_active"] = df_lasers["laser_n1_on"] + df_lasers["laser_s1_on"]

col1, col2, col3 = st.columns(3)
col1.metric("Minutes both ON",    str((df_lasers["lasers_active"] == 2).sum()))
col2.metric("Minutes one ON",     str((df_lasers["lasers_active"] == 1).sum()))
col3.metric("Minutes both OFF",   str((df_lasers["lasers_active"] == 0).sum()))

st.subheader(f"Laser activity periods | session: {id_session}")
fig = px.timeline(
    df_timeline, x_start="start", x_end="end", y="laser", color="laser",
    color_discrete_map={"North Laser": "#1f77b4", "South Laser": "#ff7f0e"},
)
st.plotly_chart(fig, use_container_width=True)

fig_count = px.line(
    df_lasers, x="minute", y="lasers_active",
    title="Number of active lasers over time",
    labels={"minute": "Time (min)", "lasers_active": "Active lasers"},
    color_discrete_sequence=["#2ca02c"],
)
fig_count.update_yaxes(tickvals=[0, 1, 2], ticktext=["0 – Both off", "1 – One on", "2 – Both on"])
fig_count.update_layout(showlegend=False)
st.plotly_chart(fig_count, use_container_width=True)


st.header("Section 3 — Pressure monitoring", divider=True)
df_pressure = con.execute(
    """SELECT
        minute, avg_blower_pressure, avg_compressor_pressure
        FROM metrics_per_minute WHERE session_id = ? AND fpga_state_mode = 4 ORDER BY minute""",[id_session]).df()

limits = con.execute("""
    SELECT
        avg(avg_blower_pressure) as blower_mean,
        stddev(avg_blower_pressure) as blower_std,
        avg(avg_compressor_pressure) as compressor_mean,
        stddev(avg_compressor_pressure) as compressor_std
    FROM metrics_per_minute
    WHERE session_id = ? AND fpga_state_mode = 4
""", [id_session]).df()

blower_mean = limits["blower_mean"].iloc[0]
blower_upper = (limits["blower_mean"] + 3 * limits["blower_std"]).iloc[0]
blower_lower = (limits["blower_mean"] - 3 * limits["blower_std"]).iloc[0]

compressor_mean = limits["compressor_mean"].iloc[0]
compressor_upper = (limits["compressor_mean"] + 3 * limits["compressor_std"]).iloc[0]
compressor_lower = (limits["compressor_mean"] - 3 * limits["compressor_std"]).iloc[0]

col1, col2 = st.columns(2)
with col1:
    fig_1 = px.line(
        df_pressure, x="minute", y="avg_blower_pressure",
        title="Blower pressure",
        labels={"minute": "Time (min)", "avg_blower_pressure": "Pressure (mbar)"},
        color_discrete_sequence=["#1f77b4"],
    )
    fig_1.add_hrect(
        y0=blower_lower, y1=blower_upper,
        fillcolor="green", opacity=0.18,
        line_width=0, annotation_text="Normal operating range",
        annotation_position="top left",
    )
    fig_1.add_hline(
        y=blower_mean, line_dash="dot", line_color="green"
    )
    blower_margin = (blower_upper - blower_lower) * 0.20
    fig_1.update_yaxes(range=[blower_lower - blower_margin, blower_upper + blower_margin])
    fig_1.update_layout(showlegend=False)
    st.plotly_chart(fig_1, use_container_width=True)

with col2:
    fig_2 = px.line(
        df_pressure, x="minute", y="avg_compressor_pressure",
        title="Compressor pressure",
        labels={"minute": "Time (min)", "avg_compressor_pressure": "Pressure (bar)"},
        color_discrete_sequence=["#ff7f0e"],
    )
    fig_2.add_hrect(
        y0=compressor_lower, y1=compressor_upper,
        fillcolor="green", opacity=0.18,
        line_width=0, annotation_text="Normal operating range",
        annotation_position="top left",
    )
    fig_2.add_hline(
        y=compressor_mean, line_dash="dot", line_color="green",
    )
    compressor_margin = (compressor_upper - compressor_lower) * 0.20
    fig_2.update_yaxes(range=[compressor_lower - compressor_margin, compressor_upper + compressor_margin])
    fig_2.update_layout(showlegend=False)
    st.plotly_chart(fig_2, use_container_width=True)

st.header("Section 4 —  Laser & optics temperatures", divider=True)

stuck_sensors = con.execute("""
    SELECT column_name FROM (
        SELECT 'temp_s1_top_pw' AS column_name, COUNT(DISTINCT temp_s1_top_pw) AS n FROM raw_sessions WHERE session_id = ? UNION ALL
        SELECT 'temp_n1_top_pw',                 COUNT(DISTINCT temp_n1_top_pw)                 FROM raw_sessions WHERE session_id = ? UNION ALL
        SELECT 'temp_s1_bottom_pw',              COUNT(DISTINCT temp_s1_bottom_pw)              FROM raw_sessions WHERE session_id = ? UNION ALL
        SELECT 'temp_n1_bottom_pw',              COUNT(DISTINCT temp_n1_bottom_pw)              FROM raw_sessions WHERE session_id = ?
    ) WHERE n = 1
""", [id_session, id_session, id_session, id_session]).df()

if not stuck_sensors.empty:
    names = ", ".join(stuck_sensors["column_name"].tolist())
    st.warning(f"Stuck sensor detected: **{names}** returns a constant value throughout the session — likely hardware failure.")

df_thermal_comparations = con.execute(
    """SELECT
        minute,
        avg_temp_lens_box_n1, avg_temp_lens_box_s1, 
        avg_temp_n1_top_pw, avg_temp_s1_top_pw,
        avg_temp_n1_bottom_pw, avg_temp_s1_bottom_pw,
        avg_n1_main_chiller_temp, avg_s1_main_chiller_temp
        FROM metrics_per_minute WHERE session_id = ? AND fpga_state_mode = 4 ORDER BY minute""",[id_session]).df()


df_lens = df_thermal_comparations[["minute", "avg_temp_lens_box_n1", "avg_temp_lens_box_s1"]].rename(columns={
    "avg_temp_lens_box_n1": "North laser",
    "avg_temp_lens_box_s1": "South laser",
})

fig_1 = px.line(
    df_lens, x="minute", y=["North laser", "South laser"],
    title="Lens box temperature",
    color_discrete_map={"North laser": "#1f77b4", "South laser": "#ff7f0e"},
    labels={"minute": "Time (min)", "value": "Temperature (°C)"},
)
st.plotly_chart(fig_1, use_container_width=True)

df_pw = df_thermal_comparations[["minute", "avg_temp_n1_top_pw", "avg_temp_s1_top_pw", "avg_temp_n1_bottom_pw", "avg_temp_s1_bottom_pw"]].rename(columns={
    "avg_temp_n1_top_pw":    "N1 top",
    "avg_temp_s1_top_pw":    "S1 top",
    "avg_temp_n1_bottom_pw": "N1 bottom",
    "avg_temp_s1_bottom_pw": "S1 bottom",
})
fig_2 = px.line(
    df_pw, x="minute", y=["N1 top", "S1 top", "N1 bottom", "S1 bottom"],
    title="Power unit temperature",
    color_discrete_map={"N1 top": "#1f77b4", "S1 top": "#ff7f0e", "N1 bottom": "#aec7e8", "S1 bottom": "#ffbb78"},
    labels={"minute": "Time (min)", "value": "Temperature (°C)"},
)
st.plotly_chart(fig_2, use_container_width=True)

df_chiller = df_thermal_comparations[["minute", "avg_n1_main_chiller_temp", "avg_s1_main_chiller_temp"]].rename(columns={
    "avg_n1_main_chiller_temp": "N1 chiller",
    "avg_s1_main_chiller_temp": "S1 chiller",
})
fig_3 = px.line(
    df_chiller, x="minute", y=["N1 chiller", "S1 chiller"],
    title="Chiller temperature",
    color_discrete_map={"N1 chiller": "#1f77b4", "S1 chiller": "#ff7f0e"},
    labels={"minute": "Time (min)", "value": "Temperature (°C)"},
)
st.plotly_chart(fig_3, use_container_width=True)

st.header("Section 5 —  GPS Health", divider=True)

df_gps = con.execute(
    """SELECT minute, gps_avg_quality, gps_avg_dop
    FROM metrics_per_minute WHERE session_id = ? ORDER BY minute""", [id_session]).df()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Avg DOP",                f"{df_gps['gps_avg_dop'].mean():.2f}")
col2.metric("Max DOP",                f"{df_gps['gps_avg_dop'].max():.2f}")
col3.metric("Avg quality",            f"{df_gps['gps_avg_quality'].mean():.2f}")
col4.metric("Minutes without GPS fix", str((df_gps['gps_avg_quality'] == 0).sum()))

fig_dop = px.line(
    df_gps, x="minute", y="gps_avg_dop",
    title="Dilution of Precision (DOP) over time",
    labels={"minute": "Time (min)", "gps_avg_dop": "DOP"},
    color_discrete_sequence=["#1f77b4"],
)
fig_dop.add_hrect(y0=0,  y1=2,  fillcolor="green",  opacity=0.08, line_width=0, annotation_text="Good (<2)",     annotation_position="top left")
fig_dop.add_hrect(y0=2,  y1=5,  fillcolor="orange", opacity=0.08, line_width=0, annotation_text="Moderate (2–5)", annotation_position="top left")
fig_dop.add_hrect(y0=5,  y1=20, fillcolor="red",    opacity=0.08, line_width=0, annotation_text="Poor (>5)",     annotation_position="top left")
fig_dop.update_layout(showlegend=False)
st.plotly_chart(fig_dop, use_container_width=True)

fig_quality = px.line(
    df_gps, x="minute", y="gps_avg_quality",
    title="GPS quality over time  (0 = no fix / dropout)",
    labels={"minute": "Time (min)", "gps_avg_quality": "Quality"},
    color_discrete_sequence=["#ff7f0e"],
)
fig_quality.add_hrect(y0=-0.1, y1=0.5, fillcolor="red", opacity=0.08, line_width=0, annotation_text="No fix", annotation_position="top left")
fig_quality.update_yaxes(tickvals=[0, 1, 2, 3], ticktext=["0 – No fix", "1 – GPS", "2 – DGPS", "3 – PPS"])
fig_quality.update_layout(showlegend=False)
st.plotly_chart(fig_quality, use_container_width=True)
st.info(
    "**Note on satellite data:** `gps_n_satellites` reports 0 across all records in both sessions, "
    "indicating this sensor is not reporting in the current hardware configuration. "
    "GPS health is therefore assessed via DOP and fix quality. "
    "Quality > 0 confirms the receiver had sufficient satellites to compute a position fix."
)


st.header("Section 6 — Anomalies", divider=True)

df_anomalies = con.execute(
    """SELECT time_stamp, anomaly_type, detail
    FROM detect_anomalies WHERE session_id = ? ORDER BY time_stamp""",
    [id_session]
).df()

ANOMALY_LABELS = {
    "impossible_temperature":        "Impossible temperature",
    "GPS_poor_signal":               "GPS poor signal",
    "GPS_moderate_signal":           "GPS moderate signal",
    "GPS_warning_moderate_signal":   "GPS moderate signal",
    "compressor_pressure":           "Compressor pressure",
    "blower_pressure":               "Blower pressure",
    "chiller_n1_alarm":              "Chiller N1 alarm",
    "chiller_s1_alarm":              "Chiller S1 alarm",
    "laser_n1_humidity":             "Laser N1 humidity",
    "laser_s1_humidity":             "Laser S1 humidity",
    "high_cpu_usage":                "High CPU usage",
    "stuck_sensor":                  "Stuck sensor",
    "subsystem_offline":             "Subsystem offline",
}
df_anomalies["anomaly_type"] = df_anomalies["anomaly_type"].map(ANOMALY_LABELS).fillna(df_anomalies["anomaly_type"])

total = len(df_anomalies)
top_type = df_anomalies["anomaly_type"].value_counts().idxmax() if total > 0 else "—"
top_count = df_anomalies["anomaly_type"].value_counts().max() if total > 0 else 0

col1, col2 = st.columns(2)
col1.metric("Total anomalies", total)
col2.metric("Most frequent", f"{top_type} ({top_count})")

df_counts = df_anomalies["anomaly_type"].value_counts().reset_index()
df_counts.columns = ["anomaly_type", "count"]
fig_bar = px.bar(
    df_counts, x="count", y="anomaly_type", orientation="h",
    title="Anomaly count by type",
    labels={"count": "Count", "anomaly_type": ""},
    color="anomaly_type",
)
fig_bar.update_layout(showlegend=False, yaxis={"categoryorder": "total ascending"})
st.plotly_chart(fig_bar, use_container_width=True)

fig_scatter = px.scatter(
    df_anomalies, x="time_stamp", y="anomaly_type",
    color="anomaly_type", hover_data=["detail"],
    title="Anomaly timeline",
    labels={"time_stamp": "Time", "anomaly_type": ""},
)
fig_scatter.update_traces(marker=dict(size=6, opacity=0.7))
fig_scatter.update_layout(showlegend=False)
st.plotly_chart(fig_scatter, use_container_width=True)