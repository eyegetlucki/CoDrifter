import numpy as np
import pandas as pd
from collections import deque
from dataclasses import dataclass
from typing import Optional

WINDOW_SIZE = 30  # 0.5 seconds at 60hz


@dataclass
class FeatureVector:
    speed_kmh: float
    throttle: float
    brake: float
    abs_steering: float
    lateral_speed: float
    speed_delta: float
    throttle_delta: float
    steering_delta: float
    throttle_mean: float
    throttle_std: float
    steering_mean: float
    steering_std: float
    speed_mean: float
    lateral_speed_mean: float
    slip_proxy: float  # abs_steering * speed — correlates with oversteer intensity

    def to_list(self) -> list:
        return [
            self.speed_kmh,
            self.throttle,
            self.brake,
            self.abs_steering,
            self.lateral_speed,
            self.speed_delta,
            self.throttle_delta,
            self.steering_delta,
            self.throttle_mean,
            self.throttle_std,
            self.steering_mean,
            self.steering_std,
            self.speed_mean,
            self.lateral_speed_mean,
            self.slip_proxy,
        ]

    @staticmethod
    def feature_names() -> list:
        return [
            "speed_kmh", "throttle", "brake", "abs_steering",
            "lateral_speed", "speed_delta", "throttle_delta", "steering_delta",
            "throttle_mean", "throttle_std", "steering_mean", "steering_std",
            "speed_mean", "lateral_speed_mean", "slip_proxy",
        ]


def _lateral_speed(vx: float, vz: float, speed_kmh: float) -> float:
    total = np.sqrt(vx ** 2 + vz ** 2)
    speed_ms = speed_kmh / 3.6
    lateral = np.sqrt(max(0.0, total ** 2 - speed_ms ** 2))
    return float(lateral)


class FeatureExtractor:
    def __init__(self, window: int = WINDOW_SIZE):
        self._window = window
        self._speeds: deque = deque(maxlen=window)
        self._throttles: deque = deque(maxlen=window)
        self._steerings: deque = deque(maxlen=window)
        self._laterals: deque = deque(maxlen=window)

    def update(self, speed: float, throttle: float, brake: float,
               steering: float, vx: float, vz: float) -> Optional[FeatureVector]:
        lat = _lateral_speed(vx, vz, speed)

        self._speeds.append(speed)
        self._throttles.append(throttle)
        self._steerings.append(abs(steering))
        self._laterals.append(lat)

        if len(self._speeds) < 2:
            return None

        speeds = list(self._speeds)
        throttles = list(self._throttles)
        steerings = list(self._steerings)
        laterals = list(self._laterals)

        return FeatureVector(
            speed_kmh=speed,
            throttle=throttle,
            brake=brake,
            abs_steering=abs(steering),
            lateral_speed=lat,
            speed_delta=speeds[-1] - speeds[0],
            throttle_delta=throttles[-1] - throttles[0],
            steering_delta=steerings[-1] - steerings[0],
            throttle_mean=float(np.mean(throttles)),
            throttle_std=float(np.std(throttles)),
            steering_mean=float(np.mean(steerings)),
            steering_std=float(np.std(steerings)),
            speed_mean=float(np.mean(speeds)),
            lateral_speed_mean=float(np.mean(laterals)),
            slip_proxy=abs(steering) * speed,
        )

    def reset(self):
        self._speeds.clear()
        self._throttles.clear()
        self._steerings.clear()
        self._laterals.clear()


def extract_features_from_df(df: pd.DataFrame) -> pd.DataFrame:
    extractor = FeatureExtractor()
    rows = []
    for _, row in df.iterrows():
        fv = extractor.update(
            speed=row["speed_kmh"],
            throttle=row["throttle"],
            brake=row["brake"],
            steering=row["steering_angle"],
            vx=row["velocity_x"],
            vz=row["velocity_z"],
        )
        if fv is not None:
            rows.append(fv.to_list())

    return pd.DataFrame(rows, columns=FeatureVector.feature_names())
