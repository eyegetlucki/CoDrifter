import numpy as np
import pandas as pd

MISTAKE_CLASSES = ["CLEAN", "EARLY_THROTTLE", "UNDERSTEER", "MISSED_APEX"]
CLASS_TO_INT = {c: i for i, c in enumerate(MISTAKE_CLASSES)}
INT_TO_CLASS = {i: c for i, c in enumerate(MISTAKE_CLASSES)}

# Thresholds tuned for drift map data (no footbrake signal)
OVERSTEER_LATERAL_SPEED = 4.0    # m/s lateral component — significant slide
OVERSTEER_STEERING = 0.3          # steering input engaged
OVERSTEER_MIN_SPEED = 15.0        # only flag when actually moving

EARLY_THROTTLE_THROTTLE = 0.6     # heavy throttle applied
EARLY_THROTTLE_STEERING = 0.4     # while steering is still loaded
EARLY_THROTTLE_SPEED_LOW = 35.0   # at relatively low speed (mid-corner)

UNDERSTEER_THROTTLE = 0.7         # heavy throttle
UNDERSTEER_STEERING = 0.5         # high steering demand
UNDERSTEER_LATERAL_LOW = 1.5      # but car not actually sliding much (pushing straight)

MISSED_APEX_STEERING_STD = 0.25   # erratic steering corrections
MISSED_APEX_MIN_SPEED = 20.0


def label_frame(
    speed: float,
    throttle: float,
    steering: float,
    lateral_speed: float,
    steering_std: float,
    is_in_pit: bool,
    is_engine_running: bool,
) -> str:
    if is_in_pit or not is_engine_running or speed < 5.0:
        return "CLEAN"

    abs_steer = abs(steering)

    if (throttle > EARLY_THROTTLE_THROTTLE
            and abs_steer > EARLY_THROTTLE_STEERING
            and speed < EARLY_THROTTLE_SPEED_LOW):
        return "EARLY_THROTTLE"

    if (throttle > UNDERSTEER_THROTTLE
            and abs_steer > UNDERSTEER_STEERING
            and lateral_speed < UNDERSTEER_LATERAL_LOW):
        return "UNDERSTEER"

    if (steering_std > MISSED_APEX_STEERING_STD
            and speed > MISSED_APEX_MIN_SPEED):
        return "MISSED_APEX"

    return "CLEAN"


def label_dataframe(df: pd.DataFrame, features_df: pd.DataFrame) -> pd.Series:
    labels = []
    feat_rows = features_df.reset_index(drop=True)
    raw_rows = df.tail(len(features_df)).reset_index(drop=True)

    for i in range(len(feat_rows)):
        fr = feat_rows.iloc[i]
        rr = raw_rows.iloc[i]
        label = label_frame(
            speed=fr["speed_kmh"],
            throttle=fr["throttle"],
            steering=fr["abs_steering"],
            lateral_speed=fr["lateral_speed"],
            steering_std=fr["steering_std"],
            is_in_pit=bool(rr["is_in_pit"]),
            is_engine_running=bool(rr["is_engine_running"]),
        )
        labels.append(CLASS_TO_INT[label])

    return pd.Series(labels, name="label")
