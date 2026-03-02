"""Manual live test for KDC101 stage."""

from __future__ import annotations

from pathlib import Path

import yaml

from instruments.kdc101 import KDC101Stage


def main() -> None:
    """Run live stage move sequence.

    Parameters:
        None (units: none).
    """
    config = yaml.safe_load(Path("config/instruments.yaml").read_text(encoding="utf-8"))
    with KDC101Stage(config["kdc101"]) as stage:
        print(stage.instrument_id)
        stage.home()
        print(f"Angle: {stage.get_angle():.3f} deg")
        for angle in [45.0, 90.0, 180.0, 0.0]:
            stage.move_to(angle)
            print(f"Angle: {stage.get_angle():.3f} deg")
        print("All moves complete")


if __name__ == "__main__":
    main()
