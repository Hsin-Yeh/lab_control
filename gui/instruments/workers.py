"""Instrument-level QThread workers for manual GUI panels."""

from __future__ import annotations

import threading
import time

from PySide6.QtCore import QThread, Signal


class ConnectWorker(QThread):
    """Connect/disconnect test worker that reads instrument id only.

    Parameters:
        cls: Instrument class to instantiate (units: none).
        cfg: Instrument config mapping (units: none).
    """

    connected = Signal(bool, str)

    def __init__(self, cls: type, cfg: dict):
        super().__init__()
        self._cls = cls
        self._cfg = cfg

    def run(self) -> None:
        """Attempt connection and emit id or error.

        Parameters:
            None (units: none).
        """
        try:
            with self._cls(self._cfg) as inst:
                identifier = inst.instrument_id
                if callable(identifier):
                    identifier = identifier()
                self.connected.emit(True, str(identifier))
        except Exception as exc:
            self.connected.emit(False, str(exc))


class SingleReadWorker(QThread):
    """Worker performing one non-destructive instrument read.

    Parameters:
        cls: Instrument class to instantiate (units: none).
        cfg: Instrument config mapping (units: none).
        channel: Optional channel selection for multi-channel devices (units: channel index).
    """

    data = Signal(dict)
    error = Signal(str)

    def __init__(self, cls: type, cfg: dict, channel: int | None = None):
        super().__init__()
        self._cls = cls
        self._cfg = cfg
        self._channel = channel

    def run(self) -> None:
        """Read one data sample.

        Parameters:
            None (units: none).
        """
        try:
            with self._cls(self._cfg) as inst:
                now = time.time()
                if hasattr(inst, "measure_iv"):
                    iv = inst.measure_iv()
                    self.data.emit(
                        {
                            "voltage_V": float(iv["voltage"]),
                            "current_A": float(iv["current"]),
                            "power_W": float(iv["power"]),
                            "timestamp_s": now,
                        }
                    )
                    return

                if self._channel is None:
                    self.error.emit("Channel is required for this instrument read")
                    return

                voltage = float(inst.measure_voltage(self._channel))
                current = float(inst.measure_current(self._channel))
                self.data.emit(
                    {
                        "voltage_V": voltage,
                        "current_A": current,
                        "channel": int(self._channel),
                        "timestamp_s": now,
                    }
                )
        except Exception as exc:
            self.error.emit(str(exc))


class ContinuousPollWorker(QThread):
    """Worker for periodic GSM read polling.

    Parameters:
        cls: Instrument class to instantiate (units: none).
        cfg: Instrument config mapping (units: none).
        interval_ms: Polling interval (units: ms).
        output_off_on_stop: If True, call output_off() when worker exits (units: boolean).
    """

    data = Signal(dict)
    error = Signal(str)
    stopped = Signal(str)

    def __init__(
        self,
        cls: type,
        cfg: dict,
        interval_ms: int,
        output_off_on_stop: bool = False,
    ) -> None:
        super().__init__()
        self._cls = cls
        self._cfg = cfg
        self._interval_ms = max(50, int(interval_ms))
        self._output_off_on_stop = output_off_on_stop
        self._abort_event = threading.Event()

    def abort(self) -> None:
        """Request polling loop stop.

        Parameters:
            None (units: none).
        """
        self._abort_event.set()

    def run(self) -> None:
        """Run polling loop until abort or error.

        Parameters:
            None (units: none).
        """
        try:
            with self._cls(self._cfg) as inst:
                while not self._abort_event.is_set():
                    iv = inst.measure_iv()
                    self.data.emit(
                        {
                            "voltage_V": float(iv["voltage"]),
                            "current_A": float(iv["current"]),
                            "power_W": float(iv["power"]),
                            "timestamp_s": time.time(),
                        }
                    )
                    if self._abort_event.wait(self._interval_ms / 1000.0):
                        break

                if self._output_off_on_stop and hasattr(inst, "output_off"):
                    inst.output_off()
                self.stopped.emit("user")
        except Exception as exc:
            self.error.emit(str(exc))
            self.stopped.emit("error")
