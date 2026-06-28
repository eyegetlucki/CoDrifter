from collections import deque

import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSlot
import ui.theme as T

pg.setConfigOptions(antialias=True, foreground=T.TEXT_DIM, background=T.BG_CARD)

TRACE_LEN = 300  # ~30s at 10hz


def _ms_to_laptime(ms: int) -> str:
    if ms <= 0:
        return "--:--.---"
    total_s = ms / 1000
    m = int(total_s // 60)
    s = total_s % 60
    return f"{m}:{s:06.3f}"


def _card(radius: int = 12) -> QFrame:
    f = QFrame()
    f.setStyleSheet(f"""
        QFrame {{
            background-color: {T.BG_CARD};
            border: 1px solid {T.BORDER};
            border-radius: {radius}px;
        }}
    """)
    return f


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("section_title")
    return lbl


# ── Prediction badge ───────────────────────────────────────────────────────────

class PredictionBadge(QLabel):
    _CLEAN_STYLE = f"""
        QLabel {{
            background-color: rgba(34, 197, 94, 0.06);
            color: {T.GREEN};
            border: 1px solid rgba(34, 197, 94, 0.18);
            border-radius: 8px;
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 0.5px;
            padding: 12px 20px;
        }}
    """
    _MISTAKE_STYLES = {
        "LOSING_ANGLE": (T.RED,    "rgba(255,74,74,0.06)",  "rgba(255,74,74,0.18)"),
        "SPEED_LOSS":   (T.ORANGE, "rgba(232,160,32,0.06)", "rgba(232,160,32,0.18)"),
        "SNAP_RISK":    (T.RED,    "rgba(255,74,74,0.06)",  "rgba(255,74,74,0.18)"),
    }

    def __init__(self):
        super().__init__("Clean")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(48)
        self.setStyleSheet(self._CLEAN_STYLE)

    def _set(self, mistake: str, conf: float):
        if mistake == "CLEAN":
            self.setText("Clean")
            self.setStyleSheet(self._CLEAN_STYLE)
        else:
            color, bg, border = self._MISTAKE_STYLES.get(
                mistake, (T.RED, "rgba(255,74,74,0.06)", "rgba(255,74,74,0.18)")
            )
            label = mistake.replace("_", " ").title()
            self.setText(f"{label}  ·  {conf:.0%}")
            self.setStyleSheet(f"""
                QLabel {{
                    background-color: {bg};
                    color: {color};
                    border: 1px solid {border};
                    border-radius: 8px;
                    font-size: 12px;
                    font-weight: 600;
                    letter-spacing: 0.5px;
                    padding: 12px 20px;
                }}
            """)

    @pyqtSlot(str, float)
    def update_prediction(self, mistake_type: str, confidence: float):
        self._set(mistake_type, confidence)


# ── Input bar ─────────────────────────────────────────────────────────────────

class InputBar(QWidget):
    def __init__(self, label: str, bar_id: str, color: str):
        super().__init__()
        self._color = color
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        header = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: {T.TEXT_SECONDARY}; font-size: 11.5px; font-weight: 400;"
        )
        header.addWidget(lbl)
        header.addStretch()
        self._pct = QLabel("0%")
        self._pct.setStyleSheet(
            f"color: {T.TEXT_DIM}; font-size: 11.5px; font-weight: 500;"
        )
        header.addWidget(self._pct)
        layout.addLayout(header)

        self._bar = QProgressBar()
        self._bar.setObjectName(bar_id)
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setFixedHeight(3)
        self._bar.setTextVisible(False)
        layout.addWidget(self._bar)

    def set_value(self, v: float):
        pct = int(v * 100)
        self._bar.setValue(pct)
        self._pct.setText(f"{pct}%")
        color = self._color if pct > 0 else T.TEXT_DIM
        self._pct.setStyleSheet(
            f"color: {color}; font-size: 11.5px; font-weight: 500;"
        )


# ── Steering bar ──────────────────────────────────────────────────────────────

class SteeringWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        header = QHBoxLayout()
        lbl = QLabel("Steering")
        lbl.setStyleSheet(
            f"color: {T.TEXT_SECONDARY}; font-size: 11.5px; font-weight: 400;"
        )
        header.addWidget(lbl)
        header.addStretch()
        self._val = QLabel("0.00")
        self._val.setStyleSheet(
            f"color: {T.TEXT_DIM}; font-size: 11.5px; font-weight: 500;"
        )
        header.addWidget(self._val)
        layout.addLayout(header)

        self._bar = QProgressBar()
        self._bar.setRange(0, 200)
        self._bar.setValue(100)
        self._bar.setFixedHeight(3)
        self._bar.setTextVisible(False)
        self._bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #1C1C20;
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {T.INDIGO};
                border-radius: 2px;
            }}
        """)
        layout.addWidget(self._bar)

    def set_value(self, v: float):
        mapped = int((v + 1.0) * 100)
        self._bar.setValue(max(0, min(200, mapped)))
        color = T.INDIGO if abs(v) > 0.05 else T.TEXT_DIM
        self._val.setStyleSheet(
            f"color: {color}; font-size: 11.5px; font-weight: 500;"
        )
        self._val.setText(f"{v:+.2f}")


# ── Lap times ─────────────────────────────────────────────────────────────────

class LapTimesWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        cells = [
            ("_current", "Current", "#E0DDD8"),
            ("_best",    "Best",    T.PURPLE),
            ("_last",    "Last",    "#44444E"),
        ]
        for attr, label, value_color in cells:
            cell = QWidget()
            cell.setStyleSheet(f"""
                QWidget {{
                    background-color: {T.BG_INPUT};
                    border-radius: 7px;
                    border: none;
                }}
            """)
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(10, 8, 10, 8)
            cl.setSpacing(3)

            title = QLabel(label.upper())
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title.setStyleSheet(
                "color: #33333C; font-size: 9.5px; font-weight: 600; letter-spacing: 0.5px;"
            )

            val = QLabel("--:--.---")
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val.setStyleSheet(
                f"color: {value_color}; font-size: 13px; font-weight: 500;"
                f" font-family: 'Consolas', monospace;"
            )

            cl.addWidget(title)
            cl.addWidget(val)
            setattr(self, attr, val)
            layout.addWidget(cell, 1)

    def update_times(self, lap_ms: int, best_ms: int, last_ms: int):
        self._current.setText(_ms_to_laptime(lap_ms))
        self._best.setText(_ms_to_laptime(best_ms))
        self._last.setText(_ms_to_laptime(last_ms))


# ── Telemetry trace ───────────────────────────────────────────────────────────

class TelemetryTrace(QWidget):
    def __init__(self):
        super().__init__()
        self._throttle  = deque([0.0] * TRACE_LEN, maxlen=TRACE_LEN)
        self._brake     = deque([0.0] * TRACE_LEN, maxlen=TRACE_LEN)
        self._speed     = deque([0.0] * TRACE_LEN, maxlen=TRACE_LEN)
        self._max_speed = 1.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._plot = pg.PlotWidget()
        self._plot.setBackground(T.BG_CARD)
        self._plot.showGrid(x=False, y=False)
        self._plot.setMouseEnabled(x=False, y=False)
        self._plot.hideButtons()
        self._plot.setMenuEnabled(False)
        self._plot.setYRange(0, 1, padding=0.06)

        for axis in ("left", "bottom", "right", "top"):
            self._plot.getPlotItem().hideAxis(axis)

        for y in (0.25, 0.5, 0.75):
            line = pg.InfiniteLine(
                pos=y, angle=0,
                pen=pg.mkPen(color=T.BORDER, width=1, style=Qt.PenStyle.SolidLine),
            )
            self._plot.addItem(line)

        x = list(range(TRACE_LEN))
        self._speed_curve = self._plot.plot(
            x, list(self._speed),
            pen=pg.mkPen(color="#44888A", width=1.5, style=Qt.PenStyle.DashLine),
        )
        self._throttle_curve = self._plot.plot(
            x, list(self._throttle),
            pen=pg.mkPen(color=T.GREEN, width=1.8),
        )
        self._brake_curve = self._plot.plot(
            x, list(self._brake),
            pen=pg.mkPen(color=T.ACCENT, width=1.8),
        )

        layout.addWidget(self._plot)

    def push(self, throttle: float, brake: float, speed_kmh: float):
        if speed_kmh > self._max_speed:
            self._max_speed = speed_kmh
        self._throttle.append(throttle)
        self._brake.append(brake)
        self._speed.append(speed_kmh / max(self._max_speed, 1.0))

        x = list(range(TRACE_LEN))
        self._throttle_curve.setData(x, list(self._throttle))
        self._brake_curve.setData(x, list(self._brake))
        self._speed_curve.setData(x, list(self._speed))


# ── Dashboard tab ─────────────────────────────────────────────────────────────

class DashboardTab(QWidget):
    def __init__(self, settings, on_coach_toggle, on_stop_session):
        super().__init__()
        self._settings = settings
        self._on_coach_toggle = on_coach_toggle
        self._on_stop = on_stop_session
        self._coach_enabled = settings.get("coach_enabled", False)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Topbar ────────────────────────────────────────────────────
        topbar = QWidget()
        topbar.setFixedHeight(44)
        topbar.setStyleSheet(f"""
            QWidget {{
                background-color: {T.BG_PANEL};
                border-bottom: 1px solid {T.TOPBAR_SEP};
            }}
        """)
        tb_row = QHBoxLayout(topbar)
        tb_row.setContentsMargins(20, 0, 20, 0)
        tb_row.setSpacing(8)

        self._status_dot = QWidget()
        self._status_dot.setFixedSize(6, 6)
        self._status_dot.setStyleSheet(
            "background-color: #3A3A44; border-radius: 3px;"
        )

        self._status_lbl = QLabel("Not connected — waiting for Assetto Corsa")
        self._status_lbl.setStyleSheet(
            "color: #44444E; font-size: 11.5px; font-weight: 400;"
        )

        tb_row.addWidget(self._status_dot)
        tb_row.addWidget(self._status_lbl)
        tb_row.addStretch()

        # Active track badge
        active_track = self._settings.get("active_track", "")
        track_name = active_track.replace("_", " ").title() if active_track else "No track selected"
        self._track_badge = QLabel(track_name)
        self._track_badge.setStyleSheet(f"""
            color: {T.TEXT_DIM};
            background-color: {T.BG_INPUT};
            border: 1px solid {T.BORDER};
            border-radius: 5px;
            font-size: 10.5px;
            font-weight: 500;
            padding: 3px 10px;
        """)
        tb_row.addWidget(self._track_badge)

        self._pit_badge = QLabel("Pit Lane")
        self._pit_badge.setVisible(False)
        self._pit_badge.setStyleSheet(f"""
            color: {T.ORANGE}; background-color: rgba(232,160,32,0.08);
            border: 1px solid rgba(232,160,32,0.25); border-radius: 5px;
            font-size: 10px; font-weight: 600; padding: 3px 10px;
        """)
        tb_row.addWidget(self._pit_badge)

        outer.addWidget(topbar)

        # ── Content area ──────────────────────────────────────────────
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(20, 12, 20, 16)
        root.setSpacing(10)
        outer.addWidget(content, 1)

        # ── Hero: Speed | Gear + RPM ──────────────────────────────────
        hero = QWidget()
        hl = QHBoxLayout(hero)
        hl.setContentsMargins(36, 12, 36, 12)
        hl.setSpacing(0)

        speed_col = QVBoxLayout()
        speed_col.setSpacing(0)
        speed_col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._speed_val = QLabel("0")
        self._speed_val.setObjectName("speed_value")
        self._speed_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        unit = QLabel("KM / H")
        unit.setObjectName("speed_unit")
        unit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        speed_col.addWidget(self._speed_val)
        speed_col.addWidget(unit)
        hl.addLayout(speed_col, 3)

        vd = QFrame()
        vd.setFrameShape(QFrame.Shape.VLine)
        vd.setStyleSheet(f"background-color: {T.BORDER}; max-width: 1px; border: none;")
        hl.addWidget(vd)
        hl.addSpacing(32)

        gr_col = QVBoxLayout()
        gr_col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gr_col.setSpacing(2)

        gear_lbl = QLabel("GEAR")
        gear_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gear_lbl.setStyleSheet(
            f"color: {T.TEXT_DIM}; font-size: 9px; font-weight: 600; letter-spacing: 2px;"
        )
        self._gear_val = QLabel("N")
        self._gear_val.setObjectName("gear_value")
        self._gear_val.setAlignment(Qt.AlignmentFlag.AlignCenter)

        rpm_lbl = QLabel("RPM")
        rpm_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rpm_lbl.setStyleSheet(
            f"color: {T.TEXT_DIM}; font-size: 9px; font-weight: 600; letter-spacing: 2px;"
        )
        self._rpm_val = QLabel("0")
        self._rpm_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._rpm_val.setStyleSheet(
            f"color: {T.TEXT_SECONDARY}; font-size: 14px; font-weight: 400;"
        )

        gr_col.addWidget(gear_lbl)
        gr_col.addWidget(self._gear_val)
        gr_col.addSpacing(6)
        gr_col.addWidget(rpm_lbl)
        gr_col.addWidget(self._rpm_val)
        hl.addLayout(gr_col, 1)

        root.addWidget(hero)

        # ── Middle: Inputs | Prediction + Laps ───────────────────────
        mid = QHBoxLayout()
        mid.setSpacing(10)

        # Inputs card
        inp_card = _card()
        il = QVBoxLayout(inp_card)
        il.setContentsMargins(20, 16, 20, 16)
        il.setSpacing(14)
        il.addWidget(_section_label("Inputs"))

        self._throttle_bar = InputBar("Throttle", "throttle_bar", T.GREEN)
        self._brake_bar    = InputBar("Brake",    "brake_bar",    T.RED)
        self._steering     = SteeringWidget()
        il.addWidget(self._throttle_bar)
        il.addWidget(self._brake_bar)
        il.addWidget(self._steering)
        il.addStretch()
        mid.addWidget(inp_card, 1)

        # Right column: prediction + lap times in one card
        right_card = _card()
        rl = QVBoxLayout(right_card)
        rl.setContentsMargins(20, 16, 20, 16)
        rl.setSpacing(14)

        rl.addWidget(_section_label("AI prediction"))
        self._prediction_badge = PredictionBadge()
        rl.addWidget(self._prediction_badge)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {T.BORDER}; max-height: 1px; border: none;")
        rl.addWidget(sep)

        rl.addWidget(_section_label("Lap times"))
        self._lap_times = LapTimesWidget()
        rl.addWidget(self._lap_times)
        rl.addStretch()

        mid.addWidget(right_card, 1)
        root.addLayout(mid)

        # ── Telemetry trace ───────────────────────────────────────────
        trace_card = _card()
        tl = QVBoxLayout(trace_card)
        tl.setContentsMargins(18, 14, 18, 10)
        tl.setSpacing(8)

        trace_header = QHBoxLayout()
        trace_header.addWidget(_section_label("Telemetry trace"))
        trace_header.addStretch()
        for label, color, dashed in [
            ("Speed", "#44888A", True),
            ("Throttle", T.GREEN, False),
            ("Brake", T.ACCENT, False),
        ]:
            dot = QLabel("— " if dashed else "●")
            dot.setStyleSheet(f"color: {color}; font-size: 10px;")
            txt = QLabel(label)
            txt.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 10px;")
            trace_header.addWidget(dot)
            trace_header.addWidget(txt)
            trace_header.addSpacing(10)
        tl.addLayout(trace_header)

        self._trace = TelemetryTrace()
        tl.addWidget(self._trace)
        root.addWidget(trace_card, 1)

        # ── Controls ──────────────────────────────────────────────────
        controls = QHBoxLayout()
        controls.setSpacing(8)

        self._coach_btn = QPushButton()
        self._coach_btn.setFixedHeight(40)
        self._coach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._coach_btn.clicked.connect(self._toggle_coach)
        self._refresh_coach_btn()
        controls.addWidget(self._coach_btn, 1)

        self._stop_btn = QPushButton("Stop session")
        self._stop_btn.setFixedHeight(40)
        self._stop_btn.setEnabled(False)
        self._stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stop_btn.clicked.connect(self._on_stop)
        self._stop_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 74, 74, 0.04);
                color: {T.TEXT_DIM};
                border: 1px solid rgba(255, 74, 74, 0.12);
                border-radius: 9px;
                font-weight: 400;
                font-size: 12px;
            }}
            QPushButton:enabled {{
                color: {T.ACCENT};
                border-color: rgba(255, 74, 74, 0.3);
            }}
            QPushButton:enabled:hover {{
                background-color: rgba(255, 74, 74, 0.10);
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
            self._coach_btn.setText("Coach on")
        else:
            self._coach_btn.setObjectName("toggle_off")
            self._coach_btn.setText("Coach off")
        self._coach_btn.setStyleSheet("")
        self._coach_btn.setStyle(self._coach_btn.style())

    def _toggle_coach(self):
        self._coach_enabled = not self._coach_enabled
        self._settings.set("coach_enabled", self._coach_enabled)
        self._refresh_coach_btn()
        self._on_coach_toggle(self._coach_enabled)

    def update_track_badge(self, slug: str):
        name = slug.replace("_", " ").title() if slug else "No track selected"
        self._track_badge.setText(name)

    @pyqtSlot(str)
    def on_status_changed(self, status: str):
        states = {
            "connecting": (T.ORANGE,   "Connecting to Assetto Corsa..."),
            "connected":  (T.GREEN,    "Connected"),
            "stopped":    ("#44444E",  "Not connected — waiting for Assetto Corsa"),
        }
        color, text = states.get(status, ("#44444E", status))
        self._status_dot.setStyleSheet(f"background-color: {color}; border-radius: 3px;")
        self._status_lbl.setStyleSheet(f"color: {color}; font-size: 11.5px; font-weight: 400;")
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
        self._trace.push(
            data.get("throttle", 0),
            data.get("brake", 0),
            data.get("speed_kmh", 0),
        )

    @pyqtSlot(str, float)
    def on_prediction(self, mistake_type: str, confidence: float):
        self._prediction_badge.update_prediction(mistake_type, confidence)

    def sync_coach_state(self, enabled: bool):
        self._coach_enabled = enabled
        self._refresh_coach_btn()
