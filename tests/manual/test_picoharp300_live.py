"""Manual live test for PicoHarp300."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml

from instruments.picoharp300 import PicoHarp300


def main() -> None:
    """Run live PicoHarp300 acquisition test.

    Parameters:
        None (units: none).
    """
    config = yaml.safe_load(Path("config/instruments.yaml").read_text(encoding="utf-8"))
    with PicoHarp300(config["picoharp300"]) as tcspc:
        print(tcspc.instrument_id)
        print(f"Resolution: {tcspc.get_resolution():.1f} ps")
        print(f"Count rates: sync={tcspc.get_count_rate(0)}, input={tcspc.get_count_rate(1)}")
        histogram = tcspc.acquire(1000)
        peak_channel = int(np.argmax(histogram))
        print(f"Peak channel: {peak_channel}")
        print(f"Peak counts: {int(histogram[peak_channel])}")
        print(f"Total counts: {int(histogram.sum())}")
        np.save("tcspc_test.npy", histogram)
        print("Test complete. Saved tcspc_test.npy")


if __name__ == "__main__":
    main()
