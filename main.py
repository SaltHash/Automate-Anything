"""
Automate Anything - Main Entry Point
"""
import sys
import os

# Ensure the app directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QFontDatabase, QFont

from ui.main_window import MainWindow
from core.storage import Database
from core.config import Config


def main():
    # Enable high DPI
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Automate Anything")
    app.setOrganizationName("AutomateAnything")
    app.setStyle("Fusion")

    # Initialize core services
    config = Config()
    db = Database()
    db.initialize()

    # Launch main window
    window = MainWindow(config=config, db=db)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
