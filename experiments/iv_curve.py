"""I-V sweep experiment using GSM-20H10."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import threading
import time

import numpy as np
import yaml

import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from instruments.gsm20h10 import GSM20H10
from utils.data_writer import save_csv
from utils.logger import setup_logger
from utils.plotter import plot_iv_curve


def run_iv_curve(
    config_path: str = "config/instruments.yaml",
    output_dir: str = "output",
    v_start: float = -5.0,
    v_stop: float = 5.0,
    v_step: float = 0.1,
    i_limit: float = 0.05,
    abort_event: threading.Event | None = None,
) -> list[dict]:
    """Run I-V sweep and save outputs.

    Parameters:
        config_path: YAML config path (units: none).
        output_dir: Root output directory (units: none).
        v_start: Sweep start voltage (units: V).
        v_stop: Sweep stop voltage (units: V).
        v_step: Sweep voltage step (units: V).
        i_limit: Current compliance limit (units: A).
        abort_event: Optional abort event checked each step (units: none).
    """
    with Path(config_path).open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    logger = setup_logger("iv_curve", "logs/iv_curve.log")
    out_subdir = Path(output_dir) / datetime.now().strftime("%Y%m%d_%H%M%S")
    out_subdir.mkdir(parents=True, exist_ok=True)

    voltages = np.arange(v_start, v_stop + v_step, v_step, dtype=float)
    results: list[dict] = []

    smu = GSM20H10(config["gsm20h10"])
    with smu:
        try:
            for voltage in voltages:
                if abort_event is not None and abort_event.is_set():
                    logger.warning("I-V sweep aborted at voltage=%.3f V", float(voltage))
                    break

                smu.set_source_voltage(float(voltage), i_limit)
                smu.output_on()
                time.sleep(0.1)
                measurement = smu.measure_iv()
                measurement["set_voltage"] = float(voltage)
                results.append(measurement)

                if abs(float(measurement["current"])) >= i_limit * 0.99:
                    logger.warning("Compliance at %.3f V — stopping sweep", float(voltage))
                    break
        finally:
            if smu.is_connected:
                smu.output_off()

    if results:
        powers = [abs(row["power"]) for row in results]
        max_power = max(powers)
        logger.info("Max power point: %.6e W", max_power)

        measured_voltages = np.array([row["voltage"] for row in results], dtype=float)
        currents = np.array([row["current"] for row in results], dtype=float)
        if len(results) >= 2:
            d_v = np.gradient(measured_voltages)
            d_i = np.gradient(currents)
            dyn_res = np.where(np.abs(d_i) > 1e-12, d_v / d_i, np.inf)
            logger.info("Dynamic resistance median: %.6e Ohm", float(np.median(np.abs(dyn_res))))

        save_csv(results, str(out_subdir / "iv_curve.csv"))
        plot_iv_curve(measured_voltages, currents, save_path=str(out_subdir / "iv_curve.png"))

    return results


def _build_parser() -> argparse.ArgumentParser:
    """Build CLI parser.

    Parameters:
        None (units: none).
    """
    parser = argparse.ArgumentParser(description="Run I-V curve experiment")
    parser.add_argument("--config", default="config/instruments.yaml")
    parser.add_argument("--output", default="output")
    parser.add_argument("--v_start", type=float, default=-5.0)
    parser.add_argument("--v_stop", type=float, default=5.0)
    parser.add_argument("--v_step", type=float, default=0.1)
    parser.add_argument("--i_limit", type=float, default=0.05)
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()
    run_iv_curve(
        config_path=args.config,
        output_dir=args.output,
        v_start=args.v_start,
        v_stop=args.v_stop,
        v_step=args.v_step,
        i_limit=args.i_limit,
    )
