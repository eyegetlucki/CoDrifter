import time
import queue
import threading
import csv
import os
from typing import Callable, Optional

from dotenv import load_dotenv

from telemetry.sim_info import SimInfo
from telemetry.models import TelemetryFrame

load_dotenv()

TELEMETRY_HZ = 60
FRAME_INTERVAL = 1.0 / TELEMETRY_HZ

CSV_COLUMNS = [
    "timestamp_ms", "speed_kmh", "throttle", "brake", "steering_angle",
    "gear", "rpm", "lap_time_ms", "last_lap_ms", "best_lap_ms",
    "sector_index", "normalized_car_position",
    "world_position_x", "world_position_y", "world_position_z",
    "velocity_x", "velocity_y", "velocity_z",
    "is_in_pit", "is_engine_running",
    "local_velocity_x", "local_velocity_y", "local_velocity_z",
    "yaw_rate", "heading",
    "wheel_slip_fl", "wheel_slip_fr", "wheel_slip_rl", "wheel_slip_rr",
    "tyre_temp_fl", "tyre_temp_fr", "tyre_temp_rl", "tyre_temp_rr",
    "tc_active", "abs_active",
]


def _csv_writer_thread(write_queue: queue.Queue, csv_path: str):
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        while True:
            item = write_queue.get()
            if item is None:
                break
            writer.writerow(item)
            write_queue.task_done()


class TelemetryReader:
    def __init__(self, session_csv_path: str):
        self._sim = SimInfo()
        self._csv_path = session_csv_path
        self._write_queue: queue.Queue = queue.Queue(maxsize=1000)
        self._writer_thread: Optional[threading.Thread] = None
        self._running = False

    def _frame_to_dict(self, frame: TelemetryFrame) -> dict:
        return {
            "timestamp_ms": frame.timestamp_ms,
            "speed_kmh": round(frame.speed_kmh, 3),
            "throttle": round(frame.throttle, 4),
            "brake": round(frame.brake, 4),
            "steering_angle": round(frame.steering_angle, 4),
            "gear": frame.gear,
            "rpm": round(frame.rpm, 1),
            "lap_time_ms": frame.lap_time_ms,
            "last_lap_ms": frame.last_lap_ms,
            "best_lap_ms": frame.best_lap_ms,
            "sector_index": frame.sector_index,
            "normalized_car_position": round(frame.normalized_car_position, 6),
            "world_position_x": round(frame.world_position_x, 3),
            "world_position_y": round(frame.world_position_y, 3),
            "world_position_z": round(frame.world_position_z, 3),
            "velocity_x": round(frame.velocity_x, 4),
            "velocity_y": round(frame.velocity_y, 4),
            "velocity_z": round(frame.velocity_z, 4),
            "is_in_pit": frame.is_in_pit,
            "is_engine_running": frame.is_engine_running,
            "local_velocity_x": round(frame.local_velocity_x, 4),
            "local_velocity_y": round(frame.local_velocity_y, 4),
            "local_velocity_z": round(frame.local_velocity_z, 4),
            "yaw_rate": round(frame.yaw_rate, 4),
            "heading": round(frame.heading, 4),
            "wheel_slip_fl": round(frame.wheel_slip_fl, 4),
            "wheel_slip_fr": round(frame.wheel_slip_fr, 4),
            "wheel_slip_rl": round(frame.wheel_slip_rl, 4),
            "wheel_slip_rr": round(frame.wheel_slip_rr, 4),
            "tyre_temp_fl": round(frame.tyre_temp_fl, 2),
            "tyre_temp_fr": round(frame.tyre_temp_fr, 2),
            "tyre_temp_rl": round(frame.tyre_temp_rl, 2),
            "tyre_temp_rr": round(frame.tyre_temp_rr, 2),
            "tc_active": round(frame.tc_active, 4),
            "abs_active": round(frame.abs_active, 4),
        }

    def _read_frame(self) -> TelemetryFrame:
        p = self._sim.physics
        g = self._sim.graphics
        return TelemetryFrame(
            speed_kmh=p.speedKmh,
            throttle=p.gas,
            brake=p.brake,
            steering_angle=p.steerAngle,
            gear=p.gear,
            rpm=p.rpms,
            lap_time_ms=g.iCurrentTime,
            last_lap_ms=g.iLastTime,
            best_lap_ms=g.iBestTime,
            sector_index=g.currentSectorIndex,
            normalized_car_position=g.normalizedCarPosition,
            world_position_x=g.carCoordinates[0],
            world_position_y=g.carCoordinates[1],
            world_position_z=g.carCoordinates[2],
            velocity_x=p.velocity[0],
            velocity_y=p.velocity[1],
            velocity_z=p.velocity[2],
            is_in_pit=bool(g.isInPit or g.isInPitLane),
            is_engine_running=bool(p.rpms > 0),
            timestamp_ms=int(time.time() * 1000),
            local_velocity_x=p.localVelocity[0],
            local_velocity_y=p.localVelocity[1],
            local_velocity_z=p.localVelocity[2],
            yaw_rate=p.localAngularVel[1],
            heading=p.heading,
            wheel_slip_fl=p.wheelSlip[0],
            wheel_slip_fr=p.wheelSlip[1],
            wheel_slip_rl=p.wheelSlip[2],
            wheel_slip_rr=p.wheelSlip[3],
            tyre_temp_fl=p.tyreCoreTemperature[0],
            tyre_temp_fr=p.tyreCoreTemperature[1],
            tyre_temp_rl=p.tyreCoreTemperature[2],
            tyre_temp_rr=p.tyreCoreTemperature[3],
            tc_active=p.tc,
            abs_active=p.abs,
        )

    def connect(self):
        print("Connecting to Assetto Corsa shared memory...")
        while not self._sim.connect():
            print("  AC not running — retrying in 2 seconds... (launch AC to continue)")
            time.sleep(2)
        print("Connected.")

        self._writer_thread = threading.Thread(
            target=_csv_writer_thread,
            args=(self._write_queue, self._csv_path),
            daemon=True,
        )
        self._writer_thread.start()
        self._running = True

    def stop(self):
        self._running = False
        self._write_queue.put(None)
        if self._writer_thread:
            self._writer_thread.join(timeout=5)
        self._sim.close()

    def run(self, on_frame: Optional[Callable[[TelemetryFrame, int], None]] = None):
        frame_count = 0
        while self._running:
            loop_start = time.perf_counter()

            frame = self._read_frame()
            frame_count += 1

            try:
                self._write_queue.put_nowait(self._frame_to_dict(frame))
            except queue.Full:
                pass

            if on_frame:
                on_frame(frame, frame_count)

            elapsed = time.perf_counter() - loop_start
            sleep_time = FRAME_INTERVAL - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
