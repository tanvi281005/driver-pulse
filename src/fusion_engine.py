import pandas as pd


def fuse_events(motion_events, audio_events, stress_model):

    flags = []

    flag_id = 1

    for _, audio in audio_events.iterrows():

        trip_id = audio["trip_id"]

        motion_subset = motion_events[
            motion_events["trip_id"] == trip_id
        ]

        motion_score = 0
        motion_type = "none"

        if not motion_subset.empty:

            closest = motion_subset.iloc[0]

            motion_score = closest["motion_score"]
            motion_type = closest["motion_type"]

        stress_prob = stress_model.predict(
            audio["audio_level_db"],
            audio["duration"]
        )

        combined = (
            0.4 * motion_score +
            0.4 * audio["audio_score"] +
            0.2 * stress_prob
        )

        if combined < 0.4:
            continue

        severity = "low"

        if combined > 0.8:
            severity = "high"
        elif combined > 0.6:
            severity = "medium"

        flags.append({

            "flag_id": f"FLAG{flag_id:03}",
            "trip_id": trip_id,
            "timestamp": audio["timestamp"],
            "elapsed_seconds": audio["elapsed_seconds"],

            "flag_type": audio["audio_type"],
            "severity": severity,

            "motion_score": round(motion_score,2),
            "audio_score": round(audio["audio_score"],2),
            "combined_score": round(combined,2),

            "explanation":
            f"Audio {audio['audio_type']} ({audio['audio_level_db']} dB) with motion {motion_type}",

            "context":
            f"Motion:{motion_type} | Audio:{audio['audio_type']}"
        })

        flag_id += 1

    flags_df = pd.DataFrame(flags)

    print("  flagged moments:", len(flags_df))

    return flags_df