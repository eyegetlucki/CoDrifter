import os
import glob
import threading

from version import __version__

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSlider, QCheckBox, QLineEdit, QPushButton,
    QFrame, QScrollArea, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject

import ui.theme as T
from ui.settings_manager import SettingsManager

MODEL_PATH = os.path.join("models", "mistake_predictor.pkl")
ENV_PATH = ".env"


def _h_sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"background-color: {T.BORDER}; max-height: 1px; border: none;")
    return f


def _section_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("section_title")
    return lbl


def _card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setStyleSheet(f"""
        QFrame {{
            background-color: {T.BG_CARD};
            border: 1px solid {T.BORDER};
            border-radius: 10px;
        }}
    """)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(22, 18, 22, 18)
    layout.setSpacing(14)
    return frame, layout


def _read_env_key(key: str) -> str:
    if not os.path.exists(ENV_PATH):
        return ""
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line.startswith(f"{key}="):
                return line[len(key) + 1:]
    return ""


def _write_env_key(key: str, value: str):
    lines = []
    found = False
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH) as f:
            lines = f.readlines()
    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}=") or line.strip() == key:
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}\n")
    with open(ENV_PATH, "w") as f:
        f.writelines(new_lines)
    os.environ[key] = value


class SliderRow(QWidget):
    value_changed = pyqtSignal(int)

    def __init__(self, label: str, min_v: int, max_v: int, current: int,
                 unit: str = "", step: int = 1):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        lbl = QLabel(label)
        lbl.setFixedWidth(200)
        lbl.setStyleSheet(f"color: {T.TEXT_PRIMARY}; font-size: 13px;")
        layout.addWidget(lbl)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(min_v, max_v)
        self._slider.setValue(current)
        self._slider.setSingleStep(step)
        self._slider.setPageStep(step)
        layout.addWidget(self._slider, 1)

        self._val_lbl = QLabel(f"{current}{unit}")
        self._val_lbl.setFixedWidth(64)
        self._val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._val_lbl.setStyleSheet(f"color: {T.ACCENT}; font-weight: 700; font-size: 13px;")
        self._unit = unit
        layout.addWidget(self._val_lbl)

        self._slider.valueChanged.connect(self._on_change)

    def _on_change(self, v: int):
        self._val_lbl.setText(f"{v}{self._unit}")
        self.value_changed.emit(v)

    def get_value(self) -> int:
        return self._slider.value()

    def set_value(self, v: int):
        self._slider.setValue(v)


class CheckRow(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, label: str, checked: bool, description: str = ""):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        row = QHBoxLayout()
        row.setSpacing(10)
        self._cb = QCheckBox(label)
        self._cb.setChecked(checked)
        self._cb.setStyleSheet(f"color: {T.TEXT_PRIMARY}; font-size: 13px;")
        self._cb.toggled.connect(self.toggled.emit)
        row.addWidget(self._cb)
        row.addStretch()
        layout.addLayout(row)

        if description:
            desc = QLabel(description)
            desc.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 11px; padding-left: 26px;")
            layout.addWidget(desc)

    def is_checked(self) -> bool:
        return self._cb.isChecked()


class _KeyRow(QWidget):
    """Single API key field with show/hide toggle."""

    def __init__(self, label: str, env_key: str, placeholder: str = "", masked: bool = True):
        super().__init__()
        self._env_key = env_key
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        lbl = QLabel(label)
        lbl.setFixedWidth(160)
        lbl.setStyleSheet(f"color: {T.TEXT_PRIMARY}; font-size: 13px;")
        layout.addWidget(lbl)

        self._field = QLineEdit()
        self._field.setPlaceholderText(placeholder)
        self._field.setText(_read_env_key(env_key))
        if masked:
            self._field.setEchoMode(QLineEdit.EchoMode.Password)
        self._field.setStyleSheet(f"""
            QLineEdit {{
                background: {T.BG_INPUT};
                border: 1px solid {T.BORDER};
                border-radius: 7px;
                color: {T.TEXT_PRIMARY};
                padding: 6px 10px;
                font-size: 12px;
                font-family: 'Consolas', monospace;
            }}
            QLineEdit:focus {{
                border-color: {T.ACCENT};
            }}
        """)
        layout.addWidget(self._field, 1)

        if masked:
            self._toggle = QPushButton("Show")
            self._toggle.setFixedWidth(52)
            self._toggle.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: 1px solid {T.BORDER};
                    border-radius: 5px;
                    color: {T.TEXT_DIM};
                    font-size: 11px;
                    padding: 4px 0;
                }}
                QPushButton:hover {{ color: {T.TEXT_PRIMARY}; }}
            """)
            self._toggle.clicked.connect(self._toggle_visibility)
            layout.addWidget(self._toggle)
        else:
            self._toggle = None

    def _toggle_visibility(self):
        if self._field.echoMode() == QLineEdit.EchoMode.Password:
            self._field.setEchoMode(QLineEdit.EchoMode.Normal)
            self._toggle.setText("Hide")
        else:
            self._field.setEchoMode(QLineEdit.EchoMode.Password)
            self._toggle.setText("Show")

    def get_value(self) -> str:
        return self._field.text().strip()


class _TrainSignals(QObject):
    log = pyqtSignal(str)
    done = pyqtSignal(bool)


class SettingsTab(QWidget):
    settings_changed = pyqtSignal()

    def __init__(self, settings: SettingsManager):
        super().__init__()
        self._settings = settings
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(0)

        title_row = QHBoxLayout()
        title = QLabel("Settings")
        title.setStyleSheet(f"color: {T.TEXT_PRIMARY}; font-size: 18px; font-weight: 600; margin-bottom: 16px;")
        title_row.addWidget(title)
        title_row.addStretch()
        ver_lbl = QLabel(f"v{__version__}")
        ver_lbl.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 11px; margin-bottom: 16px;")
        title_row.addWidget(ver_lbl)
        outer.addLayout(title_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(0, 0, 12, 20)
        root.setSpacing(16)

        s = self._settings

        # ── API Keys ─────────────────────────────────────────────────
        card0, cl0 = _card()
        cl0.addWidget(_section_title("API Keys"))

        self._el_key = _KeyRow(
            "ElevenLabs API Key", "ELEVENLABS_API_KEY",
            "sk_...", masked=True,
        )
        cl0.addWidget(self._el_key)

        self._el_voice = _KeyRow(
            "ElevenLabs Voice ID", "ELEVENLABS_VOICE_ID",
            "Voice ID from ElevenLabs dashboard", masked=False,
        )
        cl0.addWidget(self._el_voice)

        self._anthropic_key = _KeyRow(
            "Anthropic API Key", "ANTHROPIC_API_KEY",
            "sk-ant-...", masked=True,
        )
        cl0.addWidget(self._anthropic_key)

        save_row = QHBoxLayout()
        save_row.addStretch()
        self._save_keys_btn = QPushButton("Save API Keys")
        self._save_keys_btn.setFixedWidth(140)
        self._save_keys_btn.setStyleSheet(f"""
            QPushButton {{
                background: {T.ACCENT};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 7px 14px;
                font-weight: 700;
                font-size: 12px;
            }}
            QPushButton:hover {{ background: #ff4d5a; }}
            QPushButton:pressed {{ background: #c0303b; }}
        """)
        self._save_keys_btn.clicked.connect(self._save_api_keys)
        save_row.addWidget(self._save_keys_btn)
        cl0.addLayout(save_row)

        self._key_status = QLabel("")
        self._key_status.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 11px;")
        self._key_status.setAlignment(Qt.AlignmentFlag.AlignRight)
        cl0.addWidget(self._key_status)

        root.addWidget(card0)

        # ── Mistake Predictor ────────────────────────────────────────
        card_m, cl_m = _card()
        cl_m.addWidget(_section_title("Mistake Predictor"))

        model_status_row = QHBoxLayout()
        status_lbl = QLabel("Model file:")
        status_lbl.setStyleSheet(f"color: {T.TEXT_PRIMARY}; font-size: 13px;")
        model_status_row.addWidget(status_lbl)

        self._model_badge = QLabel()
        self._model_badge.setStyleSheet("font-size: 12px; font-weight: 700; padding: 3px 10px; border-radius: 5px;")
        model_status_row.addWidget(self._model_badge)
        model_status_row.addStretch()
        cl_m.addLayout(model_status_row)

        cl_m.addWidget(_h_sep())
        cl_m.addWidget(_section_title("Train from session data"))

        session_count = len(glob.glob(os.path.join("data", "sessions", "*.csv")))
        self._train_note = QLabel(
            f"{session_count} session file(s) found in data/sessions/ — "
            "collect more sessions with the rig before training for best accuracy."
            if session_count > 0 else
            "No session files found. Drive sessions first to collect training data."
        )
        self._train_note.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 11px;")
        self._train_note.setWordWrap(True)
        cl_m.addWidget(self._train_note)

        train_row = QHBoxLayout()
        train_row.addStretch()
        self._train_btn = QPushButton("Train Model")
        self._train_btn.setFixedWidth(140)
        self._train_btn.setEnabled(session_count > 0)
        self._train_btn.setStyleSheet(f"""
            QPushButton {{
                background: {T.ACCENT if session_count > 0 else T.BG_DEEP};
                color: {'white' if session_count > 0 else T.TEXT_DIM};
                border: {'none' if session_count > 0 else f'1px solid {T.BORDER}'};
                border-radius: 6px;
                padding: 7px 14px;
                font-weight: 700;
                font-size: 12px;
            }}
            QPushButton:hover {{ background: #ff4d5a; }}
            QPushButton:pressed {{ background: #c0303b; }}
            QPushButton:disabled {{ background: {T.BG_DEEP}; color: {T.TEXT_DIM}; border: 1px solid {T.BORDER}; }}
        """)
        self._train_btn.clicked.connect(self._train_model)
        train_row.addWidget(self._train_btn)
        cl_m.addLayout(train_row)

        self._train_log = QLabel("")
        self._train_log.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 11px; font-family: Consolas, monospace;")
        self._train_log.setWordWrap(True)
        self._train_log.hide()
        cl_m.addWidget(self._train_log)

        root.addWidget(card_m)
        self._refresh_model_badge()

        # ── Voice ─────────────────────────────────────────────────────
        card, cl = _card()
        cl.addWidget(_section_title("Voice"))

        self._volume = SliderRow(
            "Voice Volume", 0, 100,
            s.get("voice_volume", 80), "%",
        )
        self._volume.value_changed.connect(
            lambda v: (s.set("voice_volume", v), self.settings_changed.emit())
        )
        cl.addWidget(self._volume)

        cl.addWidget(_h_sep())
        cl.addWidget(_section_title("Callouts"))

        self._approach_cb = CheckRow(
            "Corner approach callouts",
            s.get("corner_approach_enabled", True),
            "Fires 2 seconds before each corner entry",
        )
        self._approach_cb.toggled.connect(lambda v: s.set("corner_approach_enabled", v))
        cl.addWidget(self._approach_cb)

        cl.addWidget(_section_title("Active mistake types"))
        mc = s.get("mistake_callouts", {})
        self._mistake_cbs: dict[str, CheckRow] = {}
        for key, label, desc in [
            ("LOSING_ANGLE", "Losing Angle",  "Car straightening in a corner unintentionally"),
            ("SPEED_LOSS",   "Speed Loss",     "Bleeding speed without rear slip"),
            ("SNAP_RISK",    "Snap Risk",      "Erratic yaw — on the edge of spinning"),
        ]:
            cb = CheckRow(label, mc.get(key, True), desc)
            cb.toggled.connect(lambda v, k=key: self._on_mistake_toggle(k, v))
            self._mistake_cbs[key] = cb
            cl.addWidget(cb)

        root.addWidget(card)

        # ── Timing ───────────────────────────────────────────────────
        card2, cl2 = _card()
        cl2.addWidget(_section_title("Timing"))

        self._same_cooldown = SliderRow(
            "Same-mistake cooldown", 2, 15,
            s.get("same_mistake_cooldown", 5), "s",
        )
        self._same_cooldown.value_changed.connect(lambda v: s.set("same_mistake_cooldown", v))
        cl2.addWidget(self._same_cooldown)

        self._any_cooldown = SliderRow(
            "Min gap between callouts", 1, 8,
            s.get("any_callout_cooldown", 2), "s",
        )
        self._any_cooldown.value_changed.connect(lambda v: s.set("any_callout_cooldown", v))
        cl2.addWidget(self._any_cooldown)

        root.addWidget(card2)

        # ── Model ────────────────────────────────────────────────────
        card3, cl3 = _card()
        cl3.addWidget(_section_title("AI Model"))

        self._threshold = SliderRow(
            "Confidence threshold", 60, 99,
            s.get("confidence_threshold", 90), "%",
        )
        self._threshold.value_changed.connect(lambda v: s.set("confidence_threshold", v))
        cl3.addWidget(self._threshold)
        note = QLabel("Higher = fewer but more certain callouts. Lower = more callouts, more false positives.")
        note.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 11px;")
        note.setWordWrap(True)
        cl3.addWidget(note)

        root.addWidget(card3)

        # ── Session ──────────────────────────────────────────────────
        card4, cl4 = _card()
        cl4.addWidget(_section_title("Session"))

        self._auto_debrief = CheckRow(
            "Auto-run debrief after session",
            s.get("auto_debrief", True),
            "Automatically calls Claude when you stop a session",
        )
        self._auto_debrief.toggled.connect(lambda v: s.set("auto_debrief", v))
        cl4.addWidget(self._auto_debrief)

        root.addWidget(card4)
        root.addStretch()

        # ── Restore Defaults ─────────────────────────────────────────
        restore_row = QHBoxLayout()
        restore_row.addStretch()
        self._restore_btn = QPushButton("Restore Defaults")
        self._restore_btn.setFixedHeight(36)
        self._restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._restore_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {T.TEXT_SECONDARY};
                border: 1px solid {T.BORDER};
                border-radius: 7px;
                font-size: 12px;
                font-weight: 500;
                padding: 0 18px;
            }}
            QPushButton:hover {{
                border-color: {T.BORDER_LIT};
                color: {T.TEXT_PRIMARY};
            }}
            QPushButton:pressed {{
                color: {T.ACCENT};
                border-color: {T.ACCENT};
            }}
        """)
        self._restore_btn.clicked.connect(self._restore_defaults)
        restore_row.addWidget(self._restore_btn)
        root.addLayout(restore_row)

        scroll.setWidget(content)
        outer.addWidget(scroll)

    # ── API Keys ──────────────────────────────────────────────────────

    def _save_api_keys(self):
        el_key = self._el_key.get_value()
        el_voice = self._el_voice.get_value()
        ant_key = self._anthropic_key.get_value()

        if el_key:
            _write_env_key("ELEVENLABS_API_KEY", el_key)
        if el_voice:
            _write_env_key("ELEVENLABS_VOICE_ID", el_voice)
            self._settings.set("voice_id", el_voice)
        if ant_key:
            _write_env_key("ANTHROPIC_API_KEY", ant_key)

        self._key_status.setStyleSheet(f"color: #4CAF50; font-size: 11px;")
        self._key_status.setText("Saved to .env — keys active immediately")
        self._save_keys_btn.setText("Saved ✓")

        from PyQt6.QtCore import QTimer
        QTimer.singleShot(3000, lambda: (
            self._save_keys_btn.setText("Save API Keys"),
            self._key_status.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 11px;"),
            self._key_status.setText(""),
        ))

    # ── Model ─────────────────────────────────────────────────────────

    def _refresh_model_badge(self):
        if os.path.exists(MODEL_PATH):
            self._model_badge.setText("Found ✓")
            self._model_badge.setStyleSheet(
                "font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 5px;"
                f"background: rgba(34,197,94,0.10); color: {T.GREEN};"
                f"border: 1px solid rgba(34,197,94,0.22);"
            )
        else:
            self._model_badge.setText("Missing")
            self._model_badge.setStyleSheet(
                "font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 5px;"
                f"background: rgba(255,74,74,0.08); color: {T.ACCENT};"
                f"border: 1px solid rgba(255,74,74,0.22);"
            )

    def _train_model(self):
        self._train_btn.setEnabled(False)
        self._train_btn.setText("Training…")
        self._train_log.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 11px; font-family: Consolas, monospace;")
        self._train_log.setText("Starting trainer...")
        self._train_log.show()

        sig = _TrainSignals()
        sig.log.connect(self._on_train_log)
        sig.done.connect(self._on_train_done)

        def run():
            import io
            import sys as _sys
            import importlib

            class _Capture(io.StringIO):
                def write(self, s):
                    super().write(s)
                    clean = s.strip()
                    if clean:
                        sig.log.emit(clean)

            capture = _Capture()
            old_stdout = _sys.stdout
            old_stderr = _sys.stderr
            _sys.stdout = capture
            _sys.stderr = capture
            try:
                from prediction import trainer
                importlib.reload(trainer)
                trainer.train()
                sig.done.emit(True)
            except Exception as e:
                sig.log.emit(f"Error: {e}")
                sig.done.emit(False)
            finally:
                _sys.stdout = old_stdout
                _sys.stderr = old_stderr

        threading.Thread(target=run, daemon=True).start()

    def _on_train_log(self, msg: str):
        self._train_log.setText(msg)

    def _on_train_done(self, success: bool):
        self._train_btn.setEnabled(True)
        self._train_btn.setText("Train Model")
        self._refresh_model_badge()
        if success:
            self._train_log.setStyleSheet("color: #4CAF50; font-size: 11px; font-family: Consolas, monospace;")
            self._train_log.setText("Training complete — model saved to models/mistake_predictor.pkl")
        else:
            self._train_log.setStyleSheet(f"color: {T.ACCENT}; font-size: 11px; font-family: Consolas, monospace;")

    # ── Helpers ───────────────────────────────────────────────────────

    def _on_mistake_toggle(self, key: str, value: bool):
        self._settings.set_mistake_callout(key, value)
        self.settings_changed.emit()

    def _restore_defaults(self):
        self._settings.reset_to_defaults()
        self._refresh_widgets()
        self.settings_changed.emit()

        self._restore_btn.setText("Restored ✓")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(2500, lambda: self._restore_btn.setText("Restore Defaults"))

    def _refresh_widgets(self):
        s = self._settings
        self._volume.set_value(s.get("voice_volume", 80))
        self._same_cooldown.set_value(s.get("same_mistake_cooldown", 5))
        self._any_cooldown.set_value(s.get("any_callout_cooldown", 2))
        self._threshold.set_value(s.get("confidence_threshold", 90))
        self._approach_cb._cb.setChecked(s.get("corner_approach_enabled", True))
        self._auto_debrief._cb.setChecked(s.get("auto_debrief", True))
        mc = s.get("mistake_callouts", {})
        for key, cb in self._mistake_cbs.items():
            cb._cb.setChecked(mc.get(key, True))

    def emit_all_changes(self):
        self.settings_changed.emit()

    def get_auto_debrief(self) -> bool:
        return self._auto_debrief.is_checked()
