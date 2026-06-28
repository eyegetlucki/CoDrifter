import base64

_CHECKMARK_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 12">
  <polyline points="1.5,6.5 4.5,9.5 10.5,2.5" stroke="white" stroke-width="2"
    fill="none" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""
_CHECKMARK_URI = "data:image/svg+xml;base64," + base64.b64encode(_CHECKMARK_SVG).decode()

BG_DEEP    = "#0C0C0F"
BG_PANEL   = "#111116"
BG_CARD    = "#18181F"
BG_HOVER   = "#1E1E28"
BORDER     = "#1F1F2E"
BORDER_LIT = "#2E2E45"

ACCENT      = "#E63946"
ACCENT_DARK = "#B82E38"
ACCENT_GLOW = "#FF4D5A"
ACCENT_DIM  = "#2A0C10"

TEXT_PRIMARY   = "#EBEBF5"
TEXT_SECONDARY = "#6B6B8A"
TEXT_DIM       = "#30304A"

GREEN  = "#34C77B"
ORANGE = "#E8A020"
RED    = "#E63946"

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
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_LIT};
    border-radius: 2px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

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
    letter-spacing: 0.5px;
    border-radius: 8px;
}}
QPushButton#accent:hover {{
    background-color: {ACCENT_GLOW};
}}
QPushButton#accent:pressed {{
    background-color: {ACCENT_DARK};
}}
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
    border-radius: 8px;
    padding: 8px 14px;
}}
QPushButton#toggle_off {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    color: {TEXT_SECONDARY};
    font-weight: 500;
    font-size: 12px;
    border-radius: 8px;
    padding: 8px 14px;
}}
QPushButton#toggle_on:hover {{
    background-color: {ACCENT_GLOW};
}}
QPushButton#toggle_off:hover {{
    border-color: {BORDER_LIT};
    color: {TEXT_PRIMARY};
}}

/* ── Nav sidebar buttons ── */
QPushButton#nav {{
    background-color: transparent;
    border: none;
    border-left: 2px solid transparent;
    border-radius: 0px;
    color: {TEXT_SECONDARY};
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 1px;
    text-align: left;
    padding: 12px 20px 12px 22px;
}}
QPushButton#nav:hover {{
    background-color: {BG_HOVER};
    color: {TEXT_PRIMARY};
}}
QPushButton#nav[active="true"] {{
    background-color: {BG_HOVER};
    color: {TEXT_PRIMARY};
    border-left: 2px solid {ACCENT};
}}

/* ── Labels ── */
QLabel#section_title {{
    color: {TEXT_SECONDARY};
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1.5px;
}}
QLabel#speed_value {{
    color: {TEXT_PRIMARY};
    font-size: 80px;
    font-weight: 700;
    font-family: "{FONT_FAMILY}";
    letter-spacing: -3px;
}}
QLabel#speed_unit {{
    color: {TEXT_DIM};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 3px;
}}
QLabel#gear_value {{
    color: {ACCENT};
    font-size: 60px;
    font-weight: 700;
    letter-spacing: -2px;
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
    background-color: {BG_HOVER};
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
    font-size: 0px;
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 4px;
}}
QProgressBar#throttle_bar {{
    background-color: #0A1A0F;
}}
QProgressBar#throttle_bar::chunk {{
    background-color: {GREEN};
    border-radius: 4px;
}}
QProgressBar#brake_bar {{
    background-color: #1A0A0C;
}}
QProgressBar#brake_bar::chunk {{
    background-color: {RED};
    border-radius: 4px;
}}

/* ── Sliders ── */
QSlider::groove:horizontal {{
    background: {BG_HOVER};
    height: 3px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {TEXT_SECONDARY};
    width: 14px;
    height: 14px;
    margin: -6px 0;
    border-radius: 7px;
    border: 2px solid {BG_DEEP};
}}
QSlider::handle:horizontal:hover {{
    background: {TEXT_PRIMARY};
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
    background: {BG_CARD};
}}
QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    image: url("{_CHECKMARK_URI}");
}}
QCheckBox::indicator:hover {{
    border-color: {TEXT_SECONDARY};
}}

/* ── Line edits ── */
QLineEdit {{
    background-color: {BG_DEEP};
    border: 1px solid {BORDER_LIT};
    border-radius: 7px;
    padding: 8px 12px;
    color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT};
    font-size: 13px;
}}
QLineEdit:focus {{
    border-color: {ACCENT};
}}
QLineEdit:hover {{
    border-color: {BORDER_LIT};
}}

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
    padding: 13px 16px;
    border-bottom: 1px solid {BORDER};
    color: {TEXT_PRIMARY};
}}
QTableWidget::item:selected {{
    background-color: {ACCENT_DIM};
    color: {TEXT_PRIMARY};
}}
QTableWidget::item:hover {{
    background-color: {BG_HOVER};
}}
QHeaderView::section {{
    background-color: {BG_CARD};
    color: {TEXT_SECONDARY};
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1px;
    padding: 12px 16px;
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
"""
