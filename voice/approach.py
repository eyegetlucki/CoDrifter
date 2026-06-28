"""
Position-based corner approach warnings.
Triggers a callout when the car enters the warning window before each corner.
Also exposes is_in_corner() so mistake detection can be suppressed on straights.
"""
import json
import os
from typing import Optional

CORNER_MAP_PATH      = os.path.join("data", "corner_map.json")
TRACK_MAPS_DIR       = os.path.join("data", "track_maps")
_DEFAULT_TRACK_LENGTH_M = 783.413  # Drift Playground 2021 fallback
WARNING_SECONDS = 2.0

MIN_WARNING_OFFSET = 0.025
MAX_WARNING_OFFSET = 0.075

# How far past the corner entry position to consider "in corner" (normalized units)
CORNER_ACTIVE_WINDOW = 0.02  # ~16m at track length 783m — entry and apex only

EXIT_CALLOUTS: dict[str, list[str]] = {
    "TIGHT": [
        "Good exit — drive it out",
        "Clear — open the throttle now",
        "Corner done — carry the angle",
    ],
    "MEDIUM": [
        "Exit — maintain your angle out",
        "Clear — smooth throttle out",
        "Drive it out — hold the drift",
    ],
    "HAIRPIN": [
        "Hairpin exit — unwind and drive",
        "Clear — straighten and push",
        "Out of the hairpin — build speed",
    ],
    "SWEEPING": [
        "Sweeper done — carry momentum",
        "Clear — stay committed through",
        "Exit — hold your line out",
    ],
    "FEEDER": [
        "Set up now — tight corner coming",
        "Position yourself — next corner ahead",
        "Feeder done — prepare your entry",
    ],
}

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
_exit_index: dict[int, int] = {}


def _get_callout(corner_idx: int, corner_type: str) -> str:
    options = CALLOUTS.get(corner_type, CALLOUTS["MEDIUM"])
    idx = _callout_index.get(corner_idx, 0)
    text = options[idx % len(options)]
    _callout_index[corner_idx] = idx + 1
    return text


def _get_exit_callout(corner_idx: int, corner_type: str) -> str:
    options = EXIT_CALLOUTS.get(corner_type, EXIT_CALLOUTS["MEDIUM"])
    idx = _exit_index.get(corner_idx, 0)
    text = options[idx % len(options)]
    _exit_index[corner_idx] = idx + 1
    return text


class CornerApproachDetector:
    def __init__(self):
        self._corners: list[dict] = []
        self._triggered: set[int] = set()
        self._exit_triggered: set[int] = set()
        self._loaded = False
        self._track_length_m: float = _DEFAULT_TRACK_LENGTH_M

    def set_track_length(self, meters: float):
        if meters and meters > 0:
            self._track_length_m = meters

    def load(self, track_slug: str = "") -> bool:
        """Load corner map. Tries active track slug first, falls back to legacy path."""
        path = None
        if track_slug:
            candidate = os.path.join(TRACK_MAPS_DIR, f"{track_slug}.json")
            if os.path.exists(candidate):
                path = candidate
        if path is None and os.path.exists(CORNER_MAP_PATH):
            path = CORNER_MAP_PATH

        if path is None:
            return False

        with open(path) as f:
            raw = json.load(f)

        # Support both array format and {name, corners} dict format
        if isinstance(raw, list):
            self._corners = raw
        else:
            self._corners = raw.get("corners", [])
            track_length = raw.get("track_length_m")
            if track_length and track_length > 0:
                self._track_length_m = float(track_length)

        self._loaded = True
        print(f"Corner map loaded: {len(self._corners)} corners from {path} "
              f"(track length: {self._track_length_m:.1f}m)")
        return True

    def _warning_offset(self, speed_kmh: float) -> float:
        speed_ms = speed_kmh / 3.6
        offset = (speed_ms * WARNING_SECONDS) / self._track_length_m
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

    def check_exit(self, normalized_pos: float, speed_kmh: float) -> Optional[str]:
        if not self._loaded or speed_kmh < 10:
            return None
        for i, corner in enumerate(self._corners):
            exit_pos = corner.get("exit_position")
            if exit_pos is None:
                continue
            corner_type = corner.get("type", "MEDIUM")
            window_start = exit_pos
            window_end = (exit_pos + 0.02) % 1.0
            if window_start < window_end:
                in_window = window_start <= normalized_pos < window_end
            else:
                in_window = normalized_pos >= window_start or normalized_pos < window_end
            if in_window:
                if i not in self._exit_triggered:
                    self._exit_triggered.add(i)
                    return _get_exit_callout(i, corner_type)
            else:
                self._exit_triggered.discard(i)
        return None

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
