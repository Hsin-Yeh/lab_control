"""Manual live test for GSM-20H10."""

from __future__ import annotations

from pathlib import Path
import time

import yaml

from instruments.gsm20h10 import GSM20H10


def main() -> None:
    """Run live GSM-20H10 check and sweep.

    Parameters:
        None (units: none).
    """
    config = yaml.safe_load(Path("config/instruments.yaml").read_text(encoding="utf-8"))
    with GSM20H10(config["gsm20h10"]) as smu:
        idn = smu.instrument_id
        print(idn)
        assert "INSTEK" in idn.upper() or "GW" in idn.upper()
        smu.set_source_voltage(1.0, current_limit=0.01)
        smu.output_on()
        time.sleep(0.5)
        print(smu.measure_iv())
        smu.output_off()
        results = smu.sweep_voltage(0, 5.0, 0.5, current_limit=0.01, delay_s=0.2)
        for row in results:
            print(row)
        print("Test complete — output is OFF")


if __name__ == "__main__":
    main()
