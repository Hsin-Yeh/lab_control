"""Rotation sweep experiment tab UI."""

from __future__ import annotations

import subprocess
import sys
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

from gui.workers import RotationSweepWorker


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

        self._start = QDoubleSpinBox(self)
        self._start.setRange(0.0, 360.0)
        self._start.setValue(0.0)
        self._stop = QDoubleSpinBox(self)
        self._stop.setRange(0.0, 360.0)
        self._stop.setValue(30.0)
        self._step = QDoubleSpinBox(self)
        self._step.setRange(0.1, 360.0)
        self._step.setValue(5.0)
        self._output = QLineEdit("output", self)

        self._run = QPushButton("Run", self)
        self._abort = QPushButton("Abort", self)
        self._abort.setEnabled(False)
        self._progress = QProgressBar(self)
        self._status = QLabel("Idle", self)
        self._output_path = QLabel("", self)
        self._output_path.setOpenExternalLinks(False)

        form = QFormLayout()
        form.addRow("Start (deg)", self._start)
        form.addRow("Stop (deg)", self._stop)
        form.addRow("Step (deg)", self._step)
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
        self._output_path.linkActivated.connect(self._on_open_output)

    def set_config_path(self, config_path: str) -> None:
        """Update config path used by worker.

        Parameters:
            config_path: YAML config path (units: none).
        """
        self._config_path = config_path

    def _on_run(self) -> None:
        """Start rotation worker.

        Parameters:
            None (units: none).
        """
        self._worker = RotationSweepWorker(
            config_path=self._config_path,
            output_dir=self._output.text(),
            start_deg=float(self._start.value()),
            stop_deg=float(self._stop.value()),
            step_deg=float(self._step.value()),
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
        """Abort by requesting worker termination.

        Parameters:
            None (units: none).
        """
        if self._worker is not None and self._worker.isRunning():
            self._worker.terminate()
            self._status.setText("Aborted")
            self._run.setEnabled(True)
            self._abort.setEnabled(False)

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
