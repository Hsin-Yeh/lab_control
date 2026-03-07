"""Thorlabs Kinesis filter flipper driver."""

from __future__ import annotations

import time
from typing import Any

from .base import BaseInstrument, InstrumentCommandError, InstrumentConnectionError


class KinesisFlipper(BaseInstrument):
    """Kinesis filter flipper wrapper with real and simulate modes."""

    def __init__(self, config: dict[str, Any]):
        """Initialize flipper state.

        Parameters:
            config: Flipper config (time in s, position unitless state index).
        """
        super().__init__(config)
        self._device = None
        self._sim_position = int(self.config.get("initial_position", 1))

    def connect(self) -> None:
        """Connect to Kinesis filter flipper.

        Parameters:
            None (units: none).
        """
        if self.simulate:
            self._device = "SIMULATED"
            self._sim_position = int(self.config.get("initial_position", 1))
            self.logger.info("Connected to simulated flipper")
            return

        serial = str(self.config["serial"])
        kinesis_path = str(self.config.get("kinesis_path", ""))

        try:
            import pylablib as pll  # type: ignore

            if kinesis_path:
                pll.par["devices/dlls/kinesis"] = kinesis_path
            from pylablib.devices import Thorlabs  # type: ignore

            devices = Thorlabs.list_kinesis_devices()
            device_models = {str(item[0]): str(item[1]) for item in devices}
            if serial not in device_models:
                raise InstrumentConnectionError("KinesisFlipper", serial)

            model = device_models[serial].lower()
            if "flipper" not in model and not model.startswith("mff"):
                raise InstrumentConnectionError("KinesisFlipper", serial)

            if hasattr(Thorlabs, "MFF"):
                self._device = Thorlabs.MFF(serial)
            elif hasattr(Thorlabs, "KinesisFlipper"):
                self._device = Thorlabs.KinesisFlipper(serial)
            else:
                raise InstrumentConnectionError("KinesisFlipper", serial)

            self.logger.info("Connected to flipper serial %s", serial)
        except InstrumentConnectionError:
            raise
        except Exception as exc:
            raise InstrumentConnectionError("KinesisFlipper", serial) from exc

    def disconnect(self) -> None:
        """Disconnect from flipper.

        Parameters:
            None (units: none).
        """
        if self.simulate:
            self._device = None
            return
        if self._device is not None and hasattr(self._device, "close"):
            self._device.close()
        self._device = None

    @property
    def is_connected(self) -> bool:
        """Return connection state.

        Parameters:
            None (units: none).
        """
        return self._device is not None

    @property
    def instrument_id(self) -> str:
        """Return instrument identifier.

        Parameters:
            None (units: none).
        """
        return f"MFF:{self.config.get('serial', 'SIM')}"

    def get_position(self) -> int:
        """Read current flipper position.

        Parameters:
            None (units: none).
        """
        self._require_connected()
        if self.simulate:
            return int(self._sim_position)

        value = self._invoke_read(("get_state", "get_position", "get_flipper_state"))
        position = int(value)
        if position not in {1, 2}:
            raise InstrumentCommandError("KinesisFlipper", "get_position", str(value))
        return position

    def set_position(self, position: int) -> None:
        """Set flipper position state.

        Parameters:
            position: Target state index (units: state, valid range [1, 2]).
        """
        if position not in {1, 2}:
            raise ValueError("position must be in valid range [1, 2]")
        self._require_connected()

        if self.simulate:
            self._sim_position = int(position)
            time.sleep(float(self.config.get("settle_time_s", 0.2)))
            self.logger.info("[SIM] Flipper moved to state %d", position)
            return

        self._invoke_write(("move_to_state", "set_state", "move_to", "set_position", "flip_to"), position)
        time.sleep(float(self.config.get("settle_time_s", 0.2)))
        self.logger.info("Flipper moved to state %d", position)

    def home(self) -> None:
        """Move flipper to state 1 as home position.

        Parameters:
            None (units: none).
        """
        self.set_position(1)

    def toggle(self) -> int:
        """Toggle flipper between states 1 and 2.

        Parameters:
            None (units: none).
        """
        new_position = 2 if self.get_position() == 1 else 1
        self.set_position(new_position)
        return new_position

    def _invoke_read(self, method_names: tuple[str, ...]) -> Any:
        """Call first available read method.

        Parameters:
            method_names: Candidate API method names (units: none).
        """
        for method_name in method_names:
            method = getattr(self._device, method_name, None)
            if callable(method):
                try:
                    return method()
                except Exception as exc:
                    raise InstrumentCommandError("KinesisFlipper", method_name, str(exc)) from exc
        raise InstrumentCommandError("KinesisFlipper", "read_position", "No compatible read method")

    def _invoke_write(self, method_names: tuple[str, ...], position: int) -> None:
        """Call first available write method.

        Parameters:
            method_names: Candidate API method names (units: none).
            position: Target state index (units: state).
        """
        for method_name in method_names:
            method = getattr(self._device, method_name, None)
            if callable(method):
                try:
                    method(position)
                    return
                except TypeError:
                    try:
                        method(position, True)
                        return
                    except Exception as exc:
                        raise InstrumentCommandError("KinesisFlipper", method_name, str(exc)) from exc
                except Exception as exc:
                    raise InstrumentCommandError("KinesisFlipper", method_name, str(exc)) from exc
        raise InstrumentCommandError("KinesisFlipper", "set_position", "No compatible write method")

    def _require_connected(self) -> None:
        """Ensure flipper is connected.

        Parameters:
            None (units: none).
        """
        if not self.is_connected:
            raise RuntimeError("KinesisFlipper is not connected")
