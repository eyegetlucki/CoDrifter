"""
World-position-based corner approach warnings.
Uses X/Z coordinates from AC shared memory — no AI spline required.
Triggers a callout when the car enters the warning bubble before each corner.
Also exposes is_in_corner() so mistake detection can be suppressed on straights.
"""
import json
import math
import os
from typing import Optional

CORNER_MAP_PATH  = os.path.join("data", "corner_map.json")
TRACK_MAPS_DIR   = os.path.join("data", "track_maps")

WARNING_SECONDS      = 2.0   # seconds of warning before corner entry
MIN_WARN_DIST_M      = 20.0  # minimum warning distance in meters
MAX_WARN_DIST_M      = 60.0  # maximum warning distance in meters

CORNER_ACTIVE_RADIUS_M = 25.0  # "in corner" within this radius of entry point
CORNER_EXIT_RADIUS_M   = 12.0  # exit callout fires within this radius of exit point
EXIT_YAW_THRESHOLD     = 15.0  # deg/s — suppress exit callout if not drifting


def _dist(x1: float, z1: float, x2: float, z2: float) -> float:
    return math.sqrt((x1 - x2) ** 2 + (z1 - z2) ** 2)


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

        corners = raw if isinstance(raw, list) else raw.get("corners", [])

        # Only keep corners that have world position data
        self._corners = [c for c in corners if "x" in c and "z" in c]
        self._loaded = bool(self._corners)

        total = len(corners)
        usable = len(self._corners)
        skipped = total - usable
        note = f" ({skipped} skipped — no x/z data)" if skipped else ""
        print(f"Corner map loaded: {usable} corners from {path}{note}")
        return self._loaded

    def _warn_dist(self, speed_kmh: float) -> float:
        speed_ms = speed_kmh / 3.6
        return max(MIN_WARN_DIST_M, min(MAX_WARN_DIST_M, speed_ms * WARNING_SECONDS))

    def is_in_corner(self, x: float, z: float) -> bool:
        if not self._loaded:
            return False
        for corner in self._corners:
            if _dist(x, z, corner["x"], corner["z"]) <= CORNER_ACTIVE_RADIUS_M:
                return True
        return False

    def check_exit(self, x: float, z: float, speed_kmh: float, yaw_rate: float = 0.0) -> Optional[str]:
        if not self._loaded or speed_kmh < 10:
            return None
        if abs(yaw_rate) < EXIT_YAW_THRESHOLD:
            return None
        for i, corner in enumerate(self._corners):
            ex = corner.get("exit_x")
            ez = corner.get("exit_z")
            if ex is None or ez is None:
                continue
            corner_type = corner.get("type", "MEDIUM")
            in_window = _dist(x, z, ex, ez) <= CORNER_EXIT_RADIUS_M
            if in_window:
                if i not in self._exit_triggered:
                    self._exit_triggered.add(i)
                    return _get_exit_callout(i, corner_type)
            else:
                self._exit_triggered.discard(i)
        return None

    def check(self, x: float, z: float, speed_kmh: float) -> Optional[str]:
        if not self._loaded or speed_kmh < 10:
            return None

        warn_dist = self._warn_dist(speed_kmh)

        for i, corner in enumerate(self._corners):
            corner_type = corner.get("type", "MEDIUM")
            dist = _dist(x, z, corner["x"], corner["z"])
            in_window = dist <= warn_dist

            if in_window:
                if i not in self._triggered:
                    self._triggered.add(i)
                    return _get_callout(i, corner_type)
            else:
                self._triggered.discard(i)

        return None
