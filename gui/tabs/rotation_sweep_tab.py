"""Rotation sweep experiment tab UI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
import yaml

from gui.instruments.workers import WriteCommandWorker
from gui.workers import RotationSweepWorker
from instruments.pm100d import PM100D


def open_folder(path: Path) -> None:
    """Open folder in native file browser.

    Parameters:
        path: Path to open (units: none).
    """
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)])
    elif sys.platform == "win32":
        subprocess.run(["explorer", str(path)])
    else:
        subprocess.run(["xdg-open", str(path)])


class RotationSweepTab(QWidget):
    """GUI tab for running rotation sweep experiment.

    Parameters:
        config_path: YAML configuration path (units: none).
        parent: Optional parent widget (units: none).
    """

    log_message = Signal(str, int)

    def __init__(self, config_path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config_path = config_path
        self._worker: RotationSweepWorker | None = None
        self._pm_zero_worker: WriteCommandWorker | None = None
        self._pending_run_kwargs: dict | None = None
        self._zero_sequence_active: bool = False

        self._start = QDoubleSpinBox(self)
        self._start.setRange(0.0, 360.0)
        self._start.setValue(0.0)
        self._stop = QDoubleSpinBox(self)
        self._stop.setRange(0.0, 360.0)
        self._stop.setValue(30.0)
        self._step = QDoubleSpinBox(self)
        self._step.setRange(0.1, 360.0)
        self._step.setValue(5.0)
        self._wavelength_nm = QDoubleSpinBox(self)
        self._wavelength_nm.setRange(400.0, 1100.0)
        self._wavelength_nm.setDecimals(1)
        self._wavelength_nm.setSingleStep(1.0)
        self._average_count = QSpinBox(self)
        self._average_count.setRange(1, 300)
        self._zero_before_sweep = QCheckBox("Zero PM before sweep", self)
        self._initialize_devices = QCheckBox("Initialize devices before run", self)
        self._initialize_devices.setChecked(True)
        self._output = QLineEdit("output", self)

        self._run = QPushButton("Run", self)
        self._abort = QPushButton("Abort", self)
        self._abort.setEnabled(False)
        self._covered_btn = QPushButton("I Covered PM - Zero Now", self)
        self._uncovered_btn = QPushButton("I Uncovered PM - Start Run", self)
        self._covered_btn.setVisible(False)
        self._uncovered_btn.setVisible(False)
        self._progress = QProgressBar(self)
        self._status = QLabel("Idle", self)
        self._output_path = QLabel("", self)
        self._output_path.setOpenExternalLinks(False)

        form = QFormLayout()
        form.addRow("Start (deg)", self._start)
        form.addRow("Stop (deg)", self._stop)
        form.addRow("Step (deg)", self._step)
        form.addRow("PM wavelength (nm)", self._wavelength_nm)
        form.addRow("Readings per angle", self._average_count)
        form.addRow("", self._zero_before_sweep)
        form.addRow("", self._initialize_devices)
        form.addRow("Output Dir", self._output)

        left = QVBoxLayout()
        left.addLayout(form)
        btns = QHBoxLayout()
        btns.addWidget(self._run)
        btns.addWidget(self._abort)
        left.addLayout(btns)
        zero_btns = QHBoxLayout()
        zero_btns.addWidget(self._covered_btn)
        zero_btns.addWidget(self._uncovered_btn)
        left.addLayout(zero_btns)
        left.addWidget(self._progress)
        left.addWidget(self._status)
        left.addWidget(self._output_path)
        left.addStretch(1)

        self._plot = pg.PlotWidget(self)
        self._plot.setLabel("left", "Power", units="W")
        self._plot.setLabel("bottom", "Angle", units="deg")
        self._curve = self._plot.plot([], [], pen=pg.mkPen("c", width=2), symbol="o")

        main = QHBoxLayout(self)
        left_widget = QWidget(self)
        left_widget.setLayout(left)
        left_widget.setMaximumWidth(300)
        main.addWidget(left_widget)
        main.addWidget(self._plot, 1)

        self._run.clicked.connect(self._on_run)
        self._abort.clicked.connect(self._on_abort)
        self._covered_btn.clicked.connect(self._on_zero_covered)
        self._uncovered_btn.clicked.connect(self._on_zero_uncovered_start)
        self._output_path.linkActivated.connect(self._on_open_output)
        self._load_defaults_from_config()

    def set_config_path(self, config_path: str) -> None:
        """Update config path used by worker.

        Parameters:
            config_path: YAML config path (units: none).
        """
        self._config_path = config_path
        self._load_defaults_from_config()

    def _load_defaults_from_config(self) -> None:
        """Load PM defaults from active YAML config.

        Parameters:
            None (units: none).
        """
        try:
            config = yaml.safe_load(Path(self._config_path).read_text(encoding="utf-8")) or {}
        except Exception:
            config = {}

        pm_cfg = config.get("pm100d", {})
        self._wavelength_nm.setValue(float(pm_cfg.get("wavelength_nm", 780.0)))
        self._average_count.setValue(int(pm_cfg.get("averaging_count", 10)))

    def _on_run(self) -> None:
        """Start rotation worker.

        Parameters:
            None (units: none).
        """
        if self._zero_sequence_active:
            return

        self._pending_run_kwargs = self._collect_run_kwargs()
        self._progress.setValue(0)

        if bool(self._zero_before_sweep.isChecked()):
            self._begin_zero_sequence()
            return

        self._start_rotation_worker(self._pending_run_kwargs)

    def _collect_run_kwargs(self) -> dict:
        """Collect current run inputs into worker kwargs.

        Parameters:
            None (units: none).
        """
        return {
            "config_path": self._config_path,
            "output_dir": self._output.text(),
            "start_deg": float(self._start.value()),
            "stop_deg": float(self._stop.value()),
            "step_deg": float(self._step.value()),
            "wavelength_nm": float(self._wavelength_nm.value()),
            "average_count": int(self._average_count.value()),
            "zero_before_sweep": bool(self._zero_before_sweep.isChecked()),
            "initialize_devices": bool(self._initialize_devices.isChecked()),
        }

    def _start_rotation_worker(self, kwargs: dict) -> None:
        """Instantiate and start rotation worker.

        Parameters:
            kwargs: Worker keyword arguments (units: per field).
        """
        self._worker = RotationSweepWorker(
            config_path=str(kwargs["config_path"]),
            output_dir=str(kwargs["output_dir"]),
            start_deg=float(kwargs["start_deg"]),
            stop_deg=float(kwargs["stop_deg"]),
            step_deg=float(kwargs["step_deg"]),
            wavelength_nm=float(kwargs["wavelength_nm"]),
            average_count=int(kwargs["average_count"]),
            zero_before_sweep=bool(kwargs["zero_before_sweep"]),
            initialize_devices=bool(kwargs["initialize_devices"]),
        )
        self._worker.log_message.connect(self.log_message.emit)
        self._worker.status_text.connect(self._status.setText)
        self._worker.progress.connect(lambda cur, total: self._progress.setValue(int(100 * cur / max(1, total))))
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        self._run.setEnabled(False)
        self._abort.setEnabled(True)
        self._covered_btn.setVisible(False)
        self._uncovered_btn.setVisible(False)
        self._status.setText("Running")
        self._worker.start()

    def _begin_zero_sequence(self) -> None:
        """Enter guided PM zero sequence before sweep start.

        Parameters:
            None (units: none).
        """
        self._zero_sequence_active = True
        self._run.setEnabled(False)
        self._abort.setEnabled(True)
        self._covered_btn.setVisible(True)
        self._covered_btn.setEnabled(True)
        self._uncovered_btn.setVisible(False)
        self._uncovered_btn.setEnabled(False)
        self._status.setText("Cover PM, then click 'I Covered PM - Zero Now'.")

    def _cancel_zero_sequence(self) -> None:
        """Reset UI state for canceled guided PM zero.

        Parameters:
            None (units: none).
        """
        self._zero_sequence_active = False
        self._pending_run_kwargs = None
        self._covered_btn.setVisible(False)
        self._uncovered_btn.setVisible(False)
        self._run.setEnabled(True)
        self._abort.setEnabled(False)

    def _pm_zero_config(self) -> dict:
        """Build PM config for guided zero step.

        Parameters:
            None (units: none).
        """
        try:
            cfg = yaml.safe_load(Path(self._config_path).read_text(encoding="utf-8")) or {}
        except Exception:
            cfg = {}

        pm_cfg = dict(cfg.get("pm100d", {}))
        pm_cfg["wavelength_nm"] = float(self._wavelength_nm.value())
        pm_cfg["averaging_count"] = int(self._average_count.value())
        return pm_cfg

    def _on_zero_covered(self) -> None:
        """Zero PM after user confirms sensor is covered.

        Parameters:
            None (units: none).
        """
        if not self._zero_sequence_active:
            return

        self._covered_btn.setEnabled(False)
        self._status.setText("Zeroing PM…")
        pm_cfg = self._pm_zero_config()

        def _zero_cmd(inst: PM100D) -> None:
            inst.set_wavelength(float(self._wavelength_nm.value()))
            inst.set_averaging(int(self._average_count.value()))
            inst.auto_range(bool(pm_cfg.get("auto_range", True)))
            inst.zero()

        self._pm_zero_worker = WriteCommandWorker(PM100D, pm_cfg, _zero_cmd)
        self._pm_zero_worker.success.connect(self._on_zero_complete)
        self._pm_zero_worker.error.connect(self._on_zero_error)
        self._pm_zero_worker.start()

    def _on_zero_complete(self) -> None:
        """Show uncover prompt after PM zero succeeds.

        Parameters:
            None (units: none).
        """
        self._covered_btn.setVisible(False)
        self._uncovered_btn.setVisible(True)
        self._uncovered_btn.setEnabled(True)
        self._status.setText("Zero complete. Uncover PM, then click 'I Uncovered PM - Start Run'.")

    def _on_zero_error(self, message: str) -> None:
        """Handle PM zero failure.

        Parameters:
            message: Error description (units: none).
        """
        QMessageBox.warning(self, "PM Zero Failed", message)
        self._status.setText(f"Error: {message}")
        self._cancel_zero_sequence()

    def _on_zero_uncovered_start(self) -> None:
        """Start sweep after user confirms PM is uncovered.

        Parameters:
            None (units: none).
        """
        if not self._zero_sequence_active or self._pending_run_kwargs is None:
            return

        kwargs = dict(self._pending_run_kwargs)
        kwargs["zero_before_sweep"] = False
        self._zero_sequence_active = False
        self._covered_btn.setVisible(False)
        self._uncovered_btn.setVisible(False)
        self._start_rotation_worker(kwargs)

    def _on_abort(self) -> None:
        """Abort by requesting cooperative worker stop.

        Parameters:
            None (units: none).
        """
        if self._worker is not None and self._worker.isRunning():
            self._worker.request_abort()
            self._status.setText("Aborting…")
            return

        if self._zero_sequence_active:
            if self._pm_zero_worker is not None and self._pm_zero_worker.isRunning():
                self._status.setText("PM zero in progress; wait for completion.")
                return
            self._cancel_zero_sequence()
            self._status.setText("Zero sequence canceled.")

    def _on_finished(self, results: list) -> None:
        """Update plot and state after completion.

        Parameters:
            results: Experiment results list (units: per result fields).
        """
        angles = [float(row.get("angle_deg", 0.0)) for row in results]
        powers = [float(row.get("power_W", 0.0)) for row in results]
        self._curve.setData(angles, powers)
        self._status.setText(f"Finished: {len(results)} points")
        self._run.setEnabled(True)
        self._abort.setEnabled(False)
        self._pending_run_kwargs = None

        output_root = Path(self._output.text())
        latest = self._latest_output_dir(output_root)
        if latest is not None:
            self._output_path.setText(f'<a href="{latest.as_posix()}">Open Output Folder</a>')

    def _on_error(self, message: str) -> None:
        """Handle worker error event.

        Parameters:
            message: Error description (units: none).
        """
        self._status.setText(f"Error: {message}")
        self._run.setEnabled(True)
        self._abort.setEnabled(False)
        self._pending_run_kwargs = None

    def _on_open_output(self, path_text: str) -> None:
        """Open output folder.

        Parameters:
            path_text: Folder path string (units: none).
        """
        open_folder(Path(path_text))

    @staticmethod
    def _latest_output_dir(root: Path) -> Path | None:
        """Return latest timestamped output folder.

        Parameters:
            root: Output root directory (units: none).
        """
        if not root.exists():
            return None
        dirs = [child for child in root.iterdir() if child.is_dir()]
        if not dirs:
            return None
        return max(dirs, key=lambda path: path.stat().st_mtime)
