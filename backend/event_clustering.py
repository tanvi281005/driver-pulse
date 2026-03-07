# backend/event_clustering.py
import pandas as pd
import numpy as np

# Use DBSCAN to cluster close-by flagged events (temporal clustering on elapsed_seconds)
def cluster_flagged_events(events_df, eps_seconds=120, min_samples=1):
    """
    events_df: DataFrame with at least columns ['timestamp' or 'elapsed_seconds', 'db', 'type', 'trip_id']
    Returns DataFrame with an added 'cluster_id' column and aggregated clusters.
    eps_seconds: temporal window (seconds) to cluster events close by
    """
    if events_df is None or len(events_df) == 0:
        return pd.DataFrame(columns=list(events_df.columns) + ["cluster_id"]) if events_df is not None else pd.DataFrame()

    df = events_df.copy()
    # create numeric time axis: prefer elapsed_seconds, else timestamp
    if "elapsed_seconds" in df.columns and df["elapsed_seconds"].notna().any():
        times = df["elapsed_seconds"].fillna(0).astype(float).to_numpy().reshape(-1, 1)
    else:
        # convert timestamp to unix seconds
        times = pd.to_datetime(df["timestamp"], errors="coerce").astype('int64') // 10**9
        times = times.fillna(0).astype(float).to_numpy().reshape(-1, 1)

    from sklearn.cluster import DBSCAN
    # eps in seconds
    try:
        clustering = DBSCAN(eps=eps_seconds, min_samples=min(2, max(1, len(times))), metric='euclidean').fit(times)
        labels = clustering.labels_
    except Exception:
        # fallback: every event its own cluster
        labels = np.arange(len(times))

    df["cluster_id"] = labels
    # compute cluster aggregates
    clusters = df.groupby("cluster_id").agg(
        start_time=("timestamp", lambda x: x.iloc[0] if len(x)>0 else None),
        end_time=("timestamp", lambda x: x.iloc[-1] if len(x)>0 else None),
        max_db=("db", "max"),
        mean_db=("db", "mean"),
        events_count=("db", "count"),
        types=("type", lambda x: list(x.unique()))
    ).reset_index()

    return df, clusters