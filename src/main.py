"""Application entry point for LoudspeakerFEA."""

import sys
from pathlib import Path

# Ensure the project root is on sys.path so 'src' resolves when running directly
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from PyQt6.QtWidgets import QApplication
from src.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("LoudspeakerFEA")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
