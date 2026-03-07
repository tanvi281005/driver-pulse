# backend/api_server.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import pandas as pd
import random
import os
import json
import numpy as np
from simulator.stream_simulator import StreamSimulator
from backend.analytics_runner import AnalyticsRunner
from backend.trip_manager import TripManager
from backend.earnings_predictor import EarningsPredictor

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# data paths
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DATA_DIR = os.path.abspath(DATA_DIR)
TRIPS_PATH = os.path.join(DATA_DIR, "trips.csv")
EARNINGS_PATH = os.path.join(DATA_DIR, "earnings.csv")
GOALS_PATH = os.path.join(DATA_DIR, "driver_goals.csv")
DRIVERS_PATH = os.path.join(DATA_DIR, "drivers.csv")

# load drivers once (static)
try:
    drivers = pd.read_csv(DRIVERS_PATH)
except Exception:
    drivers = pd.DataFrame()

# components
simulator = StreamSimulator()
analytics_runner = AnalyticsRunner(models_dir=os.path.join(os.path.dirname(__file__), "models"))
trip_manager = TripManager()
earnings_predictor = EarningsPredictor(goals_path=GOALS_PATH, trips_path=TRIPS_PATH, earnings_path=EARNINGS_PATH)

# request models
class LoginRequest(BaseModel):
    driver_id: str

class EndTripRequest(BaseModel):
    earnings: float = 0.0

@app.post("/login")
def login(req: LoginRequest):
    driver = drivers[drivers["driver_id"] == req.driver_id] if not drivers.empty else pd.DataFrame()
    if len(driver) == 0:
        return {"status": "invalid"}
    return {"status": "success", "driver": driver.iloc[0].to_dict()}

@app.get("/driver_trips/{driver_id}")
def driver_trips(driver_id: str):
    try:
        trips_df = pd.read_csv(TRIPS_PATH)
    except Exception:
        trips_df = pd.DataFrame()
    driver_trips = trips_df[trips_df["driver_id"] == driver_id] if not trips_df.empty else pd.DataFrame()
    driver_trips = driver_trips.fillna(0)
    return driver_trips.to_dict(orient="records")

@app.get("/earnings/{driver_id}")
def driver_earnings(driver_id: str):
    # Prefer trips.csv fare column, fallback to earnings.csv
    try:
        trips_df = pd.read_csv(TRIPS_PATH)
    except Exception:
        trips_df = pd.DataFrame()
    records = []
    if not trips_df.empty and "fare" in trips_df.columns:
        dd = trips_df[trips_df["driver_id"] == driver_id][["trip_id", "fare"]].fillna(0)
        records = dd.to_dict(orient="records")
    else:
        try:
            earnings_df = pd.read_csv(EARNINGS_PATH)
        except Exception:
            earnings_df = pd.DataFrame()
        col = "fare" if "fare" in earnings_df.columns else ("earnings" if "earnings" in earnings_df.columns else None)
        if col:
            dd = earnings_df[earnings_df["driver_id"] == driver_id][["trip_id", col]].rename(columns={col: "fare"}).fillna(0)
            records = dd.to_dict(orient="records")
    return records

@app.get("/flagged_events/{driver_id}")
def flagged_events(driver_id: str):
    flagged_file = os.path.join(os.path.dirname(__file__), "..", "outputs", "flagged_moments3.csv")
    if os.path.exists(flagged_file):
        try:
            flagged = pd.read_csv(flagged_file)
            trips_df = pd.read_csv(TRIPS_PATH) if os.path.exists(TRIPS_PATH) else pd.DataFrame()
            driver_trip_ids = trips_df[trips_df["driver_id"] == driver_id]["trip_id"] if not trips_df.empty else []
            events = flagged[flagged["trip_id"].isin(driver_trip_ids)]
            return events.to_dict(orient="records")
        except Exception:
            return []
    # no external flagged file; we can derive from trips.csv flagged raw (if you stored them)
    return []

@app.get("/goal_prediction/{driver_id}")
def goal_prediction(driver_id: str):
    prob = earnings_predictor.goal_probability(driver_id)
    return {"probability": float(prob)}

@app.post("/start_trip/{driver_id}")
def start_trip(driver_id: str):
    trip_id = trip_manager.start_trip(driver_id)

    # create a starter row in trips.csv so UI sees it
    try:
        trips_df = pd.read_csv(TRIPS_PATH)
    except Exception:
        trips_df = pd.DataFrame(columns=["trip_id","driver_id","start_datetime","end_datetime","duration_min","distance_km","fare","surge_multiplier"])

    new_row = {
        "trip_id": trip_id,
        "driver_id": driver_id,
        "start_datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "end_datetime": "",
        "duration_min": "",
        "distance_km": "",
        "fare": "",
        "surge_multiplier": 1.0
    }
    trips_df = pd.concat([trips_df, pd.DataFrame([new_row])], ignore_index=True)
    trips_df.to_csv(TRIPS_PATH, index=False)

    return {"trip_id": trip_id}

@app.get("/trip_step/{trip_id}")
def trip_step(trip_id: str):
    try:
        motion, audio, stress = trip_manager.step_trip(trip_id)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Make sure objects are JSON serializable
    audio_safe = audio if isinstance(audio, dict) else (audio.to_dict() if hasattr(audio, "to_dict") else {})
    motion_safe = motion if isinstance(motion, dict) else (motion.to_dict() if hasattr(motion, "to_dict") else {})
    # cast stress floats
    stress_safe = {k: (float(v) if isinstance(v, (int, float,  np.floating, np.integer)) else v) for k,v in stress.items()}
    return {"motion": motion_safe, "audio": audio_safe, "stress": stress_safe}

@app.post("/end_trip/{trip_id}")
def end_trip(trip_id: str, req: EndTripRequest):
    # End trip and get data + in-memory events
    try:
        accel, audio, driver_id, events = trip_manager.end_trip(trip_id)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Run analytics (this uses models to compute flagged moments and trip summary)
    result = analytics_runner.run_pipeline(accel, audio, trip_id=trip_id)

    # compute start/end/duration
    try:
        start_dt = pd.to_datetime(accel["start_datetime"].iloc[0])
        end_dt = pd.to_datetime(accel["timestamp"].iloc[-1])
        duration_min = (end_dt - start_dt).total_seconds() / 60.0
    except Exception:
        start_dt = datetime.now()
        end_dt = datetime.now()
        duration_min = 0.0

    # estimate distance
    distance_km = 0.0
    try:
        if "speed_kmh" in accel.columns and len(accel)>0:
            avg_speed = float(accel["speed_kmh"].mean())
            distance_km = avg_speed * (duration_min/60.0)
    except Exception:
        distance_km = 0.0

    fare_val = float(req.earnings or 0.0)

    # Update trips.csv (update starter row)
    try:
        trips_df = pd.read_csv(TRIPS_PATH)
    except Exception:
        trips_df = pd.DataFrame(columns=["trip_id","driver_id","start_datetime","end_datetime","duration_min","distance_km","fare","surge_multiplier"])

    idx = trips_df[trips_df["trip_id"] == trip_id].index
    if len(idx) > 0:
        i = idx[0]
        trips_df.at[i, "end_datetime"] = end_dt.strftime("%Y-%m-%d %H:%M:%S")
        trips_df.at[i, "duration_min"] = round(duration_min, 2)
        trips_df.at[i, "distance_km"] = round(distance_km, 3)
        trips_df.at[i, "fare"] = round(fare_val, 2)
        if "surge_multiplier" not in trips_df.columns or pd.isna(trips_df.at[i, "surge_multiplier"]):
            trips_df.at[i, "surge_multiplier"] = 1.0
    else:
        new_trip_row = {
            "trip_id": trip_id,
            "driver_id": driver_id,
            "start_datetime": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "end_datetime": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "duration_min": round(duration_min, 2),
            "distance_km": round(distance_km, 3),
            "fare": round(fare_val, 2),
            "surge_multiplier": 1.0
        }
        trips_df = pd.concat([trips_df, pd.DataFrame([new_trip_row])], ignore_index=True)

    trips_df.to_csv(TRIPS_PATH, index=False)

    # Append to earnings.csv (minimal row)
    try:
        earnings_df = pd.read_csv(EARNINGS_PATH)
    except Exception:
        earnings_df = pd.DataFrame(columns=["log_id","driver_id","date","timestamp","cumulative_earnings","elapsed_hours","current_velocity","target_velocity","velocity_delta","trips_completed","forecast_status","behind_target","trip_id","fare"])
    new_earn_row = {
        "log_id": "",
        "driver_id": driver_id,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cumulative_earnings": "",
        "elapsed_hours": "",
        "current_velocity": "",
        "target_velocity": "",
        "velocity_delta": "",
        "trips_completed": "",
        "forecast_status": "",
        "behind_target": "",
        "trip_id": trip_id,
        "fare": round(fare_val, 2)
    }
    earnings_df = pd.concat([earnings_df, pd.DataFrame([new_earn_row])], ignore_index=True)
    earnings_df.to_csv(EARNINGS_PATH, index=False)

    # return analytics summaries to frontend
    return {
        "summary": result.get("trip_summary").to_dict(orient="records") if result.get("trip_summary") is not None else [],
        "flags": result.get("flagged").to_dict(orient="records") if result.get("flagged") is not None else [],
        "flags_raw": result.get("flagged_raw").to_dict(orient="records") if result.get("flagged_raw") is not None else []
    }

@app.get("/driver_today_stats/{driver_id}")
def today_stats(driver_id: str):
    today_earnings = earnings_predictor.total_today(driver_id)
    predicted = earnings_predictor.predict_end_shift(driver_id)
    prob = earnings_predictor.goal_probability(driver_id)

    return {
        "today_earnings": round(float(today_earnings), 2),
        "predicted_end": round(float(predicted), 2),
        "goal_probability": float(prob)
    }