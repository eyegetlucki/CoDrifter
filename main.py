import os
import signal
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from telemetry.reader import TelemetryReader
from telemetry.models import TelemetryFrame
from prediction.features import FeatureExtractor
from prediction.model import MistakePredictor
from voice.coach import VoiceCoach

SESSIONS_DIR = os.path.join("data", "sessions")
PRINT_EVERY_N_FRAMES = 30  # ~2hz display update


def _make_session_path() -> str:
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(SESSIONS_DIR, f"session_{ts}.csv")


def main():
    session_path = _make_session_path()
    reader = TelemetryReader(session_csv_path=session_path)
    extractor = FeatureExtractor()
    coach = VoiceCoach()

    predictor = MistakePredictor()
    model_available = False
    try:
        predictor.load()
        model_available = True
    except FileNotFoundError:
        print("No trained model found — running telemetry only.")
        print("To train: python -m prediction.trainer\n")

    last_prediction = "CLEAN"

    def _on_frame(frame: TelemetryFrame, count: int):
        nonlocal last_prediction

        fv = extractor.update(
            speed=frame.speed_kmh,
            throttle=frame.throttle,
            brake=frame.brake,
            steering=frame.steering_angle,
            vx=frame.velocity_x,
            vz=frame.velocity_z,
            local_vx=frame.local_velocity_x,
            local_vz=frame.local_velocity_z,
            yaw_rate=frame.yaw_rate,
            wheel_slip_rl=frame.wheel_slip_rl,
            wheel_slip_rr=frame.wheel_slip_rr,
        )

        coach.check_approach(frame.normalized_car_position, frame.speed_kmh, frame.is_in_pit, frame.is_engine_running)
        coach.check_exit(frame.normalized_car_position, frame.speed_kmh, frame.is_in_pit, frame.is_engine_running)

        if model_available and fv is not None:
            pred = predictor.predict(fv.to_list())
            if pred and pred.is_mistake:
                last_prediction = f"{pred.mistake_type} ({pred.confidence:.0%})"
                coach.call_out(pred.mistake_type, frame.is_in_pit, frame.is_engine_running)
            elif pred and pred.mistake_type == "CLEAN":
                last_prediction = "CLEAN"

        if count % PRINT_EVERY_N_FRAMES == 0:
            pit = " [PIT]" if frame.is_in_pit else ""
            print(
                f"\r  {frame.speed_kmh:6.1f} km/h  "
                f"Thr: {frame.throttle:.2f}  "
                f"Brk: {frame.brake:.2f}  "
                f"Steer: {frame.steering_angle:+.2f}  "
                f"Gear: {frame.gear}  "
                f"| {last_prediction:<30}"
                f"{pit}   ",
                end="",
                flush=True,
            )

    def _shutdown(sig, frame):
        print("\n\nShutting down...")
        coach.stop()
        reader.stop()

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    reader.connect()

    print(f"Session CSV: {os.path.abspath(session_path)}")
    print("Reading telemetry at 60hz — press Ctrl+C to stop.\n")

    reader.run(on_frame=_on_frame)

    print(f"\nSession saved to: {os.path.abspath(session_path)}")


if __name__ == "__main__":
    main()
