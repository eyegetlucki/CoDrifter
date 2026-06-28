import json
import os
import numpy as np
import pandas as pd

MISTAKE_CLASSES = ["CLEAN", "LOSING_ANGLE", "SPEED_LOSS", "SNAP_RISK"]
CLASS_TO_INT = {c: i for i, c in enumerate(MISTAKE_CLASSES)}
INT_TO_CLASS = {i: c for i, c in enumerate(MISTAKE_CLASSES)}

CORNER_MAP_PATH = os.path.join("data", "corner_map.json")
CORNER_ACTIVE_WINDOW = 0.02  # normalized position units past corner entry

# Thresholds
LOSING_ANGLE_THROTTLE = 0.3       # lifting off (throttle below this)
LOSING_ANGLE_STEERING = 0.3       # while steering is loaded
LOSING_ANGLE_MIN_SPEED = 20.0     # at meaningful speed

SPEED_LOSS_DELTA = -0.5           # km/h per frame (at 60hz = -30 km/h/s)
SPEED_LOSS_MIN_SPEED = 20.0

SNAP_RISK_STEERING_STD = 0.2      # erratic steering corrections
SNAP_RISK_MIN_SPEED = 20.0


def _load_corner_positions() -> list[float]:
    if not os.path.exists(CORNER_MAP_PATH):
        return []
    with open(CORNER_MAP_PATH) as f:
        data = json.load(f)
    return [c["position"] for c in data]


def _in_corner(pos: float, corner_positions: list[float]) -> bool:
    for cp in corner_positions:
        end = (cp + CORNER_ACTIVE_WINDOW) % 1.0
        if cp < end:
            if cp <= pos < end:
                return True
        else:
            if pos >= cp or pos < end:
                return True
    return False


def label_frame(
    speed: float,
    throttle: float,
    steering: float,
    speed_delta: float,
    steering_std: float,
    normalized_pos: float,
    is_in_pit: bool,
    is_engine_running: bool,
    corner_positions: list[float],
) -> str:
    if is_in_pit or not is_engine_running or speed < 5.0:
        return "CLEAN"

    in_corner = _in_corner(normalized_pos, corner_positions)
    abs_steer = abs(steering)

    # SPEED_LOSS — rapid deceleration while not on throttle
    if (speed_delta < SPEED_LOSS_DELTA
            and speed > SPEED_LOSS_MIN_SPEED
            and throttle < 0.4):
        return "SPEED_LOSS"

    # Corner-only mistakes
    if in_corner:
        # LOSING_ANGLE — lifting throttle while steering loaded
        if (throttle < LOSING_ANGLE_THROTTLE
                and abs_steer > LOSING_ANGLE_STEERING
                and speed > LOSING_ANGLE_MIN_SPEED):
            return "LOSING_ANGLE"

        # SNAP_RISK — erratic steering at speed
        if steering_std > SNAP_RISK_STEERING_STD and speed > SNAP_RISK_MIN_SPEED:
            return "SNAP_RISK"

    return "CLEAN"


def label_dataframe(df: pd.DataFrame, features_df: pd.DataFrame) -> pd.Series:
    corner_positions = _load_corner_positions()
    labels = []
    feat_rows = features_df.reset_index(drop=True)
    raw_rows = df.tail(len(features_df)).reset_index(drop=True)

    # Compute per-frame speed delta on the raw df
    speed_series = raw_rows["speed_kmh"]
    speed_delta = speed_series.diff().fillna(0)

    for i in range(len(feat_rows)):
        fr = feat_rows.iloc[i]
        rr = raw_rows.iloc[i]
        label = label_frame(
            speed=fr["speed_kmh"],
            throttle=fr["throttle"],
            steering=fr["abs_steering"],
            speed_delta=speed_delta.iloc[i],
            steering_std=fr["steering_std"],
            normalized_pos=rr["normalized_car_position"],
            is_in_pit=bool(rr["is_in_pit"]),
            is_engine_running=bool(rr["is_engine_running"]),
            corner_positions=corner_positions,
        )
        labels.append(CLASS_TO_INT[label])

    return pd.Series(labels, name="label")
