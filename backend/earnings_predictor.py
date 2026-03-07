# backend/earnings_predictor.py
import pandas as pd
from datetime import datetime
import os

class EarningsPredictor:
    def __init__(self, goals_path="data/driver_goals.csv", trips_path="data/trips.csv", earnings_path="data/earnings.csv"):
        self.goals_path = goals_path
        self.trips_path = trips_path
        self.earnings_path = earnings_path

    def _safe_load(self, path):
        if not os.path.exists(path):
            return pd.DataFrame()
        try:
            return pd.read_csv(path)
        except Exception:
            try:
                return pd.read_csv(path, encoding="utf-8", engine="python")
            except Exception:
                return pd.DataFrame()

    def total_today(self, driver_id):
        df = self._safe_load(self.trips_path)
        if df.empty:
            # try earnings file
            df2 = self._safe_load(self.earnings_path)
            if df2.empty:
                return 0.0
            col = "fare" if "fare" in df2.columns else ("earnings" if "earnings" in df2.columns else None)
            if col is None:
                return 0.0
            df2["date"] = pd.to_datetime(df2["date"], errors="coerce").dt.date
            today = datetime.now().date()
            res = df2[(df2["driver_id"]==driver_id) & (df2["date"]==today)][col].fillna(0).sum()
            return float(res)

        # trips.csv present
        if "start_datetime" in df.columns:
            try:
                df["start_datetime_parsed"] = pd.to_datetime(df["start_datetime"], errors="coerce")
                today = datetime.now().date()
                df_today = df[(df["driver_id"]==driver_id) & (df["start_datetime_parsed"].dt.date == today)]
            except Exception:
                df_today = df[df["driver_id"]==driver_id]
        else:
            df_today = df[df["driver_id"]==driver_id]

        fare_col = "fare" if "fare" in df.columns else ("earnings" if "earnings" in df.columns else None)
        if fare_col is None:
            return 0.0
        total = df_today[fare_col].fillna(0).sum()
        try:
            return float(total)
        except Exception:
            return 0.0

    def predict_end_shift(self, driver_id, remaining_trips_hint=5):
        df = self._safe_load(self.trips_path)
        if df.empty:
            return 0.0

        fare_col = "fare" if "fare" in df.columns else ("earnings" if "earnings" in df.columns else None)
        if fare_col is None:
            return 0.0

        # today's sum
        try:
            df["start_datetime_parsed"] = pd.to_datetime(df["start_datetime"], errors="coerce")
            today = datetime.now().date()
            today_sum = df[(df["driver_id"]==driver_id) & (df["start_datetime_parsed"].dt.date == today)][fare_col].fillna(0).sum()
        except Exception:
            today_sum = df[df["driver_id"]==driver_id][fare_col].fillna(0).sum()

        hist = df[df["driver_id"] == driver_id][fare_col].dropna()
        if len(hist) == 0:
            return float(today_sum)

        avg_val = float(hist.mean())
        predicted = float(today_sum) + avg_val * remaining_trips_hint
        return predicted

    def goal_probability(self, driver_id):
        goals = self._safe_load(self.goals_path)
        if goals.empty:
            return 0.0
        if "driver_id" not in goals.columns:
            return 0.0
        row = goals[goals["driver_id"] == driver_id]
        if row.empty:
            return 0.0
        # try multiple possible target column names
        col_candidates = ["target_earnings", "target", "goal", "target_earnings_amount"]
        target = None
        for c in col_candidates:
            if c in row.columns:
                try:
                    target = float(row.iloc[0][c])
                    break
                except Exception:
                    continue
        if target is None:
            # try 'current_earnings' as last resort
            target = float(row.iloc[0].get("target_earnings", 0) or 0.0)
        if target <= 0:
            return 0.0
        predicted = self.predict_end_shift(driver_id)
        prob = min(max(predicted / target, 0.0), 1.0)
        return prob