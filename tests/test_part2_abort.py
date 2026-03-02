"""Part 2 abort behavior tests for experiment runners (simulate mode)."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
import yaml

from experiments.iv_curve import run_iv_curve
from experiments.rotation_sweep import run_rotation_sweep
from experiments.tcspc_scan import run_tcspc_scan


def _request_abort_later(abort_event: threading.Event, delay_s: float) -> threading.Thread:
    """Set abort event after a delay.

    Parameters:
        abort_event: Event used by experiment loops (units: none).
        delay_s: Delay before setting event (units: s).
    """

    def _set_event() -> None:
        time.sleep(delay_s)
        abort_event.set()

    thread = threading.Thread(target=_set_event, daemon=True)
    thread.start()
    return thread


def _write_sim_config(tmp_path: Path) -> str:
    """Write a minimal simulate-only instrument config.

    Parameters:
        tmp_path: Temporary directory (units: none).
    """
    cfg = {
        "kdc101": {
            "simulate": True,
            "serial_number": "27000001",
            "kinesis_path": None,
            "settle_time_s": 0.0,
        },
        "pm100d": {
            "simulate": True,
            "resource": "USB0::dummy",
            "visa_resource": "USB0::dummy",
            "wavelength_nm": 532,
            "averaging_count": 1,
        },
        "gsm20h10": {
            "simulate": True,
            "resource": "GPIB0::5::INSTR",
            "visa_resource": "GPIB0::5::INSTR",
        },
        "picoharp300": {
            "simulate": True,
            "dll_path": None,
            "phlib_path": None,
        },
        "e36300": {
            "simulate": True,
            "resource": "TCPIP0::dummy",
            "visa_resource": "TCPIP0::dummy",
        },
    }
    cfg_path = tmp_path / "instruments_sim.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return str(cfg_path)


def test_rotation_sweep_abort_returns_partial_or_empty(tmp_path: Path) -> None:
    """Rotation sweep exits cleanly when abort is pre-requested.

    Parameters:
        tmp_path: Temporary directory (units: none).
    """
    cfg_path = _write_sim_config(tmp_path)
    out_dir = tmp_path / "out_rotation"
    abort_event = threading.Event()
    abort_event.set()

    results = run_rotation_sweep(
        config_path=cfg_path,
        output_dir=str(out_dir),
        start_deg=0.0,
        stop_deg=20.0,
        step_deg=5.0,
        abort_event=abort_event,
    )

    assert isinstance(results, list)
    assert len(results) == 0


def test_iv_curve_abort_returns_empty(tmp_path: Path) -> None:
    """I-V sweep exits cleanly when abort is pre-requested.

    Parameters:
        tmp_path: Temporary directory (units: none).
    """
    cfg_path = _write_sim_config(tmp_path)
    out_dir = tmp_path / "out_iv"
    abort_event = threading.Event()
    abort_event.set()

    results = run_iv_curve(
        config_path=cfg_path,
        output_dir=str(out_dir),
        v_start=-1.0,
        v_stop=1.0,
        v_step=0.2,
        i_limit=0.05,
        abort_event=abort_event,
    )

    assert isinstance(results, list)
    assert len(results) == 0


def test_tcspc_abort_returns_empty_summary(tmp_path: Path) -> None:
    """TCSPC scan exits cleanly when abort is pre-requested.

    Parameters:
        tmp_path: Temporary directory (units: none).
    """
    cfg_path = _write_sim_config(tmp_path)
    out_dir = tmp_path / "out_tcspc"
    abort_event = threading.Event()
    abort_event.set()

    result = run_tcspc_scan(
        config_path=cfg_path,
        output_dir=str(out_dir),
        angles=[0.0, 10.0, 20.0],
        acq_time_ms=20,
        abort_event=abort_event,
    )

    assert isinstance(result, dict)
    assert result.get("summary", []) == []


def test_rotation_sweep_mid_abort_returns_partial(tmp_path: Path) -> None:
    """Rotation sweep returns partial data when aborted during execution.

    Parameters:
        tmp_path: Temporary directory (units: none).
    """
    cfg_path = _write_sim_config(tmp_path)
    out_dir = tmp_path / "out_rotation_mid"
    abort_event = threading.Event()
    _request_abort_later(abort_event, delay_s=1.0)

    start_deg = 0.0
    stop_deg = 20.0
    step_deg = 1.0
    total_points = int((stop_deg - start_deg) / step_deg) + 1

    results = run_rotation_sweep(
        config_path=cfg_path,
        output_dir=str(out_dir),
        start_deg=start_deg,
        stop_deg=stop_deg,
        step_deg=step_deg,
        abort_event=abort_event,
    )

    assert 1 <= len(results) < total_points


def test_iv_curve_mid_abort_returns_partial(tmp_path: Path) -> None:
    """I-V sweep returns partial data when aborted during execution.

    Parameters:
        tmp_path: Temporary directory (units: none).
    """
    cfg_path = _write_sim_config(tmp_path)
    out_dir = tmp_path / "out_iv_mid"
    abort_event = threading.Event()
    _request_abort_later(abort_event, delay_s=0.35)

    v_start = -1.0
    v_stop = 1.0
    v_step = 0.1
    total_points = int((v_stop - v_start) / v_step) + 1

    results = run_iv_curve(
        config_path=cfg_path,
        output_dir=str(out_dir),
        v_start=v_start,
        v_stop=v_stop,
        v_step=v_step,
        i_limit=0.05,
        abort_event=abort_event,
    )

    assert 1 <= len(results) < total_points


def test_tcspc_mid_abort_returns_partial_summary(tmp_path: Path) -> None:
    """TCSPC scan returns partial summary when aborted during execution.

    Parameters:
        tmp_path: Temporary directory (units: none).
    """
    cfg_path = _write_sim_config(tmp_path)
    out_dir = tmp_path / "out_tcspc_mid"
    abort_event = threading.Event()
    _request_abort_later(abort_event, delay_s=0.9)

    angles = [0.0, 5.0, 10.0, 15.0, 20.0]
    result = run_tcspc_scan(
        config_path=cfg_path,
        output_dir=str(out_dir),
        angles=angles,
        acq_time_ms=20,
        abort_event=abort_event,
    )

    summary = result.get("summary", [])
    assert isinstance(summary, list)
    assert 1 <= len(summary) < len(angles)


def test_gui_main_positional_config_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """GUI entrypoint accepts positional YAML config path.

    Parameters:
        monkeypatch: Pytest monkeypatch fixture (units: none).
        tmp_path: Temporary directory (units: none).
    """
    cfg_path = tmp_path / "custom.yaml"
    cfg_path.write_text("gsm20h10:\n  simulate: true\n", encoding="utf-8")

    import gui_main

    captured: dict[str, object] = {}

    class DummyApp:
        def __init__(self, argv: list[str]) -> None:
            captured["argv"] = list(argv)

        def setApplicationName(self, name: str) -> None:
            captured["app_name"] = name

        def exec(self) -> int:
            return 0

    class DummyWindow:
        def __init__(self, config_path: str) -> None:
            captured["config_path"] = config_path

        def show(self) -> None:
            captured["shown"] = True

    monkeypatch.setattr(gui_main, "QApplication", DummyApp)
    monkeypatch.setattr(gui_main, "MainWindow", DummyWindow)
    monkeypatch.setattr(gui_main.sys, "argv", ["gui_main.py", str(cfg_path)])

    with pytest.raises(SystemExit) as exit_info:
        gui_main.main()

    assert exit_info.value.code == 0
    assert captured.get("config_path") == str(cfg_path)
    assert captured.get("shown") is True
