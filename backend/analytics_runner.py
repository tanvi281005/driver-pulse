import pandas as pd

from src.motion_events import detect_motion_events
from src.audio_events import detect_audio_events
from src.fusion_engine import fuse_events
from src.trip_summary import generate_trip_summary
from src.stress_model import StressModel


class AnalyticsRunner:

    def __init__(self, audio_training_data):

        self.stress_model = StressModel()
        self.stress_model.train(audio_training_data)

    def run_pipeline(self, accel_df, audio_df, trips_df):

        motion_events = detect_motion_events(accel_df)

        audio_events = detect_audio_events(audio_df)

        flagged = fuse_events(
            motion_events,
            audio_events,
            self.stress_model
        )

        trip_summary = generate_trip_summary(
            flagged,
            trips_df
        )

        return {

            "motion_events": motion_events,
            "audio_events": audio_events,
            "flagged": flagged,
            "trip_summary": trip_summary
        }