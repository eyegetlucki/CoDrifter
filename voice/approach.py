"""
Position-based corner approach warnings.
Triggers a callout when the car enters the warning window before each corner.
Also exposes is_in_corner() so mistake detection can be suppressed on straights.
"""
import json
import os
from typing import Optional

CORNER_MAP_PATH = os.path.join("data", "corner_map.json")
TRACK_LENGTH_M = 783.413
WARNING_SECONDS = 2.0

MIN_WARNING_OFFSET = 0.025
MAX_WARNING_OFFSET = 0.075

# How far past the corner entry position to consider "in corner" (normalized units)
CORNER_ACTIVE_WINDOW = 0.02  # ~16m at track length 783m — entry and apex only

CALLOUTS: dict[str, list[str]] = {
    "TIGHT": [
        "Tight corner — get your angle early",
        "Sharp turn — initiate now",
        "Tight one coming — set the rear",
        "Get sideways early — it's tight",
    ],
    "MEDIUM": [
        "Medium corner — smooth entry",
        "Set your line — corner ahead",
        "Rotate and carry — medium turn",
        "Corner coming — control your angle",
    ],
    "SWEEPING": [
        "Sweeping turn — maintain your angle",
        "Long curve — stay committed",
        "Sweeper ahead — hold the drift",
        "Gradual turn — smooth throttle",
    ],
    "HAIRPIN": [
        "Hairpin — scrub speed and flick",
        "Sharp hairpin — get the rotation early",
        "Hairpin coming — slow in, drift out",
        "Tight hairpin — maximum rotation needed",
    ],
    "FEEDER": [
        "Slight turn — set up for the next corner",
        "Feeder corner — position yourself early",
        "Easy bend — get your line for what's next",
        "Light turn — feed into the next one",
    ],
}

_callout_index: dict[int, int] = {}


def _get_callout(corner_idx: int, corner_type: str) -> str:
    options = CALLOUTS.get(corner_type, CALLOUTS["MEDIUM"])
    idx = _callout_index.get(corner_idx, 0)
    text = options[idx % len(options)]
    _callout_index[corner_idx] = idx + 1
    return text


class CornerApproachDetector:
    def __init__(self):
        self._corners: list[dict] = []
        self._triggered: set[int] = set()
        self._loaded = False

    def load(self) -> bool:
        if not os.path.exists(CORNER_MAP_PATH):
            return False
        with open(CORNER_MAP_PATH) as f:
            self._corners = json.load(f)
        self._loaded = True
        print(f"Corner map loaded: {len(self._corners)} corners")
        return True

    def _warning_offset(self, speed_kmh: float) -> float:
        speed_ms = speed_kmh / 3.6
        offset = (speed_ms * WARNING_SECONDS) / TRACK_LENGTH_M
        return max(MIN_WARNING_OFFSET, min(MAX_WARNING_OFFSET, offset))

    def is_in_corner(self, normalized_pos: float) -> bool:
        if not self._loaded:
            return False
        for corner in self._corners:
            corner_pos = corner["position"]
            end_pos = (corner_pos + CORNER_ACTIVE_WINDOW) % 1.0
            if corner_pos < end_pos:
                if corner_pos <= normalized_pos < end_pos:
                    return True
            else:
                if normalized_pos >= corner_pos or normalized_pos < end_pos:
                    return True
        return False

    def check(self, normalized_pos: float, speed_kmh: float) -> Optional[str]:
        if not self._loaded or speed_kmh < 10:
            return None

        offset = self._warning_offset(speed_kmh)

        for i, corner in enumerate(self._corners):
            corner_pos = corner["position"]
            corner_type = corner.get("type", "MEDIUM")
            warning_start = (corner_pos - offset) % 1.0
            warning_end = corner_pos

            if warning_start < warning_end:
                in_window = warning_start <= normalized_pos < warning_end
            else:
                in_window = normalized_pos >= warning_start or normalized_pos < warning_end

            if in_window:
                if i not in self._triggered:
                    self._triggered.add(i)
                    return _get_callout(i, corner_type)
            else:
                self._triggered.discard(i)

        return None
