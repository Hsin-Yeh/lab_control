"""QThread workers for running experiment workflows from GUI."""

from __future__ import annotations

import logging
from pathlib import Path
import threading

from PySide6.QtCore import QThread, Signal

from experiments.iv_curve import run_iv_curve
from experiments.gsm_monitor import run_gsm_monitor
from experiments.resistance_log import run_resistance_log
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
        wavelength_nm: PM wavelength setting (units: nm).
        average_count: Number of readings averaged per angle (units: count).
        zero_before_sweep: If True, zero PM before sweep (units: boolean).
        initialize_devices: If True, initialize devices before sweep (units: boolean).
    """

    def __init__(
        self,
        config_path: str,
        output_dir: str,
        start_deg: float,
        stop_deg: float,
        step_deg: float,
        wavelength_nm: float,
        average_count: int,
        zero_before_sweep: bool,
        initialize_devices: bool,
    ) -> None:
        super().__init__()
        self._config_path = config_path
        self._output_dir = str(Path(output_dir))
        self._start_deg = start_deg
        self._stop_deg = stop_deg
        self._step_deg = step_deg
        self._wavelength_nm = wavelength_nm
        self._average_count = average_count
        self._zero_before_sweep = zero_before_sweep
        self._initialize_devices = initialize_devices

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
                wavelength_nm=self._wavelength_nm,
                average_count=self._average_count,
                zero_before_sweep=self._zero_before_sweep,
                initialize_devices=self._initialize_devices,
                abort_event=self._abort_event,
                progress_callback=self._on_progress,
            )
            self.finished.emit(results)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self._detach_logger(logger_name)

    def _on_progress(self, current: int, total: int, row: dict) -> None:
        """Forward per-point progress from experiment runner.

        Parameters:
            current: Completed point count (units: count).
            total: Total point count (units: count).
            row: Latest result row (units: per row fields).
        """
        _ = row
        self.progress.emit(current, total)


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


class ResistanceLogWorker(_BaseWorker):
    """Worker that runs long-term resistance logging.

    Parameters:
        config_path: YAML configuration path (units: none).
        output_dir: Output directory path (units: none).
        source_voltage_v: Fixed source voltage (units: V).
        current_limit_a: Current compliance limit (units: A).
        interval_s: Sampling interval (units: s).
        duration_s: Total duration (units: s).
        compliance_stop: Enable compliance-based stop (units: boolean).
    """

    def __init__(
        self,
        config_path: str,
        output_dir: str,
        source_voltage_v: float,
        current_limit_a: float,
        interval_s: float,
        duration_s: float,
        compliance_stop: bool,
    ) -> None:
        super().__init__()
        self._config_path = config_path
        self._output_dir = str(Path(output_dir))
        self._source_voltage_v = source_voltage_v
        self._current_limit_a = current_limit_a
        self._interval_s = interval_s
        self._duration_s = duration_s
        self._compliance_stop = compliance_stop

    def run(self) -> None:
        """Execute resistance logging in worker thread.

        Parameters:
            None (units: none).
        """
        logger_name = "resistance_log"
        self._attach_logger(logger_name)
        self.status_text.emit("Running resistance log")
        try:
            results = run_resistance_log(
                config_path=self._config_path,
                output_dir=self._output_dir,
                source_voltage_v=self._source_voltage_v,
                current_limit_a=self._current_limit_a,
                interval_s=self._interval_s,
                duration_s=self._duration_s,
                compliance_stop=self._compliance_stop,
                abort_event=self._abort_event,
                progress_callback=lambda cur, total: self.progress.emit(int(cur), int(total)),
            )
            self.finished.emit(results)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self._detach_logger(logger_name)


class GSMMonitorWorker(_BaseWorker):
    """Worker that runs GSM continuous monitor experiment.

    Parameters:
        config_path: YAML configuration path (units: none).
        output_dir: Output directory path (units: none).
        source_voltage_v: Fixed source voltage (units: V).
        current_limit_a: Current compliance limit (units: A).
        interval_s: Sampling interval (units: s).
        duration_s: Total duration (units: s).
    """

    def __init__(
        self,
        config_path: str,
        output_dir: str,
        source_voltage_v: float,
        current_limit_a: float,
        interval_s: float,
        duration_s: float,
    ) -> None:
        super().__init__()
        self._config_path = config_path
        self._output_dir = str(Path(output_dir))
        self._source_voltage_v = source_voltage_v
        self._current_limit_a = current_limit_a
        self._interval_s = interval_s
        self._duration_s = duration_s

    def run(self) -> None:
        """Execute GSM monitor run in worker thread.

        Parameters:
            None (units: none).
        """
        logger_name = "gsm_monitor"
        self._attach_logger(logger_name)
        self.status_text.emit("Running GSM monitor")
        try:
            results = run_gsm_monitor(
                config_path=self._config_path,
                output_dir=self._output_dir,
                source_voltage_v=self._source_voltage_v,
                current_limit_a=self._current_limit_a,
                interval_s=self._interval_s,
                duration_s=self._duration_s,
                abort_event=self._abort_event,
                progress_callback=lambda cur, total: self.progress.emit(int(cur), int(total)),
            )
            self.finished.emit(results)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self._detach_logger(logger_name)
