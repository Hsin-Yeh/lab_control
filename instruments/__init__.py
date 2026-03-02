"""Instrument package exports with safe lazy imports."""

from __future__ import annotations

import logging

from .base import BaseInstrument, InstrumentCommandError, InstrumentConnectionError

logger = logging.getLogger(__name__)

__all__ = [
    "BaseInstrument",
    "InstrumentConnectionError",
    "InstrumentCommandError",
    "KDC101Stage",
    "PM100D",
    "E36300Supply",
    "GSM20H10",
    "PicoHarp300",
]


def _safe_import(module_name: str, class_name: str):
    """Import a class from module and return None if import fails.

    Parameters:
        module_name: Relative module name under instruments (units: none).
        class_name: Class to import from module (units: none).
    """
    try:
        module = __import__(f"{__name__}.{module_name}", fromlist=[class_name])
        return getattr(module, class_name)
    except ImportError as exc:
        logger.warning("Optional import failed for %s.%s: %s", module_name, class_name, exc)
        return None


KDC101Stage = _safe_import("kdc101", "KDC101Stage")
PM100D = _safe_import("pm100d", "PM100D")
E36300Supply = _safe_import("e36300", "E36300Supply")
GSM20H10 = _safe_import("gsm20h10", "GSM20H10")
PicoHarp300 = _safe_import("picoharp300", "PicoHarp300")