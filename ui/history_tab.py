import os
import csv
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

import ui.theme as T

SESSIONS_DIR = os.path.join("data", "sessions")


def _ms_to_laptime(ms: float) -> str:
    if ms <= 0:
        return "--:--.---"
    total_s = ms / 1000
    m = int(total_s // 60)
    s = total_s % 60
    return f"{m}:{s:06.3f}"


def _parse_session(path: str) -> dict | None:
    try:
        rows = []
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        if not rows:
            return None

        # Derive stats
        best_lap = max((int(r.get("best_lap_ms", 0) or 0) for r in rows), default=0)
        last_laps = [int(r.get("last_lap_ms", 0) or 0) for r in rows if int(r.get("last_lap_ms", 0) or 0) > 0]
        unique_laps = list(dict.fromkeys(last_laps))  # dedupe preserving order
        avg_lap = int(sum(unique_laps) / len(unique_laps)) if unique_laps else 0
        lap_count = len(unique_laps)

        # Timestamp from filename: session_YYYYMMDD_HHMMSS.csv
        basename = os.path.basename(path)
        try:
            ts_str = basename.replace("session_", "").replace(".csv", "")
            dt = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
            date_str = dt.strftime("%Y-%m-%d  %H:%M")
        except Exception:
            date_str = basename

        return {
            "path": path,
            "date": date_str,
            "laps": lap_count,
            "best_lap_ms": best_lap,
            "best_lap": _ms_to_laptime(best_lap),
            "avg_lap": _ms_to_laptime(avg_lap),
            "frame_count": len(rows),
        }
    except Exception:
        return None


class HistoryTab(QWidget):
    session_selected = pyqtSignal(str)  # emits CSV path

    def __init__(self):
        super().__init__()
        self._sessions: list[dict] = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # Header row
        header = QHBoxLayout()
        title = QLabel("Session History")
        title.setStyleSheet(f"color: {T.TEXT_PRIMARY}; font-size: 18px; font-weight: 600;")
        header.addWidget(title)
        header.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self.refresh)
        refresh_btn.setFixedHeight(34)
        header.addWidget(refresh_btn)
        root.addLayout(header)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Date", "Laps", "Best Lap", "Avg Lap", ""])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(1, 60)
        self._table.setColumnWidth(2, 110)
        self._table.setColumnWidth(3, 110)
        self._table.setColumnWidth(4, 180)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setShowGrid(False)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        root.addWidget(self._table)

        # Empty state label
        self._empty_lbl = QLabel("No sessions recorded yet.\nStart a session to see history here.")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 14px; line-height: 2;")
        self._empty_lbl.setVisible(False)
        root.addWidget(self._empty_lbl)

        self.refresh()

    def refresh(self):
        self._sessions = []
        if os.path.exists(SESSIONS_DIR):
            paths = sorted(
                [os.path.join(SESSIONS_DIR, f) for f in os.listdir(SESSIONS_DIR) if f.endswith(".csv")],
                reverse=True,
            )
            for p in paths:
                info = _parse_session(p)
                if info:
                    self._sessions.append(info)

        self._populate()

    def _populate(self):
        self._table.setRowCount(0)
        if not self._sessions:
            self._table.setVisible(False)
            self._empty_lbl.setVisible(True)
            return

        self._table.setVisible(True)
        self._empty_lbl.setVisible(False)
        self._table.setRowCount(len(self._sessions))

        for row, s in enumerate(self._sessions):
            self._table.setRowHeight(row, 72)

            for col, (val, align) in enumerate([
                (s["date"],     Qt.AlignmentFlag.AlignLeft   | Qt.AlignmentFlag.AlignVCenter),
                (str(s["laps"]), Qt.AlignmentFlag.AlignCenter),
                (s["best_lap"], Qt.AlignmentFlag.AlignCenter),
                (s["avg_lap"],  Qt.AlignmentFlag.AlignCenter),
            ]):
                item = QTableWidgetItem(val)
                item.setTextAlignment(align)
                if col == 2:
                    item.setForeground(QColor(T.ACCENT))
                self._table.setItem(row, col, item)

            # View debrief button
            container = QWidget()
            cl = QHBoxLayout(container)
            cl.setContentsMargins(10, 4, 10, 4)
            btn = QPushButton("View Debrief")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {T.ACCENT};
                    border: 1px solid {T.ACCENT_DIM};
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 500;
                    padding: 9px 18px;
                }}
                QPushButton:hover {{
                    background-color: {T.ACCENT_DIM};
                    border-color: {T.ACCENT};
                }}
            """)
            path = s["path"]
            btn.clicked.connect(lambda _, p=path: self.session_selected.emit(p))
            cl.addWidget(btn)
            self._table.setCellWidget(row, 4, container)

    def add_session(self, path: str):
        info = _parse_session(path)
        if info:
            self._sessions.insert(0, info)
            self._populate()
