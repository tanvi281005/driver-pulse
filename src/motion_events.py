import pandas as pd
import numpy as np


def detect_motion_events(accel):

    accel = accel.copy()

    # parse timestamps
    accel["timestamp"] = pd.to_datetime(accel["timestamp"], errors="coerce")
    accel["start_datetime"] = pd.to_datetime(accel["start_datetime"], errors="coerce")

    # compute elapsed time
    accel["elapsed_seconds"] = (
        accel["timestamp"] - accel["start_datetime"]
    ).dt.total_seconds()

    # ensure numeric values
    accel["accel_x"] = pd.to_numeric(accel["accel_x"], errors="coerce")
    accel["accel_y"] = pd.to_numeric(accel["accel_y"], errors="coerce")
    accel["accel_z"] = pd.to_numeric(accel["accel_z"], errors="coerce")
    accel["speed_kmh"] = pd.to_numeric(accel["speed_kmh"], errors="coerce")
    accel["speed_change_rate"] = pd.to_numeric(accel["speed_change_rate"], errors="coerce")

    # compute magnitude if missing
    if "accel_magnitude" not in accel.columns:
        accel["accel_magnitude"] = np.sqrt(
            accel["accel_x"]**2 +
            accel["accel_y"]**2 +
            accel["accel_z"]**2
        )

    events = []

    for _, row in accel.iterrows():

        motion_type = None
        score = 0

        # harsh braking
        if row["speed_change_rate"] < -0.5 and row["speed_kmh"] > 20:
            motion_type = "harsh_brake"
            score = 0.9

        # sudden acceleration
        elif row["speed_change_rate"] > 0.5:
            motion_type = "sudden_acceleration"
            score = 0.8

        # rough road / vibration
        elif row["accel_magnitude"] > 10.5:
            motion_type = "rough_motion"
            score = 0.6

        if motion_type:

            events.append({

                "trip_id": row["trip_id"],
                "timestamp": row["timestamp"],
                "elapsed_seconds": row["elapsed_seconds"],

                "motion_type": motion_type,
                "motion_score": score
            })

    events_df = pd.DataFrame(events)

    print("  motion events:", len(events_df))

    return events_df