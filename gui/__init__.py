"""GUI package for lab instrument control.

Cross-platform notes:
- macOS: KDC101 and PicoHarp300 imports may fail (DLLs not available). This is expected.
- Windows: All instruments supported.
- Always use pathlib.Path for file paths, never hardcode OS-specific absolute paths.
"""
from __future__ import annotations

try:
    from instruments.kdc101 import KDC101Stage
    KDC101_AVAILABLE = True
except (ImportError, OSError):
    KDC101Stage = None
    KDC101_AVAILABLE = False

try:
    from instruments.picoharp300 import PicoHarp300
    PICOHARP_AVAILABLE = True
except (ImportError, OSError):
    PicoHarp300 = None
    PICOHARP_AVAILABLE = False

from instruments.pm100d import PM100D
from instruments.e36300 import E36300Supply
from instruments.gsm20h10 import GSM20H10
