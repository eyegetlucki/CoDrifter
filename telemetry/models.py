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
    # Extended fields for improved drift detection
    local_velocity_x: float    # car-relative lateral velocity (true sideways speed)
    local_velocity_y: float
    local_velocity_z: float    # car-relative forward velocity
    yaw_rate: float            # angular velocity around vertical axis (rotation speed)
    heading: float             # car facing direction in radians
    wheel_slip_fl: float       # wheel slip ratio front-left
    wheel_slip_fr: float       # wheel slip ratio front-right
    wheel_slip_rl: float       # wheel slip ratio rear-left
    wheel_slip_rr: float       # wheel slip ratio rear-right
    tyre_temp_fl: float        # tyre core temp front-left
    tyre_temp_fr: float        # tyre core temp front-right
    tyre_temp_rl: float        # tyre core temp rear-left
    tyre_temp_rr: float        # tyre core temp rear-right
    tc_active: float           # traction control activation 0-1
    abs_active: float          # ABS activation 0-1
