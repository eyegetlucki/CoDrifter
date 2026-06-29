import os
import pickle
from collections import deque
from typing import Optional
from dataclasses import dataclass

from prediction.labels import INT_TO_CLASS

MODEL_PATH = os.path.join("models", "mistake_predictor.pkl")
CONFIDENCE_THRESHOLD = 0.9
HYSTERESIS_FRAMES = 4   # consecutive frames required before firing a callout
SPEED_GATE_KMH = 25.0   # suppress predictions below this speed


@dataclass
class MistakePrediction:

    mistake_type: str
    confidence: float
    is_mistake: bool


class MistakePredictor:
    def __init__(self, confidence_threshold: float = CONFIDENCE_THRESHOLD):
        self._model = None
        self._class_names: list[str] = []
        self._threshold = confidence_threshold
        self._history: deque[str] = deque(maxlen=HYSTERESIS_FRAMES)

    def set_threshold(self, value: float):
        self._threshold = value

    def load(self):
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"Model not found at {MODEL_PATH}. Run: python -m prediction.trainer"
            )
        with open(MODEL_PATH, "rb") as f:
            payload = pickle.load(f)
        if isinstance(payload, dict):
            self._model = payload["model"]
            self._class_names: list[str] = payload["class_names"]
        else:
            # Legacy pickle — raw model, assume full MISTAKE_CLASSES order
            self._model = payload
            self._class_names = list(INT_TO_CLASS[i] for i in range(len(INT_TO_CLASS)))
        print(f"Model loaded from {MODEL_PATH} (classes: {self._class_names})")

    def predict(self, feature_vector: list, speed_kmh: float = 0.0) -> Optional[MistakePrediction]:
        if self._model is None:
            return None

        if speed_kmh < SPEED_GATE_KMH:
            self._history.clear()
            return MistakePrediction(mistake_type="CLEAN", confidence=0.0, is_mistake=False)

        proba = self._model.predict_proba([feature_vector])[0]
        class_idx = int(proba.argmax())
        confidence = float(proba[class_idx])
        mistake_type = self._class_names[class_idx] if self._class_names else INT_TO_CLASS.get(class_idx, "CLEAN")

        if mistake_type == "CLEAN" or confidence < self._threshold:
            self._history.clear()
            return MistakePrediction(
                mistake_type=mistake_type,
                confidence=confidence,
                is_mistake=False,
            )

        self._history.append(mistake_type)

        # Only fire if the same mistake class fills the entire history window
        confirmed = (
            len(self._history) == HYSTERESIS_FRAMES
            and len(set(self._history)) == 1
        )

        return MistakePrediction(
            mistake_type=mistake_type,
            confidence=confidence,
            is_mistake=confirmed,
        )
