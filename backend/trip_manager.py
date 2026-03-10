import uuid
import os
from simulator.sensor_simulator import SensorSimulator
from datetime import datetime
from backend.offline_queue import append_event
import pandas as pd

# Import LiveStressEngine from backend.live_stress_engine or fallback in api_server
try:
    from backend.live_stress_engine import LiveStressEngine
except Exception:
    LiveStressEngine = None


class TripManager:
    def __init__(self, stress_model=None):
        self.active_trips = {}
        # stress_engine will be created by api_server (it passed model earlier)
        # stress_model argument is treated as models_dir (optional)
        self.stress_engine = LiveStressEngine(stress_model) if LiveStressEngine else None

    def start_trip(self, driver_id):
        trip_id = "TRIP_" + str(uuid.uuid4())[:6]
        simulator = SensorSimulator(trip_id)
        self.active_trips[trip_id] = {
            "driver_id": driver_id,
            "simulator": simulator,
            "events": []  ,
            "last_event_ts": None
        }
        return trip_id

    def step_trip(self, trip_id):
        if trip_id not in self.active_trips:
            raise KeyError(f"Unknown trip_id {trip_id}")

        entry = self.active_trips[trip_id]
        sim = entry["simulator"]

        motion = sim.generate_motion()
        audio = sim.generate_audio()

        # make sure dict-like
        m = motion if isinstance(motion, dict) else (motion.to_dict() if hasattr(motion, "to_dict") else dict(motion))
        a = audio if isinstance(audio, dict) else (audio.to_dict() if hasattr(audio, "to_dict") else dict(audio))

        stress = self.stress_engine.evaluate(m, a) if self.stress_engine else {"stress": 0.0, "flagged": False, "risk_score": 0.0, "model_used": "none"}

        # when flagged, append a normalized event and add to offline queue
        try:
            is_flagged = bool(stress.get("flagged", False))
        except Exception:
            is_flagged = False

        if is_flagged:
            audio_score = float(stress.get("audio_score", 0))
            motion_score = float(stress.get("motion_score", 0))

# decide event type
            if motion_score > audio_score:
                event_type = "motion"
            else:
                event_type = a.get("audio_classification", "audio")

            event = {
    "trip_id": trip_id,
    "driver_id": entry["driver_id"],
    "timestamp": a.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),

    "type": event_type,

    "audio_db": float(a.get("audio_level_db", 0) or 0),
    "speed_kmh": float(m.get("speed_kmh", 0) or 0),
    "speed_change_rate": float(m.get("speed_change_rate", 0) or 0),
    "accel_magnitude": float(m.get("accel_magnitude", 0) or 0),

    "audio_score": audio_score,
    "motion_score": motion_score,

    "risk_score": float(stress.get("risk_score", 0.0)),
    "model_used": stress.get("model_used", "")
}
            entry["events"].append(event)

            # DEBUG log so you can see server-side when an event is detected
            try:
                print(f"[TRIP_MANAGER] EVENT DETECTED for {trip_id}: {event}")
            except Exception:
                pass

            # save to outputs/flagged_moments3.csv (append) and also to offline queue
            try:
                os.makedirs(os.path.join(os.path.dirname(__file__), "..", "outputs"), exist_ok=True)
                csvp = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "outputs", "flagged_moments3.csv"))
                df = pd.DataFrame([event])
                if not os.path.exists(csvp):
                    df.to_csv(csvp, index=False)
                else:
                    df.to_csv(csvp, mode="a", index=False, header=False)
            except Exception as e:
                print("Failed to persist flagged to CSV:", e)
            try:
                append_event(event)
                try:
                    print(f"[TRIP_MANAGER] appended to offline queue for {trip_id}")
                except Exception:
                    pass
            except Exception as e:
                print("append_event failed:", e)

        return m, a, stress

    def get_trip_data(self, trip_id):
        if trip_id not in self.active_trips:
            raise KeyError(f"Unknown trip_id {trip_id}")
        sim = self.active_trips[trip_id]["simulator"]
        return sim.get_dataframes()

    def end_trip(self, trip_id):
        if trip_id not in self.active_trips:
            print("Trip already ended:", trip_id)
            return None, None, None, []
        trip = self.active_trips[trip_id]
        sim = trip["simulator"]
        driver_id = trip["driver_id"]
        accel, audio = sim.get_dataframes()
        # collect events for this trip (in-memory)
        events = trip.get("events", [])
        # Remove active trip
        del self.active_trips[trip_id]
        return accel, audio, driver_id, events