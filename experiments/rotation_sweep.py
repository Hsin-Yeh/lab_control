"""Rotation sweep experiment using stage + power meter."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys
import threading
import time

import numpy as np
from tqdm import tqdm
import yaml

import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from instruments.base import InstrumentConnectionError
from instruments.kdc101 import KDC101Stage
from instruments.pm100d import PM100D
from utils.data_writer import save_csv
from utils.logger import setup_logger
from utils.plotter import plot_cartesian_power, plot_power_vs_angle


def run_rotation_sweep(
    config_path: str = "config/instruments.yaml",
    output_dir: str = "output",
    start_deg: float = 0.0,
    stop_deg: float = 360.0,
    step_deg: float = 5.0,
    abort_event: threading.Event | None = None,
) -> list[dict]:
    """Run stage rotation sweep while measuring power.

    Parameters:
        config_path: YAML config path (units: none).
        output_dir: Root output directory (units: none).
        start_deg: Start angle (units: deg).
        stop_deg: Stop angle (units: deg).
        step_deg: Angle increment (units: deg).
        abort_event: Optional abort event checked each step (units: none).
    """
    with Path(config_path).open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    logger = setup_logger("rotation_sweep", "logs/rotation_sweep.log")
    out_subdir = Path(output_dir) / datetime.now().strftime("%Y%m%d_%H%M%S")
    out_subdir.mkdir(parents=True, exist_ok=True)

    stage = KDC101Stage(config["kdc101"])
    pm = PM100D(config["pm100d"])
    angles = np.arange(start_deg, stop_deg + step_deg, step_deg)
    results: list[dict] = []

    try:
        with stage, pm:
            stage.home()
            pm.set_wavelength(float(config["pm100d"]["wavelength_nm"]))
            pm.set_averaging(int(config["pm100d"]["averaging_count"]))
            pm.auto_range(True)

            for i, angle in enumerate(tqdm(angles, desc="Rotation Sweep")):
                if abort_event is not None and abort_event.is_set():
                    logger.warning("Sweep aborted at angle=%.2f deg", float(angle))
                    break
                stage.move_to(float(angle))
                time.sleep(float(config["kdc101"].get("settle_time_s", 0.3)))
                power = pm.read_power_average(n=int(config["pm100d"]["averaging_count"]))
                power_dbm = pm.read_power_dbm()
                row = {"angle_deg": float(angle), "power_W": float(power), "power_dBm": float(power_dbm)}
                results.append(row)
                logger.info("[%d/%d] %.1f° -> %.3e W (%.1f dBm)", i + 1, len(angles), angle, power, power_dbm)
    except InstrumentConnectionError as exc:
        logger.error("Connection error: %s", exc)
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning("Aborted — returning stage to 0°")
        try:
            if stage.is_connected:
                stage.move_to(0.0)
        except Exception:
            logger.exception("Failed to return stage to 0° after interruption")

    if results:
        powers = [row["power_W"] for row in results]
        measured_angles = [row["angle_deg"] for row in results]
        save_csv(results, str(out_subdir / "rotation_sweep.csv"))
        plot_power_vs_angle(measured_angles, powers, save_path=str(out_subdir / "polar.png"))
        plot_cartesian_power(measured_angles, powers, save_path=str(out_subdir / "cartesian.png"))
    logger.info("Sweep complete. %d points. Results in %s", len(results), out_subdir)
    return results


def _build_parser() -> argparse.ArgumentParser:
    """Build CLI parser.

    Parameters:
        None (units: none).
    """
    parser = argparse.ArgumentParser(description="Run rotation sweep experiment")
    parser.add_argument("--config", default="config/instruments.yaml")
    parser.add_argument("--output", default="output")
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--stop", type=float, default=360.0)
    parser.add_argument("--step", type=float, default=5.0)
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()
    run_rotation_sweep(
        config_path=args.config,
        output_dir=args.output,
        start_deg=args.start,
        stop_deg=args.stop,
        step_deg=args.step,
    )
