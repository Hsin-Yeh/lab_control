"""QThread workers for running experiment workflows from GUI."""

from __future__ import annotations

import logging
from pathlib import Path
import threading

from PySide6.QtCore import QThread, Signal

from experiments.iv_curve import run_iv_curve
from experiments.rotation_sweep import run_rotation_sweep
from experiments.tcspc_scan import run_tcspc_scan
from gui.widgets.log_viewer import GuiLogHandler, SignalRelay


class _BaseWorker(QThread):
    """Base experiment worker with common signals and log forwarding.

    Parameters:
        None (units: none).
    """

    log_message = Signal(str, int)
    progress = Signal(int, int)
    status_text = Signal(str)
    finished = Signal(list)
    error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._abort_event = threading.Event()
        self._relay = SignalRelay()
        self._relay.message.connect(self.log_message.emit)
        self._gui_handler = GuiLogHandler(self._relay)
        self._gui_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s")
        )

    def request_abort(self) -> None:
        """Signal the worker to stop at next checkpoint.

        Parameters:
            None (units: none).
        """
        self._abort_event.set()

    def _attach_logger(self, logger_name: str) -> None:
        """Attach GUI handler to logger.

        Parameters:
            logger_name: Name of logger to attach (units: none).
        """
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(self._gui_handler)

    def _detach_logger(self, logger_name: str) -> None:
        """Detach GUI handler from logger.

        Parameters:
            logger_name: Name of logger to detach from (units: none).
        """
        logger = logging.getLogger(logger_name)
        try:
            logger.removeHandler(self._gui_handler)
        except Exception:
            pass


class RotationSweepWorker(_BaseWorker):
    """Worker that runs rotation sweep experiment.

    Parameters:
        config_path: YAML configuration path (units: none).
        output_dir: Output directory path (units: none).
        start_deg: Sweep start angle (units: deg).
        stop_deg: Sweep stop angle (units: deg).
        step_deg: Sweep increment (units: deg).
    """

    def __init__(
        self,
        config_path: str,
        output_dir: str,
        start_deg: float,
        stop_deg: float,
        step_deg: float,
    ) -> None:
        super().__init__()
        self._config_path = config_path
        self._output_dir = str(Path(output_dir))
        self._start_deg = start_deg
        self._stop_deg = stop_deg
        self._step_deg = step_deg

    def run(self) -> None:
        """Execute experiment call in worker thread.

        Parameters:
            None (units: none).
        """
        logger_name = "rotation_sweep"
        self._attach_logger(logger_name)
        self.status_text.emit("Running rotation sweep")
        try:
            results = run_rotation_sweep(
                config_path=self._config_path,
                output_dir=self._output_dir,
                start_deg=self._start_deg,
                stop_deg=self._stop_deg,
                step_deg=self._step_deg,
                abort_event=self._abort_event,
            )
            self.progress.emit(1, 1)
            self.finished.emit(results)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self._detach_logger(logger_name)


class IVCurveWorker(_BaseWorker):
    """Worker that runs I-V curve experiment.

    Parameters:
        config_path: YAML configuration path (units: none).
        output_dir: Output directory path (units: none).
        v_start: Sweep start voltage (units: V).
        v_stop: Sweep stop voltage (units: V).
        v_step: Sweep increment (units: V).
        i_limit: Current compliance limit (units: A).
    """

    def __init__(
        self,
        config_path: str,
        output_dir: str,
        v_start: float,
        v_stop: float,
        v_step: float,
        i_limit: float,
    ) -> None:
        super().__init__()
        self._config_path = config_path
        self._output_dir = str(Path(output_dir))
        self._v_start = v_start
        self._v_stop = v_stop
        self._v_step = v_step
        self._i_limit = i_limit

    def run(self) -> None:
        """Execute experiment call in worker thread.

        Parameters:
            None (units: none).
        """
        logger_name = "iv_curve"
        self._attach_logger(logger_name)
        self.status_text.emit("Running I-V curve")
        try:
            results = run_iv_curve(
                config_path=self._config_path,
                output_dir=self._output_dir,
                v_start=self._v_start,
                v_stop=self._v_stop,
                v_step=self._v_step,
                i_limit=self._i_limit,
                abort_event=self._abort_event,
            )
            self.progress.emit(1, 1)
            self.finished.emit(results)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self._detach_logger(logger_name)


class TCSPCScanWorker(_BaseWorker):
    """Worker that runs TCSPC scan experiment.

    Parameters:
        config_path: YAML configuration path (units: none).
        output_dir: Output directory path (units: none).
        angles: List of angles for scan (units: deg).
        acq_time_ms: Acquisition time per angle (units: ms).
    """

    def __init__(
        self,
        config_path: str,
        output_dir: str,
        angles: list[float],
        acq_time_ms: int,
    ) -> None:
        super().__init__()
        self._config_path = config_path
        self._output_dir = str(Path(output_dir))
        self._angles = angles
        self._acq_time_ms = acq_time_ms

    def run(self) -> None:
        """Execute experiment call in worker thread.

        Parameters:
            None (units: none).
        """
        logger_name = "tcspc_scan"
        self._attach_logger(logger_name)
        self.status_text.emit("Running TCSPC scan")
        try:
            result = run_tcspc_scan(
                config_path=self._config_path,
                output_dir=self._output_dir,
                angles=self._angles,
                acq_time_ms=self._acq_time_ms,
                abort_event=self._abort_event,
            )
            summary = result.get("summary", []) if isinstance(result, dict) else []
            self.progress.emit(1, 1)
            self.finished.emit(summary)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self._detach_logger(logger_name)
