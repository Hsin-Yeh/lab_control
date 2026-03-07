"""Tests for resistance logging experiment."""

from __future__ import annotations

from pathlib import Path
import threading

import yaml

from experiments.resistance_log import run_resistance_log


def _write_config(path: Path) -> str:
    """Write simulate config for GSM tests.

    Parameters:
        path: Destination YAML path (units: none).
    """
    cfg = {
        "gsm20h10": {
            "simulate": True,
            "visa_resource": "GPIB0::5::INSTR",
        }
    }
    path.write_text(yaml.dump(cfg), encoding="utf-8")
    return str(path)


def test_run_resistance_log_creates_output(tmp_path):
    """Resistance log run returns records and writes CSV.

    Parameters:
        tmp_path: Temporary path fixture (units: none).
    """
    config_path = _write_config(tmp_path / "cfg.yaml")
    output_dir = tmp_path / "out"

    results = run_resistance_log(
        config_path=config_path,
        output_dir=str(output_dir),
        source_voltage_v=0.1,
        current_limit_a=0.01,
        interval_s=0.05,
        duration_s=0.2,
    )

    assert isinstance(results, list)
    assert len(results) >= 1

    csv_files = list(output_dir.glob("*/resistance_log.csv"))
    assert csv_files


def test_run_resistance_log_respects_abort(tmp_path):
    """Resistance log honors pre-set abort event.

    Parameters:
        tmp_path: Temporary path fixture (units: none).
    """
    config_path = _write_config(tmp_path / "cfg_abort.yaml")
    output_dir = tmp_path / "out_abort"
    abort_event = threading.Event()
    abort_event.set()

    results = run_resistance_log(
        config_path=config_path,
        output_dir=str(output_dir),
        source_voltage_v=0.1,
        current_limit_a=0.01,
        interval_s=0.05,
        duration_s=1.0,
        abort_event=abort_event,
    )

    assert isinstance(results, list)


def test_run_resistance_log_emits_progress(tmp_path):
    """Resistance log emits progress callback updates.

    Parameters:
        tmp_path: Temporary path fixture (units: none).
    """
    config_path = _write_config(tmp_path / "cfg_progress.yaml")
    output_dir = tmp_path / "out_progress"
    progress_updates: list[tuple[int, int]] = []

    _ = run_resistance_log(
        config_path=config_path,
        output_dir=str(output_dir),
        source_voltage_v=0.1,
        current_limit_a=0.01,
        interval_s=0.05,
        duration_s=0.15,
        progress_callback=lambda cur, total: progress_updates.append((cur, total)),
    )

    assert progress_updates
    assert progress_updates[-1][0] == progress_updates[-1][1]
