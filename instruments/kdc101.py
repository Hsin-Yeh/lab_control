"""Thorlabs KDC101 rotation stage driver."""

from __future__ import annotations

import time
from typing import Any

from .base import BaseInstrument, InstrumentConnectionError


class KDC101Stage(BaseInstrument):
    """KDC101 stage wrapper with real and simulate modes."""

    def __init__(self, config: dict[str, Any]):
        """Initialize KDC101 state.

        Parameters:
            config: Stage config (angles in deg, velocities in deg/s, times in s).
        """
        super().__init__(config)
        self._motor = None
        self._sim_angle = 0.0
        self._sim_velocity = float(self.config.get("velocity_deg_per_s", 10.0))

    def connect(self) -> None:
        """Connect to KDC101 controller.

        Parameters:
            None (units: none).
        """
        if self.simulate:
            self._motor = "SIMULATED"
            self._sim_angle = 0.0
            self.logger.info("Connected to simulated KDC101")
            return

        serial = str(self.config["serial"])
        kinesis_path = str(self.config["kinesis_path"])
        scale = str(self.config.get("scale", "PRM1-Z8"))

        try:
            import pylablib as pll  # type: ignore

            pll.par["devices/dlls/kinesis"] = kinesis_path
            from pylablib.devices import Thorlabs  # type: ignore

            devices = Thorlabs.list_kinesis_devices()
            available_serials = {str(item[0]) for item in devices}
            if serial not in available_serials:
                raise InstrumentConnectionError("KDC101Stage", serial)

            self._motor = Thorlabs.KinesisMotor(serial, scale=scale)
            self.logger.info("Connected to KDC101 serial %s", serial)
        except InstrumentConnectionError:
            raise
        except Exception as exc:
            raise InstrumentConnectionError("KDC101Stage", serial) from exc

    def disconnect(self) -> None:
        """Disconnect from KDC101 controller.

        Parameters:
            None (units: none).
        """
        if self.simulate:
            self._motor = None
            return
        if self._motor is not None:
            self._motor.close()
            self._motor = None

    @property
    def is_connected(self) -> bool:
        """Return connection state.

        Parameters:
            None (units: none).
        """
        return self._motor is not None

    @property
    def instrument_id(self) -> str:
        """Return instrument identifier.

        Parameters:
            None (units: none).
        """
        return f"KDC101:{self.config.get('serial', 'SIM')}"

    def home(self) -> None:
        """Home stage to 0 deg.

        Parameters:
            None (units: none).
        """
        self._require_connected()
        if self.simulate:
            time.sleep(0.5)
            self._sim_angle = 0.0
            self.logger.info("Homing complete, position: %.3f deg", self.get_angle())
            return
        self._motor.home(sync=True)
        self.logger.info("Homing complete, position: %.3f deg", self.get_angle())

    def move_to(self, angle_deg: float) -> None:
        """Move stage to absolute angle.

        Parameters:
            angle_deg: Target angle (units: deg).
        """
        if not 0.0 <= angle_deg <= 360.0:
            raise ValueError("angle_deg must be in valid range [0.0, 360.0] deg")
        self._require_connected()

        if self.simulate:
            delta = abs(angle_deg - self._sim_angle)
            velocity = max(self._sim_velocity, 1e-6)
            time.sleep(delta / velocity)
            self._sim_angle = float(angle_deg)
            self.logger.info("Move complete, position: %.3f deg", self._sim_angle)
            return

        self._motor.move_to(angle_deg)
        self._motor.wait_move()
        self.logger.info("Move complete, position: %.3f deg", self.get_angle())

    def get_angle(self) -> float:
        """Read current stage angle.

        Parameters:
            None (units: none).
        """
        self._require_connected()
        if self.simulate:
            return float(self._sim_angle)
        return float(self._motor.get_position())

    def set_velocity(self, deg_per_s: float) -> None:
        """Set stage max velocity.

        Parameters:
            deg_per_s: Maximum speed (units: deg/s).
        """
        if deg_per_s <= 0:
            raise ValueError("deg_per_s must be > 0 deg/s")
        self._sim_velocity = float(deg_per_s)
        self._require_connected()
        if self.simulate:
            self.logger.info("[SIM] Velocity set to %.3f deg/s", deg_per_s)
            return
        self._motor.setup_velocity(max_speed=deg_per_s)

    def stop(self) -> None:
        """Stop stage motion immediately.

        Parameters:
            None (units: none).
        """
        self._require_connected()
        if self.simulate:
            self.logger.info("[SIM] Stop requested")
            return
        self._motor.stop(immediate=True)

    def jog(self, direction: str, step_deg: float = 1.0) -> None:
        """Jog stage in a direction.

        Parameters:
            direction: Jog sign, "+" or "-" (units: none).
            step_deg: Simulated jog step size (units: deg).
        """
        if direction not in {"+", "-"}:
            raise ValueError("direction must be '+' or '-'")
        self._require_connected()
        if self.simulate:
            sign = 1.0 if direction == "+" else -1.0
            self.move_to(min(360.0, max(0.0, self._sim_angle + sign * step_deg)))
            return
        self._motor.jog(direction)

    def _require_connected(self) -> None:
        """Ensure instrument is connected.

        Parameters:
            None (units: none).
        """
        if not self.is_connected:
            raise RuntimeError("KDC101Stage is not connected")