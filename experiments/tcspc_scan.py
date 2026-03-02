"""TCSPC angle scan using stage + PicoHarp300."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import time

import h5py
import numpy as np
from tqdm import tqdm
import yaml

import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from instruments.kdc101 import KDC101Stage
from instruments.picoharp300 import PicoHarp300
from utils.data_writer import save_csv
from utils.logger import setup_logger
from utils.plotter import plot_tcspc_histogram


def run_tcspc_scan(
    config_path: str = "config/instruments.yaml",
    output_dir: str = "output",
    angles: list[float] | None = None,
    acq_time_ms: int | None = None,
) -> dict:
    """Run angle-resolved TCSPC scan.

    Parameters:
        config_path: YAML config path (units: none).
        output_dir: Root output directory (units: none).
        angles: List of stage angles (units: deg).
        acq_time_ms: Acquisition duration for each point (units: ms).
    """
    with Path(config_path).open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    logger = setup_logger("tcspc_scan", "logs/tcspc_scan.log")
    out_subdir = Path(output_dir) / datetime.now().strftime("%Y%m%d_%H%M%S")
    out_subdir.mkdir(parents=True, exist_ok=True)
    hdf5_path = out_subdir / "tcspc_scan.h5"

    scan_angles = angles if angles is not None else [0.0, 45.0, 90.0, 135.0, 180.0]

    stage = KDC101Stage(config["kdc101"])
    tcspc = PicoHarp300(config["picoharp300"])
    summary: list[dict] = []

    with stage, tcspc:
        stage.home()
        with h5py.File(hdf5_path, "w") as hdf5_file:
            for angle in tqdm(scan_angles, desc="TCSPC Scan"):
                stage.move_to(float(angle))
                time.sleep(float(config["kdc101"].get("settle_time_s", 0.3)))
                hist = tcspc.acquire(acq_time_ms)
                rate_sync = tcspc.get_count_rate(0)
                rate_input = tcspc.get_count_rate(1)
                peak_ch = int(np.argmax(hist))
                peak_counts = int(hist[peak_ch])
                total = int(hist.sum())

                dataset_name = f"angle_{float(angle):.1f}"
                hdf5_file.create_dataset(dataset_name, data=hist)
                plot_tcspc_histogram(
                    hist,
                    tcspc.get_resolution(),
                    save_path=str(out_subdir / f"hist_angle_{float(angle):.0f}.png"),
                )

                row = {
                    "angle_deg": float(angle),
                    "peak_channel": peak_ch,
                    "peak_counts": peak_counts,
                    "total_counts": total,
                    "count_rate_sync": int(rate_sync),
                    "count_rate_input": int(rate_input),
                }
                summary.append(row)
                logger.info(
                    "Angle %.1f°: peak=%d, total=%d, rates=(%d,%d)",
                    angle,
                    peak_ch,
                    total,
                    rate_sync,
                    rate_input,
                )

    save_csv(summary, str(out_subdir / "tcspc_summary.csv"))
    return {"summary": summary, "hdf5_path": str(hdf5_path), "output_dir": str(out_subdir)}


def _build_parser() -> argparse.ArgumentParser:
    """Build CLI parser.

    Parameters:
        None (units: none).
    """
    parser = argparse.ArgumentParser(description="Run TCSPC scan experiment")
    parser.add_argument("--config", default="config/instruments.yaml")
    parser.add_argument("--output", default="output")
    parser.add_argument("--angles", nargs="+", type=float, default=None)
    parser.add_argument("--acq_time_ms", type=int, default=None)
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()
    run_tcspc_scan(
        config_path=args.config,
        output_dir=args.output,
        angles=args.angles,
        acq_time_ms=args.acq_time_ms,
    )
