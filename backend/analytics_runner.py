# backend/analytics_runner.py
import pandas as pd
import numpy as np
from backend.live_stress_engine import LiveStressEngine
from backend.event_clustering import cluster_flagged_events
from datetime import datetime

class AnalyticsRunner:
    def __init__(self, audio_training_data=None, models_dir=None):
        # audio_training_data kept for backward compat; not required now
        self.engine = LiveStressEngine(models_dir=models_dir)

    def run_pipeline(self, accel_df, audio_df, trips_df=None, trip_id=None):
        """
        accel_df, audio_df : pandas DataFrames (can be empty)
        trips_df : optional reference data
        trip_id: optional trip_id string
        Returns dict: trip_summary (DataFrame), flagged (DataFrame)
        """
        # defensive
        if accel_df is None:
            accel_df = pd.DataFrame()
        if audio_df is None:
            audio_df = pd.DataFrame()

        # ensure timestamps exist
        if "timestamp" in audio_df.columns:
            audio_df["timestamp"] = pd.to_datetime(audio_df["timestamp"], errors="coerce")
        else:
            audio_df["timestamp"] = pd.Timestamp(datetime.now())

        flagged_records = []
        stress_series = []

        # iterate audio rows and evaluate stress
        for idx, row in audio_df.iterrows():
            audio_row = row.to_dict()
            # for motion we choose nearest accel row by index if available
            motion_row = {}
            if idx < len(accel_df):
                motion_row = accel_df.iloc[idx].to_dict()
            elif len(accel_df) > 0:
                motion_row = accel_df.iloc[-1].to_dict()

            res = self.engine.evaluate(motion_row, audio_row)

            # normalize output fields
            stress = float(res.get("stress", 0.0))
            flagged = bool(res.get("flagged", False))
            audio_score = float(res.get("audio_score", 0.0))
            motion_score = float(res.get("motion_score", 0.0))
            model_used = str(res.get("model_used", "heuristic"))

            stress_series.append({
                "timestamp": audio_row.get("timestamp"),
                "stress": stress,
                "flagged": flagged,
                "audio_score": audio_score,
                "motion_score": motion_score,
                "model_used": model_used,
                "db": float(audio_row.get("audio_level_db", 0.0)),
                "type": audio_row.get("audio_classification", "")
            })

            if flagged:
                flagged_records.append({
                    "timestamp": audio_row.get("timestamp"),
                    "elapsed_seconds": audio_row.get("elapsed_seconds", None),
                    "db": float(audio_row.get("audio_level_db", 0.0)),
                    "type": audio_row.get("audio_classification", ""),
                    "trip_id": trip_id or audio_row.get("trip_id", None)
                })

        stress_df = pd.DataFrame(stress_series)
        flagged_df = pd.DataFrame(flagged_records)

        # cluster flagged events and produce cluster summary
        if not flagged_df.empty:
            clustered_events_df, clusters_df = cluster_flagged_events(flagged_df)
        else:
            clustered_events_df = pd.DataFrame()
            clusters_df = pd.DataFrame()

        # trip summary (basic aggregates)
        try:
            avg_speed = float(accel_df["speed_kmh"].mean()) if ("speed_kmh" in accel_df.columns and len(accel_df)>0) else 0.0
        except Exception:
            avg_speed = 0.0
        try:
            max_db = float(audio_df["audio_level_db"].max()) if ("audio_level_db" in audio_df.columns and len(audio_df)>0) else 0.0
        except Exception:
            max_db = 0.0

        trip_summary = pd.DataFrame([{
            "trip_id": trip_id,
            "avg_speed_kmh": round(avg_speed, 3),
            "max_db": round(max_db, 2),
            "flagged_events": int(len(flagged_df)),
            "clustered_moments": int(len(clusters_df)),
            "max_stress": round(stress_df["stress"].max() if not stress_df.empty else 0.0, 3),
            "mean_stress": round(stress_df["stress"].mean() if not stress_df.empty else 0.0, 3)
        }])

        # ensure JSON-safe dtypes
        for df in (clustered_events_df, clusters_df, flagged_df, stress_df, trip_summary):
            if df is None:
                continue
            for col in df.columns:
                if pd.api.types.is_float_dtype(df[col]):
                    df[col] = df[col].fillna(0.0).astype(float)
                if pd.api.types.is_integer_dtype(df[col]):
                    df[col] = df[col].fillna(0).astype(int)
                # timestamps -> ISO
                if "timestamp" == col or df[col].dtype == "datetime64[ns]":
                    try:
                        df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        pass

        return {
            "motion_events": accel_df,
            "audio_events": audio_df,
            "flagged": clusters_df,               # clusters summary (moments)
            "flagged_raw": clustered_events_df,   # per-event with cluster_id
            "trip_summary": trip_summary
        }