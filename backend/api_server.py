from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

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
simulator = StreamSimulator()
trip_manager= TripManager();
analytics_runner= AnalyticsRunner(audio_training);


class LoginRequest(BaseModel):
    driver_id: str


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

    driver_data = earnings[earnings["driver_id"] == driver_id]

    return driver_data.to_dict(orient="records")


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

@app.get("/flagged_events/{driver_id}")
def flagged_events(driver_id: str):

    flagged = pd.read_csv("outputs/flagged_moments3.csv")

    driver_trips = trips[trips["driver_id"] == driver_id]["trip_id"]

    events = flagged[flagged["trip_id"].isin(driver_trips)]

    return events.to_dict(orient="records")

@app.get("/goal_prediction/{driver_id}")
def goal_prediction(driver_id: str):

    goals = pd.read_csv("data/goals.csv")

    driver_goal = goals[goals["driver_id"] == driver_id]

    if len(driver_goal) == 0:
        return {"probability": 0}

    return {
        "probability": random.uniform(0.5,0.95)
    }

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