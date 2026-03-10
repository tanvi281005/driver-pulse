import random
import pandas as pd
from datetime import datetime


class SensorSimulator:

    def __init__(self, trip_id):

        self.trip_id = trip_id
        self.start_time = datetime.now()
        self.elapsed_seconds = 0

        self.accel_data = []
        self.audio_data = []

    def generate_motion(self):

        accel_x = random.uniform(-2,2)
        accel_y = random.uniform(-2,2)
        accel_z = random.uniform(8,11)

        speed = random.uniform(20,60)

        speed_change = random.uniform(-1,1)

        if random.random() < 0.08:
            speed_change = random.uniform(-2,-1)  
            
        prev_speed = self.accel_data[-1]["speed_kmh"] if self.accel_data else speed

        delta_speed = speed - prev_speed

        accel_magnitude = (accel_x**2 + accel_y**2 + accel_z**2) ** 0.5

        row = {

            "trip_id": self.trip_id,
            "timestamp": datetime.now(),
            "start_datetime": self.start_time,

            "accel_x": accel_x,
            "accel_y": accel_y,
            "accel_z": accel_z,

            "accel_magnitude": accel_magnitude,

        "speed_kmh": speed,
        "speed_change_rate": speed_change,
        "delta_speed": delta_speed
        }

        self.accel_data.append(row)

        return row

    def generate_audio(self):

        db = random.uniform(55,75)
        audio_type = "normal"

        r = random.random()

        if r < 0.05:
            db = random.uniform(90,100)
            audio_type = "argument"

        elif r < 0.15:
            db = random.uniform(80,90)
            audio_type = "loud"

        elif r < 0.3:
            db = random.uniform(70,80)
            audio_type = "conversation"

        row = {

            "trip_id": self.trip_id,
            "timestamp": datetime.now(),
            "elapsed_seconds": self.elapsed_seconds,

            "audio_level_db": db,
            "audio_classification": audio_type,
            "sustained_duration_sec": random.randint(0,30)
        }

        self.audio_data.append(row)

        self.elapsed_seconds += 60

        return row

    def get_dataframes(self):

        accel = pd.DataFrame(self.accel_data)
        audio = pd.DataFrame(self.audio_data)

        return accel, audio