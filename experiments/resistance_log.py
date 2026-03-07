"""Long-term constant-voltage resistance logging experiment."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
import threading
import time

import yaml

import sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from instruments.gsm20h10 import GSM20H10
from utils.data_writer import save_csv
from utils.logger import setup_logger


def run_resistance_log(
    config_path: str = "config/instruments.yaml",
    output_dir: str = "output",
    source_voltage_v: float = 0.1,
    current_limit_a: float = 0.01,
    interval_s: float = 0.5,
    duration_s: float = 60.0,
    compliance_stop: bool = True,
    abort_event: threading.Event | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[dict]:
    """Run long-term resistance logging at fixed source voltage.

    Parameters:
        config_path: YAML config path (units: none).
        output_dir: Root output directory (units: none).
        source_voltage_v: Fixed source voltage setpoint (units: V).
        current_limit_a: Source current compliance limit (units: A).
        interval_s: Sampling interval (units: s).
        duration_s: Total logging duration (units: s).
        compliance_stop: Stop when measured current reaches compliance (units: boolean).
        abort_event: Optional cooperative abort signal (units: none).
        progress_callback: Optional callback receiving (current_step, total_steps) (units: count).
    """
    if interval_s <= 0.0:
        raise ValueError("interval_s must be > 0 s")
    if duration_s <= 0.0:
        raise ValueError("duration_s must be > 0 s")

    with Path(config_path).open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    logger = setup_logger("resistance_log", "logs/resistance_log.log")
    out_subdir = Path(output_dir) / datetime.now().strftime("%Y%m%d_%H%M%S")
    out_subdir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    start_t = time.time()
    total_steps = max(1, int(duration_s / interval_s) + 1)
    current_step = 0

    smu = GSM20H10(config["gsm20h10"])
    with smu:
        try:
            smu.set_source_voltage(source_voltage_v, current_limit_a)
            smu.output_on()
            logger.info(
                "Resistance log started: V=%.6f V, I_limit=%.6f A, interval=%.3f s, duration=%.3f s",
                source_voltage_v,
                current_limit_a,
                interval_s,
                duration_s,
            )

            while True:
                if abort_event is not None and abort_event.is_set():
                    logger.warning("Resistance log aborted by user")
                    break

                now_t = time.time()
                elapsed_s = now_t - start_t
                if elapsed_s > duration_s:
                    break

                iv = smu.measure_iv()
                voltage_v = float(iv["voltage"])
                current_a = float(iv["current"])
                power_w = float(iv["power"])
                resistance_ohm = float("inf") if abs(current_a) < 1e-12 else voltage_v / current_a

                results.append(
                    {
                        "timestamp_s": now_t,
                        "elapsed_s": elapsed_s,
                        "set_voltage_V": float(source_voltage_v),
                        "voltage_V": voltage_v,
                        "current_A": current_a,
                        "power_W": power_w,
                        "resistance_Ohm": resistance_ohm,
                    }
                )
                current_step = min(total_steps, current_step + 1)
                if progress_callback is not None:
                    progress_callback(current_step, total_steps)

                if compliance_stop and abs(current_a) >= current_limit_a * 0.99:
                    logger.warning("Compliance reached at t=%.3f s — stopping", elapsed_s)
                    break

                if abort_event is not None and abort_event.wait(interval_s):
                    logger.warning("Resistance log aborted during wait")
                    break
                if abort_event is None:
                    time.sleep(interval_s)
        finally:
            if smu.is_connected:
                smu.output_off()

    if results:
        save_csv(results, str(out_subdir / "resistance_log.csv"))
        logger.info("Saved resistance log: %d rows", len(results))

    if progress_callback is not None:
        progress_callback(total_steps, total_steps)

    return results


def _build_parser() -> argparse.ArgumentParser:
    """Build CLI parser.

    Parameters:
        None (units: none).
    """
    parser = argparse.ArgumentParser(description="Run long-term resistance logging")
    parser.add_argument("--config", default="config/instruments.yaml")
    parser.add_argument("--output", default="output")
    parser.add_argument("--source_voltage", type=float, default=0.1)
    parser.add_argument("--current_limit", type=float, default=0.01)
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--no_compliance_stop", action="store_true")
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()
    run_resistance_log(
        config_path=args.config,
        output_dir=args.output,
        source_voltage_v=args.source_voltage,
        current_limit_a=args.current_limit,
        interval_s=args.interval,
        duration_s=args.duration,
        compliance_stop=not bool(args.no_compliance_stop),
    )
