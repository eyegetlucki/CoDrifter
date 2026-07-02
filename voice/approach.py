"""
World-position-based corner approach warnings.
Uses X/Z coordinates from AC shared memory — no AI spline required.
Triggers a callout when the car enters the warning bubble before each corner.
Context-aware: reads speed and yaw_rate at entry to diagnose the approach.
Learned per-corner approach speeds are persisted per track across sessions.
"""
import json
import math
import os
import random
from collections import deque
from typing import Optional

CORNER_MAP_PATH  = os.path.join("data", "corner_map.json")
TRACK_MAPS_DIR   = os.path.join("data", "track_maps")
TRACK_LEARNING_DIR = os.path.join("data", "track_learning")

WARNING_SECONDS      = 2.0   # seconds of warning before corner entry
MIN_WARN_DIST_M      = 20.0  # minimum warning distance in meters
MAX_WARN_DIST_M      = 60.0  # maximum warning distance in meters

CORNER_ACTIVE_RADIUS_M = 25.0  # "in corner" within this radius of entry point
CORNER_EXIT_RADIUS_M   = 12.0  # exit callout fires within this radius of exit point
EXIT_YAW_THRESHOLD     = 0.4   # rad/s — suppress exit callout if not actually drifting
                               # (yaw_rate from AC is rad/s: drift p50~0.65, straight~0)
REARM_MARGIN           = 1.4   # must travel 40% past the trigger boundary before it re-arms
                               # (prevents re-fires when the car wobbles across the edge)

# Context-aware approach thresholds
YAW_INITIATED_THRESHOLD = 0.4    # rad/s — below this = car still pointed forward / not rotating
HOT_MULTIPLIER          = 1.2    # 20% above personal average = hot entry
MIN_PASSES_FOR_SPEED_CTX = 3     # passes needed before speed context activates
MAX_SPEED_HISTORY       = 20     # max passes stored per corner


def _dist(x1: float, z1: float, x2: float, z2: float) -> float:
    return math.sqrt((x1 - x2) ** 2 + (z1 - z2) ** 2)


# Exit callouts are corrective-only and framed toward linking the NEXT corner.
# Keyed by mistake type; {next} is filled with the upcoming corner number.
EXIT_MISTAKE_CALLOUTS: dict[str, list[str]] = {
    "dropped": [
        "You dropped it — you'll be late linking into corner {next}",
        "Lost the angle on exit — reset for corner {next}",
        "Straightened too early — that breaks the link",
        "Angle died on exit — stay committed into corner {next}",
    ],
    "snap": [
        "Overcooked the exit — you'll miss the link into corner {next}",
        "Nearly spun it — regroup for corner {next}",
        "Too much on exit — that kills your flow",
        "Snapped on exit — settle it before corner {next}",
    ],
    "bog": [
        "Bogged it — carry more speed to link corner {next}",
        "Killed your momentum — slow into corner {next}",
        "Too much scrub on exit — drive it out",
        "Lost drive on exit — keep it lit into corner {next}",
    ],
}


def is_manji(yaw_window, amp: float = 0.5, min_reversals: int = 2) -> bool:
    """True if the yaw trace swayed both directions (manji / transition) — an intentional
    technique, not a mistake. Mistakes are one-directional; manji reverses sign repeatedly."""
    signs = [1 if v > amp else (-1 if v < -amp else 0) for v in yaw_window]
    signs = [s for s in signs if s != 0]
    reversals = sum(1 for a, b in zip(signs, signs[1:]) if a != b)
    return reversals >= min_reversals

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

# Context-aware approach callouts — only spoken when the driver is too hot.
CONTEXT_CALLOUTS = {
    "hot_no_angle": [
        "Too fast and too straight — brake and initiate",
        "Way too hot and upright — scrub speed and get sideways",
        "Hot and not rotating — brake now, then flick",
    ],
    "hot_has_angle": [
        "Hot into this one — scrub a bit more speed",
        "Good angle but too fast — ease off slightly",
        "You're sideways but carrying too much — back off a touch",
    ],
}


CLIP_MISS_CALLOUTS = [
    "Too wide — you missed the clip",
    "Wide of the clip — tighten up",
    "Missed it — get closer to the clip",
]


class CornerApproachDetector:
    def __init__(self):
        self._corners: list[dict] = []
        self._clip_zones: list[dict] = []
        self._triggered: set[int] = set()
        self._exit_triggered: set[int] = set()
        self._zone_active: set[int] = set()
        self._clip_hit: set[int] = set()
        self._approach_speeds: dict[int, list[float]] = {}  # corner_idx -> [speed, ...]
        self._recent: deque[str] = deque(maxlen=3)  # anti-repeat: no line repeats within 3 callouts
        self._exit_flags: deque = deque(maxlen=60)  # rolling ~1s of exit mistake flags
        self._exit_yaw: deque = deque(maxlen=60)    # rolling ~1s of yaw for manji detection
        self._track_slug: str = ""
        self._loaded = False

    def _pick(self, options: list[str]) -> str:
        """Random choice that avoids repeating any of the last 3 spoken lines."""
        fresh = [o for o in options if o not in self._recent]
        choice = random.choice(fresh) if fresh else random.choice(options)
        self._recent.append(choice)
        return choice

    def load(self, track_slug: str = "") -> bool:
        self._track_slug = track_slug
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
        self._clip_zones = raw.get("clip_zones", []) if isinstance(raw, dict) else []
        self._corners = [c for c in corners if "x" in c and "z" in c]
        self._loaded = bool(self._corners) or bool(self._clip_zones)

        total = len(corners)
        usable = len(self._corners)
        skipped = total - usable
        note = f" ({skipped} skipped — no x/z data)" if skipped else ""
        print(f"Corner map loaded: {usable} corners from {path}{note}")

        self._load_learning(track_slug)
        return self._loaded

    def _load_learning(self, track_slug: str):
        if not track_slug:
            return
        path = os.path.join(TRACK_LEARNING_DIR, f"{track_slug}.json")
        if not os.path.exists(path):
            return
        try:
            with open(path) as f:
                data = json.load(f)
            raw_speeds = data.get("corner_approach_speeds", {})
            self._approach_speeds = {int(k): v for k, v in raw_speeds.items()}
            print(f"Track learning loaded: {len(self._approach_speeds)} corners from {path}")
        except Exception as e:
            print(f"[approach] Could not load track learning: {e}")

    def save_learning(self, track_slug: str = ""):
        slug = track_slug or self._track_slug
        if not slug or not self._approach_speeds:
            return
        os.makedirs(TRACK_LEARNING_DIR, exist_ok=True)
        path = os.path.join(TRACK_LEARNING_DIR, f"{slug}.json")
        data = {"corner_approach_speeds": {str(k): v for k, v in self._approach_speeds.items()}}
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            print(f"Track learning saved: {path}")
        except Exception as e:
            print(f"[approach] Could not save track learning: {e}")

    def _warn_dist(self, speed_kmh: float) -> float:
        speed_ms = speed_kmh / 3.6
        return max(MIN_WARN_DIST_M, min(MAX_WARN_DIST_M, speed_ms * WARNING_SECONDS))

    def _avg_approach_speed(self, corner_idx: int) -> Optional[float]:
        history = self._approach_speeds.get(corner_idx, [])
        if len(history) < MIN_PASSES_FOR_SPEED_CTX:
            return None
        return sum(history) / len(history)

    def _record_approach_speed(self, corner_idx: int, speed_kmh: float):
        history = self._approach_speeds.setdefault(corner_idx, [])
        history.append(speed_kmh)
        if len(history) > MAX_SPEED_HISTORY:
            self._approach_speeds[corner_idx] = history[-MAX_SPEED_HISTORY:]

    def _context_callout(self, corner_idx: int, corner_type: str, speed_kmh: float, yaw_rate: float) -> str:
        # Only override the standard callout when the driver is genuinely hot vs their
        # own learned average for this corner. Being straight on approach is normal, so
        # there's no "you should be rotating" nag — the type callouts carry that coaching.
        avg = self._avg_approach_speed(corner_idx)
        if avg is not None and speed_kmh > avg * HOT_MULTIPLIER:
            if abs(yaw_rate) >= YAW_INITIATED_THRESHOLD:
                return self._pick(CONTEXT_CALLOUTS["hot_has_angle"])   # hot but already rotating
            return self._pick(CONTEXT_CALLOUTS["hot_no_angle"])        # hot and still straight

        # Normal approach — standard corner-type callout
        return self._pick(CALLOUTS.get(corner_type, CALLOUTS["MEDIUM"]))

    def is_in_corner(self, x: float, z: float) -> bool:
        if not self._loaded:
            return False
        for corner in self._corners:
            if _dist(x, z, corner["x"], corner["z"]) <= CORNER_ACTIVE_RADIUS_M:
                return True
        return False

    # Which mistake wins if several flagged during the exit window (most urgent first).
    _EXIT_PRIORITY = [("SNAP_RISK", "snap"), ("LOSING_ANGLE", "dropped"), ("SPEED_LOSS", "bog")]

    def check_exit(self, x: float, z: float, speed_kmh: float, yaw_rate: float = 0.0,
                   mistake_flag: Optional[str] = None) -> Optional[str]:
        if not self._loaded or speed_kmh < 10:
            return None

        # Accumulate the rolling drift-phase history every frame.
        self._exit_flags.append(mistake_flag)
        self._exit_yaw.append(yaw_rate)

        for i, corner in enumerate(self._corners):
            ex = corner.get("exit_x")
            ez = corner.get("exit_z")
            if ex is None or ez is None:
                continue
            dist = _dist(x, z, ex, ez)
            if dist <= CORNER_EXIT_RADIUS_M:
                if i not in self._exit_triggered:
                    self._exit_triggered.add(i)
                    return self._exit_mistake_callout(i)
            elif dist > CORNER_EXIT_RADIUS_M * REARM_MARGIN:
                self._exit_triggered.discard(i)
        return None

    def _exit_mistake_callout(self, corner_idx: int) -> Optional[str]:
        # Manji / drifting the straight to transition is intentional — never a mistake.
        if is_manji(self._exit_yaw):
            return None
        flags = set(f for f in self._exit_flags if f)
        for label, key in self._EXIT_PRIORITY:
            if label in flags:
                next_num = (corner_idx + 1) % len(self._corners) + 1
                return self._pick(EXIT_MISTAKE_CALLOUTS[key]).format(next=next_num)
        return None  # clean exit — stay silent

    def check_clips(self, x: float, z: float, speed_kmh: float, yaw_rate: float = 0.0) -> Optional[str]:
        if not self._clip_zones or speed_kmh < 10:
            return None
        for i, zone in enumerate(self._clip_zones):
            ex = zone.get("zone_entry_x")
            ez = zone.get("zone_entry_z")
            xx = zone.get("zone_exit_x")
            xz = zone.get("zone_exit_z")
            cx = zone.get("clip_x")
            cz = zone.get("clip_z")
            radius = zone.get("clip_radius_m", 3.0)
            if ex is None or xx is None or cx is None:
                continue

            entry_dist = _dist(x, z, ex, ez)
            exit_dist  = _dist(x, z, xx, xz)

            if entry_dist < 20.0 and i not in self._zone_active:
                self._zone_active.add(i)
                self._clip_hit.discard(i)

            if i in self._zone_active and _dist(x, z, cx, cz) <= radius:
                self._clip_hit.add(i)

            if i in self._zone_active and exit_dist < 15.0:
                self._zone_active.discard(i)
                if i not in self._clip_hit and abs(yaw_rate) >= EXIT_YAW_THRESHOLD:
                    return self._pick(CLIP_MISS_CALLOUTS)

        return None

    def check(self, x: float, z: float, speed_kmh: float, yaw_rate: float = 0.0) -> Optional[str]:
        if not self._loaded or speed_kmh < 10:
            return None

        warn_dist = self._warn_dist(speed_kmh)

        for i, corner in enumerate(self._corners):
            corner_type = corner.get("type", "MEDIUM")
            dist = _dist(x, z, corner["x"], corner["z"])

            if dist <= warn_dist:
                if i not in self._triggered:
                    self._triggered.add(i)
                    self._record_approach_speed(i, speed_kmh)
                    return self._context_callout(i, corner_type, speed_kmh, yaw_rate)
            elif dist > warn_dist * REARM_MARGIN:
                self._triggered.discard(i)

        return None
