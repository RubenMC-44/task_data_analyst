import pandas as pd

def aggregate_by_minute(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["minute"] = df["time_stamp"].dt.floor("min")
    metrics_per_minute = df.groupby(["session_id","minute"]).agg(
        gps_avg_speed = ("gps_speed","mean"),
        gps_count_no_signal =("gps_n_satellites",lambda x: (x == 0).sum()),
        gps_avg_quality = ("gps_quality", "mean"),
        avg_blower_pressure = ("blower_pressure","mean"),
        max_blower_pressure = ("blower_pressure","max"),
        avg_compressor_pressure = ("compressor_pressure","mean"),
        max_compressor_pressure = ("compressor_pressure","max"),
        laser_n1_avg_power = ("laser_n1_measured_power", "mean"),
        laser_s1_avg_power = ("laser_s1_measured_power", "mean"),
        avg_temp_lens_box_n1 = ("temp_n1_lens_box","mean"),
        avg_temp_lens_box_s1 = ("temp_s1_lens_box","mean"),
        avg_system_health_cpu = ("system_health_cpu","mean"),
        avg_system_health_free_memory = ("system_health_free_memory","mean"),
        fpga_state_mode = ("fpga_state", lambda x: x.mode()[0])
    )
    return metrics_per_minute.reset_index()