"""PicoHarp 300 TCSPC driver."""

from __future__ import annotations

import ctypes
import random
import time
from typing import Any

import numpy as np

from .base import BaseInstrument, InstrumentCommandError, InstrumentConnectionError

HISTCHAN = 65536
MODE_HIST = 0
MODE_T2 = 2
MODE_T3 = 3


class PicoHarp300(BaseInstrument):
    """ctypes-based PicoHarp 300 interface with simulation mode."""

    def __init__(self, config: dict[str, Any]):
        """Initialize PicoHarp state.

        Parameters:
            config: PicoHarp config (times in ps/ms, levels in mV).
        """
        super().__init__(config)
        self._dll = None
        self._serial = ""

    def _check(self, retcode: int, func_name: str) -> None:
        """Raise InstrumentCommandError on negative PicoHarp return code.

        Parameters:
            retcode: Return code from PHLib function (units: none).
            func_name: Function label for error context (units: none).
        """
        if retcode >= 0:
            return

        if self._dll is None:
            raise InstrumentCommandError("PicoHarp300", func_name, f"retcode={retcode}")

        err_buf = ctypes.create_string_buffer(40)
        try:
            self._dll.PH_GetErrorString(err_buf, retcode)
            response = err_buf.value.decode(errors="replace")
        except Exception:
            response = f"retcode={retcode}"
        raise InstrumentCommandError("PicoHarp300", func_name, response)

    def connect(self) -> None:
        """Connect and initialize PicoHarp in histogram mode.

        Parameters:
            None (units: none).
        """
        if self.simulate:
            self._dll = "SIMULATED"
            self._serial = "SIM0001"
            self.logger.info("PicoHarp300 connected, serial=%s, resolution=%.1f ps", self._serial, self.get_resolution())
            return

        dev_idx = int(self.config.get("device_index", 0))
        dll_path = str(self.config["phlib_path"])
        try:
            self._dll = ctypes.CDLL(dll_path)
        except Exception as exc:
            raise InstrumentConnectionError("PicoHarp300", dll_path) from exc

        serial_buf = ctypes.create_string_buffer(8)
        self._check(self._dll.PH_OpenDevice(dev_idx, serial_buf), "OpenDevice")

        configured_mode = self.config.get("mode", "hist")
        fallback_enabled = bool(self.config.get("init_mode_fallback", True))

        mode_map = {"hist": MODE_HIST, "t2": MODE_T2, "t3": MODE_T3}
        if isinstance(configured_mode, str):
            key = configured_mode.strip().lower()
            if key not in mode_map:
                raise ValueError("mode must be one of {'hist', 't2', 't3'} or integer 0/2/3")
            preferred_mode = mode_map[key]
        else:
            preferred_mode = int(configured_mode)
            if preferred_mode not in {MODE_HIST, MODE_T2, MODE_T3}:
                raise ValueError("mode must be in valid set {0, 2, 3}")

        candidate_modes = [preferred_mode]
        if fallback_enabled:
            for mode in (MODE_HIST, MODE_T2, MODE_T3):
                if mode not in candidate_modes:
                    candidate_modes.append(mode)

        init_errors: list[tuple[int, str]] = []
        selected_mode: int | None = None
        for mode in candidate_modes:
            retcode = self._dll.PH_Initialize(dev_idx, mode)
            if retcode >= 0:
                selected_mode = mode
                break

            err_buf = ctypes.create_string_buffer(40)
            try:
                self._dll.PH_GetErrorString(err_buf, retcode)
                err_text = err_buf.value.decode(errors="replace")
            except Exception:
                err_text = f"retcode={retcode}"
            init_errors.append((mode, err_text))

        if selected_mode is None:
            err_detail = "; ".join([f"mode={mode}:{msg}" for mode, msg in init_errors])
            try:
                self._dll.PH_CloseDevice(dev_idx)
            except Exception:
                pass
            self._dll = None
            raise InstrumentCommandError("PicoHarp300", "Initialize", err_detail)

        self._check(self._dll.PH_Calibrate(dev_idx), "Calibrate")

        self.set_sync_divider(int(self.config.get("sync_divider", 1)))
        self.set_cfd(0, int(self.config.get("cfd_sync_level_mv", 100)), int(self.config.get("cfd_sync_zerocross_mv", 10)))
        self.set_cfd(1, int(self.config.get("cfd_input_level_mv", 100)), int(self.config.get("cfd_input_zerocross_mv", 10)))
        self.set_binning(int(self.config.get("binning", 0)))

        self._serial = serial_buf.value.decode(errors="replace")
        self.logger.info(
            "PicoHarp300 connected, serial=%s, mode=%d, resolution=%.1f ps",
            self._serial,
            selected_mode,
            self.get_resolution(),
        )

    def disconnect(self) -> None:
        """Disconnect PicoHarp device.

        Parameters:
            None (units: none).
        """
        if self._dll is None:
            return
        if self.simulate:
            self._dll = None
            return
        dev_idx = int(self.config.get("device_index", 0))
        self._check(self._dll.PH_CloseDevice(dev_idx), "CloseDevice")
        self._dll = None

    @property
    def is_connected(self) -> bool:
        """Return connection state.

        Parameters:
            None (units: none).
        """
        return self._dll is not None

    @property
    def instrument_id(self) -> str:
        """Return PicoHarp identity string.

        Parameters:
            None (units: none).
        """
        idx = int(self.config.get("device_index", 0))
        serial = self._serial or "UNKNOWN"
        return f"PicoHarp300:dev{idx}:{serial}"

    def set_sync_divider(self, divider: int) -> None:
        """Set sync divider.

        Parameters:
            divider: Sync divider value (units: ratio, valid 1/2/4/8).
        """
        if divider not in {1, 2, 4, 8}:
            raise ValueError("divider must be in valid set {1, 2, 4, 8}")
        self._require_connected()
        if self.simulate:
            self.logger.debug("[SIM] SetSyncDiv %d", divider)
            return
        dev_idx = int(self.config.get("device_index", 0))
        self._check(self._dll.PH_SetSyncDiv(dev_idx, divider), "SetSyncDiv")

    def set_cfd(self, channel: int, level_mv: int, zerocross_mv: int) -> None:
        """Set CFD parameters for a channel.

        Parameters:
            channel: Channel index (units: channel number, 0=sync,1=input).
            level_mv: CFD level threshold (units: mV).
            zerocross_mv: CFD zero-crossing setting (units: mV).
        """
        if channel not in {0, 1}:
            raise ValueError("channel must be in valid set {0, 1}")
        self._require_connected()
        if self.simulate:
            self.logger.debug("[SIM] SetInputCFD ch=%d level=%d zc=%d", channel, level_mv, zerocross_mv)
            return
        dev_idx = int(self.config.get("device_index", 0))
        self._check(self._dll.PH_SetInputCFD(dev_idx, channel, level_mv, zerocross_mv), "SetInputCFD")

    def set_binning(self, binning: int) -> None:
        """Set histogram binning.

        Parameters:
            binning: Binning exponent (units: integer, valid range 0..7).
        """
        if not 0 <= binning <= 7:
            raise ValueError("binning must be in valid range [0, 7]")
        self._require_connected()
        self.config["binning"] = int(binning)
        if self.simulate:
            self.logger.debug("[SIM] SetBinning %d", binning)
            return
        dev_idx = int(self.config.get("device_index", 0))
        self._check(self._dll.PH_SetBinning(dev_idx, binning), "SetBinning")

    def set_offset(self, offset_ps: int) -> None:
        """Set time offset.

        Parameters:
            offset_ps: Histogram time offset (units: ps).
        """
        self._require_connected()
        if self.simulate:
            self.logger.debug("[SIM] SetOffset %d ps", offset_ps)
            return
        dev_idx = int(self.config.get("device_index", 0))
        self._check(self._dll.PH_SetOffset(dev_idx, offset_ps), "SetOffset")

    def get_resolution(self) -> float:
        """Get histogram time resolution.

        Parameters:
            None (units: none).
        """
        self._require_connected()
        if self.simulate:
            return 4.0 * (2 ** int(self.config.get("binning", 0)))
        dev_idx = int(self.config.get("device_index", 0))
        resolution = ctypes.c_double()
        self._check(self._dll.PH_GetResolution(dev_idx, ctypes.byref(resolution)), "GetResolution")
        return float(resolution.value)

    def get_count_rate(self, channel: int) -> int:
        """Get count rate for sync/input channel.

        Parameters:
            channel: Channel index (units: channel number).
        """
        self._require_connected()
        if self.simulate:
            return random.randint(50000, 200000)
        dev_idx = int(self.config.get("device_index", 0))
        rate = ctypes.c_int()
        self._check(self._dll.PH_GetCountRate(dev_idx, channel, ctypes.byref(rate)), "GetCountRate")
        return int(rate.value)

    def acquire(self, acq_time_ms: int | None = None) -> np.ndarray:
        """Acquire one histogram frame.

        Parameters:
            acq_time_ms: Acquisition duration (units: ms).
        """
        self._require_connected()
        acquisition_ms = int(acq_time_ms or self.config.get("acq_time_ms", 1000))

        if self.simulate:
            channels = np.arange(HISTCHAN)
            peak_ch = 1000
            sigma = 50.0
            amplitude = 10000.0
            signal = amplitude * np.exp(-0.5 * ((channels - peak_ch) / sigma) ** 2)
            decay_mask = channels > peak_ch
            signal[decay_mask] += amplitude * np.exp(-(channels[decay_mask] - peak_ch) / 3000.0)
            hist = np.random.poisson(signal).astype(np.uint32)
            return hist

        dev_idx = int(self.config.get("device_index", 0))
        counts_buf = (ctypes.c_uint * HISTCHAN)()
        self._check(self._dll.PH_ClearHistMem(dev_idx, 0), "ClearHistMem")
        self._check(self._dll.PH_StartMeas(dev_idx, acquisition_ms), "StartMeas")

        ctc = ctypes.c_int(0)
        while ctc.value == 0:
            self._check(self._dll.PH_CTCStatus(dev_idx, ctypes.byref(ctc)), "CTCStatus")
            time.sleep(0.05)

        self._check(self._dll.PH_StopMeas(dev_idx), "StopMeas")
        self._check(self._dll.PH_GetHistogram(dev_idx, counts_buf, 0), "GetHistogram")
        return np.array(counts_buf[:], dtype=np.uint32)

    def _require_connected(self) -> None:
        """Ensure instrument is connected.

        Parameters:
            None (units: none).
        """
        if not self.is_connected:
            raise RuntimeError("PicoHarp300 is not connected")