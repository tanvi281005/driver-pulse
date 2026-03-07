# backend/event_clusterer.py
from datetime import datetime, timedelta
import pandas as pd

def cluster_events(flagged_df, window_seconds=5):
    """
    flagged_df: DataFrame with columns ['trip_id','timestamp','type','db','risk_score']
    returns incidents_df with aggregated incidents per trip
    Simple greedy time-window clustering: events within window_seconds are grouped.
    """
    if flagged_df is None or len(flagged_df) == 0:
        return pd.DataFrame(columns=["trip_id","incident_id","start_time","end_time","duration_sec","peak_db","avg_risk","types","count"])

    df = flagged_df.copy()
    # ensure timestamp as datetime
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.sort_values(["trip_id","timestamp"]).reset_index(drop=True)

    incidents = []
    current = None
    incident_counter = {}

    for _, row in df.iterrows():
        t = row["timestamp"]
        tid = row["trip_id"]
        if pd.isnull(t):
            continue
        if current is None or tid != current["trip_id"] or (t - current["end_time"]).total_seconds() > window_seconds:
            # start new incident
            incident_counter.setdefault(tid, 0)
            incident_counter[tid] += 1
            current = {
                "trip_id": tid,
                "incident_id": f"{tid}_INC_{incident_counter[tid]}",
                "start_time": t,
                "end_time": t,
                "peak_db": row.get("db", 0),
                "risk_sum": float(row.get("risk_score", 0) or 0),
                "count": 1,
                "types": set([str(row.get("type",""))])
            }
            incidents.append(current)
        else:
            # extend
            current["end_time"] = t
            current["peak_db"] = max(current["peak_db"], row.get("db", 0))
            current["risk_sum"] += float(row.get("risk_score", 0) or 0)
            current["count"] += 1
            current["types"].add(str(row.get("type","")))
    # convert
    records = []
    for inc in incidents:
        duration = (inc["end_time"] - inc["start_time"]).total_seconds()
        avg_risk = inc["risk_sum"] / max(1, inc["count"])
        records.append({
            "trip_id": inc["trip_id"],
            "incident_id": inc["incident_id"],
            "start_time": inc["start_time"],
            "end_time": inc["end_time"],
            "duration_sec": duration,
            "peak_db": inc["peak_db"],
            "avg_risk": avg_risk,
            "types": ",".join(sorted(list(inc["types"]))),
            "count": inc["count"]
        })
    return pd.DataFrame.from_records(records)