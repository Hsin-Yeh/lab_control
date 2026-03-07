"""Combined Kinesis panel for KDC101 stage and filter flipper."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QThread, Signal
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

from gui import FLIPPER_AVAILABLE, KDC101_AVAILABLE, KinesisFlipper, KDC101Stage
from gui.instruments.workers import ConnectWorker, WriteCommandWorker


class KinesisQueryWorker(QThread):
    """Worker for one read-only Kinesis query.

    Parameters:
        cls: Instrument class to instantiate (units: none).
        cfg: Instrument config mapping (units: none).
        query: Callable that returns a payload dictionary (units: none).
    """

    data = Signal(dict)
    error = Signal(str)

    def __init__(self, cls: type, cfg: dict, query: Callable):
        super().__init__()
        self._cls = cls
        self._cfg = cfg
        self._query = query

    def run(self) -> None:
        """Run one query and emit resulting payload.

        Parameters:
            None (units: none).
        """
        try:
            with self._cls(self._cfg) as inst:
                payload = self._query(inst)
                self.data.emit(dict(payload))
        except Exception as exc:
            self.error.emit(str(exc))


class KinesisPanel(QWidget):
    """Combined controls for KDC101 stage and filter flipper.

    Parameters:
        config: Full instrument config mapping (units: none).
        parent: Optional parent widget (units: none).
    """

    def __init__(self, config: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._stage_cfg = dict(config.get("kdc101", {}))
        self._flipper_cfg = dict(config.get("flipper", {}))

        self._stage_connect_worker: ConnectWorker | None = None
        self._flipper_connect_worker: ConnectWorker | None = None
        self._stage_write_worker: WriteCommandWorker | None = None
        self._flipper_write_worker: WriteCommandWorker | None = None
        self._stage_query_worker: KinesisQueryWorker | None = None
        self._flipper_query_worker: KinesisQueryWorker | None = None

        self._stage_connected = False
        self._flipper_connected = False
        self._stage_busy = False
        self._flipper_busy = False

        self._build_ui()
        self._wire_signals()
        self._apply_platform_availability()
        self._refresh_controls()

    def _build_ui(self) -> None:
        self._stage_target_deg = QDoubleSpinBox(self)
        self._stage_target_deg.setRange(0.0, 360.0)
        self._stage_target_deg.setDecimals(3)
        self._stage_target_deg.setSingleStep(1.0)
        self._stage_target_deg.setValue(0.0)

        self._stage_connect_btn = QPushButton("Connect", self)
        self._stage_disconnect_btn = QPushButton("Disconnect", self)
        self._stage_home_btn = QPushButton("Home", self)
        self._stage_move_btn = QPushButton("Move To", self)
        self._stage_stop_btn = QPushButton("Stop", self)
        self._stage_read_btn = QPushButton("Read Angle", self)

        self._stage_id = QLabel("ID: (not connected)", self)
        self._stage_status = QLabel("Status: idle", self)
        self._stage_angle = QLabel("Angle: n/a", self)

        stage_form = QFormLayout()
        stage_form.addRow("Target angle (deg)", self._stage_target_deg)

        stage_buttons_1 = QHBoxLayout()
        stage_buttons_1.addWidget(self._stage_home_btn)
        stage_buttons_1.addWidget(self._stage_move_btn)
        stage_buttons_1.addWidget(self._stage_stop_btn)

        stage_buttons_2 = QHBoxLayout()
        stage_buttons_2.addWidget(self._stage_read_btn)

        stage_conn = QHBoxLayout()
        stage_conn.addWidget(self._stage_connect_btn)
        stage_conn.addWidget(self._stage_disconnect_btn)

        stage_layout = QVBoxLayout()
        stage_layout.addWidget(QLabel("<b>KDC101 Stage</b>", self))
        stage_layout.addLayout(stage_form)
        stage_layout.addLayout(stage_buttons_1)
        stage_layout.addLayout(stage_buttons_2)
        stage_layout.addLayout(stage_conn)
        stage_layout.addWidget(self._stage_id)
        stage_layout.addWidget(self._stage_status)
        stage_layout.addWidget(self._stage_angle)
        stage_layout.addStretch(1)

        self._flipper_position = QComboBox(self)
        self._flipper_position.addItems(["1", "2"])

        self._flipper_connect_btn = QPushButton("Connect", self)
        self._flipper_disconnect_btn = QPushButton("Disconnect", self)
        self._flipper_set_btn = QPushButton("Set Position", self)
        self._flipper_toggle_btn = QPushButton("Toggle", self)
        self._flipper_home_btn = QPushButton("Home", self)
        self._flipper_read_btn = QPushButton("Read Position", self)

        self._flipper_id = QLabel("ID: (not connected)", self)
        self._flipper_status = QLabel("Status: idle", self)
        self._flipper_pos_label = QLabel("Position: n/a", self)

        flipper_form = QFormLayout()
        flipper_form.addRow("Target position", self._flipper_position)

        flipper_buttons_1 = QHBoxLayout()
        flipper_buttons_1.addWidget(self._flipper_set_btn)
        flipper_buttons_1.addWidget(self._flipper_toggle_btn)
        flipper_buttons_1.addWidget(self._flipper_home_btn)

        flipper_buttons_2 = QHBoxLayout()
        flipper_buttons_2.addWidget(self._flipper_read_btn)

        flipper_conn = QHBoxLayout()
        flipper_conn.addWidget(self._flipper_connect_btn)
        flipper_conn.addWidget(self._flipper_disconnect_btn)

        flipper_layout = QVBoxLayout()
        flipper_layout.addWidget(QLabel("<b>Filter Flipper</b>", self))
        flipper_layout.addLayout(flipper_form)
        flipper_layout.addLayout(flipper_buttons_1)
        flipper_layout.addLayout(flipper_buttons_2)
        flipper_layout.addLayout(flipper_conn)
        flipper_layout.addWidget(self._flipper_id)
        flipper_layout.addWidget(self._flipper_status)
        flipper_layout.addWidget(self._flipper_pos_label)
        flipper_layout.addStretch(1)

        root = QHBoxLayout(self)
        stage_widget = QWidget(self)
        stage_widget.setLayout(stage_layout)
        flipper_widget = QWidget(self)
        flipper_widget.setLayout(flipper_layout)
        root.addWidget(stage_widget)
        root.addWidget(flipper_widget)

    def _wire_signals(self) -> None:
        self._stage_connect_btn.clicked.connect(self._on_stage_connect)
        self._stage_disconnect_btn.clicked.connect(self._on_stage_disconnect)
        self._stage_home_btn.clicked.connect(self._on_stage_home)
        self._stage_move_btn.clicked.connect(self._on_stage_move)
        self._stage_stop_btn.clicked.connect(self._on_stage_stop)
        self._stage_read_btn.clicked.connect(self._on_stage_read)

        self._flipper_connect_btn.clicked.connect(self._on_flipper_connect)
        self._flipper_disconnect_btn.clicked.connect(self._on_flipper_disconnect)
        self._flipper_set_btn.clicked.connect(self._on_flipper_set)
        self._flipper_toggle_btn.clicked.connect(self._on_flipper_toggle)
        self._flipper_home_btn.clicked.connect(self._on_flipper_home)
        self._flipper_read_btn.clicked.connect(self._on_flipper_read)

    def _apply_platform_availability(self) -> None:
        if not KDC101_AVAILABLE or KDC101Stage is None:
            for button in (
                self._stage_connect_btn,
                self._stage_disconnect_btn,
                self._stage_home_btn,
                self._stage_move_btn,
                self._stage_stop_btn,
                self._stage_read_btn,
            ):
                button.setEnabled(False)
            self._stage_status.setText("Status: unavailable on this platform")

        if not FLIPPER_AVAILABLE or KinesisFlipper is None:
            for button in (
                self._flipper_connect_btn,
                self._flipper_disconnect_btn,
                self._flipper_set_btn,
                self._flipper_toggle_btn,
                self._flipper_home_btn,
                self._flipper_read_btn,
            ):
                button.setEnabled(False)
            self._flipper_status.setText("Status: unavailable on this platform")

    def _refresh_controls(self) -> None:
        """Refresh button states from current connectivity and busy flags.

        Parameters:
            None (units: none).
        """
        stage_available = bool(KDC101_AVAILABLE and KDC101Stage is not None)
        flipper_available = bool(FLIPPER_AVAILABLE and KinesisFlipper is not None)

        self._stage_target_deg.setEnabled(stage_available and self._stage_connected and not self._stage_busy)
        self._stage_connect_btn.setEnabled(stage_available and not self._stage_connected and not self._stage_busy)
        self._stage_disconnect_btn.setEnabled(stage_available and self._stage_connected and not self._stage_busy)
        self._stage_home_btn.setEnabled(stage_available and self._stage_connected and not self._stage_busy)
        self._stage_move_btn.setEnabled(stage_available and self._stage_connected and not self._stage_busy)
        self._stage_stop_btn.setEnabled(stage_available and self._stage_connected and not self._stage_busy)
        self._stage_read_btn.setEnabled(stage_available and self._stage_connected and not self._stage_busy)

        self._flipper_position.setEnabled(flipper_available and self._flipper_connected and not self._flipper_busy)
        self._flipper_connect_btn.setEnabled(flipper_available and not self._flipper_connected and not self._flipper_busy)
        self._flipper_disconnect_btn.setEnabled(flipper_available and self._flipper_connected and not self._flipper_busy)
        self._flipper_set_btn.setEnabled(flipper_available and self._flipper_connected and not self._flipper_busy)
        self._flipper_toggle_btn.setEnabled(flipper_available and self._flipper_connected and not self._flipper_busy)
        self._flipper_home_btn.setEnabled(flipper_available and self._flipper_connected and not self._flipper_busy)
        self._flipper_read_btn.setEnabled(flipper_available and self._flipper_connected and not self._flipper_busy)

    def _set_stage_busy(self, busy: bool, status: str | None = None) -> None:
        """Set stage busy flag and refresh controls.

        Parameters:
            busy: Busy state value (units: boolean).
            status: Optional status line override (units: none).
        """
        self._stage_busy = bool(busy)
        if status is not None:
            self._stage_status.setText(status)
        self._refresh_controls()

    def _set_flipper_busy(self, busy: bool, status: str | None = None) -> None:
        """Set flipper busy flag and refresh controls.

        Parameters:
            busy: Busy state value (units: boolean).
            status: Optional status line override (units: none).
        """
        self._flipper_busy = bool(busy)
        if status is not None:
            self._flipper_status.setText(status)
        self._refresh_controls()

    def set_config(self, config: dict) -> None:
        """Update panel config values.

        Parameters:
            config: Full instrument config mapping (units: none).
        """
        self._stage_cfg = dict(config.get("kdc101", {}))
        self._flipper_cfg = dict(config.get("flipper", {}))
        self._on_stage_disconnect()
        self._on_flipper_disconnect()
        self._refresh_controls()

    def _on_stage_connect(self) -> None:
        if not KDC101_AVAILABLE or KDC101Stage is None:
            return
        if self._stage_busy:
            return
        self._set_stage_busy(True, "Status: connecting")
        self._stage_connect_worker = ConnectWorker(KDC101Stage, self._stage_cfg)
        self._stage_connect_worker.connected.connect(self._on_stage_connected)
        self._stage_connect_worker.finished.connect(lambda: self._set_stage_busy(False))
        self._stage_connect_worker.start()

    def _on_stage_connected(self, ok: bool, message: str) -> None:
        """Handle stage connect result.

        Parameters:
            ok: Connection success state (units: boolean).
            message: Instrument ID or error text (units: none).
        """
        self._stage_connected = ok
        if ok:
            self._stage_id.setText(f"ID: {message}")
            self._stage_status.setText("Status: connected")
        else:
            self._stage_status.setText("Status: connect failed")
            QMessageBox.warning(self, "KDC101 Connect Failed", message)
        self._refresh_controls()

    def _on_stage_disconnect(self) -> None:
        """Clear stage state labels.

        Parameters:
            None (units: none).
        """
        self._stage_connected = False
        self._stage_id.setText("ID: (not connected)")
        if KDC101_AVAILABLE and KDC101Stage is not None:
            self._stage_status.setText("Status: disconnected")
        self._stage_angle.setText("Angle: n/a")
        self._set_stage_busy(False)

    def _on_stage_home(self) -> None:
        if not self._stage_connected:
            QMessageBox.information(self, "KDC101", "Connect to KDC101 first.")
            return
        if self._stage_busy:
            return
        self._set_stage_busy(True, "Status: homing")
        self._stage_write_worker = WriteCommandWorker(KDC101Stage, self._stage_cfg, lambda inst: inst.home())
        self._stage_write_worker.success.connect(lambda: self._stage_status.setText("Status: homed"))
        self._stage_write_worker.success.connect(self._on_stage_read)
        self._stage_write_worker.error.connect(lambda message: QMessageBox.warning(self, "KDC101 Home Failed", message))
        self._stage_write_worker.finished.connect(lambda: self._set_stage_busy(False))
        self._stage_write_worker.start()

    def _on_stage_move(self) -> None:
        if not self._stage_connected:
            QMessageBox.information(self, "KDC101", "Connect to KDC101 first.")
            return
        if self._stage_busy:
            return
        target = float(self._stage_target_deg.value())
        self._set_stage_busy(True, f"Status: moving to {target:.3f} deg")
        self._stage_write_worker = WriteCommandWorker(
            KDC101Stage,
            self._stage_cfg,
            lambda inst: inst.move_to(target),
        )
        self._stage_write_worker.success.connect(
            lambda: self._stage_status.setText(f"Status: moved to {target:.3f} deg")
        )
        self._stage_write_worker.success.connect(self._on_stage_read)
        self._stage_write_worker.error.connect(lambda message: QMessageBox.warning(self, "KDC101 Move Failed", message))
        self._stage_write_worker.finished.connect(lambda: self._set_stage_busy(False))
        self._stage_write_worker.start()

    def _on_stage_stop(self) -> None:
        if not self._stage_connected:
            QMessageBox.information(self, "KDC101", "Connect to KDC101 first.")
            return
        if self._stage_busy:
            return
        self._set_stage_busy(True, "Status: stop requested")
        self._stage_write_worker = WriteCommandWorker(KDC101Stage, self._stage_cfg, lambda inst: inst.stop())
        self._stage_write_worker.success.connect(lambda: self._stage_status.setText("Status: stop requested"))
        self._stage_write_worker.error.connect(lambda message: QMessageBox.warning(self, "KDC101 Stop Failed", message))
        self._stage_write_worker.finished.connect(lambda: self._set_stage_busy(False))
        self._stage_write_worker.start()

    def _on_stage_read(self) -> None:
        if not self._stage_connected:
            QMessageBox.information(self, "KDC101", "Connect to KDC101 first.")
            return
        if self._stage_busy:
            return
        self._set_stage_busy(True, "Status: reading angle")
        self._stage_query_worker = KinesisQueryWorker(
            KDC101Stage,
            self._stage_cfg,
            lambda inst: {"angle_deg": float(inst.get_angle())},
        )
        self._stage_query_worker.data.connect(self._on_stage_data)
        self._stage_query_worker.error.connect(
            lambda message: QMessageBox.warning(self, "KDC101 Read Failed", message)
        )
        self._stage_query_worker.finished.connect(lambda: self._set_stage_busy(False))
        self._stage_query_worker.start()

    def _on_stage_data(self, payload: dict) -> None:
        """Update stage labels from data payload.

        Parameters:
            payload: Stage payload with angle (units: deg).
        """
        angle_deg = float(payload.get("angle_deg", 0.0))
        self._stage_angle.setText(f"Angle: {angle_deg:.3f} deg")
        if self._stage_connected:
            self._stage_status.setText("Status: connected")

    def _on_flipper_connect(self) -> None:
        if not FLIPPER_AVAILABLE or KinesisFlipper is None:
            return
        if self._flipper_busy:
            return
        self._set_flipper_busy(True, "Status: connecting")
        self._flipper_connect_worker = ConnectWorker(KinesisFlipper, self._flipper_cfg)
        self._flipper_connect_worker.connected.connect(self._on_flipper_connected)
        self._flipper_connect_worker.finished.connect(lambda: self._set_flipper_busy(False))
        self._flipper_connect_worker.start()

    def _on_flipper_connected(self, ok: bool, message: str) -> None:
        """Handle flipper connect result.

        Parameters:
            ok: Connection success state (units: boolean).
            message: Instrument ID or error text (units: none).
        """
        self._flipper_connected = ok
        if ok:
            self._flipper_id.setText(f"ID: {message}")
            self._flipper_status.setText("Status: connected")
        else:
            self._flipper_status.setText("Status: connect failed")
            QMessageBox.warning(self, "Flipper Connect Failed", message)
        self._refresh_controls()

    def _on_flipper_disconnect(self) -> None:
        """Clear flipper state labels.

        Parameters:
            None (units: none).
        """
        self._flipper_connected = False
        self._flipper_id.setText("ID: (not connected)")
        if FLIPPER_AVAILABLE and KinesisFlipper is not None:
            self._flipper_status.setText("Status: disconnected")
        self._flipper_pos_label.setText("Position: n/a")
        self._set_flipper_busy(False)

    def _on_flipper_set(self) -> None:
        if not self._flipper_connected:
            QMessageBox.information(self, "Flipper", "Connect to flipper first.")
            return
        if self._flipper_busy:
            return
        position = int(self._flipper_position.currentText())
        self._set_flipper_busy(True, f"Status: moving to position {position}")
        self._flipper_write_worker = WriteCommandWorker(
            KinesisFlipper,
            self._flipper_cfg,
            lambda inst: inst.set_position(position),
        )
        self._flipper_write_worker.success.connect(
            lambda: self._flipper_status.setText(f"Status: moved to position {position}")
        )
        self._flipper_write_worker.success.connect(self._on_flipper_read)
        self._flipper_write_worker.error.connect(
            lambda message: QMessageBox.warning(self, "Flipper Move Failed", message)
        )
        self._flipper_write_worker.finished.connect(lambda: self._set_flipper_busy(False))
        self._flipper_write_worker.start()

    def _on_flipper_toggle(self) -> None:
        if not self._flipper_connected:
            QMessageBox.information(self, "Flipper", "Connect to flipper first.")
            return
        if self._flipper_busy:
            return
        self._set_flipper_busy(True, "Status: toggling")
        self._flipper_write_worker = WriteCommandWorker(
            KinesisFlipper,
            self._flipper_cfg,
            lambda inst: inst.toggle(),
        )
        self._flipper_write_worker.success.connect(lambda: self._flipper_status.setText("Status: toggled"))
        self._flipper_write_worker.success.connect(self._on_flipper_read)
        self._flipper_write_worker.error.connect(
            lambda message: QMessageBox.warning(self, "Flipper Toggle Failed", message)
        )
        self._flipper_write_worker.finished.connect(lambda: self._set_flipper_busy(False))
        self._flipper_write_worker.start()

    def _on_flipper_home(self) -> None:
        if not self._flipper_connected:
            QMessageBox.information(self, "Flipper", "Connect to flipper first.")
            return
        if self._flipper_busy:
            return
        self._set_flipper_busy(True, "Status: homing")
        self._flipper_write_worker = WriteCommandWorker(
            KinesisFlipper,
            self._flipper_cfg,
            lambda inst: inst.home(),
        )
        self._flipper_write_worker.success.connect(lambda: self._flipper_status.setText("Status: homed"))
        self._flipper_write_worker.success.connect(self._on_flipper_read)
        self._flipper_write_worker.error.connect(
            lambda message: QMessageBox.warning(self, "Flipper Home Failed", message)
        )
        self._flipper_write_worker.finished.connect(lambda: self._set_flipper_busy(False))
        self._flipper_write_worker.start()

    def _on_flipper_read(self) -> None:
        if not self._flipper_connected:
            QMessageBox.information(self, "Flipper", "Connect to flipper first.")
            return
        if self._flipper_busy:
            return
        self._set_flipper_busy(True, "Status: reading position")
        self._flipper_query_worker = KinesisQueryWorker(
            KinesisFlipper,
            self._flipper_cfg,
            lambda inst: {"position": int(inst.get_position())},
        )
        self._flipper_query_worker.data.connect(self._on_flipper_data)
        self._flipper_query_worker.error.connect(
            lambda message: QMessageBox.warning(self, "Flipper Read Failed", message)
        )
        self._flipper_query_worker.finished.connect(lambda: self._set_flipper_busy(False))
        self._flipper_query_worker.start()

    def _on_flipper_data(self, payload: dict) -> None:
        """Update flipper labels from data payload.

        Parameters:
            payload: Flipper payload with state position (units: state).
        """
        position = int(payload.get("position", 1))
        self._flipper_pos_label.setText(f"Position: {position}")
        self._flipper_position.setCurrentText(str(position))
        if self._flipper_connected:
            self._flipper_status.setText("Status: connected")
