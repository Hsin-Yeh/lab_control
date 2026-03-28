"""Rotation sweep experiment using stage + power meter."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys
import threading
import time
from typing import Callable

import numpy as np
from tqdm import tqdm
import yaml

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from instruments.base import InstrumentConnectionError
from instruments.kdc101 import KDC101Stage
from instruments.pm100d import PM100D
from utils.data_writer import save_csv
from utils.logger import setup_logger
from utils.plotter import plot_cartesian_power, plot_power_vs_angle


def _power_w_to_dbm(power_w: float) -> float:
    """Convert optical power in Watts to dBm.

    Parameters:
        power_w: Optical power (units: W).
    """
    if power_w <= 0.0:
        return float("-inf")
    return 10.0 * np.log10(power_w / 1e-3)


def initialize_rotation_devices(
    stage: KDC101Stage,
    pm: PM100D,
    stage_config: dict,
    pm_config: dict,
    wavelength_nm: float,
    average_count: int,
    zero_before_sweep: bool = False,
    home_stage: bool = True,
) -> None:
    """Initialize connected rotation-sweep devices.

    Parameters:
        stage: Connected KDC101 stage instance (units: none).
        pm: Connected PM100D instance (units: none).
        stage_config: Stage config mapping (units: none).
        pm_config: PM config mapping (units: none).
        wavelength_nm: PM wavelength setting (units: nm).
        average_count: PM hardware averaging count and sweep average count (units: count).
        zero_before_sweep: If True, zero the PM before measuring (units: boolean).
        home_stage: If True, home the stage before sweep (units: boolean).
    """
    if home_stage:
        stage.home()
    pm.set_wavelength(float(wavelength_nm))
    pm.set_averaging(int(average_count))
    pm.auto_range(bool(pm_config.get("auto_range", True)))
    if zero_before_sweep:
        pm.zero()

    settle_time_s = float(stage_config.get("settle_time_s", 0.3))
    if settle_time_s > 0.0:
        time.sleep(settle_time_s)


def run_rotation_sweep(
    config_path: str = "config/instruments.yaml",
    output_dir: str = "output",
    start_deg: float = 0.0,
    stop_deg: float = 360.0,
    step_deg: float = 5.0,
    wavelength_nm: float | None = None,
    average_count: int | None = None,
    zero_before_sweep: bool = False,
    initialize_devices: bool = True,
    abort_event: threading.Event | None = None,
    progress_callback: Callable[[int, int, dict], None] | None = None,
) -> list[dict]:
    """Run stage rotation sweep while measuring power.

    Parameters:
        config_path: YAML config path (units: none).
        output_dir: Root output directory (units: none).
        start_deg: Start angle (units: deg).
        stop_deg: Stop angle (units: deg).
        step_deg: Angle increment (units: deg).
        wavelength_nm: PM wavelength override (units: nm).
        average_count: Readings averaged per angle and PM averaging setting (units: count).
        zero_before_sweep: If True, zero the PM before sweep (units: boolean).
        initialize_devices: If True, home/apply settings before sweep (units: boolean).
        abort_event: Optional abort event checked each step (units: none).
        progress_callback: Optional callback invoked after each point (units: none).
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
    resolved_wavelength_nm = float(
        config["pm100d"].get("wavelength_nm", 780.0) if wavelength_nm is None else wavelength_nm
    )
    resolved_average_count = int(
        config["pm100d"].get("averaging_count", 10) if average_count is None else average_count
    )

    try:
        with stage, pm:
            if initialize_devices:
                initialize_rotation_devices(
                    stage=stage,
                    pm=pm,
                    stage_config=config["kdc101"],
                    pm_config=config["pm100d"],
                    wavelength_nm=resolved_wavelength_nm,
                    average_count=resolved_average_count,
                    zero_before_sweep=zero_before_sweep,
                    home_stage=True,
                )

            for i, angle in enumerate(tqdm(angles, desc="Rotation Sweep")):
                if abort_event is not None and abort_event.is_set():
                    logger.warning("Sweep aborted at angle=%.2f deg", float(angle))
                    break
                stage.move_to(float(angle))
                time.sleep(float(config["kdc101"].get("settle_time_s", 0.3)))
                power = float(pm.read_power_average(n=resolved_average_count))
                power_dbm = float(_power_w_to_dbm(power))
                row = {
                    "angle_deg": float(angle),
                    "power_W": power,
                    "power_dBm": power_dbm,
                    "wavelength_nm": resolved_wavelength_nm,
                    "average_count": resolved_average_count,
                    "zero_before_sweep": bool(zero_before_sweep),
                }
                results.append(row)
                logger.info("[%d/%d] %.1f° -> %.3e W (%.1f dBm)", i + 1, len(angles), angle, power, power_dbm)
                if progress_callback is not None:
                    progress_callback(i + 1, len(angles), row)
    except InstrumentConnectionError as exc:
        logger.error("Connection error: %s", exc)
        raise
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
    parser.add_argument("--wavelength", type=float, default=None)
    parser.add_argument("--average-count", type=int, default=None)
    parser.add_argument("--zero", action="store_true")
    parser.add_argument("--skip-initialize", action="store_true")
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()
    run_rotation_sweep(
        config_path=args.config,
        output_dir=args.output,
        start_deg=args.start,
        stop_deg=args.stop,
        step_deg=args.step,
        wavelength_nm=args.wavelength,
        average_count=args.average_count,
        zero_before_sweep=bool(args.zero),
        initialize_devices=not bool(args.skip_initialize),
    )
