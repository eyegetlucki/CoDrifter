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
    # True lateral speed from car-relative velocity
    lateral_speed: float
    forward_speed: float
    yaw_rate: float
    abs_yaw_rate: float
    # Wheel slip
    rear_slip: float          # avg rear wheel slip
    rear_slip_delta: float    # change in rear slip
    # Rolling window stats
    speed_delta: float
    throttle_mean: float
    throttle_std: float
    steering_mean: float
    steering_std: float
    yaw_rate_mean: float
    yaw_rate_std: float
    lateral_speed_mean: float
    rear_slip_mean: float
    # Composite
    slip_angle_proxy: float   # lateral_speed / forward_speed — true sideslip proxy

    def to_list(self) -> list:
        return [
            self.speed_kmh, self.throttle, self.brake, self.abs_steering,
            self.lateral_speed, self.forward_speed, self.yaw_rate, self.abs_yaw_rate,
            self.rear_slip, self.rear_slip_delta,
            self.speed_delta, self.throttle_mean, self.throttle_std,
            self.steering_mean, self.steering_std,
            self.yaw_rate_mean, self.yaw_rate_std,
            self.lateral_speed_mean, self.rear_slip_mean,
            self.slip_angle_proxy,
        ]

    @staticmethod
    def feature_names() -> list:
        return [
            "speed_kmh", "throttle", "brake", "abs_steering",
            "lateral_speed", "forward_speed", "yaw_rate", "abs_yaw_rate",
            "rear_slip", "rear_slip_delta",
            "speed_delta", "throttle_mean", "throttle_std",
            "steering_mean", "steering_std",
            "yaw_rate_mean", "yaw_rate_std",
            "lateral_speed_mean", "rear_slip_mean",
            "slip_angle_proxy",
        ]


class FeatureExtractor:
    def __init__(self, window: int = WINDOW_SIZE):
        self._window = window
        self._speeds: deque = deque(maxlen=window)
        self._throttles: deque = deque(maxlen=window)
        self._steerings: deque = deque(maxlen=window)
        self._yaw_rates: deque = deque(maxlen=window)
        self._lateral_speeds: deque = deque(maxlen=window)
        self._rear_slips: deque = deque(maxlen=window)

    def update(self, speed: float, throttle: float, brake: float,
               steering: float, vx: float, vz: float,
               local_vx: float, local_vz: float,
               yaw_rate: float,
               wheel_slip_rl: float, wheel_slip_rr: float) -> Optional[FeatureVector]:

        lateral_speed = abs(local_vx)
        forward_speed = abs(local_vz)
        rear_slip = (abs(wheel_slip_rl) + abs(wheel_slip_rr)) / 2.0
        slip_angle_proxy = lateral_speed / max(forward_speed, 0.1)

        self._speeds.append(speed)
        self._throttles.append(throttle)
        self._steerings.append(abs(steering))
        self._yaw_rates.append(yaw_rate)
        self._lateral_speeds.append(lateral_speed)
        self._rear_slips.append(rear_slip)

        if len(self._speeds) < 2:
            return None

        speeds = list(self._speeds)
        throttles = list(self._throttles)
        steerings = list(self._steerings)
        yaw_rates = list(self._yaw_rates)
        laterals = list(self._lateral_speeds)
        slips = list(self._rear_slips)

        return FeatureVector(
            speed_kmh=speed,
            throttle=throttle,
            brake=brake,
            abs_steering=abs(steering),
            lateral_speed=lateral_speed,
            forward_speed=forward_speed,
            yaw_rate=yaw_rate,
            abs_yaw_rate=abs(yaw_rate),
            rear_slip=rear_slip,
            rear_slip_delta=slips[-1] - slips[0],
            speed_delta=speeds[-1] - speeds[0],
            throttle_mean=float(np.mean(throttles)),
            throttle_std=float(np.std(throttles)),
            steering_mean=float(np.mean(steerings)),
            steering_std=float(np.std(steerings)),
            yaw_rate_mean=float(np.mean(yaw_rates)),
            yaw_rate_std=float(np.std(yaw_rates)),
            lateral_speed_mean=float(np.mean(laterals)),
            rear_slip_mean=float(np.mean(slips)),
            slip_angle_proxy=slip_angle_proxy,
        )

    def reset(self):
        self._speeds.clear()
        self._throttles.clear()
        self._steerings.clear()
        self._yaw_rates.clear()
        self._lateral_speeds.clear()
        self._rear_slips.clear()


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
            local_vx=row.get("local_velocity_x", 0.0),
            local_vz=row.get("local_velocity_z", 0.0),
            yaw_rate=row.get("yaw_rate", 0.0),
            wheel_slip_rl=row.get("wheel_slip_rl", 0.0),
            wheel_slip_rr=row.get("wheel_slip_rr", 0.0),
        )
        if fv is not None:
            rows.append(fv.to_list())

    return pd.DataFrame(rows, columns=FeatureVector.feature_names())
