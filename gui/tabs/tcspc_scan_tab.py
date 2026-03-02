"""TCSPC scan experiment tab UI."""

from __future__ import annotations

from pathlib import Path

import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gui.workers import TCSPCScanWorker
from gui.tabs.rotation_sweep_tab import open_folder


class TCSPCScanTab(QWidget):
    """GUI tab for running TCSPC angle scan.

    Parameters:
        config_path: YAML configuration path (units: none).
        parent: Optional parent widget (units: none).
    """

    log_message = Signal(str, int)

    def __init__(self, config_path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config_path = config_path
        self._worker: TCSPCScanWorker | None = None

        self._angles = QLineEdit("0 90 180", self)
        self._acq_ms = QSpinBox(self)
        self._acq_ms.setRange(1, 100000)
        self._acq_ms.setValue(200)
        self._output = QLineEdit("output", self)

        self._run = QPushButton("Run", self)
        self._abort = QPushButton("Abort", self)
        self._abort.setEnabled(False)
        self._progress = QProgressBar(self)
        self._status = QLabel("Idle", self)
        self._output_path = QLabel("", self)
        self._output_path.setOpenExternalLinks(False)

        form = QFormLayout()
        form.addRow("Angles (deg)", self._angles)
        form.addRow("Acq Time (ms)", self._acq_ms)
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
        self._plot.setLabel("left", "Counts")
        self._plot.setLabel("bottom", "Bin index")
        self._bar = pg.BarGraphItem(x=[], height=[], width=0.8)
        self._plot.addItem(self._bar)

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
        """Start TCSPC worker.

        Parameters:
            None (units: none).
        """
        angles = [float(item) for item in self._angles.text().split() if item.strip()]
        self._worker = TCSPCScanWorker(
            config_path=self._config_path,
            output_dir=self._output.text(),
            angles=angles,
            acq_time_ms=int(self._acq_ms.value()),
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
        """Render summary plot from finished scan.

        Parameters:
            results: Scan summary rows (units: per result fields).
        """
        if results:
            x_vals = list(range(len(results)))
            heights = [float(row.get("total_counts", 0.0)) for row in results]
            self._plot.removeItem(self._bar)
            self._bar = pg.BarGraphItem(x=x_vals, height=heights, width=0.8)
            self._plot.addItem(self._bar)

        self._status.setText(f"Finished: {len(results)} angles")
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
