"""Thorlabs PM100D power meter driver."""

from __future__ import annotations

import math
import random
import statistics
from typing import Any

from .base import BaseInstrument, InstrumentConnectionError


class PM100D(BaseInstrument):
    """PM100D wrapper with simulation support."""

    def __init__(self, config: dict[str, Any]):
        """Initialize PM100D state.

        Parameters:
            config: PM config (wavelength in nm, averaging count in samples).
        """
        super().__init__(config)
        self._pm = None
        self._rm = None

    def connect(self) -> None:
        """Connect to PM100D over VISA.

        Parameters:
            None (units: none).
        """
        if self.simulate:
            self._pm = "SIMULATED"
            self.logger.info("Connected to PM100D: %s", self.instrument_id)
            return

        resource = str(self.config["visa_resource"])
        try:
            import pyvisa  # type: ignore
            from ThorlabsPM100 import ThorlabsPM100  # type: ignore

            self._rm = pyvisa.ResourceManager()
            raw = self._rm.open_resource(resource, timeout=5000)
            self._pm = ThorlabsPM100(inst=raw)
            self.set_wavelength(float(self.config.get("wavelength_nm", 780.0)))
            self.set_averaging(int(self.config.get("averaging_count", 10)))
            self.logger.info("Connected to PM100D: %s", self.instrument_id)
        except Exception as exc:
            raise InstrumentConnectionError("PM100D", resource) from exc

    def _get_raw_instrument(self) -> Any:
        """Return underlying VISA instrument handle from wrapper.

        Parameters:
            None (units: none).
        """
        if self._pm is None:
            return None
        for attr in ("_inst", "instrument", "inst"):
            if hasattr(self._pm, attr):
                return getattr(self._pm, attr)
        return None

    def disconnect(self) -> None:
        """Disconnect PM100D.

        Parameters:
            None (units: none).
        """
        if self.simulate:
            self._pm = None
            return
        if self._pm is not None:
            raw = self._get_raw_instrument()
            if raw is not None and hasattr(raw, "close"):
                raw.close()
            self._pm = None

    @property
    def is_connected(self) -> bool:
        """Return connection state.

        Parameters:
            None (units: none).
        """
        return self._pm is not None

    @property
    def instrument_id(self) -> str:
        """Return PM100D identity string.

        Parameters:
            None (units: none).
        """
        if self.simulate:
            return "PM100D:SIMULATED"
        self._require_connected()
        raw = self._get_raw_instrument()
        if raw is None:
            return "PM100D:UNKNOWN"
        return str(raw.query("*IDN?").strip())

    def set_wavelength(self, wavelength_nm: float) -> None:
        """Set detector correction wavelength.

        Parameters:
            wavelength_nm: Optical wavelength (units: nm).
        """
        if not 400.0 <= wavelength_nm <= 1100.0:
            raise ValueError("wavelength_nm must be in valid range [400.0, 1100.0] nm")
        self._require_connected()
        if self.simulate:
            self.logger.info("[SIM] Wavelength set to %.1f nm", wavelength_nm)
            return
        self._pm.sense.correction.wavelength = float(wavelength_nm)
        self.logger.info("Wavelength set to %.1f nm", wavelength_nm)

    def set_averaging(self, count: int) -> None:
        """Set hardware averaging count.

        Parameters:
            count: Number of averaged samples (units: count).
        """
        if not 1 <= count <= 300:
            raise ValueError("count must be in valid range [1, 300]")
        self._require_connected()
        if self.simulate:
            self.logger.info("[SIM] Averaging set to %d", count)
            return
        self._pm.sense.average.count = int(count)

    def auto_range(self, enable: bool = True) -> None:
        """Enable or disable auto range.

        Parameters:
            enable: Auto-range state (units: boolean).
        """
        self._require_connected()
        if self.simulate:
            self.logger.info("[SIM] Auto range set to %s", enable)
            return
        self._pm.sense.power.dc.range.auto = int(enable)

    def read_power(self) -> float:
        """Read optical power.

        Parameters:
            None (units: none).
        """
        self._require_connected()
        if self.simulate:
            power = abs(random.gauss(1e-6, 1e-8))
        else:
            power = float(self._pm.read)
        self.logger.debug("Power reading: %.4e W", power)
        return power

    def read_power_dbm(self) -> float:
        """Read optical power in dBm.

        Parameters:
            None (units: none).
        """
        power_w = self.read_power()
        if power_w <= 0:
            return float("-inf")
        return 10.0 * math.log10(power_w / 1e-3)

    def read_power_average(self, n: int = 10) -> float:
        """Average multiple power readings.

        Parameters:
            n: Number of samples to average (units: count).
        """
        if n <= 0:
            raise ValueError("n must be in valid range [1, inf)")
        samples = [self.read_power() for _ in range(n)]
        mean = statistics.fmean(samples)
        std = statistics.pstdev(samples) if len(samples) > 1 else 0.0
        self.logger.debug("Power avg over %d samples: mean=%.4e W std=%.4e W", n, mean, std)
        return float(mean)

    def zero(self) -> None:
        """Start PM100D zero adjustment routine.

        Parameters:
            None (units: none).
        """
        self._require_connected()
        if self.simulate:
            self.logger.info("[SIM] Zero adjustment triggered")
            return

        raw = self._get_raw_instrument()
        if raw is None:
            raise RuntimeError("PM100D raw instrument handle unavailable")

        # SCPI path is used for broad wrapper compatibility.
        raw.write("SENS:CORR:COLL:ZERO:INIT")
        if hasattr(raw, "query"):
            try:
                raw.query("*OPC?")
            except Exception:
                # Some adapters do not support OPC query; zero still starts.
                pass
        self.logger.info("Zero adjustment complete")

    def _require_connected(self) -> None:
        """Ensure instrument is connected.

        Parameters:
            None (units: none).
        """
        if not self.is_connected:
            raise RuntimeError("PM100D is not connected")