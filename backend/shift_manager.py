import pandas as pd
from datetime import datetime
import os
import uuid

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
SHIFTS_PATH = os.path.join(DATA_DIR, "shifts.csv")


class ShiftManager:

    def __init__(self):

        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)

        if not os.path.exists(SHIFTS_PATH):

            df = pd.DataFrame(columns=[
                "shift_id",
                "driver_id",
                "start_time",
                "end_time",
                "active"
            ])

            df.to_csv(SHIFTS_PATH, index=False)

    def start_shift(self, driver_id):

        shifts = pd.read_csv(SHIFTS_PATH)

        active = shifts[(shifts["driver_id"] == driver_id) & (shifts["active"] == 1)]

        if len(active) > 0:
            return active.iloc[0]["shift_id"]

        shift_id = "SHIFT_" + str(uuid.uuid4())[:6]

        row = {
            "shift_id": shift_id,
            "driver_id": driver_id,
            "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": "",
            "active": 1
        }

        shifts = pd.concat([shifts, pd.DataFrame([row])], ignore_index=True)

        shifts.to_csv(SHIFTS_PATH, index=False)

        return shift_id

    def end_shift(self, driver_id):

        shifts = pd.read_csv(SHIFTS_PATH)

        idx = shifts[(shifts["driver_id"] == driver_id) & (shifts["active"] == 1)].index

        if len(idx) == 0:
            return None

        i = idx[0]

        shifts.at[i, "end_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        shifts.at[i, "active"] = 0

        shifts.to_csv(SHIFTS_PATH, index=False)

        return shifts.at[i, "shift_id"]

    def get_active_shift(self, driver_id):

        shifts = pd.read_csv(SHIFTS_PATH)

        active = shifts[(shifts["driver_id"] == driver_id) & (shifts["active"] == 1)]

        if len(active) == 0:
            return None

        return active.iloc[0].to_dict()