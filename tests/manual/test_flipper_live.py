"""Manual live test for Kinesis flipper."""

from __future__ import annotations

from pathlib import Path

import yaml

from instruments.flipper import KinesisFlipper


def main() -> None:
    """Run live flipper toggle sequence.

    Parameters:
        None (units: none).
    """
    config = yaml.safe_load(Path("config/instruments.yaml").read_text(encoding="utf-8"))
    with KinesisFlipper(config["flipper"]) as flipper:
        print(flipper.instrument_id)
        print(f"Initial state: {flipper.get_position()}")
        print(f"Toggled to: {flipper.toggle()}")
        print(f"Toggled to: {flipper.toggle()}")
        print("Flipper live test complete")


if __name__ == "__main__":
    main()
