import os
import tempfile

_CHECKMARK_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 12">
  <polyline points="1.5,6.5 4.5,9.5 10.5,2.5" stroke="white" stroke-width="2"
    fill="none" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""
_tmp = tempfile.NamedTemporaryFile(suffix=".svg", delete=False)
_tmp.write(_CHECKMARK_SVG)
_tmp.close()
_CHECKMARK_PATH = _tmp.name.replace("\\", "/")

# ── Palette ───────────────────────────────────────────────────────────────────
BG_DEEP    = "#0E0E0F"
BG_PANEL   = "#111113"
BG_CARD    = "#141417"
BG_HOVER   = "#1C1C20"
BG_INPUT   = "#1A1A1E"
BORDER     = "#222226"
BORDER_LIT = "#2E2E38"
TOPBAR_SEP = "#1E1E22"

ACCENT      = "#FF4A4A"
ACCENT_DARK = "#CC3B3B"
ACCENT_GLOW = "#FF6060"
ACCENT_DIM  = "#2A0808"

TEXT_PRIMARY   = "#E0DDD8"
TEXT_SECONDARY = "#555562"
TEXT_DIM       = "#3A3A44"

SPEED_COLOR = "#F0EDE8"

GREEN  = "#22C55E"
ORANGE = "#E8A020"
RED    = "#FF4A4A"
PURPLE = "#A855F7"
INDIGO = "#6366F1"

FONT_FAMILY = "Segoe UI"

STYLESHEET = f"""
/* ── Base ── */
QMainWindow, QDialog {{
    background-color: {BG_DEEP};
}}
QWidget {{
    background-color: transparent;
    color: {TEXT_PRIMARY};
    font-family: "{FONT_FAMILY}";
    font-size: 13px;
}}

/* ── Scroll bars ── */
QScrollBar:vertical {{
    background: transparent;
    width: 4px;
    border-radius: 2px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_LIT};
    border-radius: 2px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TEXT_SECONDARY};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_LIT};
    border-radius: 2px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Buttons ── */
QPushButton {{
    background-color: {BG_CARD};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 18px;
    font-weight: 500;
    font-size: 12px;
}}
QPushButton:hover {{
    background-color: {BG_HOVER};
    border-color: {BORDER_LIT};
    color: {TEXT_PRIMARY};
}}
QPushButton:pressed {{
    background-color: {ACCENT_DIM};
    border-color: {ACCENT};
    color: {TEXT_PRIMARY};
}}
QPushButton:disabled {{
    color: {TEXT_DIM};
    border-color: {BORDER};
    background-color: transparent;
}}
QPushButton#accent {{
    background-color: {ACCENT};
    border: none;
    color: #FFFFFF;
    font-weight: 600;
    font-size: 12px;
    padding: 9px 18px;
    border-radius: 8px;
}}
QPushButton#accent:hover {{ background-color: {ACCENT_GLOW}; }}
QPushButton#accent:pressed {{ background-color: {ACCENT_DARK}; }}
QPushButton#accent:disabled {{
    background-color: {ACCENT_DIM};
    color: #66334A;
}}

/* ── Coach toggle ── */
QPushButton#toggle_on {{
    background-color: {ACCENT};
    border: none;
    color: #FFFFFF;
    font-weight: 600;
    font-size: 12px;
    border-radius: 9px;
    padding: 8px 14px;
}}
QPushButton#toggle_off {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    color: {TEXT_SECONDARY};
    font-weight: 400;
    font-size: 12px;
    border-radius: 9px;
    padding: 8px 14px;
}}
QPushButton#toggle_on:hover {{ background-color: {ACCENT_GLOW}; }}
QPushButton#toggle_off:hover {{
    background-color: {BG_HOVER};
    color: {TEXT_PRIMARY};
}}

/* ── Labels ── */
QLabel#section_title {{
    color: {TEXT_DIM};
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1px;
}}
QLabel#speed_value {{
    color: {SPEED_COLOR};
    font-size: 72px;
    font-weight: 200;
    font-family: "{FONT_FAMILY}";
    letter-spacing: -4px;
}}
QLabel#speed_unit {{
    color: {TEXT_DIM};
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 2.5px;
}}
QLabel#gear_value {{
    color: {ACCENT};
    font-size: 44px;
    font-weight: 300;
    letter-spacing: -1px;
}}
QLabel#stat_value {{
    color: {TEXT_PRIMARY};
    font-size: 20px;
    font-weight: 600;
}}
QLabel#stat_label {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
}}
QLabel#improvement_item {{
    color: {TEXT_PRIMARY};
    font-size: 13px;
}}
QLabel#coaching_tip {{
    color: {ACCENT};
    font-size: 14px;
    font-style: italic;
    font-weight: 400;
}}

/* ── Progress bars ── */
QProgressBar {{
    background-color: #1C1C20;
    border: none;
    border-radius: 2px;
    height: 3px;
    text-align: center;
    font-size: 0px;
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 2px;
}}
QProgressBar#throttle_bar {{
    background-color: #1C1C20;
}}
QProgressBar#throttle_bar::chunk {{
    background-color: {GREEN};
    border-radius: 2px;
}}
QProgressBar#brake_bar {{
    background-color: #1C1C20;
}}
QProgressBar#brake_bar::chunk {{
    background-color: {RED};
    border-radius: 2px;
}}

/* ── Sliders ── */
QSlider::groove:horizontal {{
    background: #1C1C20;
    height: 3px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT};
    width: 12px;
    height: 12px;
    margin: -5px 0;
    border-radius: 6px;
    border: none;
}}
QSlider::handle:horizontal:hover {{
    background: {ACCENT_GLOW};
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 2px;
}}

/* ── Checkboxes ── */
QCheckBox {{
    color: {TEXT_PRIMARY};
    spacing: 10px;
    font-size: 13px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {BORDER_LIT};
    background: {BG_INPUT};
}}
QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    image: url("{_CHECKMARK_PATH}");
}}
QCheckBox::indicator:hover {{ border-color: {TEXT_SECONDARY}; }}

/* ── Line edits ── */
QLineEdit {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 6px 10px;
    color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT};
    font-size: 12px;
}}
QLineEdit:focus {{ border-color: {ACCENT}; }}
QLineEdit:hover {{ border-color: {BORDER_LIT}; }}

/* ── Tables ── */
QTableWidget {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    gridline-color: {BORDER};
    selection-background-color: {ACCENT_DIM};
    outline: none;
}}
QTableWidget::item {{
    padding: 6px 14px;
    border-bottom: 1px solid {BORDER};
    color: {TEXT_PRIMARY};
}}
QTableWidget::item:selected {{
    background-color: {ACCENT_DIM};
    color: {TEXT_PRIMARY};
}}
QTableWidget::item:hover {{ background-color: {BG_HOVER}; }}
QHeaderView::section {{
    background-color: {BG_CARD};
    color: {TEXT_SECONDARY};
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1px;
    padding: 8px 14px;
    border: none;
    border-bottom: 1px solid {BORDER};
}}

/* ── Separators ── */
QFrame#separator {{
    color: {BORDER};
    background-color: {BORDER};
    max-height: 1px;
    border: none;
}}
QFrame#v_separator {{
    color: {BORDER};
    background-color: {BORDER};
    max-width: 1px;
    border: none;
}}

/* ── Scroll area ── */
QScrollArea {{
    border: none;
    background-color: transparent;
}}

/* ── QGroupBox kill ── */
QGroupBox {{
    border: none;
    padding-top: 24px;
    font-size: 0px;
}}
QGroupBox::title {{
    color: {TEXT_DIM};
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1px;
    subcontrol-origin: margin;
    left: 0px;
}}
"""
