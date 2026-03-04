# src/trip_summary.py
import pandas as pd
import numpy as np

SEV_MAP = {"none":0,"low":1,"medium":2,"high":3}

def _map_max_sev(flags):
    if flags.empty:
        return "none"
    order = ["none","low","medium","high"]
    # choose max by combined_score then severity
    try:
        s = flags["severity"].map(lambda x: SEV_MAP.get(x,0))
        maxsev = s.max()
        return {v:k for k,v in SEV_MAP.items()}[maxsev]
    except Exception:
        return "low"

def generate_trip_summary(flagged, trips):
    # flagged expected to contain trip_id, severity, combined_score
    trips_df = trips.copy()
    flagged_df = flagged.copy()

    # attach driver ids from trips (if flagged has driver_id blank)
    if "driver_id" in trips_df.columns:
        trip_driver = trips_df.set_index("trip_id")["driver_id"].to_dict()
        flagged_df["driver_id"] = flagged_df["trip_id"].map(trip_driver)

    summaries = []
    for _, trip in trips_df.iterrows():
        trip_id = trip["trip_id"]
        td = flagged_df[flagged_df["trip_id"]==trip_id]
        motion_count = td[td["motion_score"]>0].shape[0]
        audio_count = td[td["audio_score"]>0].shape[0]
        flagged_count = td.shape[0]
        max_severity = _map_max_sev(td)
        stress_score = float(td["combined_score"].mean()) if flagged_count>0 else 0.0

        # trip_quality mapping tuned to sample (tweak thresholds if you want different distribution)
        # priority to max_severity then stress_score and flagged_count
        if max_severity == "high" or stress_score >= 0.75 or flagged_count >= 4:
            quality = "poor"
        elif (stress_score >= 0.5) or (flagged_count >= 3):
            quality = "fair"
        elif (stress_score >= 0.35) or (flagged_count == 2):
            quality = "good"
        else:
            quality = "excellent"

        summaries.append({
            "trip_id": trip_id,
            "driver_id": trip.get("driver_id"),
            "date": trip.get("date", None),
            "duration_min": trip.get("duration_min"),
            "distance_km": trip.get("distance_km"),
            "fare": trip.get("fare"),
            "earnings_velocity": trip.get("earnings_velocity", None),
            "motion_events_count": motion_count,
            "audio_events_count": audio_count,
            "flagged_moments_count": flagged_count,
            "max_severity": max_severity,
            "stress_score": round(stress_score,3),
            "trip_quality_rating": quality
        })

    out = pd.DataFrame(summaries)
    return out