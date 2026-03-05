import uuid
import pandas as pd
from simulator.sensor_simulator import SensorSimulator


class TripManager:

    def __init__(self):

        self.active_trips = {}

    def start_trip(self, driver_id):

        trip_id = "TRIP_" + str(uuid.uuid4())[:6]

        simulator = SensorSimulator(trip_id)

        self.active_trips[trip_id] = {

            "driver_id": driver_id,
            "simulator": simulator
        }

        return trip_id

    def step_trip(self, trip_id):

        sim = self.active_trips[trip_id]["simulator"]

        motion = sim.generate_motion()
        audio = sim.generate_audio()

        return motion, audio

    def get_trip_data(self, trip_id):

        sim = self.active_trips[trip_id]["simulator"]

        return sim.get_dataframes()

    def end_trip(self, trip_id):

        sim = self.active_trips[trip_id]["simulator"]

        accel, audio = sim.get_dataframes()

        del self.active_trips[trip_id]

        return accel, audio