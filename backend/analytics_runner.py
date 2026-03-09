# backend/analytics_runner.py
import pandas as pd
import numpy as np
from datetime import datetime
from backend.event_clusterer import cluster_events

class AnalyticsRunner:
    def __init__(self, audio_training_df=None):
        # audio_training is optional; we might use it to calibrate thresholds later
        self.audio_training = audio_training_df

    def run_pipeline(self, accel_df, audio_df, trips_df=None, trip_id=None, flagged_events=None):
        """
        accel_df, audio_df: DataFrames from simulator for this trip.
        trips_df: current trips.csv (for context)
        flagged_events: list of raw event dicts collected during trip
        Returns:
            {
                "trip_summary": DataFrame (1-row) with computed fields,
                "flagged": DataFrame of raw flagged moments,
                "incidents": DataFrame of clustered incidents
            }
        """
        # Normalize inputs
        try:
            if accel_df is None:
                accel_df = pd.DataFrame()
            if audio_df is None:
                audio_df = pd.DataFrame()
            if isinstance(flagged_events, list):
                flagged_df = pd.DataFrame(flagged_events)
            else:
                # try reading flagged moments from audio_df if present
                flagged_df = pd.DataFrame(columns=["trip_id","timestamp","type","db","risk_score"])
        except Exception:
            flagged_df = pd.DataFrame(columns=["trip_id","timestamp","type","db","risk_score"])

        # compute basic trip stats
        start_dt = None
        end_dt = None
        duration_min = 0.0
        distance_km = 0.0
        if not accel_df.empty:
            # expect accel_df to have 'timestamp' and possibly 'speed_kmh'
            try:
                accel_df["timestamp"] = pd.to_datetime(accel_df["timestamp"], errors="coerce")
                start_dt = accel_df["timestamp"].min()
                end_dt = accel_df["timestamp"].max()
                duration_min = (end_dt - start_dt).total_seconds() / 60.0 if pd.notnull(end_dt) and pd.notnull(start_dt) else 0.0
                if "speed_kmh" in accel_df.columns and len(accel_df) > 0:
                    avg_speed = accel_df["speed_kmh"].mean()
                    distance_km = float(avg_speed) * (duration_min / 60.0)
            except Exception:
                pass

        # safety score: simple aggregate of risk scores + sustained stress
        # flagged_df risk_score should be present if events were collected
        avg_risk = float(flagged_df["risk_score"].astype(float).mean()) if (not flagged_df.empty and "risk_score" in flagged_df.columns) else 0.0
        incidents = cluster_events(flagged_df) if not flagged_df.empty else pd.DataFrame(columns=["trip_id","incident_id","start_time","end_time","duration_sec","peak_db","avg_risk","types","count"])

        # safety score normalized: start at 1 (perfect) and reduce by incidents influence
        # keep between 0..1 (1 safe, 0 unsafe)
        safety_penalty = min(1.0, avg_risk + 0.1 * len(incidents))
        safety_score = max(0.0, 1.0 - safety_penalty)

        # fatigue detection (very simple rule-based)
        fatigue_prob = 0.0
        if duration_min >= 240:  # 4+ hours
            fatigue_prob = 0.6
        # increase fatigue if many incidents or high stress variance in audio_df
        if not audio_df.empty and "audio_level_db" in audio_df.columns:
            var = float(audio_df["audio_level_db"].var() or 0)
            if var > 40:
                fatigue_prob = min(1.0, fatigue_prob + 0.2)
        fatigue_prob = min(1.0, fatigue_prob)

        # build trip_summary row
        trip_summary = pd.DataFrame([{
    "trip_id": trip_id,
    "driver_id": flagged_df["driver_id"].iloc[0] if not flagged_df.empty else "",
    "start_datetime": start_dt.strftime("%Y-%m-%d %H:%M:%S") if start_dt is not None else "",
    "end_datetime": end_dt.strftime("%Y-%m-%d %H:%M:%S") if end_dt is not None else "",
    "duration_min": round(duration_min,2),
    "distance_km": round(distance_km,3),

    "flagged_moments_count": len(flagged_df),
    "max_severity": round(flagged_df["risk_score"].max(),2) if not flagged_df.empty else 0,
    "stress_score": round(avg_risk,3),

    "trip_quality_rating": round((1-safety_score)*5,2)
}])

        result = {
            "trip_summary": trip_summary,
            "flagged": flagged_df,
            "incidents": incidents
        }
        return result