import pandas as pd


def compute_trip_scores(trips, flags):

    summary = flags.groupby("trip_id").agg({

        "flag_id":"count",
        "combined_score":"mean"

    }).reset_index()

    summary.rename(columns={
        "flag_id":"flagged_moments_count",
        "combined_score":"stress_score"
    }, inplace=True)

    trips = trips.merge(summary, on="trip_id", how="left")

    trips.fillna({
        "flagged_moments_count":0,
        "stress_score":0
    }, inplace=True)

    def rate(score):

        if score < 0.2:
            return "excellent"
        elif score < 0.4:
            return "good"
        elif score < 0.7:
            return "fair"
        else:
            return "poor"

    trips["trip_quality_rating"] = trips["stress_score"].apply(rate)

    return trips