"""I-V curve experiment tab UI."""

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

from gui.workers import IVCurveWorker
from gui.tabs.rotation_sweep_tab import open_folder


class IVCurveTab(QWidget):
    """GUI tab for running I-V curve experiment.

    Parameters:
        config_path: YAML configuration path (units: none).
        parent: Optional parent widget (units: none).
    """

    log_message = Signal(str, int)

    def __init__(self, config_path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config_path = config_path
        self._worker: IVCurveWorker | None = None

        self._start = QDoubleSpinBox(self)
        self._start.setRange(-210.0, 210.0)
        self._start.setValue(-1.0)
        self._stop = QDoubleSpinBox(self)
        self._stop.setRange(-210.0, 210.0)
        self._stop.setValue(1.0)
        self._step = QDoubleSpinBox(self)
        self._step.setRange(0.001, 210.0)
        self._step.setValue(0.1)
        self._limit = QDoubleSpinBox(self)
        self._limit.setRange(0.001, 1.05)
        self._limit.setValue(0.05)
        self._output = QLineEdit("output", self)

        self._run = QPushButton("Run", self)
        self._abort = QPushButton("Abort", self)
        self._abort.setEnabled(False)
        self._progress = QProgressBar(self)
        self._status = QLabel("Idle", self)
        self._output_path = QLabel("", self)
        self._output_path.setOpenExternalLinks(False)

        form = QFormLayout()
        form.addRow("V Start (V)", self._start)
        form.addRow("V Stop (V)", self._stop)
        form.addRow("V Step (V)", self._step)
        form.addRow("I Limit (A)", self._limit)
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
        self._plot.setLabel("left", "Current", units="A")
        self._plot.setLabel("bottom", "Voltage", units="V")
        self._curve = self._plot.plot([], [], pen=pg.mkPen("y", width=2), symbol="o")

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
        """Start I-V worker.

        Parameters:
            None (units: none).
        """
        self._worker = IVCurveWorker(
            config_path=self._config_path,
            output_dir=self._output.text(),
            v_start=float(self._start.value()),
            v_stop=float(self._stop.value()),
            v_step=float(self._step.value()),
            i_limit=float(self._limit.value()),
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
        """Abort worker.

        Parameters:
            None (units: none).
        """
        if self._worker is not None and self._worker.isRunning():
            self._worker.terminate()
            self._status.setText("Aborted")
            self._run.setEnabled(True)
            self._abort.setEnabled(False)

    def _on_finished(self, results: list) -> None:
        """Render plot from completed results.

        Parameters:
            results: Experiment results list (units: per result fields).
        """
        voltages = [float(row.get("voltage", 0.0)) for row in results]
        currents = [float(row.get("current", 0.0)) for row in results]
        self._curve.setData(voltages, currents)
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
