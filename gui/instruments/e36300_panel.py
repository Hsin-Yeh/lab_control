"""Manual E36300 panel for GUI."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from instruments.e36300 import E36300Supply
from gui.instruments.workers import ConnectWorker, SingleReadWorker


class E36300Panel(QWidget):
    """Manual E36300 control panel.

    Parameters:
        config: Instrument config mapping (units: none).
        parent: Optional parent widget (units: none).
    """

    def __init__(self, config: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._connect_worker: ConnectWorker | None = None
        self._single_worker: SingleReadWorker | None = None

        self._channel = QComboBox(self)
        self._channel.addItems(["1", "2", "3"])
        self._voltage = QDoubleSpinBox(self)
        self._voltage.setRange(0.0, 30.0)
        self._voltage.setValue(5.0)
        self._current = QDoubleSpinBox(self)
        self._current.setRange(0.0, 5.0)
        self._current.setValue(0.1)

        self._apply_btn = QPushButton("Apply", self)
        self._output_on_btn = QPushButton("Output ON", self)
        self._output_off_btn = QPushButton("Output OFF", self)
        self._read_btn = QPushButton("Read CH", self)
        self._connect_btn = QPushButton("Connect", self)
        self._disconnect_btn = QPushButton("Disconnect", self)
        self._panic_btn = QPushButton("🛑 ALL OUTPUT OFF (panic)", self)
        self._panic_btn.setStyleSheet("font-weight: bold; color: #CC4444;")

        self._id_label = QLabel("ID: (not connected)", self)
        self._v_label = QLabel("Measured V: 0.000 V", self)
        self._i_label = QLabel("Measured I: 0.000 A", self)
        self._status = QLabel("Status: OFF", self)

        form = QFormLayout()
        form.addRow("Channel", self._channel)
        form.addRow("Set V (V)", self._voltage)
        form.addRow("I limit (A)", self._current)

        left = QVBoxLayout()
        left.addLayout(form)
        btns1 = QHBoxLayout()
        btns1.addWidget(self._apply_btn)
        btns1.addWidget(self._read_btn)
        left.addLayout(btns1)
        btns2 = QHBoxLayout()
        btns2.addWidget(self._output_on_btn)
        btns2.addWidget(self._output_off_btn)
        left.addLayout(btns2)
        conn = QHBoxLayout()
        conn.addWidget(self._connect_btn)
        conn.addWidget(self._disconnect_btn)
        left.addLayout(conn)
        left.addWidget(self._id_label)
        left.addWidget(self._status)
        left.addWidget(self._panic_btn)
        left.addStretch(1)

        right = QVBoxLayout()
        right.addWidget(self._v_label)
        right.addWidget(self._i_label)
        right.addStretch(1)

        main = QHBoxLayout(self)
        left_widget = QWidget(self)
        left_widget.setLayout(left)
        left_widget.setMaximumWidth(320)
        main.addWidget(left_widget)
        main.addLayout(right, 1)

        self._connect_btn.clicked.connect(self._on_connect)
        self._disconnect_btn.clicked.connect(self._on_disconnect)
        self._apply_btn.clicked.connect(self._on_apply)
        self._output_on_btn.clicked.connect(self._on_output_on)
        self._output_off_btn.clicked.connect(self._on_output_off)
        self._read_btn.clicked.connect(self._on_read)
        self._channel.currentIndexChanged.connect(self._on_read)
        self._panic_btn.clicked.connect(self._on_panic)

    def set_config(self, config: dict) -> None:
        """Update panel config.

        Parameters:
            config: Instrument config mapping (units: none).
        """
        self._config = config

    def _channel_value(self) -> int:
        return int(self._channel.currentText())

    def _on_connect(self) -> None:
        self._connect_worker = ConnectWorker(E36300Supply, self._config)
        self._connect_worker.connected.connect(self._on_connected)
        self._connect_worker.start()

    def _on_connected(self, ok: bool, message: str) -> None:
        if ok:
            self._id_label.setText(f"ID: {message}")
        else:
            QMessageBox.warning(self, "Connect Failed", message)

    def _on_disconnect(self) -> None:
        self._id_label.setText("ID: (not connected)")

    def _on_apply(self) -> None:
        channel = self._channel_value()
        try:
            with E36300Supply(self._config) as inst:
                inst.set_voltage(channel, float(self._voltage.value()))
                inst.set_current_limit(channel, float(self._current.value()))
        except Exception as exc:
            QMessageBox.warning(self, "Apply Failed", str(exc))

    def _on_output_on(self) -> None:
        channel = self._channel_value()
        try:
            with E36300Supply(self._config) as inst:
                inst.output_on(channel)
            self._status.setText("Status: ON")
        except Exception as exc:
            QMessageBox.warning(self, "Output ON Failed", str(exc))

    def _on_output_off(self) -> None:
        channel = self._channel_value()
        try:
            with E36300Supply(self._config) as inst:
                inst.output_off(channel)
            self._status.setText("Status: OFF")
        except Exception as exc:
            QMessageBox.warning(self, "Output OFF Failed", str(exc))

    def _on_read(self) -> None:
        channel = self._channel_value()
        self._single_worker = SingleReadWorker(E36300Supply, self._config, channel=channel)
        self._single_worker.data.connect(self._on_data)
        self._single_worker.error.connect(lambda message: QMessageBox.warning(self, "Read Error", message))
        self._single_worker.start()

    def _on_data(self, payload: dict) -> None:
        voltage = float(payload.get("voltage_V", 0.0))
        current = float(payload.get("current_A", 0.0))
        ch = int(payload.get("channel", self._channel_value()))
        self._v_label.setText(f"Measured V (CH{ch}): {voltage:.3f} V")
        self._i_label.setText(f"Measured I (CH{ch}): {current:.3f} A")

    def _on_panic(self) -> None:
        try:
            with E36300Supply(self._config) as inst:
                inst.output_off()
            self._status.setText("Status: OFF")
        except Exception as exc:
            QMessageBox.warning(self, "Panic OFF Failed", str(exc))
