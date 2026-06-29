from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
from datetime import datetime
import os

from telemetry.reader import TelemetryReader
from telemetry.models import TelemetryFrame
from prediction.features import FeatureExtractor
from prediction.model import MistakePredictor
from voice.coach import VoiceCoach
from ui.settings_manager import SettingsManager

SESSIONS_DIR = os.path.join("data", "sessions")


def _make_session_path() -> str:
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(SESSIONS_DIR, f"session_{ts}.csv")


class TelemetryWorker(QObject):
    telemetry_updated  = pyqtSignal(dict)   # live frame data for dashboard
    prediction_updated = pyqtSignal(str, float)  # mistake_type, confidence
    callout_fired      = pyqtSignal(str)    # callout text (for dashboard log)
    session_started    = pyqtSignal(str)    # session CSV path
    session_ended      = pyqtSignal(str)    # session CSV path
    status_changed     = pyqtSignal(str)    # "connecting" | "connected" | "stopped"
    error              = pyqtSignal(str)

    def __init__(self, settings: SettingsManager):
        super().__init__()
        self._settings = settings
        self._reader: TelemetryReader | None = None
        self._coach: VoiceCoach | None = None
        self._predictor: MistakePredictor | None = None
        self._extractor: FeatureExtractor | None = None
        self._session_path: str = ""
        self._running = False

    def _build_coach(self) -> VoiceCoach:
        s = self._settings
        return VoiceCoach(
            enabled=s.get("coach_enabled", False),
            same_mistake_cooldown=float(s.get("same_mistake_cooldown", 5)),
            any_callout_cooldown=float(s.get("any_callout_cooldown", 2)),
            approach_enabled=s.get("corner_approach_enabled", True),
            enabled_mistakes=dict(s.get("mistake_callouts", {})),
        )

    def _build_predictor(self) -> MistakePredictor:
        threshold = self._settings.get("confidence_threshold", 90) / 100.0
        p = MistakePredictor(confidence_threshold=threshold)
        try:
            p.load()
        except FileNotFoundError:
            pass
        return p

    @pyqtSlot()
    def run(self):
        self._running = True
        self._session_path = _make_session_path()
        self._extractor = FeatureExtractor()
        self._predictor = self._build_predictor()
        self._coach = self._build_coach()
        self._coach.load_corner_map(self._settings.get("active_track", ""))
        self._reader = TelemetryReader(session_csv_path=self._session_path)

        self.status_changed.emit("connecting")

        try:
            self._reader.connect()
        except Exception as e:
            self.error.emit(str(e))
            self._running = False
            return

        self.status_changed.emit("connected")
        self.session_started.emit(self._session_path)

        frame_count = 0
        last_prediction = "CLEAN"

        def on_frame(frame: TelemetryFrame, count: int):
            nonlocal last_prediction, frame_count
            frame_count = count

            fv = self._extractor.update(
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

            self._coach.check_approach(
                frame.world_position_x, frame.world_position_z, frame.speed_kmh,
                frame.is_in_pit, frame.is_engine_running,
            )
            self._coach.check_exit(
                frame.world_position_x, frame.world_position_z, frame.speed_kmh,
                frame.is_in_pit, frame.is_engine_running,
                yaw_rate=frame.yaw_rate,
            )

            prediction_type = "CLEAN"
            prediction_conf = 0.0

            if self._predictor._model is not None and fv is not None:
                pred = self._predictor.predict(fv.to_list(), speed_kmh=frame.speed_kmh)
                if pred:
                    prediction_type = pred.mistake_type
                    prediction_conf = pred.confidence
                    if pred.is_mistake:
                        self._coach.call_out(pred.mistake_type, frame.is_in_pit, frame.is_engine_running)

            if count % 6 == 0:  # ~10hz UI update
                self.telemetry_updated.emit({
                    "speed_kmh":            frame.speed_kmh,
                    "throttle":             frame.throttle,
                    "brake":                frame.brake,
                    "steering_angle":       frame.steering_angle,
                    "gear":                 frame.gear,
                    "rpm":                  frame.rpm,
                    "yaw_rate":             frame.yaw_rate,
                    "is_in_pit":            frame.is_in_pit,
                    "is_engine_running":    frame.is_engine_running,
                    "lap_time_ms":          frame.lap_time_ms,
                    "last_lap_ms":          frame.last_lap_ms,
                    "best_lap_ms":          frame.best_lap_ms,
                    "normalized_car_position": frame.normalized_car_position,
                    "tyre_temp_fl":         frame.tyre_temp_fl,
                    "tyre_temp_fr":         frame.tyre_temp_fr,
                    "tyre_temp_rl":         frame.tyre_temp_rl,
                    "tyre_temp_rr":         frame.tyre_temp_rr,
                    "prediction_type":      prediction_type,
                    "prediction_conf":      prediction_conf,
                })
                self.prediction_updated.emit(prediction_type, prediction_conf)

        try:
            self._reader.run(on_frame=on_frame)
        except Exception as e:
            self.error.emit(str(e))

        self.status_changed.emit("stopped")
        self.session_ended.emit(self._session_path)
        self._running = False

    def stop(self):
        if self._coach:
            self._coach.stop()
        if self._reader:
            self._reader.stop()

    def set_coach_enabled(self, enabled: bool):
        if self._coach:
            self._coach.enabled = enabled

    def reload_settings(self):
        """Re-apply settings to live coach and predictor without restarting session."""
        if self._coach:
            s = self._settings
            self._coach.update_settings(
                same_mistake_cooldown=float(s.get("same_mistake_cooldown", 5)),
                any_callout_cooldown=float(s.get("any_callout_cooldown", 2)),
                approach_enabled=s.get("corner_approach_enabled", True),
                enabled_mistakes=dict(s.get("mistake_callouts", {})),
            )
        if self._predictor:
            threshold = self._settings.get("confidence_threshold", 90) / 100.0
            self._predictor.set_threshold(threshold)
