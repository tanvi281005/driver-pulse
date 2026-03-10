import warnings
warnings.filterwarnings("ignore", category=UserWarning)

import os
import json
import pickle
import math
import numpy as np

try:
    import joblib
except Exception:
    joblib = None

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")


def _try_load(path):
    if not os.path.exists(path):
        return None

    # prefer joblib for sklearn artifacts
    if joblib is not None:
        try:
            return joblib.load(path)
        except Exception as e:
            print("Joblib load failed:", e)

    # fallback to pickle
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        print("Pickle load failed:", e)

    return None


def _safe_float(x, default=0.0):
    try:
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return default
        return v
    except Exception:
        return default


def _build_feature_vector_from_keys(row, keys):
    vec = []
    for k in keys:
        if isinstance(row, dict):
            v = row.get(k, 0.0)
        else:
            v = getattr(row, k, 0.0)
        vec.append(_safe_float(v))
    return np.asarray(vec).reshape(1, -1)


class LiveStressEngine:
    """
    Uses audio_model.pkl and motion_model.pkl (if present).
    Returns dict with keys: stress (0..1), flagged (bool), risk_score, model_used, audio_score, motion_score
    """

    def __init__(self, models_dir=None):
        self.models_dir = models_dir or MODELS_DIR

        self.audio_fp = os.path.join(self.models_dir, "audio_model.pkl")
        self.motion_fp = os.path.join(self.models_dir, "motion_model.pkl")
        self.manifest_fp = os.path.join(self.models_dir, "model_manifest.json")

        self.audio_model = _try_load(self.audio_fp)
        self.motion_model = _try_load(self.motion_fp)

        # features (can be overridden by manifest)
        self.audio_features = None
        self.motion_features = None

        # detection threshold and smoothing
        self.flag_threshold = 0.35
        self.alpha = 0.6  # smoothing weight for current value
        self.previous_stress = 0.0

        # read manifest if present
        if os.path.exists(self.manifest_fp):
            try:
                with open(self.manifest_fp, "r") as f:
                    manifest = json.load(f)
                self.audio_features = manifest.get("audio", {}).get("features")
                self.motion_features = manifest.get("motion", {}).get("features")
                if "thresholds" in manifest:
                    self.flag_threshold = manifest["thresholds"].get("default_flag", self.flag_threshold)
            except Exception as e:
                print("Failed to read model manifest:", e)

        # fallback defaults
        if self.audio_features is None:
            self.audio_features = [
                "audio_level_db",
                "sustained_duration_sec",
                "audio_db_delta",
                "audio_variance",
                "noise_spike",
            ]

        if self.motion_features is None:
            self.motion_features = [
                "speed_kmh",
                "speed_change_rate",
                "acceleration",
                "brake_intensity",
                "speed_variance",
                "jerk",
                "speed_delta",
            ]

    def _score_from_model(self, model, X):
        if model is None:
            return None
        try:
            if hasattr(model, "predict_proba"):
                p = model.predict_proba(X)
                if p.ndim == 2 and p.shape[1] >= 2:
                    val = float(p[0, -1])
                else:
                    val = float(p[0, 0])
            else:
                pred = model.predict(X)
                val = float(pred[0])
            # squash logits to 0..1 if needed
            if val < 0 or val > 1:
                try:
                    val = 1.0 / (1.0 + math.exp(-val))
                except Exception:
                    val = max(0.0, min(1.0, val))
            return max(0.0, min(1.0, val))
        except Exception as e:
            print("Model scoring error:", e)
            return None

    def _compute_audio_score(self, audio_row):
        try:
            X = _build_feature_vector_from_keys(audio_row, self.audio_features)
            return self._score_from_model(self.audio_model, X)
        except Exception as e:
            print("audio scoring failed:", e)
            return None

    def _compute_motion_score(self, motion_row):
        try:
            X = _build_feature_vector_from_keys(motion_row, self.motion_features)
            return self._score_from_model(self.motion_model, X)
        except Exception as e:
            print("motion scoring failed:", e)
            return None
        
    def _motion_severity(self, motion):
        speed_rate = _safe_float(motion.get("speed_change_rate"), 0)
        delta_speed = _safe_float(motion.get("delta_speed"), 0)
        accel_mag = _safe_float(motion.get("accel_magnitude"), 9.8)

    # harsh braking / acceleration
        accel_event = min(abs(speed_rate) / 0.8, 1.0)

    # sudden speed change
        delta_event = min(abs(delta_speed) / 20.0, 1.0)

    # bumps / potholes
        bump_event = min(abs(accel_mag - 9.8) / 2.0, 1.0)

        severity = 0.4 * accel_event + 0.4 * delta_event + 0.2 * bump_event

        return max(0.0, min(1.0, severity))

    def evaluate(self, motion, audio):
        # normalize inputs to plain dicts
        if hasattr(motion, "to_dict"):
            motion = motion.to_dict()
        if hasattr(audio, "to_dict"):
            audio = audio.to_dict()

        # base numbers
        audio_db = _safe_float(audio.get("audio_level_db"), 0.0)
        duration = _safe_float(audio.get("sustained_duration_sec"), 0.0)
        speed = _safe_float(motion.get("speed_kmh"), 0.0)
        speed_rate = _safe_float(motion.get("speed_change_rate"), 0.0)

        # derived audio features (safe, simple)
        audio["audio_db_delta"] = abs(audio_db - 60)
        audio["audio_variance"] = audio_db * 0.05
        audio["noise_spike"] = 1.0 if audio_db > 85 else 0.0

        # derived motion features
        delta_speed = _safe_float(motion.get("delta_speed"), 0.0)
        accel_mag = _safe_float(motion.get("accel_magnitude"), 9.8)

        motion["acceleration"] = abs(speed_rate)
        motion["brake_intensity"] = abs(min(delta_speed, 0))
        motion["speed_variance"] = abs(delta_speed)
        motion["jerk"] = abs(speed_rate)
        motion["speed_delta"] = delta_speed

# very important feature
        motion["accel_force"] = abs(accel_mag - 9.8)

        # compute model scores
        audio_score = self._compute_audio_score(audio) if self.audio_model is not None else None
        motion_score = self._compute_motion_score(motion) if self.motion_model is not None else None
        # additional motion severity signal
        motion_severity = self._motion_severity(motion)

        if motion_score is None:
            motion_score = motion_severity
        else:
            motion_score = max(motion_score, motion_severity)
        # heuristic combination (audio heavier)
        if audio_score is not None and motion_score is not None:
            raw_stress =  max(audio_score, motion_score)
            model_used = "audio_motion_heuristic"
        elif audio_score is not None:
            raw_stress = float(audio_score)
            model_used = "audio_only"
        elif motion_score is not None:
            raw_stress = float(motion_score)
            model_used = "motion_only"
        else:
            raw_stress = min(audio_db / 100.0, 1.0)
            model_used = "fallback"

        # smoothing
        smoothed = self.alpha * raw_stress + (1.0 - self.alpha) * self.previous_stress
        self.previous_stress = smoothed
        motion_spike = (
    abs(speed_rate) > 0.5 or
    abs(delta_speed) > 15 or
    abs(accel_mag - 9.8) > 1.5
)

        if motion_spike:
            motion_score = max(motion_score, 0.6)
        # detection logic: allow either raw spike or smoothed value to trigger
        flagged = (raw_stress > self.flag_threshold) or (smoothed > self.flag_threshold)

        # clamp and return
        stress_val = max(0.0, min(1.0, float(smoothed)))

        # debug: helpful short log (safe to keep; remove if too verbose)
        try:
            print(
                f"[LIVE_STRESS] raw={raw_stress:.4f} smoothed={smoothed:.4f} "
                f"audio_score={audio_score} motion_score={motion_score} "
                f"flagged={flagged} threshold={self.flag_threshold}"
            )
        except Exception:
            pass

        return {
            "stress": stress_val,
            "flagged": bool(flagged),
            "risk_score": stress_val,
            "model_used": model_used,
            "audio_score": float(audio_score) if audio_score is not None else 0.0,
            "motion_score": float(motion_score) if motion_score is not None else 0.0,
        }