"""GW Instek GSM-20H10 source-measure unit driver."""

from __future__ import annotations

import random
import time
from typing import Any

import numpy as np

from .base import BaseInstrument, InstrumentConnectionError


class GSM20H10(BaseInstrument):
    """SCPI interface for GSM-20H10 with sweep helpers."""

    def __init__(self, config: dict[str, Any]):
        """Initialize GSM-20H10 state.

        Parameters:
            config: SMU config (voltage in V, current in A, time in s).
        """
        super().__init__(config)
        self._inst = None
        self._rm = None
        self._sim_last_set_voltage = 0.0

    def connect(self) -> None:
        """Connect to GSM-20H10.

        Parameters:
            None (units: none).
        """
        if self.simulate:
            self._inst = "SIMULATED"
            self.logger.info("Connected to GSM-20H10 (simulated)")
            return

        resource = str(self.config["visa_resource"])
        try:
            import pyvisa  # type: ignore

            self._rm = pyvisa.ResourceManager()
            self._inst = self._rm.open_resource(resource, timeout=10000)
            self._inst.write(":OUTP OFF")
            self.logger.info("Connected to GSM-20H10")
        except Exception as exc:
            raise InstrumentConnectionError("GSM20H10", resource) from exc

    def disconnect(self) -> None:
        """Disconnect from GSM-20H10.

        Parameters:
            None (units: none).
        """
        if self._inst is None:
            return
        try:
            self.output_off()
        finally:
            if not self.simulate:
                self._inst.close()
            self._inst = None

    @property
    def is_connected(self) -> bool:
        """Return connection state.

        Parameters:
            None (units: none).
        """
        return self._inst is not None

    @property
    def instrument_id(self) -> str:
        """Return instrument identity.

        Parameters:
            None (units: none).
        """
        if self.simulate:
            return "GSM20H10:SIMULATED"
        self._require_connected()
        return str(self._inst.query("*IDN?").strip())

    def set_source_voltage(self, voltage: float, current_limit: float = 0.1) -> None:
        """Configure voltage source mode.

        Parameters:
            voltage: Source voltage (units: V).
            current_limit: Compliance current limit (units: A).
        """
        if not -210.0 <= voltage <= 210.0:
            raise ValueError("voltage must be in valid range [-210.0, 210.0] V")
        if not 0 < current_limit <= 1.05:
            raise ValueError("current_limit must be in valid range (0, 1.05] A")

        self._sim_last_set_voltage = float(voltage)
        self._write(":SOUR:FUNC VOLT")
        self._write(f":SOUR:VOLT {voltage}")
        self._write(f":SENS:CURR:PROT {current_limit}")
        self.logger.info("Source voltage set to %.6f V, current limit %.6f A", voltage, current_limit)

    def set_source_current(self, current: float, voltage_limit: float = 10.0) -> None:
        """Configure current source mode.

        Parameters:
            current: Source current (units: A).
            voltage_limit: Compliance voltage limit (units: V).
        """
        if not -1.05 <= current <= 1.05:
            raise ValueError("current must be in valid range [-1.05, 1.05] A")
        if not 0 < voltage_limit <= 210.0:
            raise ValueError("voltage_limit must be in valid range (0, 210.0] V")

        self._write(":SOUR:FUNC CURR")
        self._write(f":SOUR:CURR {current}")
        self._write(f":SENS:VOLT:PROT {voltage_limit}")

    def output_on(self) -> None:
        """Enable source output.

        Parameters:
            None (units: none).
        """
        self._write(":OUTP ON")
        self.logger.info("Output ON")

    def output_off(self) -> None:
        """Disable source output.

        Parameters:
            None (units: none).
        """
        self._write(":OUTP OFF")
        self.logger.info("Output OFF")

    def measure_voltage(self) -> float:
        """Measure terminal voltage.

        Parameters:
            None (units: none).
        """
        if self.simulate:
            return self._sim_last_set_voltage + random.gauss(0.0, 0.001)
        return float(self._query(":MEAS:VOLT?"))

    def measure_current(self) -> float:
        """Measure terminal current.

        Parameters:
            None (units: none).
        """
        if self.simulate:
            return (self._sim_last_set_voltage / 1000.0) + random.gauss(0.0, 1e-6)
        return float(self._query(":MEAS:CURR?"))

    def measure_iv(self) -> dict[str, float]:
        """Measure voltage, current, and absolute power.

        Parameters:
            None (units: none).
        """
        voltage = self.measure_voltage()
        current = self.measure_current()
        return {"voltage": voltage, "current": current, "power": abs(voltage * current)}

    def sweep_voltage(
        self,
        start: float,
        stop: float,
        step: float,
        current_limit: float = 0.05,
        delay_s: float = 0.1,
    ) -> list[dict[str, float]]:
        """Run a voltage sweep with compliance stop.

        Parameters:
            start: Start voltage (units: V).
            stop: Stop voltage (units: V).
            step: Sweep step (units: V).
            current_limit: Compliance current limit (units: A).
            delay_s: Delay after each setpoint (units: s).
        """
        if not -210.0 <= start <= 210.0 or not -210.0 <= stop <= 210.0:
            raise ValueError("start/stop must be in valid range [-210.0, 210.0] V")
        if step == 0:
            raise ValueError("step must be non-zero V")
        if (stop - start) * step < 0:
            raise ValueError("step sign does not move from start toward stop")

        voltages = np.arange(start, stop + step, step, dtype=float)
        results: list[dict[str, float]] = []

        try:
            for voltage in voltages:
                self.set_source_voltage(float(voltage), current_limit)
                self.output_on()
                time.sleep(delay_s)
                measurement = self.measure_iv()
                measurement["set_voltage"] = float(voltage)
                results.append(measurement)
                if abs(measurement["current"]) >= current_limit * 0.99:
                    self.logger.warning("Compliance at %.3f V — stopping sweep", voltage)
                    break
        finally:
            self.output_off()

        return results

    def _write(self, command: str) -> None:
        """Write SCPI command.

        Parameters:
            command: SCPI command string (units: none).
        """
        self._require_connected()
        if self.simulate:
            self.logger.debug("[SIM WRITE] %s", command)
            return
        self._inst.write(command)

    def _query(self, command: str) -> str:
        """Query SCPI command.

        Parameters:
            command: SCPI query string (units: none).
        """
        self._require_connected()
        if self.simulate:
            self.logger.debug("[SIM QUERY] %s", command)
            return "0"
        return str(self._inst.query(command)).strip()

    def _require_connected(self) -> None:
        """Ensure instrument is connected.

        Parameters:
            None (units: none).
        """
        if not self.is_connected:
            raise RuntimeError("GSM20H10 is not connected")