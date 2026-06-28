from dataclasses import dataclass


@dataclass
class TelemetryFrame:
    speed_kmh: float
    throttle: float
    brake: float
    steering_angle: float
    gear: int
    rpm: float
    lap_time_ms: int
    last_lap_ms: int
    best_lap_ms: int
    sector_index: int
    normalized_car_position: float
    world_position_x: float
    world_position_y: float
    world_position_z: float
    velocity_x: float
    velocity_y: float
    velocity_z: float
    is_in_pit: bool
    is_engine_running: bool
    timestamp_ms: int
