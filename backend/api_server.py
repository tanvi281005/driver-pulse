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
from backend.offline_queue import read_all
from backend.trip_storage import TripStorage
from backend.shift_manager import ShiftManager

app = FastAPI()
trips_path = "data/trips.csv"
earnings_path = "data/earnings.csv"
goals_path = "data/driver_goals.csv"
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
shift_manager = ShiftManager()
# load drivers once (static)
try:
    drivers = pd.read_csv(DRIVERS_PATH)
except Exception:
    drivers = pd.DataFrame()

# components
simulator = StreamSimulator()
analytics_runner = AnalyticsRunner()
trip_manager = TripManager()
earnings_predictor = EarningsPredictor()
trip_storage = TripStorage()
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

    shift = shift_manager.get_active_shift(driver_id)

    try:
        trips_df = pd.read_csv(TRIPS_PATH)
    except Exception:
        return []
    trips_df["start_datetime"] = pd.to_datetime(
        trips_df["start_datetime"], errors="coerce"
    )
    driver_trips = trips_df[trips_df["driver_id"] == driver_id]

    if shift is not None:

        start = pd.to_datetime(shift["start_time"])

        driver_trips = trips_df[trips_df["driver_id"] == driver_id]

        driver_trips = driver_trips[driver_trips["start_datetime"] >= start]

    driver_trips = driver_trips.fillna(0)

    return driver_trips.to_dict(orient="records")

@app.get("/earnings/{driver_id}")
def driver_earnings(driver_id: str):

    shift = shift_manager.get_active_shift(driver_id)

    try:
        trips_df = pd.read_csv(TRIPS_PATH)
    except Exception:
        return []

    if trips_df.empty or "fare" not in trips_df.columns:
        return []

    trips_df["start_datetime"] = pd.to_datetime(
        trips_df["start_datetime"], errors="coerce"
    )

    driver_trips = trips_df[trips_df["driver_id"] == driver_id]

    if shift is not None:
        start = pd.to_datetime(shift["start_time"])
        driver_trips = driver_trips[
            driver_trips["start_datetime"] >= start
        ]

    dd = driver_trips[["trip_id", "fare"]].fillna(0)

    return dd.to_dict(orient="records")

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
    # returns motion, audio, stress computed live by TripManager and recent events
    motion, audio, stress = trip_manager.step_trip(trip_id)
    # cast numpy types to float for JSON safety
    def _to_safe(x):
        try:
            if isinstance(x, (np.floating, np.integer)):
                return float(x)
            return x
        except Exception:
            return x
    # return events stored in trip_manager if any
    events = []
    try:
        events = trip_manager.active_trips[trip_id]["events"][-10:]
    except Exception:
        events = []
    stress_safe = {k: (float(v) if isinstance(v, (int, float)) else v) for k,v in stress.items()}
    return {
        "motion": motion,
        "audio": audio,
        "stress": stress_safe,
        "events": events
    }


@app.post("/end_trip/{trip_id}")
def end_trip(trip_id: str, req: EndTripRequest):
    # End the trip in TripManager and gather data (now includes events)
    result = trip_manager.end_trip(trip_id)

    if result[0] is None:
        return {"status":"trip already ended"}

    accel, audio, driver_id, events = result

    # Run analytics (pass events list so clustering works)
    result = analytics_runner.run_pipeline(accel, audio, pd.read_csv(trips_path), trip_id=trip_id, flagged_events=events)

    # Build completed trip row (fill in trips.csv)
    try:
        start_dt = pd.to_datetime(accel["timestamp"].iloc[0])
        end_dt = pd.to_datetime(accel["timestamp"].iloc[-1])
        duration_min = (end_dt - start_dt).total_seconds() / 60.0
    except Exception:
        start_dt = datetime.now()
        end_dt = datetime.now()
        duration_min = 0.0

    distance_km = 0.0
    if "speed_kmh" in accel.columns and len(accel) > 0:
        avg_speed = accel["speed_kmh"].mean()
        distance_km = float(avg_speed) * (duration_min / 60.0)

    fare_val = float(req.earnings or 0.0)

    # update trips.csv
    try:
        trips_df = pd.read_csv(trips_path)
    except FileNotFoundError:
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

    trips_df.to_csv(trips_path, index=False)

    # append to earnings.csv
    try:
        earnings_df = pd.read_csv(earnings_path)
    except FileNotFoundError:
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
    earnings_df.to_csv(earnings_path, index=False)

    # optionally persist summary somewhere (trip_storage)
    if trip_storage:
        try:
            trip_storage.save_trip(result.get("trip_summary"))
        except Exception:
            pass

    # optionally save incidents to outputs/ (human-readable)
    try:
        os.makedirs(os.path.join(os.path.dirname(__file__), "..", "outputs"), exist_ok=True)
        inc_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "outputs", f"incidents_{trip_id}.csv"))
        if result.get("incidents") is not None and len(result.get("incidents"))>0:
            result["incidents"].to_csv(inc_path, index=False)
    except Exception:
        pass

    # Return summary + incidents + flagged
    return {
        "summary": result.get("trip_summary").to_dict(orient="records") if result.get("trip_summary") is not None else [],
        "flags": result.get("flagged").to_dict(orient="records") if result.get("flagged") is not None else [],
        "incidents": result.get("incidents").to_dict(orient="records") if result.get("incidents") is not None else []
    }

@app.get("/driver_today_stats/{driver_id}")
def today_stats(driver_id: str):

    shift = shift_manager.get_active_shift(driver_id)

    if shift is None:
        return {
            "today_earnings": 0,
            "predicted_end": 0,
            "goal_probability": 0
        }

    start = pd.to_datetime(shift["start_time"])

    try:
        trips_df = pd.read_csv(TRIPS_PATH)
    except Exception:
        trips_df = pd.DataFrame()

    if trips_df.empty:
        return {
            "today_earnings": 0,
            "predicted_end": 0,
            "goal_probability": 0
        }

    trips_df["start_datetime"] = pd.to_datetime(trips_df["start_datetime"], errors="coerce")

    driver_trips = trips_df[
        (trips_df["driver_id"] == driver_id) &
        (trips_df["start_datetime"] >= start)
    ]

    today_earnings = driver_trips["fare"].fillna(0).sum()

    predicted = today_earnings + driver_trips["fare"].mean() * 3 if len(driver_trips) > 0 else today_earnings

    goal_prob = earnings_predictor.goal_probability(driver_id)

    return {
        "today_earnings": float(today_earnings),
        "predicted_end": float(predicted),
        "goal_probability": float(goal_prob)
    }

@app.get("/driver_goal/{driver_id}")
def driver_goal(driver_id: str):
    info = earnings_predictor.goal_target_and_progress(driver_id)
    return {"target": round(float(info.get("target",0)),2), "progress": float(info.get("progress",0))}

@app.get("/live_events/{driver_id}")
def live_events(driver_id: str):
    # returns queued offline events + any in-memory active trips
    queued = read_all()  # offline queue
    inmem = []
    for t, v in trip_manager.active_trips.items():
        if v["driver_id"] == driver_id:
            inmem.extend(v.get("events", []))
    # combine and dedupe by timestamp+trip_id
    all_events = queued + inmem
    # limit to last 200
    return all_events[-200:]

@app.post("/start_shift/{driver_id}")
def start_shift(driver_id: str):

    shift_id = shift_manager.start_shift(driver_id)

    return {"shift_id": shift_id}

@app.post("/end_shift/{driver_id}")
def end_shift(driver_id: str):

    shift_id = shift_manager.end_shift(driver_id)

    return {"ended_shift": shift_id}

@app.get("/shift_status/{driver_id}")
def shift_status(driver_id: str):

    shift = shift_manager.get_active_shift(driver_id)

    if shift is None:
        return {"active": False}

    return {
        "active": True,
        "start_time": shift["start_time"],
        "shift_id": shift["shift_id"]
    }