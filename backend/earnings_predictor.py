# backend/earnings_predictor.py
import pandas as pd
from datetime import datetime, time
import joblib
import os
import math
class EarningsPredictor:
    def __init__(self, goals_path="data/driver_goals.csv", trips_path="data/trips.csv", drivers_path="data/drivers.csv"):

        self.goals_path = goals_path
        self.trips_path = trips_path
        self.drivers_path = drivers_path

        model_path = os.path.join(os.path.dirname(__file__), "models", "driver_goal_prediction_model.pkl")

        try:
            self.goal_model = joblib.load(model_path)
        except:
            self.goal_model = None

    def _load_trips(self):
        try:
            return pd.read_csv(self.trips_path)
        except Exception:
            return pd.DataFrame()

    def _load_goals(self):
        try:
            return pd.read_csv(self.goals_path)
        except Exception:
            return pd.DataFrame()

    def _load_drivers(self):
        try:
            return pd.read_csv(self.drivers_path)
        except Exception:
            return pd.DataFrame()

    def earnings_since(self, driver_id, start_time=None):

        df = self._load_trips()

        if df.empty or "start_datetime" not in df.columns:
            return 0.0

        df["start_datetime"] = pd.to_datetime(df["start_datetime"], errors="coerce")

        driver_df = df[df["driver_id"] == driver_id]

        if start_time is not None:
            start_time = pd.to_datetime(start_time)
            driver_df = driver_df[driver_df["start_datetime"] >= start_time]
        else:
            today = datetime.now().date()
            driver_df = driver_df[driver_df["start_datetime"].dt.date == today]

        fare_col = "fare" if "fare" in df.columns else ("earnings" if "earnings" in df.columns else None)

        if fare_col is None:
            return 0.0

        return float(driver_df[fare_col].fillna(0).sum())

    def predict_end_shift(self, driver_id, start_time=None, remaining_trips_hint=5):

        df = self._load_trips()

        fare_col = "fare" if "fare" in df.columns else "earnings"

        if fare_col not in df.columns:
            return 0.0

        today_sum = self.earnings_since(driver_id, start_time)

        hist = df[df["driver_id"] == driver_id]

        if len(hist) == 0:
            return float(today_sum)

        avg = hist[fare_col].dropna()

        if len(avg) == 0:
            return float(today_sum)

        avg_val = float(avg.mean())

        predicted = float(today_sum) + avg_val * remaining_trips_hint

        return predicted

    def goal_probability(self, driver_id, start_time=None):

        goals = self._load_goals()

        if goals.empty or "driver_id" not in goals.columns:
            return 0.0

        row = goals[goals["driver_id"] == driver_id]

        if len(row) == 0:
            return 0.0

        target = float(row.iloc[0].get("target_earnings", row.iloc[0].get("target", 0)))

        today = self.earnings_since(driver_id, start_time)

        predicted = self.predict_end_shift(driver_id, start_time)

        if target <= 0:
            return 0.0

        ratio = predicted / target

        return max(0.0, min(ratio, 1.0))
    

    def goal_target_and_progress(self, driver_id, start_time=None):
        # convenience: returns target and current_progress (0..1)
        goals = self._load_goals()
        if goals.empty or "driver_id" not in goals.columns:
            return {"target": 0.0, "progress": 0.0}
        row = goals[goals["driver_id"] == driver_id]
        if len(row) == 0:
            return {"target": 0.0, "progress": 0.0}
        if "target_earnings" in row.columns:
            target = float(row.iloc[0]["target_earnings"])
        elif "target" in row.columns:
            target = float(row.iloc[0]["target"])
        else:
            target = 0.0
        earnings = self.earnings_since(driver_id, start_time)

        progress = earnings / target if target > 0 else 0.0

        return {
        "target": target,
        "progress": min(progress, 1.0)
        }