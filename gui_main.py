"""GUI entry point for lab instrument control."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow

try:
    import pyqtgraph as pg

    pg.setConfigOption("useOpenGL", False)
    pg.setConfigOption("antialias", True)
except ImportError:
    pass


def main() -> None:
    """Launch the GUI application.

    Parameters:
        None (units: none).
    """
    parser = argparse.ArgumentParser(description="Launch lab-control GUI")
    parser.add_argument("--config", default=None)
    args = parser.parse_args()

    if args.config:
        default_config = Path(args.config)
    elif sys.platform == "darwin":
        default_config = Path("config") / "instruments_mac.yaml"
    else:
        default_config = Path("config") / "instruments.yaml"

    app = QApplication(sys.argv)
    app.setApplicationName("Lab Instrument Control")
    window = MainWindow(config_path=str(default_config))
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
