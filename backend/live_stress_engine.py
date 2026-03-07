# backend/live_stress_engine.py
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
    try:
        if joblib and path.endswith(".pkl"):
            return joblib.load(path)
    except Exception:
        pass
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        print("Failed to load model", path, e)
        return None


def _safe_float(x, default=0.0):
    try:
        if x is None:
            return default
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return default
        return v
    except Exception:
        return default


def _build_feature_vector(row, keys):
    vec = []

    for k in keys:

        if isinstance(row, dict):
            val = row.get(k, 0)
        else:
            val = getattr(row, k, 0)

        vec.append(_safe_float(val, 0))

    return np.array(vec).reshape(1, -1)


class LiveStressEngine:

    def __init__(self, models_dir=None):

        self.models_dir = models_dir or MODELS_DIR

        self.audio_model = _try_load(os.path.join(self.models_dir, "audio_model.pkl"))
        self.motion_model = _try_load(os.path.join(self.models_dir, "motion_model.pkl"))
        self.fusion_model = _try_load(os.path.join(self.models_dir, "fusion_model.pkl"))

        manifest_path = os.path.join(self.models_dir, "model_manifest.json")

        self.audio_features = None
        self.motion_features = None

        if os.path.exists(manifest_path):

            try:

                with open(manifest_path) as f:
                    manifest = json.load(f)

                self.audio_features = manifest["audio"]["features"]
                self.motion_features = manifest["motion"]["features"]

            except Exception as e:
                print("Manifest load failed:", e)

        # ----------------------------------------------------------------
        # FALLBACK FEATURE LISTS (MATCH YOUR TRAINING DATA)
        # ----------------------------------------------------------------

        if self.audio_features is None:

            self.audio_features = [

                "audio_level_db",
                "sustained_duration_sec",
                "elapsed_seconds",
                "trip_id_encoded",
                "noise_score"

            ]

        if self.motion_features is None:

            self.motion_features = [

                "accel_x",
                "accel_y",
                "accel_z",
                "speed_kmh",
                "speed_change_rate",
                "jerk",
                "road_roughness"

            ]

    def _predict_score(self, model, X):

        if model is None:
            return None

        try:

            if hasattr(model, "predict_proba"):

                prob = model.predict_proba(X)

                score = prob[0][-1]

            else:

                score = model.predict(X)[0]

            score = float(score)

            if math.isnan(score) or math.isinf(score):
                return None

            if score < 0 or score > 1:

                score = 1 / (1 + math.exp(-score))

            return max(0, min(1, score))

        except Exception as e:

            print("Model scoring error:", e)

            return None

    def evaluate(self, motion, audio):

        # ----------------------------------------------------------------
        # FEATURE ENGINEERING
        # ----------------------------------------------------------------

        audio_row = dict(audio)
        motion_row = dict(motion)

        # derived audio features

        audio_row["trip_id_encoded"] = hash(audio_row.get("trip_id", "")) % 1000

        audio_row["noise_score"] = (
            1 if audio_row.get("audio_classification") == "argument" else 0
        )

        # derived motion features

        motion_row["jerk"] = abs(motion_row.get("speed_change_rate", 0)) * 10

        motion_row["road_roughness"] = (
            abs(motion_row.get("accel_x", 0)) +
            abs(motion_row.get("accel_y", 0))
        )

        # ----------------------------------------------------------------
        # MODEL INPUTS
        # ----------------------------------------------------------------

        Xa = _build_feature_vector(audio_row, self.audio_features)
        Xm = _build_feature_vector(motion_row, self.motion_features)

        audio_score = self._predict_score(self.audio_model, Xa)
        motion_score = self._predict_score(self.motion_model, Xm)

        # ----------------------------------------------------------------
        # FUSION MODEL
        # ----------------------------------------------------------------

        if self.fusion_model and audio_score is not None and motion_score is not None:

            Xf = np.array([[audio_score, motion_score]])

            fused = self._predict_score(self.fusion_model, Xf)

            if fused is not None:

    # normalize fusion output
                stress = float(max(0, min(1, fused)))

    # amplify weak model outputs slightly
                stress = min(1.0, stress * 1.5)

                return {

                    "stress": float(stress),
                    "flagged": stress > 0.15,
                    "risk_score": float(stress),
                    "model_used": "fusion",
                    "audio_score": float(audio_score),
                    "motion_score": float(motion_score)

                }

        # ----------------------------------------------------------------
        # FALLBACK COMBINATION
        # ----------------------------------------------------------------

        if audio_score is not None and motion_score is not None:

            stress = 0.6 * audio_score + 0.4 * motion_score
            model_used = "avg"

        elif audio_score is not None:

            stress = audio_score
            model_used = "audio"

        elif motion_score is not None:

            stress = motion_score
            model_used = "motion"

        else:

            db = _safe_float(audio.get("audio_level_db"), 0)

            stress = db / 100

            model_used = "heuristic"

        return {

            "stress": float(stress),
            "flagged": stress > 0.15,
            "risk_score": float(stress),
            "model_used": model_used,
            "audio_score": float(audio_score or 0),
            "motion_score": float(motion_score or 0)

        }