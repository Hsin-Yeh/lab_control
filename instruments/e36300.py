"""Keysight E36300 series power supply driver."""

from __future__ import annotations

import time
from typing import Any

from .base import BaseInstrument, InstrumentConnectionError


class E36300Supply(BaseInstrument):
    """SCPI interface for Keysight E36300 family."""

    def __init__(self, config: dict[str, Any]):
        """Initialize E36300 state.

        Parameters:
            config: Supply config (voltage in V, current in A, times in s).
        """
        super().__init__(config)
        self._inst = None
        self._rm = None

    def connect(self) -> None:
        """Connect to supply.

        Parameters:
            None (units: none).
        """
        if self.simulate:
            self._inst = "SIMULATED"
            self.logger.info("Connected to simulated E36300")
            return

        resource = str(self.config["visa_resource"])
        try:
            import pyvisa  # type: ignore

            self._rm = pyvisa.ResourceManager()
            self._inst = self._rm.open_resource(resource, timeout=5000)
            self.logger.info("Connected to E36300: %s", self.instrument_id)
        except Exception as exc:
            raise InstrumentConnectionError("E36300Supply", resource) from exc

    def disconnect(self) -> None:
        """Disconnect from supply.

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
        """Return supply identity string.

        Parameters:
            None (units: none).
        """
        if self.simulate:
            return "E36300:SIMULATED"
        self._require_connected()
        return str(self._inst.query("*IDN?").strip())

    def _select_channel(self, ch: int) -> None:
        """Select output channel.

        Parameters:
            ch: Channel index (units: channel number).
        """
        if ch not in {1, 2, 3}:
            raise ValueError("Channel must be 1, 2, or 3")
        self._write(f":INST:SEL CH{ch}")

    def set_voltage(self, channel: int, voltage: float) -> None:
        """Set channel voltage setpoint.

        Parameters:
            channel: Output channel (units: channel number).
            voltage: Voltage setpoint (units: V).
        """
        self._select_channel(channel)
        self._write(f":VOLT {voltage:.4f}")
        self.logger.info("CH%d voltage -> %.4f V", channel, voltage)

    def set_current_limit(self, channel: int, current: float) -> None:
        """Set channel current limit.

        Parameters:
            channel: Output channel (units: channel number).
            current: Current limit (units: A).
        """
        self._select_channel(channel)
        self._write(f":CURR {current:.4f}")
        self.logger.info("CH%d current limit -> %.4f A", channel, current)

    def output_on(self, channel: int | None = None) -> None:
        """Enable outputs.

        Parameters:
            channel: Optional channel to enable; None for all (units: channel number).
        """
        if channel is None:
            self._write(":OUTP:STAT ON")
            return
        if channel not in {1, 2, 3}:
            raise ValueError("Channel must be 1, 2, or 3")
        self._write(f":OUTP:SEL CH{channel},ON")

    def output_off(self, channel: int | None = None) -> None:
        """Disable outputs.

        Parameters:
            channel: Optional channel to disable; None for all (units: channel number).
        """
        if channel is None:
            self._write(":OUTP:STAT OFF")
            return
        if channel not in {1, 2, 3}:
            raise ValueError("Channel must be 1, 2, or 3")
        self._write(f":OUTP:SEL CH{channel},OFF")

    def measure_voltage(self, channel: int) -> float:
        """Measure output voltage.

        Parameters:
            channel: Output channel (units: channel number).
        """
        if self.simulate:
            return float(self.config.get("sim_voltage", 5.0))
        self._select_channel(channel)
        return float(self._query(":MEAS:VOLT?"))

    def measure_current(self, channel: int) -> float:
        """Measure output current.

        Parameters:
            channel: Output channel (units: channel number).
        """
        if self.simulate:
            return float(self.config.get("sim_current", 0.1))
        self._select_channel(channel)
        return float(self._query(":MEAS:CURR?"))

    def measure_power(self, channel: int) -> float:
        """Compute output power from measured V and I.

        Parameters:
            channel: Output channel (units: channel number).
        """
        return self.measure_voltage(channel) * self.measure_current(channel)

    def reset(self) -> None:
        """Reset instrument and clear status.

        Parameters:
            None (units: none).
        """
        self._write("*RST")
        self._write("*CLS")
        time.sleep(1.0)
        self.logger.info("Instrument reset complete")

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
            raise RuntimeError("E36300Supply is not connected")