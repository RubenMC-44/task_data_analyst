import pandas as pd
import numpy as np

def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    anomalies = []

    #humidity anomalies
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

    #pressure anomalies
    mask_blower_active = df["fpga_state"] == 4
    mask_compressor_active = df["fpga_state"] == 4

    #calculation of mean and std for blower
    blower_mean = df.loc[mask_blower_active,"blower_pressure"].mean()
    blower_std = df.loc[mask_blower_active,"blower_pressure"].std()

    #range to filter
    blower_upper = blower_mean + 3 * blower_std
    blower_lower = blower_mean - 3 * blower_std



    #calculation of mean and std for compressor
    compressor_mean = df.loc[mask_compressor_active,"compressor_pressure"].mean()
    compressor_std = df.loc[mask_compressor_active,"compressor_pressure"].std()

    #range to filter
    compressor_upper = compressor_mean +  3 * compressor_std
    compressor_lower = compressor_mean -  3 * compressor_std

    #Adding filters
    mask_blower_anomaly = mask_blower_active & (df["blower_pressure"] < blower_lower) | (df["blower_pressure"] > blower_upper)
    mask_compressor_anomaly = mask_compressor_active & (df["compressor_pressure"] < compressor_lower) | (df["compressor_pressure"] > compressor_upper)

    #Creating the data base with the anomaly
    blower_anomaly = df.loc[mask_blower_anomaly, ["session_id", "time_stamp"]].copy()
    blower_anomaly["anomaly_type"] = "blower_pressure"
    blower_anomaly["detail"] = df.loc[mask_blower_anomaly, "blower_pressure"].values
    anomalies.append(blower_anomaly)

    #Creating the data base with the anomaly
    compressor_anomaly = df.loc[mask_compressor_anomaly, ["session_id", "time_stamp"]].copy()
    compressor_anomaly["anomaly_type"] = "compressor_pressure"
    compressor_anomaly["detail"] = df.loc[mask_compressor_anomaly, "compressor_pressure"].values
    anomalies.append(compressor_anomaly)

    #GPS anomalies
    conditions = [
        (df["gps_dilution_of_precision"] >= 5) & (df["gps_dilution_of_precision"] <= 10),
        (df["gps_dilution_of_precision"] > 10)
    ]
    levels = ("warning","critical")

    mask_dop = df["gps_dilution_of_precision"] >= 5

    dop_anomaly = df.loc[mask_dop, ["session_id", "time_stamp"]].copy()
    dop_anomaly["anomaly_type"] = np.select(conditions, levels, default="normal")[mask_dop]
    dop_anomaly["detail"] = df.loc[mask_dop, "gps_dilution_of_precision"].values
    anomalies.append(dop_anomaly)

    return pd.concat(anomalies, ignore_index=True)