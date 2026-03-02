"""Main GUI window assembly for lab instrument control."""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import yaml
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from instruments.e36300 import E36300Supply
from instruments.gsm20h10 import GSM20H10
from gui.instruments.e36300_panel import E36300Panel
from gui.instruments.gsm20h10_panel import GSM20H10Panel
from gui.tabs.iv_curve_tab import IVCurveTab
from gui.tabs.rotation_sweep_tab import RotationSweepTab
from gui.tabs.tcspc_scan_tab import TCSPCScanTab
from gui.widgets.config_editor import ConfigEditorWidget
from gui.widgets.connections_widget import ConnectionsWidget
from gui.widgets.log_viewer import LogViewerWidget


if sys.platform == "darwin":
    DEFAULT_CONFIG = Path("config") / "instruments_mac.yaml"
else:
    DEFAULT_CONFIG = Path("config") / "instruments.yaml"


class MainWindow(QMainWindow):
    """Primary application window containing all GUI tabs.

    Parameters:
        config_path: Initial YAML config path (units: none).
        parent: Optional parent widget (units: none).
    """

    def __init__(self, config_path: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Lab Instrument Control")
        self.resize(1400, 900)

        start_path = Path(config_path) if config_path else DEFAULT_CONFIG
        self._config_path = start_path
        self._config = self._load_config(self._config_path)

        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        header = QHBoxLayout()
        header.addWidget(QLabel("Lab Instrument Control v0.1", self))
        header.addStretch(1)
        self._path_label = QLabel("", self)
        self._load_button = QPushButton("Load Config…", self)
        self._load_button.clicked.connect(self._on_load_config)
        header.addWidget(self._path_label)
        header.addWidget(self._load_button)
        root.addLayout(header)

        self._tabs = QTabWidget(self)
        root.addWidget(self._tabs, 1)

        self._rotation_tab = RotationSweepTab(str(self._config_path), self)
        self._iv_tab = IVCurveTab(str(self._config_path), self)
        self._tcspc_tab = TCSPCScanTab(str(self._config_path), self)

        self._experiments_widget = QTabWidget(self)
        self._experiments_widget.addTab(self._rotation_tab, "Rotation Sweep")
        self._experiments_widget.addTab(self._iv_tab, "I-V Curve")
        self._experiments_widget.addTab(self._tcspc_tab, "TCSPC Scan")

        self._gsm_panel = GSM20H10Panel(self._config.get("gsm20h10", {}), self)
        self._e36300_panel = E36300Panel(self._config.get("e36300", {}), self)
        self._instruments_widget = QTabWidget(self)
        self._instruments_widget.addTab(self._gsm_panel, "GSM20H10")
        self._instruments_widget.addTab(self._e36300_panel, "E36300")

        self._connections = ConnectionsWidget(str(self._config_path), self)
        self._config_editor = ConfigEditorWidget(str(self._config_path), self)
        self._log_viewer = LogViewerWidget(self)

        self._tabs.addTab(self._experiments_widget, "Experiments")
        self._tabs.addTab(self._instruments_widget, "Instruments")
        self._tabs.addTab(self._connections, "Connections")
        self._tabs.addTab(self._config_editor, "Config")
        self._tabs.addTab(self._log_viewer, "Log")

        self._rotation_tab.log_message.connect(self._log_viewer.append_message)
        self._iv_tab.log_message.connect(self._log_viewer.append_message)
        self._tcspc_tab.log_message.connect(self._log_viewer.append_message)

        self._config_editor.config_saved.connect(self._on_config_saved)
        self._set_path_label()

    def closeEvent(self, event) -> None:
        """Warn user, run panic-off in background, then accept close.

        Parameters:
            event: Qt close event (units: none).
        """
        if not self.isVisible():
            event.accept()
            return

        reply = QMessageBox.question(
            self,
            "Exit",
            "Attempt panic OFF for GSM20H10 and E36300 before exit?",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.Yes,
        )
        if reply == QMessageBox.Cancel:
            event.ignore()
            return

        if reply == QMessageBox.Yes:
            gsm_cfg = dict(self._config.get("gsm20h10", {}))
            e36_cfg = dict(self._config.get("e36300", {}))

            def _panic_gsm() -> None:
                try:
                    with GSM20H10(gsm_cfg) as smu:
                        smu.output_off()
                except Exception:
                    pass

            def _panic_e36() -> None:
                try:
                    with E36300Supply(e36_cfg) as supply:
                        supply.output_off()
                except Exception:
                    pass

            t1 = threading.Thread(target=_panic_gsm, daemon=True)
            t2 = threading.Thread(target=_panic_e36, daemon=True)
            t1.start()
            t2.start()
            t1.join(timeout=3.0)
            t2.join(timeout=3.0)
        event.accept()

    def _load_config(self, path: Path) -> dict:
        """Load YAML config from disk.

        Parameters:
            path: YAML config path (units: none).
        """
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}

    def _set_path_label(self) -> None:
        """Refresh active config path label.

        Parameters:
            None (units: none).
        """
        self._path_label.setText(f"Config: {self._config_path.as_posix()}")

    def _on_load_config(self) -> None:
        """Open file chooser and reload all config-bound widgets.

        Parameters:
            None (units: none).
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Config",
            str(self._config_path),
            "YAML Files (*.yaml *.yml)",
        )
        if not file_path:
            return
        self._apply_config(Path(file_path))

    def _on_config_saved(self, path: str) -> None:
        """Handle save signal from config editor.

        Parameters:
            path: Saved config path (units: none).
        """
        self._apply_config(Path(path))

    def _apply_config(self, path: Path) -> None:
        """Apply new config across all tabs/widgets.

        Parameters:
            path: YAML config path (units: none).
        """
        self._config_path = path
        self._config = self._load_config(path)

        cfg_str = self._config_path.as_posix()
        self._rotation_tab.set_config_path(cfg_str)
        self._iv_tab.set_config_path(cfg_str)
        self._tcspc_tab.set_config_path(cfg_str)
        self._connections.set_config(cfg_str)
        self._config_editor.set_config_path(cfg_str)
        self._gsm_panel.set_config(self._config.get("gsm20h10", {}))
        self._e36300_panel.set_config(self._config.get("e36300", {}))
        self._set_path_label()
