import pandas as pd


def compute_audio_score(db):

    if db < 60:
        return 0.1
    elif db < 75:
        return 0.4
    elif db < 85:
        return 0.7
    elif db < 92:
        return 0.85
    else:
        return 0.95


def detect_audio_events(audio):

    audio = audio.copy()

    audio["audio_score"] = audio["audio_level_db"].apply(compute_audio_score)

    audio_events = audio[audio["audio_score"] > 0.5].copy()

    audio_events.rename(columns={
        "audio_classification": "audio_type",
        "sustained_duration_sec": "duration"
    }, inplace=True)

    print("  audio events:", len(audio_events))

    return audio_events[[
        "trip_id",
        "timestamp",
        "elapsed_seconds",
        "audio_level_db",
        "audio_type",
        "duration",
        "audio_score"
    ]]