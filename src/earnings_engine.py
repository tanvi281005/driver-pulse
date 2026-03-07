# src/earnings_engine.py
import pandas as pd
import numpy as np

def compute_goal_probability(earnings_df, goals_df):
    # A simple explainable approach:
    # For each driver: compute current_velocity (earnings per hour) from earnings_df
    # Project final earnings assuming same velocity for remaining work hours in their shift (if shift length present)
    # Convert difference between projected_final and goal to a sigmoid probability.
    # This is intentionally simple and explainable (can be replaced with per-driver regressors).

    df = earnings_df.copy()

    # we expect earnings_df to have: driver_id, timestamp, cumulative_earnings
    if "driver_id" not in df.columns:
        return pd.DataFrame(columns=["driver_id","projected_final","prob_hit_goal"])

    df = df.sort_values(["driver_id","timestamp"])
    results = []
    for driver, g in df.groupby("driver_id"):
        g = g.dropna(subset=["timestamp"]).sort_values("timestamp")
        if g.shape[0] < 2:
            continue
        # take last two entries to compute velocity
        last = g.iloc[-1]
        prev = g.iloc[-2]
        dt_hours = (last["timestamp"] - prev["timestamp"]).total_seconds() / 3600.0
        dt_hours = dt_hours if dt_hours>0 else 1/3600
        velocity = (last["cumulative_earnings"] - prev["cumulative_earnings"]) / dt_hours

        # estimate remaining_hours from goals_df if present
        goal_row = goals_df[goals_df["driver_id"]==driver]
        if not goal_row.empty and "target_earnings" in goal_row.columns:
            target = float(goal_row.iloc[-1]["target_earnings"])
        else:
            target = None

        current = float(last["cumulative_earnings"])
        # assume a remaining window default (e.g., 4 hours)
        remaining_hours = 4.0

        projected_final = current + velocity * remaining_hours

        # if no target, set prob as 0.5 if projected above current else 0.1
        if target is None:
            prob = 0.5 if projected_final > current else 0.1
        else:
            # use logistic on distance to goal relative to velocity
            diff = projected_final - target
            # scale factor to map diff -> probability
            scale = max(abs(velocity), 50)  # avoid division by tiny velocities
            z = diff / (scale if scale!=0 else 1)
            # sigmoid
            prob = 1.0 / (1.0 + np.exp(-z))
            prob = float(np.clip(prob, 0.01, 0.99))

        results.append({
            "driver_id": driver,
            "last_cumulative_earnings": current,
            "velocity_per_hour": velocity,
            "projected_final": round(projected_final,2),
            "prob_hit_goal": round(prob,3)
        })
    return pd.DataFrame(results) 