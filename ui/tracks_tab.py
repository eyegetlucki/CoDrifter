import os
import json
import time
import re
import threading

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QLineEdit, QFileDialog, QInputDialog,
    QSizePolicy, QDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, pyqtSlot, QTimer, QSize
from PyQt6.QtGui import QColor, QKeySequence, QIcon, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer

import ui.theme as T

TRACKS_DIR = os.path.join("data", "track_maps")
LEGACY_MAP  = os.path.join("data", "corner_map.json")
CORNER_TYPES = ["TIGHT", "MEDIUM", "HAIRPIN", "SWEEPING", "FEEDER"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _trash_icon(color: str = "#888888", size: int = 16) -> QIcon:
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">
      <line x1="3" y1="4.5" x2="13" y2="4.5" stroke="{color}" stroke-width="1.3" stroke-linecap="round"/>
      <path d="M6 4.5V3.5a0.5 0.5 0 0 1 0.5-0.5h3a0.5 0.5 0 0 1 0.5 0.5v1"
            stroke="{color}" stroke-width="1.3" fill="none" stroke-linecap="round"/>
      <path d="M4 4.5l0.8 8.5a0.5 0.5 0 0 0 0.5 0.5h5.4a0.5 0.5 0 0 0 0.5-0.5L12 4.5"
            stroke="{color}" stroke-width="1.3" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
      <line x1="6.5" y1="7" x2="6.2" y2="11" stroke="{color}" stroke-width="1.1" stroke-linecap="round"/>
      <line x1="8"   y1="7" x2="8"   y2="11" stroke="{color}" stroke-width="1.1" stroke-linecap="round"/>
      <line x1="9.5" y1="7" x2="9.8" y2="11" stroke="{color}" stroke-width="1.1" stroke-linecap="round"/>
    </svg>""".encode()
    renderer = QSvgRenderer(svg)
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(p)
    p.end()
    return QIcon(px)


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return s or "track"


def _maybe_migrate_legacy():
    """Auto-import legacy corner_map.json as Drift Playground 2021 on first run."""
    os.makedirs(TRACKS_DIR, exist_ok=True)
    if os.listdir(TRACKS_DIR):
        return
    if not os.path.exists(LEGACY_MAP):
        return
    with open(LEGACY_MAP) as f:
        corners = json.load(f)
    track = {"name": "Drift Playground 2021", "track_length_m": 783.413, "corners": corners}
    with open(os.path.join(TRACKS_DIR, "drift_playground_2021.json"), "w") as f:
        json.dump(track, f, indent=2)


def _load_track(path: str) -> dict | None:
    try:
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, list):
            name = os.path.splitext(os.path.basename(path))[0].replace("_", " ").title()
            return {"name": name, "track_length_m": 783.413, "corners": data}
        return data
    except Exception:
        return None


def _all_tracks() -> list[tuple[str, dict]]:
    os.makedirs(TRACKS_DIR, exist_ok=True)
    result = []
    for fn in sorted(os.listdir(TRACKS_DIR)):
        if not fn.endswith(".json"):
            continue
        slug = fn[:-5]
        data = _load_track(os.path.join(TRACKS_DIR, fn))
        if data:
            result.append((slug, data))
    return result


def _save_track(slug: str, data: dict):
    os.makedirs(TRACKS_DIR, exist_ok=True)
    with open(os.path.join(TRACKS_DIR, f"{slug}.json"), "w") as f:
        json.dump(data, f, indent=2)


# ── Mapping signals ───────────────────────────────────────────────────────────

class _MappingSignals(QObject):
    position_updated = pyqtSignal(float, float)   # x, speed_kmh
    mark_added       = pyqtSignal(int, float)      # count, x
    mark_undone      = pyqtSignal(int)             # new count
    finished         = pyqtSignal(list)            # list of (x, z) tuples
    status           = pyqtSignal(str)
    error            = pyqtSignal(str)


# ── Key bind overlay ─────────────────────────────────────────────────────────

class _KeyBindDialog(QDialog):
    def __init__(self, action_label: str, parent=None):
        super().__init__(parent)
        self.result_key: str | None = None
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(340, 160)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {T.BG_CARD};
                border: 1px solid {T.BORDER_LIT};
                border-radius: 12px;
            }}
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(28, 24, 28, 24)
        cl.setSpacing(10)
        cl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel(f"Bind {action_label} key")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {T.TEXT_PRIMARY}; font-size: 14px; font-weight: 600; border: none;")

        sub = QLabel("Press any key  ·  Esc to cancel")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 11px; border: none;")

        self._waiting_lbl = QLabel("Waiting for key...")
        self._waiting_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._waiting_lbl.setStyleSheet(
            f"color: {T.ACCENT}; font-size: 13px; font-weight: 600; border: none;"
        )

        cl.addWidget(title)
        cl.addWidget(sub)
        cl.addSpacing(4)
        cl.addWidget(self._waiting_lbl)
        outer.addWidget(card)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.reject()
            return
        key_str = QKeySequence(key).toString()
        if key_str:
            self.result_key = key_str
            self._waiting_lbl.setText(key_str)
            QTimer.singleShot(200, self.accept)

    def showEvent(self, event):
        if self.parent():
            parent_rect = self.parent().window().geometry()
            x = parent_rect.x() + (parent_rect.width() - self.width()) // 2
            y = parent_rect.y() + (parent_rect.height() - self.height()) // 2
            self.move(x, y)
        super().showEvent(event)


# ── Track list item ───────────────────────────────────────────────────────────

class _TrackItem(QWidget):
    clicked = pyqtSignal(str)

    def __init__(self, slug: str, name: str, corner_count: int, active: bool):
        super().__init__()
        self._slug = slug
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("background: transparent; border-radius: 8px;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        self._dot = QWidget()
        self._dot.setFixedSize(6, 6)
        self._dot.setStyleSheet(
            f"background-color: {T.GREEN if active else T.TEXT_DIM}; border-radius: 3px;"
        )
        layout.addWidget(self._dot)

        col = QVBoxLayout()
        col.setSpacing(2)
        self._name_lbl = QLabel(name)
        self._name_lbl.setStyleSheet(
            f"color: {T.TEXT_PRIMARY if active else T.TEXT_SECONDARY}; "
            f"font-size: 13px; font-weight: {'600' if active else '400'};"
        )
        self._count_lbl = QLabel(f"{corner_count} corners")
        self._count_lbl.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 10px;")
        col.addWidget(self._name_lbl)
        col.addWidget(self._count_lbl)
        layout.addLayout(col, 1)

    def set_selected(self, selected: bool):
        self.setStyleSheet(
            f"background-color: {T.BG_HOVER if selected else 'transparent'}; border-radius: 8px;"
        )

    def mousePressEvent(self, event):
        self.clicked.emit(self._slug)


# ── Main tab ──────────────────────────────────────────────────────────────────

class TracksTab(QWidget):
    active_track_changed = pyqtSignal(str)   # slug of newly active track

    def __init__(self, settings):
        super().__init__()
        self._settings = settings
        self._selected_slug = ""
        self._track_items: dict[str, _TrackItem] = {}
        self._mapping_stop = threading.Event()
        self._undo_event   = threading.Event()
        self._mapping_thread: threading.Thread | None = None

        # refs to right-panel widgets (rebuilt each time a track is selected)
        self._name_field: QLineEdit | None = None
        self._length_field: QLineEdit | None = None
        self._corner_table: QTableWidget | None = None
        self._map_entries_btn: QPushButton | None = None
        self._map_exits_btn: QPushButton | None = None
        self._start_panel: QWidget | None = None
        self._mapping_panel: QWidget | None = None
        self._mapping_mode_lbl: QLabel | None = None
        self._mapping_pos_lbl: QLabel | None = None
        self._mapping_marks_lbl: QLabel | None = None
        self._entry_key_btn: QPushButton | None = None
        self._exit_key_btn: QPushButton | None = None
        self._undo_key_btn: QPushButton | None = None

        self._build_ui()
        _maybe_migrate_legacy()

        # Auto-set active track if none is saved yet
        if not self._settings.get("active_track", ""):
            tracks = _all_tracks()
            if tracks:
                self._settings.set("active_track", tracks[0][0])

        self._refresh_list()

    # ── UI construction ───────────────────────────────────────────────

    def _build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Left panel
        left = QWidget()
        left.setFixedWidth(230)
        left.setStyleSheet(
            f"QWidget {{ background-color: {T.BG_PANEL}; border-right: 1px solid {T.BORDER}; }}"
        )
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(0)

        # Left header
        lh = QWidget()
        lh.setStyleSheet("background: transparent;")
        lhv = QVBoxLayout(lh)
        lhv.setContentsMargins(14, 16, 14, 12)
        lhv.setSpacing(10)

        lhv.addWidget(QLabel("Tracks", styleSheet=f"color: {T.TEXT_PRIMARY}; font-size: 15px; font-weight: 600;"))

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        new_btn = QPushButton("+ New")
        new_btn.setFixedHeight(30)
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.setStyleSheet(f"""
            QPushButton {{
                background: {T.ACCENT}; color: white; border: none;
                border-radius: 6px; font-size: 11px; font-weight: 600; padding: 0 12px;
            }}
            QPushButton:hover {{ background: {T.ACCENT_GLOW}; }}
        """)
        new_btn.clicked.connect(self._new_track)

        import_btn = QPushButton("Import")
        import_btn.setFixedHeight(30)
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {T.TEXT_SECONDARY};
                border: 1px solid {T.BORDER}; border-radius: 6px;
                font-size: 11px; padding: 0 12px;
            }}
            QPushButton:hover {{ border-color: {T.BORDER_LIT}; color: {T.TEXT_PRIMARY}; }}
        """)
        import_btn.clicked.connect(self._import_track)

        btn_row.addWidget(new_btn)
        btn_row.addWidget(import_btn)
        lhv.addLayout(btn_row)
        lv.addWidget(lh)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {T.BORDER}; max-height: 1px; border: none;")
        lv.addWidget(sep)

        self._list_scroll = QScrollArea()
        self._list_scroll.setWidgetResizable(True)
        self._list_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._list_scroll.setStyleSheet("background: transparent;")

        self._list_content = QWidget()
        self._list_content.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_content)
        self._list_layout.setContentsMargins(8, 8, 8, 8)
        self._list_layout.setSpacing(2)
        self._list_layout.addStretch()
        self._list_scroll.setWidget(self._list_content)
        lv.addWidget(self._list_scroll, 1)
        outer.addWidget(left)

        # Right panel
        self._right = QWidget()
        self._right.setStyleSheet("background: transparent;")
        self._right_layout = QVBoxLayout(self._right)
        self._right_layout.setContentsMargins(24, 20, 24, 20)
        self._right_layout.setSpacing(14)
        self._show_empty_state()
        outer.addWidget(self._right, 1)

    def _clear_right(self):
        def _purge(layout):
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    _purge(item.layout())
        _purge(self._right_layout)

    def _show_empty_state(self):
        self._clear_right()
        lbl = QLabel("Select a track or create a new one.")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 14px;")
        self._right_layout.addStretch()
        self._right_layout.addWidget(lbl)
        self._right_layout.addStretch()

    # ── Track list ────────────────────────────────────────────────────

    def _refresh_list(self):
        for item in self._track_items.values():
            item.setParent(None)
        self._track_items.clear()
        while self._list_layout.count():
            self._list_layout.takeAt(0)

        active_slug = self._settings.get("active_track", "")
        tracks = _all_tracks()

        if not tracks:
            empty = QLabel("No tracks yet.\nCreate or import one.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 11px;")
            self._list_layout.addWidget(empty)
        else:
            for slug, data in tracks:
                item = _TrackItem(
                    slug,
                    data.get("name", slug),
                    len(data.get("corners", [])),
                    slug == active_slug,
                )
                item.clicked.connect(self._select_track)
                item.set_selected(slug == self._selected_slug)
                self._track_items[slug] = item
                self._list_layout.addWidget(item)

        self._list_layout.addStretch()

    def _select_track(self, slug: str):
        self._selected_slug = slug
        for s, item in self._track_items.items():
            item.set_selected(s == slug)
        data = _load_track(os.path.join(TRACKS_DIR, f"{slug}.json"))
        if data:
            self._show_track_detail(slug, data)

    # ── Track detail panel ────────────────────────────────────────────

    def _show_track_detail(self, slug: str, data: dict):
        self._clear_right()
        active_slug = self._settings.get("active_track", "")
        is_active = slug == active_slug

        # Header — name field + save on row 1, action buttons on row 2
        name_row = QHBoxLayout()
        name_row.setSpacing(8)

        self._name_field = QLineEdit(data.get("name", slug))
        self._name_field.setFixedHeight(36)
        self._name_field.setStyleSheet(f"""
            QLineEdit {{
                background: {T.BG_CARD}; border: 1px solid {T.BORDER};
                border-radius: 7px; padding: 0 12px;
                color: {T.TEXT_PRIMARY}; font-size: 14px; font-weight: 600;
            }}
            QLineEdit:focus {{ border-color: {T.ACCENT}; }}
        """)
        name_row.addWidget(self._name_field, 1)

        save_btn = QPushButton("Save name")
        save_btn.setFixedHeight(36)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {T.TEXT_SECONDARY};
                border: 1px solid {T.BORDER}; border-radius: 7px;
                font-size: 12px; padding: 0 14px;
            }}
            QPushButton:hover {{ border-color: {T.BORDER_LIT}; color: {T.TEXT_PRIMARY}; }}
        """)
        save_btn.clicked.connect(lambda: self._save_name(slug))
        name_row.addWidget(save_btn)
        self._right_layout.addLayout(name_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        active_btn = QPushButton("✓  Active" if is_active else "Set Active")
        active_btn.setFixedHeight(32)
        active_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        active_btn.setEnabled(not is_active)
        active_btn.setStyleSheet(f"""
            QPushButton {{
                background: {'#0A2010' if is_active else T.ACCENT};
                color: {T.GREEN if is_active else 'white'};
                border: {'1px solid #1A4020' if is_active else 'none'};
                border-radius: 7px; font-size: 12px; font-weight: 600; padding: 0 16px;
            }}
            QPushButton:enabled:hover {{ background: {T.ACCENT_GLOW}; }}
            QPushButton:disabled {{ background: #0A2010; color: {T.GREEN}; }}
        """)
        active_btn.clicked.connect(lambda: self._set_active(slug))
        action_row.addWidget(active_btn)

        del_btn = QPushButton("Delete track")
        del_btn.setFixedHeight(32)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {T.TEXT_DIM};
                border: 1px solid {T.BORDER}; border-radius: 7px; font-size: 12px; padding: 0 14px;
            }}
            QPushButton:hover {{ color: {T.ACCENT}; border-color: {T.ACCENT}; }}
        """)
        del_btn.clicked.connect(lambda: self._delete_track(slug))
        action_row.addWidget(del_btn)
        action_row.addStretch()
        self._right_layout.addLayout(action_row)

        # Track length row
        length_row = QHBoxLayout()
        length_row.setSpacing(8)

        length_lbl = QLabel("TRACK LENGTH")
        length_lbl.setStyleSheet(
            f"color: {T.TEXT_SECONDARY}; font-size: 10px; font-weight: 600; letter-spacing: 1.5px;"
        )
        self._right_layout.addWidget(length_lbl)

        self._length_field = QLineEdit(str(data.get("track_length_m", 783.413)))
        self._length_field.setFixedHeight(32)
        self._length_field.setFixedWidth(110)
        self._length_field.setPlaceholderText("meters")
        self._length_field.setStyleSheet(f"""
            QLineEdit {{
                background: {T.BG_CARD}; border: 1px solid {T.BORDER};
                border-radius: 7px; padding: 0 10px;
                color: {T.TEXT_PRIMARY}; font-size: 13px; font-family: Consolas, monospace;
            }}
            QLineEdit:focus {{ border-color: {T.ACCENT}; }}
        """)

        save_length_btn = QPushButton("Save")
        save_length_btn.setFixedHeight(32)
        save_length_btn.setFixedWidth(70)
        save_length_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_length_btn.clicked.connect(lambda: self._save_track_length(slug))

        auto_btn = QPushButton("Auto-detect from AC folder")
        auto_btn.setFixedHeight(32)
        auto_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        auto_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {T.TEXT_SECONDARY};
                border: 1px solid {T.BORDER}; border-radius: 7px;
                font-size: 11px; padding: 0 12px;
            }}
            QPushButton:hover {{ border-color: {T.BORDER_LIT}; color: {T.TEXT_PRIMARY}; }}
        """)
        auto_btn.clicked.connect(lambda: self._auto_detect_length(slug))

        length_row.addWidget(self._length_field)
        length_row.addWidget(save_length_btn)
        length_row.addWidget(auto_btn)
        length_row.addStretch()
        self._right_layout.addLayout(length_row)

        # Corners label
        corners_lbl = QLabel("CORNERS")
        corners_lbl.setStyleSheet(
            f"color: {T.TEXT_SECONDARY}; font-size: 10px; font-weight: 600; letter-spacing: 1.5px;"
        )
        self._right_layout.addWidget(corners_lbl)

        # Corner table
        self._corner_table = QTableWidget()
        self._corner_table.setColumnCount(5)
        self._corner_table.setHorizontalHeaderLabels(["#", "Type", "Entry", "Exit", ""])
        hh = self._corner_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self._corner_table.setColumnWidth(0, 50)
        self._corner_table.setColumnWidth(1, 130)
        self._corner_table.setColumnWidth(4, 36)
        self._corner_table.verticalHeader().setVisible(False)
        self._corner_table.setShowGrid(False)
        self._corner_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._corner_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked)
        self._corner_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._corner_table.setStyleSheet(
            f"QTableWidget {{ background: {T.BG_CARD}; border: 1px solid {T.BORDER}; border-radius: 10px; }}"
        )
        self._populate_corner_table(data.get("corners", []), slug)
        self._right_layout.addWidget(self._corner_table, 1)

        # Mapping card
        map_card = QFrame()
        map_card.setStyleSheet(
            f"QFrame {{ background: {T.BG_CARD}; border: 1px solid {T.BORDER}; border-radius: 10px; }}"
        )
        mcl = QVBoxLayout(map_card)
        mcl.setContentsMargins(18, 14, 18, 14)
        mcl.setSpacing(12)

        mcl.addWidget(QLabel(
            "MAP CORNERS",
            styleSheet=f"color: {T.TEXT_SECONDARY}; font-size: 10px; font-weight: 600; letter-spacing: 1.5px;"
        ))

        # Key bind row
        key_row = QHBoxLayout()
        key_row.setSpacing(12)

        _bind_btn_style = f"""
            QPushButton {{
                background: {T.BG_DEEP}; border: 1px solid {T.BORDER_LIT};
                border-radius: 6px; color: {T.TEXT_PRIMARY};
                font-size: 12px; font-family: Consolas, monospace;
                padding: 0 10px;
            }}
            QPushButton:hover {{
                border-color: {T.ACCENT}; color: {T.ACCENT};
            }}
        """

        def _bind_pair(label: str, default: str, action: str):
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 11px;")
            btn = QPushButton(default)
            btn.setFixedHeight(28)
            btn.setFixedWidth(72)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(_bind_btn_style)
            btn.setToolTip(f"Click to rebind {action} key")
            btn.clicked.connect(lambda _, b=btn, a=action: self._rebind_key(a, b))
            pair = QHBoxLayout()
            pair.setSpacing(6)
            pair.addWidget(lbl)
            pair.addWidget(btn)
            key_row.addLayout(pair)
            return btn

        self._entry_key_btn = _bind_pair("Entry key", "F10", "Entry")
        self._exit_key_btn  = _bind_pair("Exit key",  "F11", "Exit")
        self._undo_key_btn  = _bind_pair("Undo key",  "F12", "Undo")
        key_row.addStretch()

        hint = QLabel("Avoid F1–F5  ·  common AC hotkeys")
        hint.setStyleSheet(f"color: {T.TEXT_DIM}; font-size: 10px;")
        key_row.addWidget(hint)
        mcl.addLayout(key_row)

        # Start buttons (shown when not mapping)
        self._start_panel = QWidget()
        spv = QHBoxLayout(self._start_panel)
        spv.setContentsMargins(0, 0, 0, 0)
        spv.setSpacing(10)

        self._map_entries_btn = QPushButton("Start Entry Mapping")
        self._map_entries_btn.setFixedHeight(38)
        self._map_entries_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._map_entries_btn.clicked.connect(lambda: self._start_mapping(slug, "entries"))

        self._map_exits_btn = QPushButton("Start Exit Mapping")
        self._map_exits_btn.setFixedHeight(38)
        self._map_exits_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._map_exits_btn.setEnabled(bool(data.get("corners")))
        self._map_exits_btn.clicked.connect(lambda: self._start_mapping(slug, "exits"))

        spv.addWidget(self._map_entries_btn, 1)
        spv.addWidget(self._map_exits_btn, 1)
        mcl.addWidget(self._start_panel)

        # Live mapping panel (hidden until active)
        self._mapping_panel = QWidget()
        self._mapping_panel.setVisible(False)
        mpv = QVBoxLayout(self._mapping_panel)
        mpv.setContentsMargins(0, 0, 0, 0)
        mpv.setSpacing(8)

        self._mapping_mode_lbl = QLabel("")
        self._mapping_mode_lbl.setStyleSheet(
            f"color: {T.ACCENT}; font-size: 12px; font-weight: 600;"
        )
        self._mapping_pos_lbl = QLabel("Connecting to AC...")
        self._mapping_pos_lbl.setStyleSheet(
            f"color: {T.TEXT_PRIMARY}; font-size: 13px; font-family: Consolas, monospace;"
        )
        self._mapping_marks_lbl = QLabel("Marks: 0")
        self._mapping_marks_lbl.setStyleSheet(f"color: {T.TEXT_SECONDARY}; font-size: 12px;")

        save_row = QHBoxLayout()
        undo_btn = QPushButton("Undo Last")
        undo_btn.setFixedHeight(34)
        undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        undo_btn.clicked.connect(self._undo_last_mark)

        self._save_btn = QPushButton("Save & Finish")
        self._save_btn.setFixedHeight(34)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.setObjectName("accent")
        self._save_btn.clicked.connect(self._finish_mapping)

        save_row.addWidget(undo_btn)
        save_row.addStretch()
        save_row.addWidget(self._save_btn)

        mpv.addWidget(self._mapping_mode_lbl)
        mpv.addWidget(self._mapping_pos_lbl)
        mpv.addWidget(self._mapping_marks_lbl)
        mpv.addLayout(save_row)
        mcl.addWidget(self._mapping_panel)

        self._right_layout.addWidget(map_card)

    def _populate_corner_table(self, corners: list, slug: str):
        self._corner_table.blockSignals(True)
        self._corner_table.setRowCount(len(corners))
        for i, corner in enumerate(corners):
            self._corner_table.setRowHeight(i, 44)

            num = QTableWidgetItem(str(i + 1))
            num.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            num.setFlags(Qt.ItemFlag.ItemIsEnabled)
            num.setForeground(QColor(T.TEXT_DIM))
            self._corner_table.setItem(i, 0, num)

            combo = QComboBox()
            for ct in CORNER_TYPES:
                combo.addItem(ct)
            current_type = corner.get("type", "MEDIUM")
            if current_type in CORNER_TYPES:
                combo.setCurrentText(current_type)
            combo.setStyleSheet(f"""
                QComboBox {{
                    background: {T.BG_HOVER}; color: {T.TEXT_PRIMARY};
                    border: none; border-radius: 4px; padding: 4px 8px; font-size: 12px;
                }}
                QComboBox::drop-down {{ border: none; width: 20px; }}
                QComboBox QAbstractItemView {{
                    background: {T.BG_CARD}; color: {T.TEXT_PRIMARY};
                    border: 1px solid {T.BORDER};
                    selection-background-color: {T.ACCENT_DIM};
                }}
            """)
            combo.currentTextChanged.connect(lambda t, idx=i, s=slug: self._on_type_changed(s, idx, t))
            self._corner_table.setCellWidget(i, 1, combo)

            cx = corner.get("x")
            cz = corner.get("z")
            entry_str = f"{cx:.1f}, {cz:.1f}" if cx is not None and cz is not None else "--"
            entry_item = QTableWidgetItem(entry_str)
            entry_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            entry_item.setForeground(QColor(T.TEXT_PRIMARY if cx is not None else T.TEXT_DIM))
            self._corner_table.setItem(i, 2, entry_item)

            ex = corner.get("exit_x")
            ez = corner.get("exit_z")
            exit_str = f"{ex:.1f}, {ez:.1f}" if ex is not None and ez is not None else "--"
            exit_item = QTableWidgetItem(exit_str)
            exit_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            exit_item.setForeground(QColor(T.TEXT_SECONDARY if ex is not None else T.TEXT_DIM))
            self._corner_table.setItem(i, 3, exit_item)

            del_btn = QPushButton()
            del_btn.setIcon(_trash_icon("#666666"))
            del_btn.setToolTip("Delete this corner")
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setIconSize(QSize(14, 14))
            del_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; border: none; margin: 6px 8px;
                }}
                QPushButton:hover {{ background: transparent; }}
            """)
            del_btn.clicked.connect(lambda _, row=i, s=slug: self._delete_corner(s, row))
            del_btn.enterEvent = lambda e, b=del_btn: b.setIcon(_trash_icon(T.ACCENT))
            del_btn.leaveEvent = lambda e, b=del_btn: b.setIcon(_trash_icon("#666666"))
            self._corner_table.setCellWidget(i, 4, del_btn)

        self._corner_table.blockSignals(False)
        try:
            self._corner_table.itemChanged.disconnect()
        except (RuntimeError, TypeError):
            pass
        self._corner_table.itemChanged.connect(lambda item: self._on_cell_edited(slug, item))

    # ── Actions ───────────────────────────────────────────────────────

    def _on_type_changed(self, slug: str, row: int, corner_type: str):
        data = _load_track(os.path.join(TRACKS_DIR, f"{slug}.json"))
        if data and row < len(data["corners"]):
            data["corners"][row]["type"] = corner_type
            _save_track(slug, data)

    def _on_cell_edited(self, slug: str, item: QTableWidgetItem):
        col, row = item.column(), item.row()
        if col not in (2, 3):
            return
        try:
            val = round(float(item.text()), 4)
        except ValueError:
            return
        data = _load_track(os.path.join(TRACKS_DIR, f"{slug}.json"))
        if not data or row >= len(data["corners"]):
            return
        key = "position" if col == 2 else "exit_position"
        data["corners"][row][key] = val
        _save_track(slug, data)

    def _delete_corner(self, slug: str, row: int):
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox(self)
        msg.setWindowTitle("Delete corner")
        msg.setText(f"Delete corner {row + 1}? This cannot be undone.")
        msg.setStandardButtons(QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes)
        msg.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if msg.exec() != QMessageBox.StandardButton.Yes:
            return
        data = _load_track(os.path.join(TRACKS_DIR, f"{slug}.json"))
        if not data or row >= len(data["corners"]):
            return
        data["corners"].pop(row)
        for i, c in enumerate(data["corners"]):
            c["corner"] = i + 1
        _save_track(slug, data)
        self._populate_corner_table(data["corners"], slug)
        self._refresh_list()
        if self._map_exits_btn:
            self._map_exits_btn.setEnabled(bool(data["corners"]))

    def _save_name(self, old_slug: str):
        if not self._name_field:
            return
        new_name = self._name_field.text().strip()
        if not new_name:
            return
        new_slug = _slug(new_name)
        data = _load_track(os.path.join(TRACKS_DIR, f"{old_slug}.json"))
        if not data:
            return
        data["name"] = new_name
        _save_track(old_slug, data)
        if old_slug != new_slug:
            old_path = os.path.join(TRACKS_DIR, f"{old_slug}.json")
            new_path = os.path.join(TRACKS_DIR, f"{new_slug}.json")
            os.rename(old_path, new_path)
            if self._settings.get("active_track") == old_slug:
                self._settings.set("active_track", new_slug)
                self.active_track_changed.emit(new_slug)
            self._selected_slug = new_slug
        self._refresh_list()
        self._select_track(new_slug)

    def _set_active(self, slug: str):
        self._settings.set("active_track", slug)
        self.active_track_changed.emit(slug)
        self._refresh_list()
        self._select_track(slug)

    def _delete_track(self, slug: str):
        path = os.path.join(TRACKS_DIR, f"{slug}.json")
        if os.path.exists(path):
            os.remove(path)
        if self._settings.get("active_track") == slug:
            self._settings.set("active_track", "")
            self.active_track_changed.emit("")
        self._selected_slug = ""
        self._refresh_list()
        self._show_empty_state()

    def _new_track(self):
        name, ok = QInputDialog.getText(self, "New Track", "Track name:")
        if not ok or not name.strip():
            return
        slug = _slug(name.strip())
        path = os.path.join(TRACKS_DIR, f"{slug}.json")
        if not os.path.exists(path):
            _save_track(slug, {"name": name.strip(), "track_length_m": 783.413, "corners": []})
        self._refresh_list()
        self._select_track(slug)

    def _import_track(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Track Map", "", "JSON files (*.json)")
        if not path:
            return
        data = _load_track(path)
        if not data:
            return
        name = data.get("name") or os.path.splitext(os.path.basename(path))[0]
        data["name"] = name
        slug = _slug(name)
        _save_track(slug, data)
        self._refresh_list()
        self._select_track(slug)

    def _save_track_length(self, slug: str):
        if not hasattr(self, "_length_field") or self._length_field is None:
            return
        try:
            meters = float(self._length_field.text().strip())
            if meters <= 0:
                raise ValueError
        except ValueError:
            return
        data = _load_track(os.path.join(TRACKS_DIR, f"{slug}.json"))
        if not data:
            return
        data["track_length_m"] = round(meters, 1)
        _save_track(slug, data)

    def _auto_detect_length(self, slug: str):
        from telemetry.spline import find_spline, parse_fast_lane
        folder = QFileDialog.getExistingDirectory(
            self, "Select AC track folder",
            r"C:\Program Files (x86)\Steam\steamapps\common\assettocorsa\content\tracks",
        )
        if not folder:
            return
        spline_path = find_spline(folder)
        if not spline_path:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Not found",
                "No fast_lane.ai found in aim/ or ai/ inside the selected folder.")
            return
        length = parse_fast_lane(spline_path)
        if length is None:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Parse failed",
                "Found the spline file but could not extract a valid track length.\n"
                "Enter the track length manually.")
            return
        if hasattr(self, "_length_field") and self._length_field:
            self._length_field.setText(str(length))
        self._save_track_length(slug)

    def _rebind_key(self, action: str, btn: QPushButton):
        dlg = _KeyBindDialog(action, self)
        if dlg.exec() and dlg.result_key:
            btn.setText(dlg.result_key)

    # ── Mapping ───────────────────────────────────────────────────────

    def _start_mapping(self, slug: str, mode: str):
        if self._mapping_thread and self._mapping_thread.is_alive():
            return
        self._mapping_stop.clear()
        self._undo_event.clear()

        mark_key = (self._entry_key_btn.text().strip() or "F10") if self._entry_key_btn else "F10"
        exit_key  = (self._exit_key_btn.text().strip()  or "F11") if self._exit_key_btn  else "F11"
        undo_key  = (self._undo_key_btn.text().strip()  or "F12") if self._undo_key_btn  else "F12"
        hotkey = mark_key if mode == "entries" else exit_key

        if self._start_panel:
            self._start_panel.setVisible(False)
        if self._mapping_panel:
            self._mapping_panel.setVisible(True)
        if self._mapping_mode_lbl:
            label = "entries" if mode == "entries" else "exits"
            self._mapping_mode_lbl.setText(
                f"● Mapping {label} — press {hotkey} at each corner {label[:-1]}"
            )
        if self._mapping_marks_lbl:
            self._mapping_marks_lbl.setText("Marks: 0")
        if self._mapping_pos_lbl:
            self._mapping_pos_lbl.setText("Connecting to AC...")

        sig = _MappingSignals(self)
        sig.position_updated.connect(self._on_mapping_pos)
        sig.mark_added.connect(self._on_mark_added)
        sig.mark_undone.connect(self._on_mark_undone)
        sig.finished.connect(lambda positions: self._on_mapping_finished(slug, mode, positions))
        sig.status.connect(lambda s: self._mapping_pos_lbl.setText(s) if self._mapping_pos_lbl else None)
        sig.error.connect(lambda e: self._mapping_pos_lbl.setText(f"Error: {e}") if self._mapping_pos_lbl else None)

        self._mapping_thread = threading.Thread(
            target=self._mapping_worker, args=(mode, sig, hotkey, undo_key), daemon=True
        )
        self._mapping_thread.start()

    def _mapping_worker(self, mode: str, sig: _MappingSignals, mark_key: str, undo_key: str):
        try:
            import keyboard
        except ImportError:
            sig.error.emit("'keyboard' not installed — run: pip install keyboard==0.13.5")
            return

        from telemetry.sim_info import SimInfo
        sim = SimInfo()
        sig.status.emit("Connecting to AC...")

        start = time.time()
        while not sim.connect():
            if self._mapping_stop.is_set() or time.time() - start > 15:
                sig.status.emit("AC not found — start Assetto Corsa first")
                return
            time.sleep(1)

        label = "entry" if mode == "entries" else "exit"
        sig.status.emit(f"Connected — press {mark_key} at each corner {label}  |  {undo_key} to undo")

        marks: list[tuple] = []  # list of (x, z) tuples

        def mark():
            coords = sim.graphics.carCoordinates
            x, z = round(float(coords[0]), 2), round(float(coords[2]), 2)
            marks.append((x, z))
            sig.mark_added.emit(len(marks), x)  # emit x as preview value

        def undo():
            if marks:
                marks.pop()
                sig.mark_undone.emit(len(marks))

        keyboard.add_hotkey(mark_key, mark)
        keyboard.add_hotkey(undo_key, undo)

        try:
            while not self._mapping_stop.is_set():
                if self._undo_event.is_set():
                    undo()
                    self._undo_event.clear()
                coords = sim.graphics.carCoordinates
                x = float(coords[0])
                speed = sim.physics.speedKmh
                sig.position_updated.emit(x, speed)
                time.sleep(1 / 30)
        finally:
            keyboard.unhook_all()
            sim.close()

        sig.finished.emit(marks)

    def _finish_mapping(self):
        self._mapping_stop.set()

    def _undo_last_mark(self):
        self._undo_event.set()

    @pyqtSlot(float, float)
    def _on_mapping_pos(self, x: float, speed: float):
        if self._mapping_pos_lbl:
            self._mapping_pos_lbl.setText(f"X: {x:.1f}  |  Speed: {speed:.1f} km/h")

    @pyqtSlot(int, float)
    def _on_mark_added(self, count: int, x: float):
        if self._mapping_marks_lbl:
            self._mapping_marks_lbl.setText(f"Marks: {count}  (last X: {x:.1f})")

    @pyqtSlot(int)
    def _on_mark_undone(self, count: int):
        if self._mapping_marks_lbl:
            self._mapping_marks_lbl.setText(f"Marks: {count}  (undone)")

    @pyqtSlot(list)
    def _on_mapping_finished(self, slug: str, mode: str, positions: list):
        data = _load_track(os.path.join(TRACKS_DIR, f"{slug}.json"))
        if not data:
            return

        if mode == "entries":
            data["corners"] = [
                {"corner": i + 1, "x": xz[0], "z": xz[1], "type": "MEDIUM"}
                for i, xz in enumerate(positions)
            ]
        else:
            for i, xz in enumerate(positions):
                if i < len(data.get("corners", [])):
                    data["corners"][i]["exit_x"] = xz[0]
                    data["corners"][i]["exit_z"] = xz[1]

        _save_track(slug, data)

        if self._corner_table:
            self._populate_corner_table(data["corners"], slug)

        has_corners = bool(data.get("corners"))
        if self._map_exits_btn:
            self._map_exits_btn.setEnabled(has_corners)

        self._refresh_list()

        # Restore start panel
        if self._mapping_panel:
            self._mapping_panel.setVisible(False)
        if self._start_panel:
            self._start_panel.setVisible(True)
