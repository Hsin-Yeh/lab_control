"""Connections tab widget for read-only instrument health checks."""

from __future__ import annotations

from pathlib import Path

import yaml
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gui import (
    E36300Supply,
    FLIPPER_AVAILABLE,
    GSM20H10,
    KinesisFlipper,
    KDC101_AVAILABLE,
    KDC101Stage,
    PICOHARP_AVAILABLE,
    PM100D,
    PicoHarp300,
)


class ConnectionTestWorker(QThread):
    """Thread worker for a single instrument connection test.

    Parameters:
        key: Config key for instrument (units: none).
        cls: Instrument class to instantiate (units: none).
        cfg: Instrument configuration mapping (units: none).
    """

    result = Signal(str, bool, str)

    def __init__(self, key: str, cls: type, cfg: dict):
        super().__init__()
        self._key = key
        self._cls = cls
        self._cfg = cfg

    def run(self) -> None:
        """Execute read-only connection test.

        Parameters:
            None (units: none).
        """
        try:
            if bool(self._cfg.get("simulate", False)):
                self.result.emit(self._key, True, "SIMULATED — no hardware test")
                return

            with self._cls(self._cfg) as inst:
                instrument_id = getattr(inst, "instrument_id", "UNKNOWN")
                if callable(instrument_id):
                    instrument_id = instrument_id()
                detail = str(instrument_id)
                if self._key == "pm100d" and hasattr(inst, "read_power"):
                    power = float(inst.read_power())
                    detail = f"{detail} | P={power:.3e} W"
                self.result.emit(self._key, True, detail)
        except Exception as exc:
            self.result.emit(self._key, False, str(exc))


class InstrumentRow(QWidget):
    """One instrument connection row with status and test controls.

    Parameters:
        key: Instrument config key (units: none).
        label: Human-friendly instrument label (units: none).
        cls: Instrument class for connection test (units: none).
        cfg: Instrument-specific config mapping (units: none).
        parent: Optional parent widget (units: none).
    """

    def __init__(
        self,
        key: str,
        label: str,
        cls: type,
        cfg: dict,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.key = key
        self.label = label
        self.cls = cls
        self.cfg = cfg
        self._worker: ConnectionTestWorker | None = None

        self._dot = QLabel("●", self)
        self._name = QLabel(label, self)
        self._summary = QLabel(self._resource_summary(), self)
        self._detail = QLabel("Not tested", self)
        self._test_button = QPushButton("Test", self)
        self._clear_button = QPushButton("Clear", self)

        self._dot.setStyleSheet("color: #444444; font-size: 20px;")
        self._summary.setStyleSheet("color: #AAAAAA;")
        self._detail.setStyleSheet("color: #AAAAAA;")

        top = QHBoxLayout()
        top.addWidget(self._dot)
        top.addWidget(self._name)
        top.addWidget(self._summary, 1)
        top.addWidget(self._test_button)
        top.addWidget(self._clear_button)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self._detail)

        self._test_button.clicked.connect(self.run_test)
        self._clear_button.clicked.connect(self.clear_status)

    def update_config(self, cfg: dict) -> None:
        """Update row configuration and reset summary text.

        Parameters:
            cfg: Instrument-specific config mapping (units: none).
        """
        self.cfg = cfg
        self._summary.setText(self._resource_summary())
        self.clear_status()

    def run_test(self) -> None:
        """Start asynchronous read-only connection test.

        Parameters:
            None (units: none).
        """
        self._set_running()
        self._worker = ConnectionTestWorker(self.key, self.cls, self.cfg)
        self._worker.result.connect(self._on_result)
        self._worker.start()

    def clear_status(self) -> None:
        """Reset row status to untested.

        Parameters:
            None (units: none).
        """
        self._dot.setStyleSheet("color: #444444; font-size: 20px;")
        self._detail.setStyleSheet("color: #AAAAAA;")
        self._detail.setText("Not tested")

    def _set_running(self) -> None:
        """Set row status to running.

        Parameters:
            None (units: none).
        """
        self._dot.setStyleSheet("color: #FF8800; font-size: 20px;")
        self._detail.setStyleSheet("color: #FF8800;")
        self._detail.setText("Running…")

    def _on_result(self, key: str, ok: bool, detail: str) -> None:
        """Handle test result signal from worker.

        Parameters:
            key: Instrument config key (units: none).
            ok: Test success state (units: boolean).
            detail: Result detail text (units: none).
        """
        if key != self.key:
            return

        is_simulated = "SIMULATED" in detail.upper()
        if ok and is_simulated:
            self._dot.setStyleSheet("color: #FF8800; font-size: 20px;")
            self._detail.setStyleSheet("color: #FF8800;")
        elif ok:
            self._dot.setStyleSheet("color: #44CC44; font-size: 20px;")
            self._detail.setStyleSheet("color: #44CC44;")
        else:
            self._dot.setStyleSheet("color: #CC4444; font-size: 20px;")
            self._detail.setStyleSheet("color: #CC4444;")

        prefix = "PASS" if ok else "FAIL"
        self._detail.setText(f"{prefix} — {detail}")

    def _resource_summary(self) -> str:
        """Build short resource/address summary from config.

        Parameters:
            None (units: none).
        """
        if self.key in {"kdc101", "flipper"}:
            serial = self.cfg.get("serial_number") or self.cfg.get("serial", "N/A")
            return f"Serial: {serial}"
        if self.key == "picoharp300":
            dll = self.cfg.get("dll_path") or self.cfg.get("phlib_path", "N/A")
            return f"DLL: {dll}"
        resource = self.cfg.get("resource") or self.cfg.get("visa_resource", "N/A")
        return f"Resource: {resource}"


class ConnectionsWidget(QWidget):
    """Scrollable connection test dashboard for available instruments.

    Parameters:
        config_path: Path to YAML config file (units: none).
        parent: Optional parent widget (units: none).
    """

    def __init__(self, config_path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config_path = Path(config_path)
        self._rows: dict[str, InstrumentRow] = {}

        self._container = QWidget(self)
        self._rows_layout = QVBoxLayout(self._container)
        self._rows_layout.setContentsMargins(8, 8, 8, 8)
        self._rows_layout.setSpacing(8)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._container)

        self._test_all_button = QPushButton("Test All", self)
        self._test_all_button.clicked.connect(self._on_test_all)

        layout = QVBoxLayout(self)
        layout.addWidget(scroll, 1)
        layout.addWidget(self._test_all_button)

        self.set_config(str(self._config_path))

    def set_config(self, config_path: str) -> None:
        """Load new config and rebuild rows.

        Parameters:
            config_path: Path to YAML config file (units: none).
        """
        self._config_path = Path(config_path)
        try:
            config = yaml.safe_load(self._config_path.read_text(encoding="utf-8")) or {}
        except Exception:
            config = {}

        available = [
            ("pm100d", "PM100D", PM100D),
            ("e36300", "E36300", E36300Supply),
            ("gsm20h10", "GSM20H10", GSM20H10),
        ]
        if KDC101_AVAILABLE and KDC101Stage is not None:
            available.insert(0, ("kdc101", "KDC101 Stage", KDC101Stage))
        if FLIPPER_AVAILABLE and KinesisFlipper is not None:
            available.insert(1, ("flipper", "Filter Flipper", KinesisFlipper))
        if PICOHARP_AVAILABLE and PicoHarp300 is not None:
            available.append(("picoharp300", "PicoHarp300", PicoHarp300))

        for row in list(self._rows.values()):
            row.setParent(None)
            row.deleteLater()
        self._rows.clear()

        for key, label, cls in available:
            row = InstrumentRow(key, label, cls, config.get(key, {}), self._container)
            self._rows_layout.addWidget(row)
            self._rows[key] = row

        self._rows_layout.addStretch(1)

    def _on_test_all(self) -> None:
        """Trigger test on all visible rows.

        Parameters:
            None (units: none).
        """
        for row in self._rows.values():
            row.run_test()
