from src.data_loader import load_all_data
from src.motion_events import detect_motion_events
from src.audio_events import detect_audio_events
from src.stress_model import StressModel
from src.fusion_engine import fuse_events
from src.trip_scoring import compute_trip_scores


def main():

    accel, audio, trips, earnings = load_all_data()

    print("[1/6] Motion detection")
    motion_events = detect_motion_events(accel)

    print("[2/6] Audio detection")
    audio_events = detect_audio_events(audio)

    print("[3/6] Training stress model")
    model = StressModel()
    model.train(audio)

    print("[4/6] Fusion engine")
    flags = fuse_events(motion_events, audio_events, model)

    print("[5/6] Trip scoring")
    trip_scores = compute_trip_scores(trips, flags)

    print("[6/6] Saving outputs")

    flags.to_csv("outputs/flagged_moments.csv", index=False)
    trip_scores.to_csv("outputs/trip_scores.csv", index=False)

    print("Pipeline finished successfully")


if __name__ == "__main__":
    main()
