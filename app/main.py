"""Application entry point."""

from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app import __version__
from app.paths import app_window_icon_path
from app.settings import AppSettings
from app.ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(f"Immortal")
    _ico = app_window_icon_path()
    if _ico.is_file():
        app.setWindowIcon(QIcon(str(_ico)))
    settings = AppSettings.load()
    window = MainWindow(settings)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
