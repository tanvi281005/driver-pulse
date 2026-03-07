# backend/live_stress_engine.py
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
        # joblib for sklearn artifacts; fallback to pickle
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


def _build_feature_vector_from_keys(row, keys):
    vec = []
    for k in keys:
        if isinstance(row, dict):
            v = row.get(k, 0.0)
        else:
            # pandas row or simple object
            v = getattr(row, k, None) if hasattr(row, k) else (row.get(k, 0.0) if hasattr(row, "get") else 0.0)
        vec.append(_safe_float(v, 0.0))
    return np.asarray(vec).reshape(1, -1)


class LiveStressEngine:
    """
    Loads models from backend/models (audio, motion, optional fusion).
    evaluate(motion_row, audio_row) -> dict:
      - stress: float 0..1
      - flagged: bool
      - risk_score: float 0..1
      - model_used: "fusion"|"audio"|"motion"|"heuristic"|"avg"
      - audio_score, motion_score
    Configurable via model_manifest.json keys: "audio.features", "motion.features", "thresholds"
    """

    def __init__(self, models_dir=None):
        self.models_dir = models_dir or MODELS_DIR

        # default filenames
        self.audio_fp = os.path.join(self.models_dir, "audio_model.pkl")
        self.motion_fp = os.path.join(self.models_dir, "motion_model.pkl")
        self.fusion_fp = os.path.join(self.models_dir, "fusion_model.pkl")
        self.manifest_fp = os.path.join(self.models_dir, "model_manifest.json")

        # loaded objects
        self.audio_model = _try_load(self.audio_fp)
        self.motion_model = _try_load(self.motion_fp)
        self.fusion_model = _try_load(self.fusion_fp)

        # feature lists if provided
        self.audio_features = None
        self.motion_features = None

        # thresholds
        self.thresholds = {"fusion_flag": 0.85, "default_flag": 0.85}

        if os.path.exists(self.manifest_fp):
            try:
                with open(self.manifest_fp, "r") as f:
                    manifest = json.load(f)
                self.audio_features = manifest.get("audio", {}).get("features")
                self.motion_features = manifest.get("motion", {}).get("features")
                if "thresholds" in manifest:
                    self.thresholds.update(manifest.get("thresholds", {}))
            except Exception as e:
                print("Failed to read model manifest:", e)

        # fallback defaults
        if self.audio_features is None:
            self.audio_features = ["audio_level_db", "sustained_duration_sec"]

        if self.motion_features is None:
            self.motion_features = ["speed_kmh", "speed_change_rate"]

    def _score_from_model(self, model, X):
        """
        Try predict_proba then predict. Ensure 0..1 output; handle logits by sigmoid.
        """
        if model is None:
            return None
        try:
            if hasattr(model, "predict_proba"):
                p = model.predict_proba(X)
                # take probability of positive class (last column)
                if p.ndim == 2 and p.shape[1] >= 2:
                    val = float(p[0, -1])
                else:
                    val = float(p[0, 0])
            else:
                pred = model.predict(X)
                val = float(pred[0])
            if math.isnan(val) or math.isinf(val):
                return None
            # clamp or squash
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

    def evaluate(self, motion, audio):
        """
        Evaluate one timestep. motion, audio are dict-like.
        Returns serializable dict (no NaN, no numpy types).
        """
        # ensure plain dicts
        if hasattr(motion, "to_dict"):
            motion = motion.to_dict()
        if hasattr(audio, "to_dict"):
            audio = audio.to_dict()

        audio_db = _safe_float(audio.get("audio_level_db"), 0.0)
        audio_score = self._compute_audio_score(audio) if self.audio_model is not None else None
        motion_score = self._compute_motion_score(motion) if self.motion_model is not None else None

        # fusion
        if self.fusion_model is not None and audio_score is not None and motion_score is not None:
            try:
                Xf = np.asarray([[audio_score, motion_score]])
                fused = self._score_from_model(self.fusion_model, Xf)
                if fused is not None:
                    stress = float(fused)
                    flagged = stress > float(self.thresholds.get("fusion_flag", 0.85))
                    return {
                        "stress": float(stress),
                        "flagged": bool(flagged),
                        "risk_score": float(stress),
                        "model_used": "fusion",
                        "audio_score": float(audio_score),
                        "motion_score": float(motion_score)
                    }
            except Exception as e:
                print("fusion model error:", e)

        # fallback combine
        if audio_score is not None and motion_score is not None:
            stress = float(0.6 * audio_score + 0.4 * motion_score)
            model_used = "avg_audio_motion"
        elif audio_score is not None:
            stress = float(audio_score)
            model_used = "audio"
        elif motion_score is not None:
            stress = float(motion_score)
            model_used = "motion"
        else:
            stress = max(0.0, min(1.0, audio_db / 100.0))
            model_used = "heuristic"

        flagged = bool(stress > float(self.thresholds.get("default_flag", 0.85)))

        return {
            "stress": float(stress),
            "flagged": flagged,
            "risk_score": float(stress),
            "model_used": model_used,
            "audio_score": float(audio_score) if audio_score is not None else float(_safe_float(audio_db, 0.0)),
            "motion_score": float(motion_score) if motion_score is not None else 0.0
        }