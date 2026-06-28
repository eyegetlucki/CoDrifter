from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSlot
import ui.theme as T


def _ms_to_laptime(ms: int) -> str:
    if ms <= 0:
        return "--:--.---"
    total_s = ms / 1000
    m = int(total_s // 60)
    s = total_s % 60
    return f"{m}:{s:06.3f}"


def _card() -> QFrame:
    f = QFrame()
    f.setStyleSheet(f"""
        QFrame {{
            background-color: {T.BG_CARD};
            border: 1px solid {T.BORDER};
            border-radius: 12px;
        }}
    """)
    return f


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setObjectName("section_title")
    return lbl


class PredictionBadge(QLabel):
    _STYLES = {
        "CLEAN":        (T.GREEN,  "#0A1810", T.GREEN),
        "LOSING_ANGLE": (T.RED,    "#1A0508", T.ACCENT_DIM),
        "SPEED_LOSS":   (T.ORANGE, "#1A1000", "#3A2800"),
        "SNAP_RISK":    (T.RED,    "#1A0508", T.ACCENT_DIM),
    }

    def __init__(self):
        super().__init__("CLEAN")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(54)
        self._set("CLEAN", 0.0)

    def _set(self, mistake: str, conf: float):
        fg, bg, border = self._STYLES.get(mistake, (T.TEXT_SECONDARY, T.BG_HOVER, T.BORDER))
        label = "CLEAN" if mistake == "CLEAN" else f"{mistake.replace('_', ' ')}  ·  {conf:.0%}"
        self.setText(label)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                letter-spacing: 1px;
                padding: 14px 20px;
            }}
        """)

    @pyqtSlot(str, float)
    def update_prediction(self, mistake_type: str, confidence: float):
        self._set(mistake_type, confidence)


class InputBar(QWidget):
    def __init__(self, label: str, bar_id: str, color: str):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {T.TEXT_SECONDARY}; font-size: 11px; font-weight: 500;")
        header.addWidget(lbl)
        header.addStretch()
        self._pct = QLabel("0%")
        self._pct.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 600;")
        header.addWidget(self._pct)
        layout.addLayout(header)

        self._bar = QProgressBar()
        self._bar.setObjectName(bar_id)
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setFixedHeight(6)
        self._bar.setTextVisible(False)
        layout.addWidget(self._bar)

    def set_value(self, v: float):
        pct = int(v * 100)
        self._bar.setValue(pct)
        self._pct.setText(f"{pct}%")


class SteeringWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QHBoxLayout()
        lbl = QLabel("Steering")
        lbl.setStyleSheet(f"color: {T.TEXT_SECONDARY}; font-size: 11px; font-weight: 500;")
        header.addWidget(lbl)
        header.addStretch()
        self._val = QLabel("0.00")
        self._val.setStyleSheet(f"color: {T.TEXT_SECONDARY}; font-size: 11px; font-weight: 600;")
        header.addWidget(self._val)
        layout.addLayout(header)

        self._bar = QProgressBar()
        self._bar.setRange(0, 200)
        self._bar.setValue(100)
        self._bar.setFixedHeight(6)
        self._bar.setTextVisible(False)
        self._bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {T.BG_HOVER};
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {T.TEXT_SECONDARY};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self._bar)

    def set_value(self, v: float):
        mapped = int((v + 1.0) * 100)
        self._bar.setValue(max(0, min(200, mapped)))
        self._val.setText(f"{v:+.2f}")


class LapTimesWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        for attr, label, color in [
            ("_current", "Current",  T.TEXT_PRIMARY),
            ("_best",    "Best",     T.ACCENT),
            ("_last",    "Last",     T.TEXT_SECONDARY),
        ]:
            col = QVBoxLayout()
            col.setSpacing(5)
            title = QLabel(label)
            title.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 10px; font-weight: 600; letter-spacing: 1px;")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val = QLabel("--:--.---")
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: 600;")
            col.addWidget(title)
            col.addWidget(val)
            setattr(self, attr, val)
            layout.addLayout(col, 1)
            if attr != "_last":
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.VLine)
                sep.setStyleSheet(f"background-color: {T.BORDER}; max-width: 1px; border: none;")
                layout.addWidget(sep)

    def update_times(self, lap_ms: int, best_ms: int, last_ms: int):
        self._current.setText(_ms_to_laptime(lap_ms))
        self._best.setText(_ms_to_laptime(best_ms))
        self._last.setText(_ms_to_laptime(last_ms))


class DashboardTab(QWidget):
    def __init__(self, settings, on_coach_toggle, on_stop_session):
        super().__init__()
        self._settings = settings
        self._on_coach_toggle = on_coach_toggle
        self._on_stop = on_stop_session
        self._coach_enabled = settings.get("coach_enabled", False)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 18)
        root.setSpacing(12)

        # ── Status bar ────────────────────────────────────────────────
        status_row = QHBoxLayout()
        status_row.setSpacing(8)

        self._status_dot = QWidget()
        self._status_dot.setFixedSize(7, 7)
        self._status_dot.setStyleSheet(f"background-color: {T.TEXT_DIM}; border-radius: 4px;")

        self._status_lbl = QLabel("Not connected")
        self._status_lbl.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 11px;")

        status_row.addWidget(self._status_dot)
        status_row.addWidget(self._status_lbl)
        status_row.addStretch()

        self._pit_badge = QLabel("Pit Lane")
        self._pit_badge.setVisible(False)
        self._pit_badge.setStyleSheet(f"""
            color: {T.ORANGE}; background-color: #1A1200;
            border: 1px solid #3A2800; border-radius: 5px;
            font-size: 10px; font-weight: 600; padding: 3px 10px;
        """)
        status_row.addWidget(self._pit_badge)
        root.addLayout(status_row)

        # ── Hero: Speed | Gear + RPM ──────────────────────────────────
        hero = _card()
        hl = QHBoxLayout(hero)
        hl.setContentsMargins(32, 22, 32, 22)
        hl.setSpacing(0)

        speed_col = QVBoxLayout()
        speed_col.setSpacing(0)
        speed_col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._speed_val = QLabel("0")
        self._speed_val.setObjectName("speed_value")
        self._speed_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        unit = QLabel("KM/H")
        unit.setObjectName("speed_unit")
        unit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        speed_col.addWidget(self._speed_val)
        speed_col.addWidget(unit)
        hl.addLayout(speed_col, 3)

        vd = QFrame()
        vd.setFrameShape(QFrame.Shape.VLine)
        vd.setStyleSheet(f"background-color: {T.BORDER}; max-width: 1px; border: none;")
        hl.addWidget(vd)
        hl.addSpacing(28)

        gr_col = QVBoxLayout()
        gr_col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gr_col.setSpacing(4)

        gear_lbl = QLabel("GEAR")
        gear_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gear_lbl.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 9px; font-weight: 600; letter-spacing: 2px;")

        self._gear_val = QLabel("N")
        self._gear_val.setObjectName("gear_value")
        self._gear_val.setAlignment(Qt.AlignmentFlag.AlignCenter)

        rpm_lbl = QLabel("RPM")
        rpm_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rpm_lbl.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 9px; font-weight: 600; letter-spacing: 2px;")

        self._rpm_val = QLabel("0")
        self._rpm_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._rpm_val.setStyleSheet(f"color: {T.TEXT_SECONDARY}; font-size: 14px; font-weight: 500;")

        gr_col.addWidget(gear_lbl)
        gr_col.addWidget(self._gear_val)
        gr_col.addSpacing(4)
        gr_col.addWidget(rpm_lbl)
        gr_col.addWidget(self._rpm_val)
        hl.addLayout(gr_col, 1)

        root.addWidget(hero)

        # ── Middle: Inputs | Prediction + Laps ───────────────────────
        mid = QHBoxLayout()
        mid.setSpacing(12)

        # Inputs card
        inp_card = _card()
        il = QVBoxLayout(inp_card)
        il.setContentsMargins(22, 18, 22, 18)
        il.setSpacing(18)
        il.addWidget(_section_label("Inputs"))

        self._throttle_bar = InputBar("Throttle", "throttle_bar", T.GREEN)
        self._brake_bar    = InputBar("Brake",    "brake_bar",    T.RED)
        self._steering     = SteeringWidget()
        il.addWidget(self._throttle_bar)
        il.addWidget(self._brake_bar)
        il.addWidget(self._steering)
        il.addStretch()
        mid.addWidget(inp_card, 1)

        # Right column
        right = QVBoxLayout()
        right.setSpacing(12)

        pred_card = _card()
        pl = QVBoxLayout(pred_card)
        pl.setContentsMargins(22, 18, 22, 18)
        pl.setSpacing(12)
        pl.addWidget(_section_label("AI Prediction"))
        self._prediction_badge = PredictionBadge()
        pl.addWidget(self._prediction_badge)
        pl.addStretch()
        right.addWidget(pred_card, 1)

        lap_card = _card()
        ll = QVBoxLayout(lap_card)
        ll.setContentsMargins(22, 18, 22, 18)
        ll.setSpacing(12)
        ll.addWidget(_section_label("Lap Times"))
        self._lap_times = LapTimesWidget()
        ll.addWidget(self._lap_times)
        right.addWidget(lap_card)

        mid.addLayout(right, 1)
        root.addLayout(mid, 1)

        # ── Controls ──────────────────────────────────────────────────
        controls = QHBoxLayout()
        controls.setSpacing(10)

        self._coach_btn = QPushButton()
        self._coach_btn.setFixedHeight(40)
        self._coach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._coach_btn.clicked.connect(self._toggle_coach)
        self._refresh_coach_btn()
        controls.addWidget(self._coach_btn, 1)

        self._stop_btn = QPushButton("Stop Session")
        self._stop_btn.setFixedHeight(40)
        self._stop_btn.setEnabled(False)
        self._stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stop_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {T.TEXT_DIM};
                border: 1px solid {T.BORDER};
                border-radius: 8px;
                font-weight: 500;
                font-size: 12px;
            }}
            QPushButton:enabled:hover {{
                background-color: {T.ACCENT_DIM};
                border-color: {T.ACCENT};
                color: {T.ACCENT};
            }}
            QPushButton:disabled {{
                color: {T.TEXT_DIM};
            }}
        """)
        controls.addWidget(self._stop_btn, 1)
        root.addLayout(controls)

    def _refresh_coach_btn(self):
        if self._coach_enabled:
            self._coach_btn.setObjectName("toggle_on")
            self._coach_btn.setText("Coach  On")
        else:
            self._coach_btn.setObjectName("toggle_off")
            self._coach_btn.setText("Coach  Off")
        self._coach_btn.setStyleSheet("")
        self._coach_btn.setStyle(self._coach_btn.style())

    def _toggle_coach(self):
        self._coach_enabled = not self._coach_enabled
        self._settings.set("coach_enabled", self._coach_enabled)
        self._refresh_coach_btn()
        self._on_coach_toggle(self._coach_enabled)

    @pyqtSlot(str)
    def on_status_changed(self, status: str):
        states = {
            "connecting": (T.ORANGE,        "Connecting..."),
            "connected":  (T.GREEN,         "Connected"),
            "stopped":    (T.TEXT_DIM,      "Not connected"),
        }
        color, text = states.get(status, (T.TEXT_DIM, status))
        self._status_dot.setStyleSheet(f"background-color: {color}; border-radius: 4px;")
        self._status_lbl.setStyleSheet(f"color: {color}; font-size: 11px;")
        self._status_lbl.setText(text)
        self._stop_btn.setEnabled(status == "connected")

    @pyqtSlot(dict)
    def on_telemetry(self, data: dict):
        self._speed_val.setText(f"{data['speed_kmh']:.0f}")
        gear = data.get("gear", 0)
        self._gear_val.setText("N" if gear == 0 else str(gear))
        self._rpm_val.setText(f"{data.get('rpm', 0):.0f}")
        self._throttle_bar.set_value(data.get("throttle", 0))
        self._brake_bar.set_value(data.get("brake", 0))
        self._steering.set_value(data.get("steering_angle", 0))
        self._lap_times.update_times(
            data.get("lap_time_ms", 0),
            data.get("best_lap_ms", 0),
            data.get("last_lap_ms", 0),
        )
        self._pit_badge.setVisible(bool(data.get("is_in_pit", False)))

    @pyqtSlot(str, float)
    def on_prediction(self, mistake_type: str, confidence: float):
        self._prediction_badge.update_prediction(mistake_type, confidence)

    def sync_coach_state(self, enabled: bool):
        self._coach_enabled = enabled
        self._refresh_coach_btn()
