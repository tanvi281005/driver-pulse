from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
from simulator.stream_simulator import StreamSimulator
from backend.analytics_runner import AnalyticsRunner
from backend.trip_manager import TripManager
from pydantic import BaseModel
import random

app = FastAPI()

# ---------- CORS FIX (required for React frontend) ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # allow frontend (localhost:5173)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# -----------------------------------------------------------


drivers = pd.read_csv("data/drivers.csv")
trips = pd.read_csv("data/trips.csv")
earnings = pd.read_csv("data/earnings.csv")
audio_training = pd.read_csv("data/audio.csv")
goals = pd.read_csv("data/driver_goals.csv")

earnings["timestamp"] = pd.to_datetime(earnings["timestamp"], errors="coerce")
earnings["date"] = pd.to_datetime(earnings["date"], errors="coerce").dt.date
goals["date"] = pd.to_datetime(goals["date"], errors="coerce").dt.date

simulator = StreamSimulator()
trip_manager= TripManager();
analytics_runner= AnalyticsRunner(audio_training);


class LoginRequest(BaseModel):
    driver_id: str

def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))

def compute_driver_goal_prediction(driver_id: str):
    driver_earnings = earnings[earnings["driver_id"] == driver_id].copy()
    driver_goals = goals[goals["driver_id"] == driver_id].copy()

    if driver_earnings.empty or driver_goals.empty:
        return None

    driver_earnings = driver_earnings.sort_values("timestamp")
    driver_goals = driver_goals.sort_values("date")

    latest_earn = driver_earnings.iloc[-1]
    latest_goal = driver_goals.iloc[-1]

    current_earnings = float(latest_earn.get("cumulative_earnings", 0.0))
    elapsed_hours = float(latest_earn.get("elapsed_hours", 0.0))
    current_velocity = float(latest_earn.get("current_velocity", 0.0))
    target_velocity = float(latest_earn.get("target_velocity", 0.0))
    trips_completed = int(latest_earn.get("trips_completed", 0))

    target_earnings = float(latest_goal.get("target_earnings", 0.0))
    target_hours = float(latest_goal.get("target_hours", 0.0))

    remaining_hours = max(target_hours - elapsed_hours, 0.0)
    projected_final_earnings = current_earnings + current_velocity * remaining_hours
    earnings_gap = target_earnings - projected_final_earnings

    scale = max(target_earnings * 0.10, 100.0)
    probability = float(sigmoid((projected_final_earnings - target_earnings) / scale))
    probability = float(np.clip(probability, 0.01, 0.99))

    if projected_final_earnings >= target_earnings:
        status = "ON_TRACK"
    elif probability >= 0.40:
        status = "CLOSE"
    else:
        status = "GOAL_RISK"

    return {
        "driver_id": driver_id,
        "date": str(latest_goal.get("date")),
        "current_earnings": round(current_earnings, 2),
        "elapsed_hours": round(elapsed_hours, 2),
        "current_velocity": round(current_velocity, 2),
        "target_velocity": round(target_velocity, 2),
        "target_earnings": round(target_earnings, 2),
        "target_hours": round(target_hours, 2),
        "remaining_hours": round(remaining_hours, 2),
        "projected_final_earnings": round(projected_final_earnings, 2),
        "earnings_gap": round(earnings_gap, 2),
        "probability": round(probability, 4),
        "status": status,
        "trips_completed": trips_completed,
    }

def compute_earnings_graph(driver_id: str):
    driver_earnings = earnings[earnings["driver_id"] == driver_id].copy()

    if driver_earnings.empty:
        return []

    driver_earnings = driver_earnings.sort_values("timestamp")

    result = []
    for _, row in driver_earnings.iterrows():
        result.append({
            "timestamp": row["timestamp"].strftime("%H:%M"),
            "cumulative_earnings": float(row.get("cumulative_earnings", 0.0)),
            "current_velocity": float(row.get("current_velocity", 0.0)),
            "target_velocity": float(row.get("target_velocity", 0.0)),
            "elapsed_hours": float(row.get("elapsed_hours", 0.0)),
            "trips_completed": int(row.get("trips_completed", 0)),
        })

    return result
    
@app.post("/login")
def login(req: LoginRequest):

    driver = drivers[drivers["driver_id"] == req.driver_id]

    if len(driver) == 0:
        return {"status": "invalid"}

    return {
        "status": "success",
        "driver": driver.iloc[0].to_dict()
    }


@app.get("/driver_trips/{driver_id}")
def driver_trips(driver_id: str):

    driver_trips = trips[trips["driver_id"] == driver_id]

    return driver_trips.to_dict(orient="records")

@app.get("/earnings/{driver_id}")
def driver_earnings(driver_id: str):
    driver_data = earnings[earnings["driver_id"] == driver_id].copy()
    driver_data = driver_data.sort_values("timestamp")
    driver_data["timestamp"] = driver_data["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return driver_data.to_dict(orient="records")
    
'''@app.get("/earnings/{driver_id}")
def driver_earnings(driver_id: str):

    driver_data = earnings[earnings["driver_id"] == driver_id]

    return driver_data.to_dict(orient="records")'''

@app.get("/earnings_graph/{driver_id}")
def earnings_graph(driver_id: str):
    return {
        "driver_id": driver_id,
        "series": compute_earnings_graph(driver_id)
    }

@app.get("/goal_prediction/{driver_id}")
def goal_prediction(driver_id: str):
    prediction = compute_driver_goal_prediction(driver_id)

    if prediction is None:
        return {
            "driver_id": driver_id,
            "probability": 0.0,
            "status": "NO_DATA",
            "current_earnings": 0.0,
            "projected_final_earnings": 0.0,
            "target_earnings": 0.0,
            "remaining_hours": 0.0,
            "earnings_gap": 0.0,
            "current_velocity": 0.0,
            "target_velocity": 0.0,
            "elapsed_hours": 0.0,
            "trips_completed": 0,
        }

    return prediction
    
@app.get("/live_motion")
def live_motion():

    return simulator.next_motion()


@app.get("/live_audio")
def live_audio():

    return simulator.next_audio()

@app.get("/live_stress")
def live_stress():

    motion = simulator.next_motion()
    audio = simulator.next_audio()

    stress_score = random.uniform(0, 1)

    event = {
        "motion": motion,
        "audio": audio,
        "stress_score": stress_score
    }

    return event
'''
@app.get("/flagged_events/{driver_id}")
def flagged_events(driver_id: str):

    flagged = pd.read_csv("outputs/flagged_moments3.csv")

    driver_trips = trips[trips["driver_id"] == driver_id]["trip_id"]

    events = flagged[flagged["trip_id"].isin(driver_trips)]

    return events.to_dict(orient="records")'''

@app.get("/flagged_events/{driver_id}")
def flagged_events(driver_id: str):
    flagged = pd.read_csv("outputs/flagged_moments.csv")

    driver_trip_ids = trips[trips["driver_id"] == driver_id]["trip_id"]
    events = flagged[flagged["trip_id"].isin(driver_trip_ids)].copy()

    if "timestamp" in events.columns:
        events["timestamp"] = pd.to_datetime(events["timestamp"], errors="coerce")
        events = events.sort_values("timestamp")
        events["timestamp"] = events["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")

    return events.to_dict(orient="records")

'''
@app.get("/goal_prediction/{driver_id}")
def goal_prediction(driver_id: str):

    goals = pd.read_csv("data/goals.csv")

    driver_goal = goals[goals["driver_id"] == driver_id]

    if len(driver_goal) == 0:
        return {"probability": 0}

    return {
        "probability": random.uniform(0.5,0.95)
    }'''

@app.post("/start_trip/{driver_id}")
def start_trip(driver_id: str):

    trip_id = trip_manager.start_trip(driver_id)

    return {"trip_id": trip_id}

@app.get("/trip_step/{trip_id}")
def trip_step(trip_id: str):

    motion, audio = trip_manager.step_trip(trip_id)

    return {
        "motion": motion,
        "audio": audio
    }

@app.post("/end_trip/{trip_id}")
def end_trip(trip_id: str):

    accel, audio = trip_manager.end_trip(trip_id)

    result = analytics_runner.run_pipeline(
        accel,
        audio,
        trips
    )

    return {
        "summary": result["trip_summary"].to_dict(orient="records"),
        "flags": result["flagged"].to_dict(orient="records")
    }
