"""Manual live test for E36300 supply."""

from __future__ import annotations

from pathlib import Path
import time

import yaml

from instruments.e36300 import E36300Supply


def main() -> None:
    """Run live E36300 sequence.

    Parameters:
        None (units: none).
    """
    config = yaml.safe_load(Path("config/instruments.yaml").read_text(encoding="utf-8"))
    with E36300Supply(config["e36300"]) as supply:
        print(supply.instrument_id)
        supply.reset()
        supply.set_voltage(1, 5.0)
        supply.set_current_limit(1, 0.5)
        supply.set_voltage(2, 12.0)
        supply.set_current_limit(2, 0.3)
        supply.output_on(channel=1)
        time.sleep(1.0)
        print("CH1 voltage:", supply.measure_voltage(1))
        print("CH1 current:", supply.measure_current(1))
        print("CH1 power:", supply.measure_power(1))
        supply.output_off()
        print("Outputs OFF")


if __name__ == "__main__":
    main()
