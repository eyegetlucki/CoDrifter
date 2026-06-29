import json
import math
import os
import numpy as np
import pandas as pd

MISTAKE_CLASSES = ["CLEAN", "LOSING_ANGLE", "SPEED_LOSS", "SNAP_RISK"]
CLASS_TO_INT = {c: i for i, c in enumerate(MISTAKE_CLASSES)}
INT_TO_CLASS = {i: c for i, c in enumerate(MISTAKE_CLASSES)}

CORNER_MAP_PATH  = os.path.join("data", "corner_map.json")
TRACK_MAPS_DIR   = os.path.join("data", "track_maps")
CORNER_ACTIVE_RADIUS_M = 25.0  # matches approach.py

# LOSING_ANGLE — yaw rate dropping while in corner (car straightening unintentionally)
LOSING_ANGLE_YAW_DROP = -0.3      # yaw rate delta over window (rad/s per 0.5s)
LOSING_ANGLE_MIN_YAW = 0.15       # must have been rotating meaningfully
LOSING_ANGLE_THROTTLE_MAX = 0.5   # not on full throttle (that's intentional lift)
LOSING_ANGLE_MIN_SPEED = 15.0

# SPEED_LOSS — significant deceleration with rear wheels not slipping (not a power slide)
SPEED_LOSS_DELTA = -8.0            # km/h over 0.5s window
SPEED_LOSS_MAX_REAR_SLIP = 5.0    # rear slip low = not a controlled drift deceleration
SPEED_LOSS_THROTTLE_MAX = 0.35    # not on throttle
SPEED_LOSS_MIN_SPEED = 20.0

# SNAP_RISK — sudden high yaw rate spike with erratic steering corrections
SNAP_RISK_YAW_STD = 0.25          # erratic yaw = about to spin
SNAP_RISK_MIN_LATERAL = 3.0       # actually sideways
SNAP_RISK_MIN_SPEED = 20.0


def _load_corner_xz() -> list[tuple[float, float]]:
    """Load corner X/Z positions from the active track map or legacy corner map."""
    # Try track maps dir first (newest format)
    if os.path.isdir(TRACK_MAPS_DIR):
        for fname in os.listdir(TRACK_MAPS_DIR):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(TRACK_MAPS_DIR, fname)
            with open(path) as f:
                raw = json.load(f)
            corners = raw.get("corners", []) if isinstance(raw, dict) else raw
            xz = [(c["x"], c["z"]) for c in corners if "x" in c and "z" in c]
            if xz:
                return xz
    # Fall back to legacy corner_map.json
    if os.path.exists(CORNER_MAP_PATH):
        with open(CORNER_MAP_PATH) as f:
            data = json.load(f)
        if isinstance(data, list):
            return [(c["x"], c["z"]) for c in data if "x" in c and "z" in c]
    return []


def _in_corner(x: float, z: float, corners: list[tuple[float, float]]) -> bool:
    for cx, cz in corners:
        if math.sqrt((x - cx) ** 2 + (z - cz) ** 2) <= CORNER_ACTIVE_RADIUS_M:
            return True
    return False


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
) -> str:
    if is_in_pit or not is_engine_running or speed < 5.0:
        return "CLEAN"

    in_corner = _in_corner(world_x, world_z, corner_xz)

    # SNAP_RISK — erratic yaw while sideways at speed (anywhere, not just corners)
    if (yaw_rate_std > SNAP_RISK_YAW_STD
            and lateral_speed > SNAP_RISK_MIN_LATERAL
            and speed > SNAP_RISK_MIN_SPEED):
        return "SNAP_RISK"

    if in_corner:
        # LOSING_ANGLE — yaw rate decaying, car straightening unintentionally
        if (yaw_rate_delta < LOSING_ANGLE_YAW_DROP
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

    return "CLEAN"


def label_dataframe(df: pd.DataFrame, features_df: pd.DataFrame) -> pd.Series:
    corner_xz = _load_corner_xz()
    if not corner_xz:
        print("  Warning: no corner X/Z data found — LOSING_ANGLE and SPEED_LOSS will not be labeled")

    labels = []
    feat_rows = features_df.reset_index(drop=True)
    raw_rows = df.tail(len(features_df)).reset_index(drop=True)

    yaw_series = feat_rows["yaw_rate"]
    yaw_delta = yaw_series.diff().fillna(0)

    for i in range(len(feat_rows)):
        fr = feat_rows.iloc[i]
        rr = raw_rows.iloc[i]
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
            world_x=float(rr.get("world_position_x", 0.0)),
            world_z=float(rr.get("world_position_z", 0.0)),
            is_in_pit=bool(rr["is_in_pit"]),
            is_engine_running=bool(rr["is_engine_running"]),
            corner_xz=corner_xz,
        )
        labels.append(CLASS_TO_INT[label])

    return pd.Series(labels, name="label")
