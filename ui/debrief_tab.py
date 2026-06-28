import threading

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QObject

import ui.theme as T


def _card(title: str = "") -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setStyleSheet(f"""
        QFrame {{
            background-color: {T.BG_CARD};
            border: 1px solid {T.BORDER};
            border-radius: 10px;
        }}
    """)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 16, 20, 16)
    layout.setSpacing(10)
    if title:
        lbl = QLabel(title)
        lbl.setObjectName("card_title")
        layout.addWidget(lbl)
    return frame, layout


def _stat_block(label: str, value: str, accent: bool = False) -> QWidget:
    w = QWidget()
    l = QVBoxLayout(w)
    l.setContentsMargins(0, 0, 0, 0)
    l.setSpacing(2)
    lbl = QLabel(label)
    lbl.setObjectName("stat_label")
    val = QLabel(value)
    val.setObjectName("stat_value")
    if accent:
        val.setStyleSheet(f"color: {T.ACCENT}; font-size: 20px; font-weight: 700;")
    l.addWidget(lbl)
    l.addWidget(val)
    return w


def _ms_to_laptime(ms: int) -> str:
    if ms <= 0:
        return "N/A"
    total_s = ms / 1000
    m = int(total_s // 60)
    s = total_s % 60
    return f"{m}:{s:06.3f}"


class _DebriefSignals(QObject):
    finished = pyqtSignal(object)   # dict or None
    status   = pyqtSignal(str)


class DebriefTab(QWidget):
    request_switch_to_debrief = pyqtSignal()  # ask main window to switch tab

    def __init__(self):
        super().__init__()
        self._current_path: str = ""
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # Header
        header = QHBoxLayout()
        title = QLabel("Session Debrief")
        title.setStyleSheet(f"color: {T.TEXT_PRIMARY}; font-size: 18px; font-weight: 600;")
        header.addWidget(title)
        header.addStretch()
        self._run_btn = QPushButton("Run Debrief")
        self._run_btn.setObjectName("accent")
        self._run_btn.setFixedHeight(34)
        self._run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._run_btn.setEnabled(False)
        self._run_btn.clicked.connect(self._run_debrief)
        header.addWidget(self._run_btn)
        root.addLayout(header)

        # Status label
        self._status_lbl = QLabel("Load a session from History to run a debrief.")
        self._status_lbl.setStyleSheet(f"color: {T.TEXT_SECONDARY}; font-size: 13px;")
        root.addWidget(self._status_lbl)

        # Scroll area for debrief content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(14)
        self._content_layout.addStretch()

        scroll.setWidget(self._content)
        root.addWidget(scroll, 1)

    def load_session(self, path: str):
        self._current_path = path
        self._run_btn.setEnabled(True)
        self._status_lbl.setText(f"Session: {path}")
        self._clear_content()

    def _clear_content(self):
        while self._content_layout.count() > 1:
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _run_debrief(self):
        if not self._current_path:
            return
        self._run_btn.setEnabled(False)
        self._status_lbl.setText("Analyzing session with Claude...")
        self._clear_content()

        signals = _DebriefSignals(self)
        signals.finished.connect(self._on_debrief_done)
        signals.status.connect(self._status_lbl.setText)

        path = self._current_path

        def _worker():
            try:
                from debrief.claude_debrief import run_debrief
                result = run_debrief(path)
                signals.finished.emit(result)
            except Exception as e:
                signals.status.emit(f"Error: {e}")
                signals.finished.emit(None)

        threading.Thread(target=_worker, daemon=True).start()

    @pyqtSlot(object)
    def _on_debrief_done(self, debrief: dict | None):
        self._run_btn.setEnabled(True)
        if not debrief:
            self._status_lbl.setText("Debrief failed. Check your ANTHROPIC_API_KEY in .env")
            return
        self._status_lbl.setText("Debrief complete.")
        self._render(debrief)
        self.request_switch_to_debrief.emit()

    def show_auto_debrief(self, path: str, debrief: dict):
        """Called from main window when auto-debrief completes after session ends."""
        self._current_path = path
        self._run_btn.setEnabled(True)
        self._status_lbl.setText(f"Session: {path}")
        self._clear_content()
        self._render(debrief)

    def _render(self, d: dict):
        self._clear_content()

        ss   = d.get("session_summary", {})
        perf = d.get("performance", {})
        improvements = d.get("improvements", [])
        tip  = d.get("coaching_tip", "")
        vs   = d.get("vs_previous_session", "")

        # ── Session summary card ──────────────────────────────────────
        card, cl = _card("Session Summary")
        row = QHBoxLayout()
        row.setSpacing(0)
        stats = [
            ("Laps",        str(ss.get("total_laps", 0))),
            ("Best Lap",    _ms_to_laptime(ss.get("best_lap_ms", 0)), True),
            ("Avg Lap",     _ms_to_laptime(ss.get("average_lap_ms", 0))),
            ("Duration",    f"{ss.get('total_session_time_ms', 0) / 60000:.1f} min"),
        ]
        for i, stat_args in enumerate(stats):
            row.addWidget(_stat_block(*stat_args), 1)
            if i < len(stats) - 1:
                sep = QFrame()
                sep.setObjectName("v_separator")
                sep.setFrameShape(QFrame.Shape.VLine)
                sep.setStyleSheet(f"background-color: {T.BORDER}; max-width: 1px;")
                row.addWidget(sep)
        cl.addLayout(row)
        self._content_layout.insertWidget(self._content_layout.count() - 1, card)

        # ── Performance card ──────────────────────────────────────────
        card2, cl2 = _card("Performance")
        p_row = QHBoxLayout()
        p_row.setSpacing(0)
        consistency = perf.get("consistency_score", 0.0)
        p_stats = [
            ("Best Sector",   perf.get("best_sector", "N/A")),
            ("Worst Sector",  perf.get("worst_sector", "N/A")),
            ("Consistency",   f"{consistency:.0%}"),
        ]
        for i, stat_args in enumerate(p_stats):
            accent = (i == 2 and consistency >= 0.8)
            p_row.addWidget(_stat_block(*stat_args, accent=accent), 1)
            if i < len(p_stats) - 1:
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.VLine)
                sep.setStyleSheet(f"background-color: {T.BORDER}; max-width: 1px;")
                p_row.addWidget(sep)
        cl2.addLayout(p_row)

        # Mistake frequency
        mf = perf.get("mistake_frequency", {})
        if mf:
            cl2.addWidget(_h_sep())
            mf_row = QHBoxLayout()
            mf_row.setSpacing(24)
            for k, v in mf.items():
                color = T.ACCENT if v > 0 else T.TEXT_DIM
                blk = _stat_block(k.replace("_", " "), str(v))
                blk.findChild(QLabel, "", Qt.FindChildOption.FindDirectChildrenOnly)
                mf_row.addWidget(blk)
            mf_row.addStretch()
            cl2.addLayout(mf_row)

        self._content_layout.insertWidget(self._content_layout.count() - 1, card2)

        # ── Improvements card ─────────────────────────────────────────
        if improvements:
            card3, cl3 = _card("Top 3 Improvements")
            for i, imp in enumerate(improvements[:3], 1):
                row_w = QHBoxLayout()
                num = QLabel(str(i))
                num.setFixedWidth(24)
                num.setAlignment(Qt.AlignmentFlag.AlignCenter)
                num.setStyleSheet(f"""
                    color: {T.ACCENT}; font-size: 13px; font-weight: 700;
                    background-color: {T.ACCENT_DIM}; border-radius: 12px;
                    min-width: 24px; max-width: 24px;
                    min-height: 24px; max-height: 24px;
                """)
                text = QLabel(imp)
                text.setObjectName("improvement_item")
                text.setWordWrap(True)
                row_w.addWidget(num)
                row_w.addWidget(text, 1)
                row_w.setSpacing(12)
                cl3.addLayout(row_w)
            self._content_layout.insertWidget(self._content_layout.count() - 1, card3)

        # ── Coaching tip card ─────────────────────────────────────────
        if tip:
            card4, cl4 = _card("Coaching Tip")
            tip_lbl = QLabel(f'"{tip}"')
            tip_lbl.setObjectName("coaching_tip")
            tip_lbl.setWordWrap(True)
            cl4.addWidget(tip_lbl)
            self._content_layout.insertWidget(self._content_layout.count() - 1, card4)

        # ── vs Previous session ───────────────────────────────────────
        if vs:
            card5, cl5 = _card("vs Previous Session")
            vs_color = T.GREEN if "better" in vs.lower() else T.ORANGE if "worse" in vs.lower() else T.TEXT_SECONDARY
            vs_lbl = QLabel(vs)
            vs_lbl.setStyleSheet(f"color: {vs_color}; font-size: 14px; font-weight: 600;")
            vs_lbl.setWordWrap(True)
            cl5.addWidget(vs_lbl)
            self._content_layout.insertWidget(self._content_layout.count() - 1, card5)


def _h_sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"background-color: {T.BORDER}; max-height: 1px;")
    return f
