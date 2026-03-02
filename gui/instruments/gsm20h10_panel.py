"""Manual GSM20H10 control panel for GUI."""

from __future__ import annotations

from collections import deque
from pathlib import Path
import time

import pyqtgraph as pg
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from instruments.gsm20h10 import GSM20H10
from gui.instruments.workers import ConnectWorker, ContinuousPollWorker, SingleReadWorker


class GSM20H10Panel(QWidget):
    """Manual GSM20H10 panel with live polling and panic off.

    Parameters:
        config: Instrument config mapping (units: none).
        parent: Optional parent widget (units: none).
    """

    def __init__(self, config: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._connect_worker: ConnectWorker | None = None
        self._single_worker: SingleReadWorker | None = None
        self._poll_worker: ContinuousPollWorker | None = None

        self._setpoint = QDoubleSpinBox(self)
        self._setpoint.setRange(-210.0, 210.0)
        self._setpoint.setValue(0.0)
        self._compliance = QDoubleSpinBox(self)
        self._compliance.setRange(0.001, 1.05)
        self._compliance.setValue(0.01)

        self._interval = QSpinBox(self)
        self._interval.setRange(50, 10000)
        self._interval.setValue(500)
        self._log_csv = QCheckBox("Log to CSV while live", self)

        self._connect_btn = QPushButton("Connect", self)
        self._disconnect_btn = QPushButton("Disconnect", self)
        self._output_on_btn = QPushButton("Output ON", self)
        self._output_off_btn = QPushButton("Output OFF", self)
        self._read_once_btn = QPushButton("Read Once", self)
        self._start_live_btn = QPushButton("Start Live", self)
        self._stop_live_btn = QPushButton("Stop Live", self)
        self._panic_btn = QPushButton("🛑 OUTPUT OFF (panic)", self)

        self._stop_live_btn.setEnabled(False)
        self._panic_btn.setStyleSheet("font-weight: bold; color: #CC4444;")

        self._id_label = QLabel("ID: (not connected)", self)
        self._status_label = QLabel("Status: OFF", self)
        self._v_label = QLabel("Measured V: 0.00000 V", self)
        self._i_label = QLabel("Measured I: 0.00000 A", self)
        self._p_label = QLabel("Power: 0.00000 W", self)

        self._history_t: deque[float] = deque(maxlen=200)
        self._history_p: deque[float] = deque(maxlen=200)
        self._curve_plot = pg.PlotWidget(self)
        self._curve_plot.setLabel("left", "Power", units="W")
        self._curve_plot.setLabel("bottom", "Time", units="s")
        self._curve = self._curve_plot.plot([], [], pen=pg.mkPen("m", width=2))

        form = QFormLayout()
        form.addRow("Setpoint (V)", self._setpoint)
        form.addRow("Compliance (A)", self._compliance)
        form.addRow("Poll interval (ms)", self._interval)

        left = QVBoxLayout()
        left.addLayout(form)

        output_buttons = QHBoxLayout()
        output_buttons.addWidget(self._output_on_btn)
        output_buttons.addWidget(self._output_off_btn)
        left.addLayout(output_buttons)
        left.addWidget(self._status_label)

        live_buttons = QHBoxLayout()
        live_buttons.addWidget(self._start_live_btn)
        live_buttons.addWidget(self._stop_live_btn)
        left.addWidget(self._read_once_btn)
        left.addLayout(live_buttons)
        left.addWidget(self._log_csv)

        conn_buttons = QHBoxLayout()
        conn_buttons.addWidget(self._connect_btn)
        conn_buttons.addWidget(self._disconnect_btn)
        left.addLayout(conn_buttons)
        left.addWidget(self._id_label)
        left.addWidget(self._panic_btn)
        left.addStretch(1)

        right = QVBoxLayout()
        grid = QGridLayout()
        grid.addWidget(self._v_label, 0, 0)
        grid.addWidget(self._i_label, 1, 0)
        grid.addWidget(self._p_label, 2, 0)
        right.addLayout(grid)
        right.addWidget(self._curve_plot, 1)

        main = QHBoxLayout(self)
        left_widget = QWidget(self)
        left_widget.setLayout(left)
        left_widget.setMaximumWidth(320)
        main.addWidget(left_widget)
        main.addLayout(right, 1)

        self._connect_btn.clicked.connect(self._on_connect)
        self._disconnect_btn.clicked.connect(self._on_disconnect)
        self._output_on_btn.clicked.connect(self._on_output_on)
        self._output_off_btn.clicked.connect(self._on_output_off)
        self._read_once_btn.clicked.connect(self._on_read_once)
        self._start_live_btn.clicked.connect(self._on_start_live)
        self._stop_live_btn.clicked.connect(self._on_stop_live)
        self._panic_btn.clicked.connect(self._on_panic)

    def set_config(self, config: dict) -> None:
        """Update panel config.

        Parameters:
            config: Instrument config mapping (units: none).
        """
        self._config = config

    def _on_connect(self) -> None:
        self._connect_worker = ConnectWorker(GSM20H10, self._config)
        self._connect_worker.connected.connect(self._on_connected)
        self._connect_worker.start()

    def _on_connected(self, ok: bool, message: str) -> None:
        if ok:
            self._id_label.setText(f"ID: {message}")
        else:
            QMessageBox.warning(self, "Connect Failed", message)

    def _on_disconnect(self) -> None:
        self._id_label.setText("ID: (not connected)")
        self._on_stop_live()

    def _on_output_on(self) -> None:
        try:
            with GSM20H10(self._config) as inst:
                inst.set_source_voltage(float(self._setpoint.value()), float(self._compliance.value()))
                inst.output_on()
            self._status_label.setText("Status: ON")
        except Exception as exc:
            QMessageBox.warning(self, "Output ON Failed", str(exc))

    def _on_output_off(self) -> None:
        try:
            with GSM20H10(self._config) as inst:
                inst.output_off()
            self._status_label.setText("Status: OFF")
        except Exception as exc:
            QMessageBox.warning(self, "Output OFF Failed", str(exc))

    def _on_read_once(self) -> None:
        self._single_worker = SingleReadWorker(GSM20H10, self._config)
        self._single_worker.data.connect(self._on_data)
        self._single_worker.error.connect(lambda message: QMessageBox.warning(self, "Read Error", message))
        self._single_worker.start()

    def _on_start_live(self) -> None:
        self._poll_worker = ContinuousPollWorker(
            GSM20H10,
            self._config,
            interval_ms=int(self._interval.value()),
            output_off_on_stop=False,
        )
        self._poll_worker.data.connect(self._on_data)
        self._poll_worker.error.connect(lambda message: QMessageBox.warning(self, "Live Error", message))
        self._poll_worker.stopped.connect(self._on_live_stopped)
        self._poll_worker.start()

        self._start_live_btn.setEnabled(False)
        self._stop_live_btn.setEnabled(True)

    def _on_stop_live(self) -> None:
        if self._poll_worker is not None and self._poll_worker.isRunning():
            self._poll_worker.abort()
        self._start_live_btn.setEnabled(True)
        self._stop_live_btn.setEnabled(False)

    def _on_live_stopped(self, reason: str) -> None:
        self._start_live_btn.setEnabled(True)
        self._stop_live_btn.setEnabled(False)
        _ = reason

    def _on_panic(self) -> None:
        self._on_stop_live()
        self._on_output_off()

    def _on_data(self, payload: dict) -> None:
        voltage = float(payload.get("voltage_V", 0.0))
        current = float(payload.get("current_A", 0.0))
        power = float(payload.get("power_W", voltage * current))
        self._v_label.setText(f"Measured V: {voltage:.5f} V")
        self._i_label.setText(f"Measured I: {current:.5f} A")
        self._p_label.setText(f"Power: {power:.5f} W")

        t = float(payload.get("timestamp_s", time.time()))
        self._history_t.append(t)
        self._history_p.append(power)
        if self._history_t:
            t0 = self._history_t[0]
            x = [item - t0 for item in self._history_t]
            y = list(self._history_p)
            self._curve.setData(x, y)

        if self._log_csv.isChecked():
            self._append_live_csv(voltage, current, power)

    def _append_live_csv(self, voltage: float, current: float, power: float) -> None:
        """Append a line to live CSV log.

        Parameters:
            voltage: Measured voltage (units: V).
            current: Measured current (units: A).
            power: Measured power (units: W).
        """
        file_path = Path("output") / "gsm20h10_live.csv"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        exists = file_path.exists()
        with file_path.open("a", encoding="utf-8") as handle:
            if not exists:
                handle.write("timestamp_s,voltage_V,current_A,power_W\n")
            handle.write(f"{time.time():.6f},{voltage:.6f},{current:.6f},{power:.6f}\n")
