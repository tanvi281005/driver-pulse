import pandas as pd
import os

class TripStorage:

    def __init__(self):

        self.trip_file = "outputs/trip_history.csv"

        if not os.path.exists(self.trip_file):

            df = pd.DataFrame(columns=[
                "trip_id",
                "driver_id",
                "earnings",
                "stress_score",
                "distance_km"
            ])

            df.to_csv(self.trip_file,index=False)

    def save_trip(self, trip_summary):

        df = pd.read_csv(self.trip_file)

        df = pd.concat([df,trip_summary],ignore_index=True)

        df.to_csv(self.trip_file,index=False)

    def get_driver_trips(self, driver_id):

        df = pd.read_csv(self.trip_file)

        return df[df["driver_id"] == driver_id]