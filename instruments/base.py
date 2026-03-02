"""Base abstractions and errors for lab instruments."""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging
from pathlib import Path
from typing import Any

import yaml


class InstrumentConnectionError(Exception):
    """Raised when an instrument connection cannot be established."""

    def __init__(self, instrument_name: str, resource: str):
        """Initialize a connection error.

        Parameters:
            instrument_name: Instrument logical name (units: none).
            resource: Address/identifier used for connection (units: none).
        """
        self.instrument_name = instrument_name
        self.resource = resource
        super().__init__(f"Failed to connect to {instrument_name} using resource '{resource}'")


class InstrumentCommandError(Exception):
    """Raised when an instrument command fails or returns an error."""

    def __init__(self, instrument_name: str, command: str, response: str):
        """Initialize a command error.

        Parameters:
            instrument_name: Instrument logical name (units: none).
            command: Command or API function that failed (units: none).
            response: Error response text from instrument/library (units: none).
        """
        self.instrument_name = instrument_name
        self.command = command
        self.response = response
        super().__init__(f"{instrument_name} command '{command}' failed: {response}")


class BaseInstrument(ABC):
    """Abstract base class for all instruments in this repository."""

    def __init__(self, config: dict[str, Any]):
        """Initialize base fields.

        Parameters:
            config: Instrument configuration mapping (units: none).
        """
        self.config = config
        self.simulate = bool(config.get("simulate", False))
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def connect(self) -> None:
        """Open instrument communication channel.

        Parameters:
            None (units: none).
        """

    @abstractmethod
    def disconnect(self) -> None:
        """Close instrument communication channel.

        Parameters:
            None (units: none).
        """

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Connection state.

        Parameters:
            None (units: none).
        """

    @property
    @abstractmethod
    def instrument_id(self) -> str:
        """Instrument identity string.

        Parameters:
            None (units: none).
        """

    def __enter__(self) -> "BaseInstrument":
        """Context manager entry.

        Parameters:
            None (units: none).
        """
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit; always disconnect.

        Parameters:
            exc_type: Exception type if raised in context (units: none).
            exc_val: Exception instance if raised in context (units: none).
            exc_tb: Exception traceback if raised in context (units: none).
        """
        if exc_val is not None:
            self.logger.exception("Exception in context-managed instrument block", exc_info=(exc_type, exc_val, exc_tb))
        try:
            self.disconnect()
        except Exception:
            self.logger.exception("Failed to disconnect cleanly")

    @classmethod
    def from_yaml(cls, yaml_path: str, key: str) -> "BaseInstrument":
        """Instantiate instrument from a YAML config section.

        Parameters:
            yaml_path: Path to YAML file (units: none).
            key: Top-level YAML key for this instrument (units: none).
        """
        with Path(yaml_path).open("r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle) or {}
        if key not in config:
            raise KeyError(f"Missing '{key}' in config file: {yaml_path}")
        return cls(config[key])