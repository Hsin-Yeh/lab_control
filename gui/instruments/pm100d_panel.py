"""Simple PM100D control panel for GUI."""

from __future__ import annotations

import math
import threading

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gui.instruments.workers import ConnectWorker, WriteCommandWorker
from instruments.pm100d import PM100D


class PM100DReadWorker(QThread):
    """Worker for PM100D one-shot reads.

    Parameters:
        cfg: PM100D config mapping (units: none).
        average_n: Optional averaging sample count (units: count).
    """

    data = Signal(dict)
    error = Signal(str)

    def __init__(self, cfg: dict, average_n: int | None = None):
        super().__init__()
        self._cfg = cfg
        self._average_n = average_n

    def run(self) -> None:
        """Execute one read sequence.

        Parameters:
            None (units: none).
        """
        try:
            with PM100D(self._cfg) as pm:
                power_w = float(pm.read_power())
                power_dbm = float(pm.read_power_dbm())
                payload = {
                    "power_W": power_w,
                    "power_dBm": power_dbm,
                    "instrument_id": pm.instrument_id,
                }
                if self._average_n is not None and self._average_n > 1:
                    payload["average_W"] = float(pm.read_power_average(self._average_n))
                self.data.emit(payload)
        except Exception as exc:
            self.error.emit(str(exc))


class PM100DContinuousReadWorker(QThread):
    """Worker for periodic PM100D readout.

    Parameters:
        cfg: PM100D config mapping (units: none).
        average_n: Averaging sample count per emitted sample (units: count).
        interval_ms: Loop interval between reads (units: ms).
    """

    data = Signal(dict)
    error = Signal(str)
    stopped = Signal(str)

    def __init__(self, cfg: dict, average_n: int, interval_ms: int):
        super().__init__()
        self._cfg = cfg
        self._average_n = max(1, int(average_n))
        self._interval_ms = max(100, int(interval_ms))
        self._abort_event = threading.Event()

    def abort(self) -> None:
        """Request stop for the continuous loop.

        Parameters:
            None (units: none).
        """
        self._abort_event.set()

    def run(self) -> None:
        """Run periodic readout loop until stopped.

        Parameters:
            None (units: none).
        """
        try:
            with PM100D(self._cfg) as pm:
                while not self._abort_event.is_set():
                    avg_w = float(pm.read_power_average(self._average_n))
                    avg_dbm = float("-inf") if avg_w <= 0.0 else 10.0 * math.log10(avg_w / 1e-3)
                    self.data.emit(
                        {
                            "power_W": avg_w,
                            "power_dBm": avg_dbm,
                            "average_W": avg_w,
                            "instrument_id": pm.instrument_id,
                        }
                    )
                    if self._abort_event.wait(self._interval_ms / 1000.0):
                        break
            self.stopped.emit("user")
        except Exception as exc:
            self.error.emit(str(exc))
            self.stopped.emit("error")


class PM100DPanel(QWidget):
    """Simple PM100D settings and measurement panel.

    Parameters:
        config: Instrument config mapping (units: none).
        parent: Optional parent widget (units: none).
    """

    def __init__(self, config: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = dict(config)
        self._connect_worker: ConnectWorker | None = None
        self._write_worker: WriteCommandWorker | None = None
        self._read_worker: PM100DReadWorker | None = None
        self._continuous_worker: PM100DContinuousReadWorker | None = None
        self._is_connected: bool = False

        self._wavelength = QDoubleSpinBox(self)
        self._wavelength.setRange(400.0, 1100.0)
        self._wavelength.setSingleStep(1.0)
        self._wavelength.setValue(float(self._config.get("wavelength_nm", 780.0)))

        self._averaging = QSpinBox(self)
        self._averaging.setRange(1, 300)
        self._averaging.setValue(int(self._config.get("averaging_count", 10)))

        self._average_samples = QSpinBox(self)
        self._average_samples.setRange(1, 300)
        self._average_samples.setValue(20)

        self._poll_interval_ms = QSpinBox(self)
        self._poll_interval_ms.setRange(100, 10000)
        self._poll_interval_ms.setSingleStep(100)
        self._poll_interval_ms.setValue(500)

        self._auto_range = QCheckBox("Auto range", self)
        self._auto_range.setChecked(True)

        self._connect_btn = QPushButton("Connect", self)
        self._disconnect_btn = QPushButton("Disconnect", self)
        self._apply_btn = QPushButton("Apply Settings", self)
        self._zero_btn = QPushButton("Zero Sensor", self)
        self._read_once_btn = QPushButton("Read Once", self)
        self._read_avg_btn = QPushButton("Read Average", self)
        self._read_start_btn = QPushButton("Start Continuous", self)
        self._read_stop_btn = QPushButton("Stop Continuous", self)
        self._read_stop_btn.setEnabled(False)

        self._id_label = QLabel("ID: (not connected)", self)
        self._status_label = QLabel("Status: idle", self)
        self._power_label = QLabel("Power: 0.0000e+00 W", self)
        self._dbm_label = QLabel("dBm: -inf", self)
        self._avg_label = QLabel("Average: n/a", self)

        form = QFormLayout()
        form.addRow("Wavelength (nm)", self._wavelength)
        form.addRow("Averaging count", self._averaging)
        form.addRow("Average samples", self._average_samples)
        form.addRow("Poll interval (ms)", self._poll_interval_ms)
        form.addRow("", self._auto_range)

        left = QVBoxLayout()
        left.addLayout(form)

        cmd_buttons = QHBoxLayout()
        cmd_buttons.addWidget(self._apply_btn)
        cmd_buttons.addWidget(self._zero_btn)
        left.addLayout(cmd_buttons)

        read_buttons = QHBoxLayout()
        read_buttons.addWidget(self._read_once_btn)
        read_buttons.addWidget(self._read_avg_btn)
        left.addLayout(read_buttons)

        cont_buttons = QHBoxLayout()
        cont_buttons.addWidget(self._read_start_btn)
        cont_buttons.addWidget(self._read_stop_btn)
        left.addLayout(cont_buttons)

        conn_buttons = QHBoxLayout()
        conn_buttons.addWidget(self._connect_btn)
        conn_buttons.addWidget(self._disconnect_btn)
        left.addLayout(conn_buttons)

        left.addWidget(self._id_label)
        left.addWidget(self._status_label)
        left.addStretch(1)

        right = QVBoxLayout()
        right.addWidget(self._power_label)
        right.addWidget(self._dbm_label)
        right.addWidget(self._avg_label)
        right.addStretch(1)

        main = QHBoxLayout(self)
        left_widget = QWidget(self)
        left_widget.setLayout(left)
        left_widget.setMaximumWidth(360)
        main.addWidget(left_widget)
        main.addLayout(right, 1)

        self._connect_btn.clicked.connect(self._on_connect)
        self._disconnect_btn.clicked.connect(self._on_disconnect)
        self._apply_btn.clicked.connect(self._on_apply)
        self._zero_btn.clicked.connect(self._on_zero)
        self._read_once_btn.clicked.connect(self._on_read_once)
        self._read_avg_btn.clicked.connect(self._on_read_average)
        self._read_start_btn.clicked.connect(self._on_start_continuous)
        self._read_stop_btn.clicked.connect(self._on_stop_continuous)

    def set_config(self, config: dict) -> None:
        """Update panel config.

        Parameters:
            config: Instrument config mapping (units: none).
        """
        self._config = dict(config)
        self._wavelength.setValue(float(self._config.get("wavelength_nm", self._wavelength.value())))
        self._averaging.setValue(int(self._config.get("averaging_count", self._averaging.value())))

    def _on_connect(self) -> None:
        self._connect_worker = ConnectWorker(PM100D, self._config)
        self._connect_worker.connected.connect(self._on_connected)
        self._connect_worker.start()

    def _on_connected(self, ok: bool, message: str) -> None:
        """Handle connect result.

        Parameters:
            ok: Connection success state (units: boolean).
            message: Instrument ID or error text (units: none).
        """
        self._is_connected = ok
        if ok:
            self._id_label.setText(f"ID: {message}")
            self._status_label.setText("Status: connected")
        else:
            self._status_label.setText("Status: connect failed")
            QMessageBox.warning(self, "Connect Failed", message)

    def _on_disconnect(self) -> None:
        """Clear connection state labels.

        Parameters:
            None (units: none).
        """
        self._on_stop_continuous()
        self._is_connected = False
        self._id_label.setText("ID: (not connected)")
        self._status_label.setText("Status: disconnected")

    def _on_apply(self) -> None:
        """Apply PM settings with a one-shot worker.

        Parameters:
            None (units: none).
        """
        if not self._is_connected:
            QMessageBox.information(self, "Not Connected", "Connect to PM100D first.")
            return

        wavelength_nm = float(self._wavelength.value())
        averaging_count = int(self._averaging.value())
        auto_range = bool(self._auto_range.isChecked())

        updated = dict(self._config)
        updated["wavelength_nm"] = wavelength_nm
        updated["averaging_count"] = averaging_count
        self._config = updated

        def _cmd(inst) -> None:
            inst.set_wavelength(wavelength_nm)
            inst.set_averaging(averaging_count)
            inst.auto_range(auto_range)

        self._apply_btn.setEnabled(False)
        self._write_worker = WriteCommandWorker(PM100D, self._config, _cmd)
        self._write_worker.success.connect(lambda: self._status_label.setText("Status: settings applied"))
        self._write_worker.success.connect(lambda: self._apply_btn.setEnabled(True))
        self._write_worker.error.connect(lambda message: QMessageBox.warning(self, "Apply Failed", message))
        self._write_worker.error.connect(lambda _message: self._apply_btn.setEnabled(True))
        self._write_worker.start()

    def _on_zero(self) -> None:
        """Trigger PM100D zero routine.

        Parameters:
            None (units: none).
        """
        if not self._is_connected:
            QMessageBox.information(self, "Not Connected", "Connect to PM100D first.")
            return

        self._zero_btn.setEnabled(False)
        self._write_worker = WriteCommandWorker(PM100D, self._config, lambda inst: inst.zero())
        self._write_worker.success.connect(lambda: self._status_label.setText("Status: zero complete"))
        self._write_worker.success.connect(lambda: self._zero_btn.setEnabled(True))
        self._write_worker.error.connect(lambda message: QMessageBox.warning(self, "Zero Failed", message))
        self._write_worker.error.connect(lambda _message: self._zero_btn.setEnabled(True))
        self._write_worker.start()

    def _on_read_once(self) -> None:
        """Read one PM100D sample.

        Parameters:
            None (units: none).
        """
        if not self._is_connected:
            QMessageBox.information(self, "Not Connected", "Connect to PM100D first.")
            return
        self._read_worker = PM100DReadWorker(self._config)
        self._read_worker.data.connect(self._on_read_data)
        self._read_worker.error.connect(lambda message: QMessageBox.warning(self, "Read Failed", message))
        self._read_worker.start()

    def _on_read_average(self) -> None:
        """Read averaged PM100D sample.

        Parameters:
            None (units: none).
        """
        if not self._is_connected:
            QMessageBox.information(self, "Not Connected", "Connect to PM100D first.")
            return
        self._read_worker = PM100DReadWorker(self._config, average_n=int(self._average_samples.value()))
        self._read_worker.data.connect(self._on_read_data)
        self._read_worker.error.connect(lambda message: QMessageBox.warning(self, "Read Failed", message))
        self._read_worker.start()

    def _on_start_continuous(self) -> None:
        """Start periodic averaged PM readout.

        Parameters:
            None (units: none).
        """
        if not self._is_connected:
            QMessageBox.information(self, "Not Connected", "Connect to PM100D first.")
            return
        if self._continuous_worker is not None and self._continuous_worker.isRunning():
            return

        self._continuous_worker = PM100DContinuousReadWorker(
            self._config,
            average_n=int(self._average_samples.value()),
            interval_ms=int(self._poll_interval_ms.value()),
        )
        self._continuous_worker.data.connect(self._on_read_data)
        self._continuous_worker.error.connect(
            lambda message: QMessageBox.warning(self, "Continuous Read Failed", message)
        )
        self._continuous_worker.stopped.connect(self._on_continuous_stopped)
        self._continuous_worker.start()
        self._read_start_btn.setEnabled(False)
        self._read_stop_btn.setEnabled(True)
        self._status_label.setText("Status: continuous read")

    def _on_stop_continuous(self) -> None:
        """Request stop for periodic PM readout.

        Parameters:
            None (units: none).
        """
        if self._continuous_worker is not None and self._continuous_worker.isRunning():
            self._continuous_worker.abort()

    def _on_continuous_stopped(self, reason: str) -> None:
        """Handle periodic worker stop.

        Parameters:
            reason: Stop reason tag (units: none).
        """
        self._read_start_btn.setEnabled(True)
        self._read_stop_btn.setEnabled(False)
        if not self._is_connected:
            self._status_label.setText("Status: disconnected")
        elif reason == "error":
            self._status_label.setText("Status: continuous read error")
        else:
            self._status_label.setText("Status: connected")

    def _on_read_data(self, payload: dict) -> None:
        """Update measurement labels from worker payload.

        Parameters:
            payload: PM reading payload with SI values (units: W and dBm).
        """
        power_w = float(payload.get("power_W", 0.0))
        power_dbm = float(payload.get("power_dBm", float("-inf")))
        self._power_label.setText(f"Power: {power_w:.4e} W")
        self._dbm_label.setText(f"dBm: {power_dbm:.2f}")
        if "average_W" in payload:
            self._avg_label.setText(f"Average: {float(payload['average_W']):.4e} W")
        else:
            self._avg_label.setText("Average: n/a")
