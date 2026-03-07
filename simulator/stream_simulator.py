import pandas as pd

class StreamSimulator:

    def __init__(self):

        self.accel = pd.read_csv("data/accelerometer_new.csv")
        self.audio = pd.read_csv("data/audio_full.csv")

        self.accel["timestamp"] = pd.to_datetime(self.accel["timestamp"])
        self.audio["timestamp"] = pd.to_datetime(self.audio["timestamp"])

        self.accel = self.accel.sort_values("timestamp")
        self.audio = self.audio.sort_values("timestamp")

        self.motion_index = 0
        self.audio_index = 0

    def next_motion(self):

        if self.motion_index >= len(self.accel):
            return None

        row = self.accel.iloc[self.motion_index]
        self.motion_index += 1
        return row.to_dict()

    def next_audio(self):

        if self.audio_index >= len(self.audio):
            return None

        row = self.audio.iloc[self.audio_index]
        self.audio_index += 1
        return row.to_dict()