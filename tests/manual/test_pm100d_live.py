"""Manual live test for PM100D."""

from __future__ import annotations

from pathlib import Path
import time

import yaml

from instruments.pm100d import PM100D


def main() -> None:
    """Run live PM100D readback sequence.

    Parameters:
        None (units: none).
    """
    config = yaml.safe_load(Path("config/instruments.yaml").read_text(encoding="utf-8"))
    with PM100D(config["pm100d"]) as pm:
        print(pm.instrument_id)
        pm.set_wavelength(780.0)
        pm.set_averaging(20)
        pm.auto_range(True)
        for _ in range(5):
            print(f"Power: {pm.read_power():.4e} W")
            time.sleep(0.5)
        print(f"Average: {pm.read_power_average(n=20):.4e} W")
        print(f"dBm: {pm.read_power_dbm():.2f}")
        print("Test complete")


if __name__ == "__main__":
    main()
