"""GSM continuous output + monitoring experiment tab UI."""

from __future__ import annotations

from pathlib import Path

import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from gui.tabs.rotation_sweep_tab import open_folder
from gui.workers import GSMMonitorWorker


class GSMMonitorTab(QWidget):
    """GUI tab for continuous GSM output + monitoring experiment.

    Parameters:
        config_path: YAML configuration path (units: none).
        parent: Optional parent widget (units: none).
    """

    log_message = Signal(str, int)

    def __init__(self, config_path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config_path = config_path
        self._worker: GSMMonitorWorker | None = None

        self._source_voltage = QDoubleSpinBox(self)
        self._source_voltage.setRange(-210.0, 210.0)
        self._source_voltage.setValue(0.1)

        self._current_limit = QDoubleSpinBox(self)
        self._current_limit.setRange(0.001, 1.05)
        self._current_limit.setValue(0.01)

        self._interval_s = QDoubleSpinBox(self)
        self._interval_s.setRange(0.05, 60.0)
        self._interval_s.setValue(0.5)

        self._duration_s = QDoubleSpinBox(self)
        self._duration_s.setRange(1.0, 36000.0)
        self._duration_s.setValue(60.0)

        self._output = QLineEdit("output", self)

        self._run = QPushButton("Run", self)
        self._abort = QPushButton("Abort", self)
        self._abort.setEnabled(False)
        self._progress = QProgressBar(self)
        self._status = QLabel("Idle", self)
        self._output_path = QLabel("", self)
        self._output_path.setOpenExternalLinks(False)

        form = QFormLayout()
        form.addRow("Source Voltage (V)", self._source_voltage)
        form.addRow("Current Limit (A)", self._current_limit)
        form.addRow("Interval (s)", self._interval_s)
        form.addRow("Duration (s)", self._duration_s)
        form.addRow("Output Dir", self._output)

        left = QVBoxLayout()
        left.addLayout(form)
        btns = QHBoxLayout()
        btns.addWidget(self._run)
        btns.addWidget(self._abort)
        left.addLayout(btns)
        left.addWidget(self._progress)
        left.addWidget(self._status)
        left.addWidget(self._output_path)
        left.addStretch(1)

        self._plot = pg.PlotWidget(self)
        self._plot.setLabel("left", "Power", units="W")
        self._plot.setLabel("bottom", "Elapsed Time", units="s")
        self._curve = self._plot.plot([], [], pen=pg.mkPen("m", width=2), symbol="o")

        main = QHBoxLayout(self)
        left_widget = QWidget(self)
        left_widget.setLayout(left)
        left_widget.setMaximumWidth(320)
        main.addWidget(left_widget)
        main.addWidget(self._plot, 1)

        self._run.clicked.connect(self._on_run)
        self._abort.clicked.connect(self._on_abort)
        self._output_path.linkActivated.connect(self._on_open_output)

    def set_config_path(self, config_path: str) -> None:
        """Update config path used by worker.

        Parameters:
            config_path: YAML config path (units: none).
        """
        self._config_path = config_path

    def _on_run(self) -> None:
        """Start GSM monitor worker.

        Parameters:
            None (units: none).
        """
        self._worker = GSMMonitorWorker(
            config_path=self._config_path,
            output_dir=self._output.text(),
            source_voltage_v=float(self._source_voltage.value()),
            current_limit_a=float(self._current_limit.value()),
            interval_s=float(self._interval_s.value()),
            duration_s=float(self._duration_s.value()),
        )
        self._worker.log_message.connect(self.log_message.emit)
        self._worker.status_text.connect(self._status.setText)
        self._worker.progress.connect(lambda cur, total: self._progress.setValue(int(100 * cur / max(1, total))))
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        self._run.setEnabled(False)
        self._abort.setEnabled(True)
        self._progress.setValue(0)
        self._status.setText("Running")
        self._worker.start()

    def _on_abort(self) -> None:
        """Abort worker cooperatively.

        Parameters:
            None (units: none).
        """
        if self._worker is not None and self._worker.isRunning():
            self._worker.request_abort()
            self._status.setText("Aborting…")

    def _on_finished(self, results: list) -> None:
        """Render plot from completed results.

        Parameters:
            results: Experiment results list (units: per result fields).
        """
        elapsed = [float(row.get("elapsed_s", 0.0)) for row in results]
        power = [float(row.get("power_W", 0.0)) for row in results]
        self._curve.setData(elapsed, power)
        self._status.setText(f"Finished: {len(results)} points")
        self._run.setEnabled(True)
        self._abort.setEnabled(False)

        latest = self._latest_output_dir(Path(self._output.text()))
        if latest is not None:
            self._output_path.setText(f'<a href="{latest.as_posix()}">Open Output Folder</a>')

    def _on_error(self, message: str) -> None:
        """Handle worker error.

        Parameters:
            message: Error description (units: none).
        """
        self._status.setText(f"Error: {message}")
        self._run.setEnabled(True)
        self._abort.setEnabled(False)

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
