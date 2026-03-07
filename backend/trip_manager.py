# backend/trip_manager.py
import uuid
from simulator.sensor_simulator import SensorSimulator
from backend.live_stress_engine import LiveStressEngine

class TripManager:
    def __init__(self, stress_model=None):
        # ignore external stress_model param; instantiate engine which will load models from backend/models
        self.active_trips = {}
        self.stress_engine = LiveStressEngine()

    def start_trip(self, driver_id):
        trip_id = "TRIP_" + str(uuid.uuid4())[:6]
        simulator = SensorSimulator(trip_id)
        self.active_trips[trip_id] = {
            "driver_id": driver_id,
            "simulator": simulator,
            "events": []
        }
        return trip_id

    def step_trip(self, trip_id):
        if trip_id not in self.active_trips:
            raise KeyError(f"Unknown trip_id {trip_id}")

        sim = self.active_trips[trip_id]["simulator"]
        motion = sim.generate_motion()
        audio = sim.generate_audio()

        # engine expects dict-like inputs
        stress = self.stress_engine.evaluate(motion, audio)

        # store flagged event in memory for this trip (useful if network down)
        if stress.get("flagged", False):
            self.active_trips[trip_id]["events"].append({
                "timestamp": audio.get("timestamp"),
                "elapsed_seconds": audio.get("elapsed_seconds"),
                "type": audio.get("audio_classification"),
                "db": audio.get("audio_level_db"),
                "risk": stress.get("risk_score"),
                "model_used": stress.get("model_used")
            })

        # convert numpy types to native
        stress["stress"] = float(stress.get("stress", 0.0))
        stress["risk_score"] = float(stress.get("risk_score", 0.0))
        stress["audio_score"] = float(stress.get("audio_score", 0.0))
        stress["motion_score"] = float(stress.get("motion_score", 0.0))

        return motion, audio, stress

    def get_trip_data(self, trip_id):
        sim = self.active_trips[trip_id]["simulator"]
        return sim.get_dataframes()

    def end_trip(self, trip_id):
        if trip_id not in self.active_trips:
            raise KeyError(f"Unknown trip_id {trip_id}")

        trip = self.active_trips[trip_id]
        sim = trip["simulator"]
        driver_id = trip["driver_id"]

        accel, audio = sim.get_dataframes()

        # collect events that were flagged during the trip (memory)
        events = trip.get("events", [])

        # remove active trip
        del self.active_trips[trip_id]

        return accel, audio, driver_id, events