import sys
import os

# Ensure working directory is always the project root
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont, QFontDatabase, QIcon
from PyQt6.QtCore import Qt

from ui.main_window import MainWindow
from ui.theme import STYLESHEET


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CoDrifter")
    app.setOrganizationName("CoDrifter")

    app.setStyleSheet(STYLESHEET)

    font = QFont("Segoe UI", 10)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    app.setFont(font)

    _icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "driftline.ico")
    icon = QIcon(_icon_path)
    app.setWindowIcon(icon)

    window = MainWindow()
    window.setWindowIcon(icon)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
