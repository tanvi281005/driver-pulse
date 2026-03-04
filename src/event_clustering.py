import pandas as pd


def cluster_events(flagged):

    flagged = flagged.sort_values("timestamp")

    clustered = []
    last_time = None

    for _, row in flagged.iterrows():

        if last_time is None:

            clustered.append(row)

            last_time = row["timestamp"]

            continue

        if (row["timestamp"] - last_time).seconds > 15:

            clustered.append(row)

            last_time = row["timestamp"]

    return pd.DataFrame(clustered)