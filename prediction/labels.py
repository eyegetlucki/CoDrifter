import json
import math
import os
from typing import Optional
import numpy as np
import pandas as pd

MISTAKE_CLASSES = ["CLEAN", "LOSING_ANGLE", "SPEED_LOSS", "SNAP_RISK"]
CLASS_TO_INT = {c: i for i, c in enumerate(MISTAKE_CLASSES)}
INT_TO_CLASS = {i: c for i, c in enumerate(MISTAKE_CLASSES)}

CORNER_MAP_PATH    = os.path.join("data", "corner_map.json")
TRACK_MAPS_DIR     = os.path.join("data", "track_maps")
TRACK_LEARNING_DIR = os.path.join("data", "track_learning")
CORNER_ACTIVE_RADIUS_M  = 25.0   # matches approach.py
HOT_ENTRY_RADIUS_M      = 37.5   # 1.5x CORNER_ACTIVE_RADIUS_M — approach zone
HOT_MULTIPLIER          = 1.15   # matches approach.py

# LOSING_ANGLE — |yaw| shrinking while in corner (car straightening unintentionally).
# Direction-aware: (yaw * yaw_delta) < 0 means the rotation magnitude is decreasing,
# regardless of which way the car is drifting. Calibrated from 200k Klutch frames —
# real in-corner yaw acceleration peaks ~0.09/frame, so the old -0.3 threshold was dead.
LOSING_ANGLE_YAW_ACCEL = 0.06     # |yaw_delta| per frame — shrinking fast enough to be unintentional
LOSING_ANGLE_MIN_YAW = 0.4        # must have been rotating meaningfully (raised from 0.15)
LOSING_ANGLE_THROTTLE_MAX = 0.5   # not on full throttle (that's intentional lift)
LOSING_ANGLE_MIN_SPEED = 15.0

# SPEED_LOSS — significant deceleration with rear wheels not slipping (not a power slide)
SPEED_LOSS_DELTA = -8.0            # km/h over 0.5s window
SPEED_LOSS_MAX_REAR_SLIP = 5.0    # rear slip low = not a controlled drift deceleration
SPEED_LOSS_THROTTLE_MAX = 0.35    # not on throttle
SPEED_LOSS_MIN_SPEED = 20.0

# SNAP_RISK — rotation accelerating in the direction it's already turning = losing it.
# A controlled drift HOLDS a high yaw rate steadily; a snap has |yaw| growing fast.
# The same-sign (growing) gate is what separates a real snap from an aggressive-but-held slide.
# Calibrated from 200k Klutch frames: drifting abs_yaw p90=1.41, so MIN_ABS_YAW=1.2 only
# fires when rotation is already near the high end. Old 0.45 sat below the median (0.74).
SNAP_RISK_YAW_STD     = 0.40      # erratic yaw (p90 of drifting is 0.35)
SNAP_RISK_MIN_LATERAL = 3.0       # actually sideways
SNAP_RISK_MIN_SPEED   = 20.0
SNAP_RISK_MIN_ABS_YAW = 1.2       # rad/s — rotation already near the high end of drifting
SNAP_RISK_YAW_ACCEL   = 0.07      # rad/s per frame — rotation diverging fast, not being held


def _load_corner_learning() -> dict[int, float]:
    """Load per-corner average approach speeds from the most recent track learning file."""
    if not os.path.isdir(TRACK_LEARNING_DIR):
        return {}
    result: dict[int, float] = {}
    for fname in os.listdir(TRACK_LEARNING_DIR):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(TRACK_LEARNING_DIR, fname)
        try:
            with open(path) as f:
                data = json.load(f)
            for k, speeds in data.get("corner_approach_speeds", {}).items():
                if len(speeds) >= 3:
                    result[int(k)] = sum(speeds) / len(speeds)
        except Exception:
            pass
    return result


def _is_real_corner(c: dict) -> bool:
    """A corner needs real world coords. (0,0) is legacy garbage from the
    normalized-position era — those maps were never remapped to world X/Z."""
    if "x" not in c or "z" not in c:
        return False
    return not (abs(c["x"]) < 0.01 and abs(c["z"]) < 0.01)


def _load_corner_xz() -> list[tuple[float, float]]:
    """Load corner X/Z positions from the active track map or legacy corner map."""
    # Try track maps dir first (newest format)
    if os.path.isdir(TRACK_MAPS_DIR):
        for fname in sorted(os.listdir(TRACK_MAPS_DIR)):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(TRACK_MAPS_DIR, fname)
            with open(path) as f:
                raw = json.load(f)
            corners = raw.get("corners", []) if isinstance(raw, dict) else raw
            xz = [(c["x"], c["z"]) for c in corners if _is_real_corner(c)]
            if xz:
                return xz
    # Fall back to legacy corner_map.json
    if os.path.exists(CORNER_MAP_PATH):
        with open(CORNER_MAP_PATH) as f:
            data = json.load(f)
        if isinstance(data, list):
            return [(c["x"], c["z"]) for c in data if _is_real_corner(c)]
    return []


def _in_corner(x: float, z: float, corners: list[tuple[float, float]]) -> bool:
    for cx, cz in corners:
        if math.sqrt((x - cx) ** 2 + (z - cz) ** 2) <= CORNER_ACTIVE_RADIUS_M:
            return True
    return False


def classify_drift_mistake(
    yaw_rate: float,
    yaw_rate_delta: float,
    yaw_rate_mean: float,
    yaw_rate_std: float,
    lateral_speed: float,
    speed: float,
    throttle: float,
    speed_delta: float,
    rear_slip_mean: float,
) -> Optional[str]:
    """Calibrated drift-mistake rules with NO in-corner gate. Single source of truth
    shared by label_frame (which adds the in-corner gate) and the exit/transition detector."""
    # SNAP_RISK — rotation accelerating in the same direction it's already going.
    # yaw_rate * yaw_rate_delta > 0 means |yaw| is GROWING (same sign) — rotating harder,
    # not being caught. Distinguishes a real snap from a controlled high-but-held drift.
    if (abs(yaw_rate) > SNAP_RISK_MIN_ABS_YAW
            and abs(yaw_rate_delta) > SNAP_RISK_YAW_ACCEL
            and (yaw_rate * yaw_rate_delta) > 0
            and yaw_rate_std > SNAP_RISK_YAW_STD
            and lateral_speed > SNAP_RISK_MIN_LATERAL
            and speed > SNAP_RISK_MIN_SPEED):
        return "SNAP_RISK"

    # LOSING_ANGLE — |yaw| shrinking (either drift direction), car straightening unintentionally.
    if ((yaw_rate * yaw_rate_delta) < 0
            and abs(yaw_rate_delta) > LOSING_ANGLE_YAW_ACCEL
            and abs(yaw_rate_mean) > LOSING_ANGLE_MIN_YAW
            and throttle < LOSING_ANGLE_THROTTLE_MAX
            and speed > LOSING_ANGLE_MIN_SPEED):
        return "LOSING_ANGLE"

    # SPEED_LOSS — bleeding speed without rear slip (not a drift, something wrong)
    if (speed_delta < SPEED_LOSS_DELTA
            and rear_slip_mean < SPEED_LOSS_MAX_REAR_SLIP
            and throttle < SPEED_LOSS_THROTTLE_MAX
            and speed > SPEED_LOSS_MIN_SPEED):
        return "SPEED_LOSS"

    return None


def label_frame(
    speed: float,
    throttle: float,
    lateral_speed: float,
    yaw_rate: float,
    yaw_rate_mean: float,
    yaw_rate_std: float,
    yaw_rate_delta: float,
    speed_delta: float,
    rear_slip_mean: float,
    world_x: float,
    world_z: float,
    is_in_pit: bool,
    is_engine_running: bool,
    corner_xz: list[tuple[float, float]],
    hot_entry: bool = False,
) -> str:
    if is_in_pit or not is_engine_running or speed < 5.0:
        return "CLEAN"

    mistake = classify_drift_mistake(
        yaw_rate, yaw_rate_delta, yaw_rate_mean, yaw_rate_std,
        lateral_speed, speed, throttle, speed_delta, rear_slip_mean,
    )
    # SNAP_RISK applies anywhere; LOSING_ANGLE / SPEED_LOSS only count inside a corner.
    if mistake == "SNAP_RISK":
        return "SNAP_RISK"
    if mistake in ("LOSING_ANGLE", "SPEED_LOSS") and _in_corner(world_x, world_z, corner_xz):
        return mistake

    return "CLEAN"


def _compute_hot_entry(world_x: float, world_z: float, speed: float,
                        corner_xz: list[tuple[float, float]],
                        corner_avgs: dict[int, float]) -> bool:
    """True if the car is in the approach zone of a corner and moving faster than personal average."""
    for idx, (cx, cz) in enumerate(corner_xz):
        d = math.sqrt((world_x - cx) ** 2 + (world_z - cz) ** 2)
        if d <= HOT_ENTRY_RADIUS_M and d > CORNER_ACTIVE_RADIUS_M:
            avg = corner_avgs.get(idx)
            if avg is not None and speed > avg * HOT_MULTIPLIER:
                return True
    return False


def label_dataframe(df: pd.DataFrame, features_df: pd.DataFrame) -> pd.Series:
    corner_xz = _load_corner_xz()
    if not corner_xz:
        print("  Warning: no corner X/Z data found — LOSING_ANGLE and SPEED_LOSS will not be labeled")

    corner_avgs = _load_corner_learning()
    if corner_avgs:
        print(f"  Track learning loaded: {len(corner_avgs)} corner speed averages")

    labels = []
    feat_rows = features_df.reset_index(drop=True)
    raw_rows = df.tail(len(features_df)).reset_index(drop=True)

    yaw_series = feat_rows["yaw_rate"]
    yaw_delta = yaw_series.diff().fillna(0)

    for i in range(len(feat_rows)):
        fr = feat_rows.iloc[i]
        rr = raw_rows.iloc[i]
        wx = float(rr.get("world_position_x", 0.0))
        wz = float(rr.get("world_position_z", 0.0))
        hot_entry = _compute_hot_entry(wx, wz, fr["speed_kmh"], corner_xz, corner_avgs)
        label = label_frame(
            speed=fr["speed_kmh"],
            throttle=fr["throttle"],
            lateral_speed=fr["lateral_speed"],
            yaw_rate=fr["yaw_rate"],
            yaw_rate_mean=fr["yaw_rate_mean"],
            yaw_rate_std=fr["yaw_rate_std"],
            yaw_rate_delta=yaw_delta.iloc[i],
            speed_delta=fr["speed_delta"],
            rear_slip_mean=fr["rear_slip_mean"],
            world_x=wx,
            world_z=wz,
            is_in_pit=bool(rr["is_in_pit"]),
            is_engine_running=bool(rr["is_engine_running"]),
            corner_xz=corner_xz,
            hot_entry=hot_entry,
        )
        labels.append(CLASS_TO_INT[label])

    return pd.Series(labels, name="label")
