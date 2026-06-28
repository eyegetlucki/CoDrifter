import threading
import ctypes
import sys

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QStackedWidget, QFrame, QSizePolicy,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSlot, pyqtSignal
from PyQt6.QtGui import QFont, QIcon

from version import __version__
from ui.updater import UpdateChecker

import ui.theme as T
from ui.settings_manager import SettingsManager
from ui.telemetry_worker import TelemetryWorker
from ui.dashboard_tab import DashboardTab
from ui.history_tab import HistoryTab
from ui.debrief_tab import DebriefTab
from ui.settings_tab import SettingsTab
from ui.tracks_tab import TracksTab


NAV_ITEMS = [
    ("dashboard", "Dashboard",  "▣"),
    ("history",   "History",    "◈"),
    ("debrief",   "Debrief",    "◉"),
    ("tracks",    "Tracks",     "◍"),
    ("settings",  "Settings",   "◎"),
]
PAGE_INDEX = {key: i for i, (key, _, _) in enumerate(NAV_ITEMS)}


class NavButton(QWidget):
    clicked = pyqtSignal()

    def __init__(self, icon: str, label: str):
        super().__init__()
        self._label_text = label
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(40)

        row = QHBoxLayout(self)
        row.setContentsMargins(20, 0, 16, 0)
        row.setSpacing(10)

        self._dot = QWidget()
        self._dot.setFixedSize(5, 5)
        self._dot.setStyleSheet("border-radius: 3px; background: transparent;")
        row.addWidget(self._dot)

        self._lbl = QLabel(label)
        self._lbl.setStyleSheet(
            f"color: {T.TEXT_SECONDARY}; font-size: 12px; font-weight: 400;"
        )
        row.addWidget(self._lbl)
        row.addStretch()

        self._active = False
        self._hovered = False
        self._update_style()

    def _update_style(self):
        if self._active:
            self.setStyleSheet("background-color: #1E1A1A; border-radius: 0px;")
            self._dot.setStyleSheet("border-radius: 3px; background: #FF4A4A;")
            self._lbl.setStyleSheet(
                f"color: {T.TEXT_PRIMARY}; font-size: 12px; font-weight: 500;"
            )
        elif self._hovered:
            self.setStyleSheet(f"background-color: {T.BG_HOVER}; border-radius: 0px;")
            self._dot.setStyleSheet("border-radius: 3px; background: transparent;")
            self._lbl.setStyleSheet(
                f"color: {T.TEXT_PRIMARY}; font-size: 12px; font-weight: 400;"
            )
        else:
            self.setStyleSheet("background-color: transparent;")
            self._dot.setStyleSheet("border-radius: 3px; background: transparent;")
            self._lbl.setStyleSheet(
                f"color: {T.TEXT_SECONDARY}; font-size: 12px; font-weight: 400;"
            )

    def set_active(self, active: bool):
        self._active = active
        self._update_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def enterEvent(self, event):
        self._hovered = True
        self._update_style()

    def leaveEvent(self, event):
        self._hovered = False
        self._update_style()


class MainWindow(QMainWindow):
    def __init__(self, wordmark_path: str = "driftlinewordmark.png"):
        super().__init__()
        self.setWindowTitle("CoDrifter")
        self.setMinimumSize(960, 660)
        self.resize(1140, 740)
        self._wordmark_path = wordmark_path

        self._settings = SettingsManager()
        self._worker: TelemetryWorker | None = None
        self._thread: QThread | None = None
        self._session_active = False
        self._update_installer_path: str | None = None
        self._pending_download_url: str | None = None

        self._build_ui()
        self._nav_to("dashboard")
        self._apply_titlebar_theme()

        # Check for updates in background — silent on failure
        self._updater = UpdateChecker()
        self._updater.update_available.connect(self._on_update_available)
        self._updater.download_progress.connect(self._on_download_progress)
        self._updater.download_ready.connect(self._on_download_ready)
        self._updater.download_failed.connect(self._on_download_failed)
        self._updater.check_async()

    def _apply_titlebar_theme(self):
        if sys.platform != "win32":
            return
        try:
            # Convert #0C0C0F to COLORREF (0x00BBGGRR)
            hex_color = T.BG_DEEP.lstrip("#")
            r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
            colorref = r | (g << 8) | (b << 16)

            hwnd = int(self.winId())
            DWMWA_CAPTION_COLOR = 35
            DWMWA_TEXT_COLOR    = 36
            color_c = ctypes.c_uint32(colorref)

            # Title text: near-white (#EBEBF5)
            text_hex = T.TEXT_PRIMARY.lstrip("#")
            tr, tg, tb = int(text_hex[0:2], 16), int(text_hex[2:4], 16), int(text_hex[4:6], 16)
            text_colorref = tr | (tg << 8) | (tb << 16)
            text_c = ctypes.c_uint32(text_colorref)

            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_CAPTION_COLOR,
                ctypes.byref(color_c), ctypes.sizeof(color_c),
            )
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_TEXT_COLOR,
                ctypes.byref(text_c), ctypes.sizeof(text_c),
            )
        except Exception:
            pass  # older Windows versions don't support these attributes

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        central.setStyleSheet(f"background-color: {T.BG_DEEP};")
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Sidebar ───────────────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setFixedWidth(210)
        sidebar.setStyleSheet(f"background-color: {T.BG_PANEL};")
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        sb_layout.setSpacing(0)

        # Logo area
        logo_container = QWidget()
        logo_container.setStyleSheet("background-color: transparent; border: none;")
        logo_container.setFixedHeight(72)
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setSpacing(0)

        logo = QLabel()
        logo.setStyleSheet("background: transparent; border: none;")
        from PyQt6.QtGui import QPixmap
        pixmap = QPixmap(self._wordmark_path).scaled(
            210, 72,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        logo.setPixmap(pixmap)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setScaledContents(False)
        logo_layout.addWidget(logo)
        sb_layout.addWidget(logo_container)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {T.BORDER}; max-height: 1px; border: none;")
        sb_layout.addWidget(sep)
        sb_layout.addSpacing(6)

        # Nav buttons
        self._nav_btns: dict[str, NavButton] = {}
        for key, label, icon in NAV_ITEMS:
            btn = NavButton(icon, label)
            btn.clicked.connect(lambda k=key: self._nav_to(k))
            self._nav_btns[key] = btn
            sb_layout.addWidget(btn)

        sb_layout.addStretch()

        # Start session button
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"background-color: {T.BORDER}; max-height: 1px; border: none;")
        sb_layout.addWidget(sep2)

        start_container = QWidget()
        start_container.setStyleSheet("background: transparent; border: none;")
        sc_layout = QVBoxLayout(start_container)
        sc_layout.setContentsMargins(16, 14, 16, 18)
        self._start_btn = QPushButton("▶   START SESSION")
        self._start_btn.setObjectName("accent")
        self._start_btn.setFixedHeight(42)
        self._start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_btn.clicked.connect(self._start_session)
        sc_layout.addWidget(self._start_btn)
        sb_layout.addWidget(start_container)

        outer.addWidget(sidebar)

        # ── Content area ──────────────────────────────────────────────
        right_col = QWidget()
        right_col.setStyleSheet("background: transparent;")
        right_col_layout = QVBoxLayout(right_col)
        right_col_layout.setContentsMargins(0, 0, 0, 0)
        right_col_layout.setSpacing(0)

        # Update banner — hidden until an update is detected
        self._update_banner = QWidget()
        self._update_banner.setFixedHeight(40)
        self._update_banner.setStyleSheet(
            "background-color: #2A1F00; border-bottom: 1px solid #4A3800;"
        )
        self._update_banner.setVisible(False)
        banner_row = QHBoxLayout(self._update_banner)
        banner_row.setContentsMargins(20, 0, 20, 0)
        banner_row.setSpacing(12)

        self._banner_lbl = QLabel()
        self._banner_lbl.setStyleSheet("color: #E8A020; font-size: 12px; background: transparent; border: none;")
        banner_row.addWidget(self._banner_lbl)
        banner_row.addStretch()

        self._banner_btn = QPushButton()
        self._banner_btn.setFixedHeight(26)
        self._banner_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._banner_btn.setStyleSheet(f"""
            QPushButton {{
                background: #4A3800; color: #E8A020;
                border: 1px solid #6A5200; border-radius: 5px;
                font-size: 11px; font-weight: 600; padding: 0 12px;
            }}
            QPushButton:hover {{ background: #5A4600; }}
        """)
        self._banner_btn.clicked.connect(self._on_banner_btn_clicked)
        banner_row.addWidget(self._banner_btn)

        right_col_layout.addWidget(self._update_banner)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background-color: {T.BG_DEEP};")

        self._dashboard = DashboardTab(
            self._settings,
            on_coach_toggle=self._on_coach_toggle,
            on_stop_session=self._stop_session,
        )
        self._history      = HistoryTab()
        self._debrief      = DebriefTab()
        self._tracks       = TracksTab(self._settings)
        self._settings_tab = SettingsTab(self._settings)

        self._stack.addWidget(self._dashboard)    # 0
        self._stack.addWidget(self._history)      # 1
        self._stack.addWidget(self._debrief)      # 2
        self._stack.addWidget(self._tracks)       # 3
        self._stack.addWidget(self._settings_tab) # 4

        right_col_layout.addWidget(self._stack, 1)
        outer.addWidget(right_col, 1)

        # Wire cross-tab signals
        self._history.session_selected.connect(self._on_session_selected)
        self._debrief.request_switch_to_debrief.connect(lambda: self._nav_to("debrief"))
        self._tracks.active_track_changed.connect(self._on_active_track_changed)
        self._settings_tab.settings_changed.connect(self._on_settings_changed)

    def _nav_to(self, key: str):
        for k, btn in self._nav_btns.items():
            btn.set_active(k == key)
        self._stack.setCurrentIndex(PAGE_INDEX[key])
        if key == "history":
            self._history.refresh()

    def _start_session(self):
        if self._session_active:
            return

        self._thread = QThread()
        self._worker = TelemetryWorker(self._settings)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.telemetry_updated.connect(self._dashboard.on_telemetry)
        self._worker.prediction_updated.connect(self._dashboard.on_prediction)
        self._worker.status_changed.connect(self._dashboard.on_status_changed)
        self._worker.status_changed.connect(self._on_worker_status)
        self._worker.session_ended.connect(self._on_session_ended)

        self._session_active = True
        self._start_btn.setEnabled(False)
        self._start_btn.setText("◼   SESSION ACTIVE")
        self._thread.start()
        self._nav_to("dashboard")

    def _stop_session(self):
        if self._worker:
            self._worker.stop()

    def _on_worker_status(self, status: str):
        if status == "stopped":
            self._session_active = False
            self._start_btn.setEnabled(True)
            self._start_btn.setText("▶   START SESSION")
            if self._thread:
                self._thread.quit()
                self._thread.wait()
                self._thread = None
            self._worker = None

    def _on_session_ended(self, path: str):
        self._history.add_session(path)

        if self._settings.get("auto_debrief", True):
            def _run():
                try:
                    from debrief.claude_debrief import run_debrief
                    result = run_debrief(path)
                    if result:
                        self._debrief.show_auto_debrief(path, result)
                        self._nav_to("debrief")
                except Exception:
                    pass
            threading.Thread(target=_run, daemon=True).start()

    def _on_session_selected(self, path: str):
        self._debrief.load_session(path)
        self._nav_to("debrief")

    def _on_coach_toggle(self, enabled: bool):
        if self._worker:
            self._worker.set_coach_enabled(enabled)

    def _on_active_track_changed(self, slug: str):
        self._dashboard.update_track_badge(slug)

    def _on_settings_changed(self):
        if self._worker:
            self._worker.reload_settings()

    # ── Update slots ──────────────────────────────────────────────────

    def _on_update_available(self, version: str, url: str):
        self._pending_download_url = url
        self._banner_lbl.setText(f"↓  CoDrifter v{version} is available")
        self._banner_btn.setText("Download & Install")
        self._banner_btn.setEnabled(True)
        self._update_banner.setVisible(True)

    def _on_banner_btn_clicked(self):
        if self._update_installer_path:
            self._install_update()
        elif self._pending_download_url:
            self._banner_btn.setEnabled(False)
            self._banner_btn.setText("Downloading…")
            self._updater.download_async(self._pending_download_url)

    def _on_download_progress(self, pct: int):
        self._banner_btn.setText(f"Downloading…  {pct}%")

    def _on_download_ready(self, path: str):
        self._update_installer_path = path
        self._banner_lbl.setText("Update downloaded — ready to install")
        self._banner_btn.setText("Restart & Install")
        self._banner_btn.setEnabled(True)

    def _on_download_failed(self, error: str):
        self._banner_lbl.setText("Download failed — try again later")
        self._banner_btn.setText("Retry")
        self._banner_btn.setEnabled(True)
        self._update_installer_path = None

    def _install_update(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("Install update")
        msg.setText(
            "CoDrifter will close and the update will install automatically.\n\n"
            "Any active session will be stopped first."
        )
        msg.setStandardButtons(
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        msg.setDefaultButton(QMessageBox.StandardButton.Ok)
        if msg.exec() == QMessageBox.StandardButton.Ok:
            self._updater.install(self._update_installer_path)

    def closeEvent(self, event):
        self._stop_session()
        if self._thread:
            self._thread.quit()
            self._thread.wait()
        event.accept()
