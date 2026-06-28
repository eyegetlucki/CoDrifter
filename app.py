import sys
import os

# Ensure working directory is always the project root (works both frozen and as script)
if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont, QFontDatabase, QIcon
from PyQt6.QtCore import Qt

from ui.main_window import MainWindow
from ui.theme import STYLESHEET


def _asset(filename: str) -> str:
    """
    Resolve a bundled asset path for both dev and frozen (PyInstaller) modes.
    In frozen mode PyInstaller 6+ puts datas in _internal/ (sys._MEIPASS), not
    next to the exe, so relative paths from cwd don't work for assets.
    """
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, filename)
    return filename  # cwd is already set to project root above


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CoDrifter")
    app.setOrganizationName("CoDrifter")

    app.setStyleSheet(STYLESHEET)

    font = QFont("Segoe UI", 10)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    app.setFont(font)

    icon = QIcon(_asset("driftline.ico"))
    app.setWindowIcon(icon)

    window = MainWindow(_asset("driftlinewordmark.png"))
    window.setWindowIcon(icon)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
