import pandas as pd


def load_all_data():

    accel = pd.read_csv("data/accelerometer.csv")
    audio = pd.read_csv("data/audio.csv")
    trips = pd.read_csv("data/trips.csv")
    earnings = pd.read_csv("data/earnings.csv")

    accel["timestamp"] = pd.to_datetime(accel["timestamp"], errors="coerce")
    audio["timestamp"] = pd.to_datetime(audio["timestamp"], errors="coerce")

    # accel["elapsed_seconds"] = pd.to_numeric(accel["elapsed_seconds"], errors="coerce")
    audio["elapsed_seconds"] = pd.to_numeric(audio["elapsed_seconds"], errors="coerce")

    audio["audio_level_db"] = pd.to_numeric(audio["audio_level_db"], errors="coerce")
    audio["sustained_duration_sec"] = pd.to_numeric(audio["sustained_duration_sec"], errors="coerce")

    return accel, audio, trips, earnings