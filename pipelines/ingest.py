import pandas as pd
from pathlib import Path

ROOT = Path (__file__).parent.parent

def load_session(path: Path) -> pd.DataFrame:
    #Reading csv
    df = pd.read_csv(path)

    #datetime parse
    df["time_stamp"] = pd.to_datetime(df["time_stamp"], format="ISO8601")
    
    # Converting string to booleans
    BOOL_COLS = ["chiller_n1_alarm","chiller_n1_on","chiller_s1_alarm","chiller_s1_on","n1_emission_stop","s1_emission_stop"]
    df[BOOL_COLS] = df[BOOL_COLS].replace({"t": True, "f": False}).astype(bool)
    
    # session_id from each session
    df["session_id"] = path.stem.split("_")[-1]
    session_id = df.pop("session_id")
    df.insert(0, "session_id", session_id)

    return df
