import os
import pickle
from typing import Optional
from dataclasses import dataclass

from prediction.labels import INT_TO_CLASS

MODEL_PATH = os.path.join("models", "mistake_predictor.pkl")
CONFIDENCE_THRESHOLD = 0.9


@dataclass
class MistakePrediction:
    mistake_type: str
    confidence: float
    is_mistake: bool


class MistakePredictor:
    def __init__(self):
        self._model = None

    def load(self):
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"Model not found at {MODEL_PATH}. Run: python -m prediction.trainer"
            )
        with open(MODEL_PATH, "rb") as f:
            self._model = pickle.load(f)
        print(f"Model loaded from {MODEL_PATH}")

    def predict(self, feature_vector: list) -> Optional[MistakePrediction]:
        if self._model is None:
            return None

        proba = self._model.predict_proba([feature_vector])[0]
        class_idx = int(proba.argmax())
        confidence = float(proba[class_idx])
        mistake_type = INT_TO_CLASS[class_idx]

        return MistakePrediction(
            mistake_type=mistake_type,
            confidence=confidence,
            is_mistake=mistake_type != "CLEAN" and confidence >= CONFIDENCE_THRESHOLD,
        )
