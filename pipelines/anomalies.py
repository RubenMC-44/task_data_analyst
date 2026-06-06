import pandas as pd
import numpy as np

def anomaly_flags(df: pd.DataFrame):
    """Detects anomalies across a session and returns a flat table with session_id, time_stamp, anomaly_type and detail."""
    df = df.copy()
    anomalies = []

    # Laser alarm flags — bit 0 of main_status indicates alarm active
    mask_laser_n1_alarm = (df["laser_n1_main_status"] & 1).astype(bool)
    mask_laser_s1_alarm = (df["laser_s1_main_status"] & 1).astype(bool)

    laser_n1_alarm = df.loc[mask_laser_n1_alarm, ["session_id", "time_stamp"]].copy()
    laser_n1_alarm["anomaly_type"] = "n1_laser_alarm"
    laser_n1_alarm["detail"] = "alarm_n1_activated"
    anomalies.append(laser_n1_alarm)

    laser_s1_alarm = df.loc[mask_laser_s1_alarm, ["session_id", "time_stamp"]].copy()
    laser_s1_alarm["anomaly_type"] = "s1_laser_alarm"
    laser_s1_alarm["detail"] = "alarm_s1_activated"
    anomalies.append(laser_s1_alarm)

    # Chiller alarms — hardware-reported fault flag, no inference needed
    mask_chiller_n1_alarm = df["chiller_n1_alarm"] == True
    mask_chiller_s1_alarm = df["chiller_s1_alarm"] == True

    chiller_n1_alarm = df.loc[mask_chiller_n1_alarm, ["session_id", "time_stamp"]].copy()
    chiller_n1_alarm["anomaly_type"] = "chiller_n1_alarm"
    chiller_n1_alarm["detail"] = "alarm_n1_activated"
    anomalies.append(chiller_n1_alarm)

    chiller_s1_alarm = df.loc[mask_chiller_s1_alarm, ["session_id", "time_stamp"]].copy()
    chiller_s1_alarm["anomaly_type"] = "chiller_s1_alarm"
    chiller_s1_alarm["detail"] = "alarm_s1_activated"
    anomalies.append(chiller_s1_alarm)

    # Laser humidity — reading of 0 indicates sensor failure
    mask_humidity_n1 = df["laser_n1_humidity"] == 0
    mask_humidity_s1 = df["laser_s1_humidity"] == 0

    laser_humidity_n1 = df.loc[mask_humidity_n1, ["session_id", "time_stamp"]].copy()
    laser_humidity_n1["anomaly_type"] = "laser_n1_humidity"
    laser_humidity_n1["detail"] = "sensor_reading_zero"
    anomalies.append(laser_humidity_n1)

    laser_humidity_s1 = df.loc[mask_humidity_s1, ["session_id", "time_stamp"]].copy()
    laser_humidity_s1["anomaly_type"] = "laser_s1_humidity"
    laser_humidity_s1["detail"] = "sensor_reading_zero"
    anomalies.append(laser_humidity_s1)

    # Pressure anomalies — baseline built only from cleaning state (fpga_state == 4),
    # other states have different expected ranges. Outliers flagged with 3-sigma rule.
    mask_cleaning = df["fpga_state"] == 4

    blower_mean  = df.loc[mask_cleaning, "blower_pressure"].mean()
    blower_std   = df.loc[mask_cleaning, "blower_pressure"].std()
    blower_upper = blower_mean + 3 * blower_std
    blower_lower = blower_mean - 3 * blower_std

    compressor_mean  = df.loc[mask_cleaning, "compressor_pressure"].mean()
    compressor_std   = df.loc[mask_cleaning, "compressor_pressure"].std()
    compressor_upper = compressor_mean + 3 * compressor_std
    compressor_lower = compressor_mean - 3 * compressor_std

    mask_blower_anomaly     = mask_cleaning & ((df["blower_pressure"] < blower_lower)         | (df["blower_pressure"] > blower_upper))
    mask_compressor_anomaly = mask_cleaning & ((df["compressor_pressure"] < compressor_lower) | (df["compressor_pressure"] > compressor_upper))

    blower_anomaly = df.loc[mask_blower_anomaly, ["session_id", "time_stamp"]].copy()
    blower_anomaly["anomaly_type"] = "blower_pressure"
    blower_anomaly["detail"] = df.loc[mask_blower_anomaly, "blower_pressure"].astype(str).values
    anomalies.append(blower_anomaly)

    compressor_anomaly = df.loc[mask_compressor_anomaly, ["session_id", "time_stamp"]].copy()
    compressor_anomaly["anomaly_type"] = "compressor_pressure"
    compressor_anomaly["detail"] = df.loc[mask_compressor_anomaly, "compressor_pressure"].astype(str).values
    anomalies.append(compressor_anomaly)

    # GPS Dilution of Precision — 2–5: moderate (warning), >5: poor (critical)
    mask_dop = df["gps_dilution_of_precision"] > 2
    dop_anomaly = df.loc[mask_dop, ["session_id", "time_stamp"]].copy()
    dop_anomaly["anomaly_type"] = np.where(
        df.loc[mask_dop, "gps_dilution_of_precision"] > 5, "GPS_poor_signal", "GPS_moderate_signal")
    dop_anomaly["detail"] = df.loc[mask_dop, "gps_dilution_of_precision"].astype(str).values
    anomalies.append(dop_anomaly)

    # CPU health — upper 3-sigma bound only (high usage is the concern)
    health_cpu_mean  = df["system_health_cpu"].mean()
    health_cpu_std   = df["system_health_cpu"].std()
    health_cpu_upper = health_cpu_mean + 3 * health_cpu_std

    mask_health_cpu = df["system_health_cpu"] > health_cpu_upper
    health_cpu_anomaly = df.loc[mask_health_cpu, ["session_id", "time_stamp"]].copy()
    health_cpu_anomaly["anomaly_type"] = "high_cpu_usage"
    health_cpu_anomaly["detail"] = df.loc[mask_health_cpu, "system_health_cpu"].astype(str).values
    anomalies.append(health_cpu_anomaly)

    # Impossible temperature readings — values below 0°C indicate a sensor fault or corrupt reading.
    # A working sensor on active hardware should never report sub-zero temperatures.
    TEMP_COLS = [
        "temp_n1_top_pw", "temp_s1_top_pw",
        "temp_n1_bottom_pw", "temp_s1_bottom_pw",
        "temp_lens_box_n1", "temp_lens_box_s1",
    ]
    for col in TEMP_COLS:
        if col not in df.columns:
            continue
        mask_impossible = df[col] < 0
        if mask_impossible.any():
            impossible = df.loc[mask_impossible, ["session_id", "time_stamp"]].copy()
            impossible["anomaly_type"] = "impossible_temperature"
            impossible["detail"] = col + ": " + df.loc[mask_impossible, col].round(2).astype(str) + "°C"
            anomalies.append(impossible)

    # Stuck temperature sensors — a sensor returning a single constant value across the entire session
    # indicates hardware failure. One anomaly row per affected sensor per session.
    TEMP_SENSORS = [
        "temp_s1_top_pw", "temp_n1_top_pw",
        "temp_s1_bottom_pw", "temp_n1_bottom_pw",
        "temp_lens_box_n1", "temp_lens_box_s1",
    ]
    for col in TEMP_SENSORS:
        if col in df.columns and df[col].nunique() <= 1 and df[col].notna().any():
            stuck = df[["session_id", "time_stamp"]].iloc[[0]].copy()
            stuck["anomaly_type"] = "stuck_sensor"
            stuck["detail"] = f"{col} stuck at {df[col].iloc[0]:.4f}"
            anomalies.append(stuck)

    # Subsystem offline / warming-up — NaN in the key measurement column means the subsystem was not reporting
    SUBSYSTEM_PROBES = {
        "laser_n1":   "laser_n1_measured_power",
        "laser_s1":   "laser_s1_measured_power",
        "chiller_n1": "chiller_n1_main_circuit_temperature",
        "chiller_s1": "chiller_s1_main_circuit_temperature",
    }
    for subsystem, col in SUBSYSTEM_PROBES.items():
        mask_offline = df[col].isna()
        if mask_offline.any():
            offline = df.loc[mask_offline, ["session_id", "time_stamp"]].copy()
            offline["anomaly_type"] = "subsystem_offline"
            offline["detail"] = subsystem
            anomalies.append(offline)

    return pd.concat(anomalies, ignore_index=True)