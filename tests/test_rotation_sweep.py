"""Unit tests for rotation sweep experiment flow."""

from __future__ import annotations

import csv
from pathlib import Path

import yaml

from experiments import rotation_sweep as rotation_module


class _FakeStage:
    home_calls = 0
    moves: list[float] = []

    def __init__(self, config: dict):
        self.config = config
        self.is_connected = False

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.disconnect()
        return False

    def connect(self) -> None:
        self.is_connected = True

    def disconnect(self) -> None:
        self.is_connected = False

    def home(self) -> None:
        type(self).home_calls += 1

    def move_to(self, angle_deg: float) -> None:
        type(self).moves.append(float(angle_deg))


class _FakePM:
    wavelength_values: list[float] = []
    averaging_values: list[int] = []
    auto_range_values: list[bool] = []
    zero_calls = 0
    average_requests: list[int] = []

    def __init__(self, config: dict):
        self.config = config
        self.is_connected = False

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.disconnect()
        return False

    def connect(self) -> None:
        self.is_connected = True

    def disconnect(self) -> None:
        self.is_connected = False

    def set_wavelength(self, wavelength_nm: float) -> None:
        type(self).wavelength_values.append(float(wavelength_nm))

    def set_averaging(self, count: int) -> None:
        type(self).averaging_values.append(int(count))

    def auto_range(self, enable: bool = True) -> None:
        type(self).auto_range_values.append(bool(enable))

    def zero(self) -> None:
        type(self).zero_calls += 1

    def read_power_average(self, n: int = 10) -> float:
        type(self).average_requests.append(int(n))
        return 1.5e-6 * float(n)


def _write_config(tmp_path: Path) -> str:
    cfg = {
        "kdc101": {"simulate": True, "serial": "27000001", "settle_time_s": 0.0},
        "pm100d": {
            "simulate": True,
            "visa_resource": "USB0::dummy",
            "wavelength_nm": 780.0,
            "averaging_count": 10,
            "auto_range": False,
        },
    }
    path = tmp_path / "rotation_test.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return str(path)


def _reset_fakes() -> None:
    _FakeStage.home_calls = 0
    _FakeStage.moves = []
    _FakePM.wavelength_values = []
    _FakePM.averaging_values = []
    _FakePM.auto_range_values = []
    _FakePM.zero_calls = 0
    _FakePM.average_requests = []


def test_rotation_sweep_applies_pm_settings_and_writes_csv(tmp_path: Path, monkeypatch) -> None:
    """Rotation sweep applies requested PM settings and writes result file.

    Parameters:
        tmp_path: Temporary directory (units: none).
        monkeypatch: Pytest monkeypatch fixture (units: none).
    """
    _reset_fakes()
    cfg_path = _write_config(tmp_path)
    output_dir = tmp_path / "out"
    progress_updates: list[tuple[int, int, dict]] = []

    monkeypatch.setattr(rotation_module, "KDC101Stage", _FakeStage)
    monkeypatch.setattr(rotation_module, "PM100D", _FakePM)
    monkeypatch.setattr(rotation_module, "plot_power_vs_angle", lambda *args, **kwargs: None)
    monkeypatch.setattr(rotation_module, "plot_cartesian_power", lambda *args, **kwargs: None)

    results = rotation_module.run_rotation_sweep(
        config_path=cfg_path,
        output_dir=str(output_dir),
        start_deg=0.0,
        stop_deg=2.0,
        step_deg=1.0,
        wavelength_nm=650.0,
        average_count=4,
        zero_before_sweep=True,
        initialize_devices=True,
        progress_callback=lambda cur, total, row: progress_updates.append((cur, total, dict(row))),
    )

    assert len(results) == 3
    assert _FakeStage.home_calls == 1
    assert _FakeStage.moves == [0.0, 1.0, 2.0]
    assert _FakePM.wavelength_values == [650.0]
    assert _FakePM.averaging_values == [4]
    assert _FakePM.auto_range_values == [False]
    assert _FakePM.zero_calls == 1
    assert _FakePM.average_requests == [4, 4, 4]
    assert [item[0] for item in progress_updates] == [1, 2, 3]
    assert all(item[1] == 3 for item in progress_updates)

    output_subdirs = [child for child in output_dir.iterdir() if child.is_dir()]
    assert len(output_subdirs) == 1
    csv_path = output_subdirs[0] / "rotation_sweep.csv"
    assert csv_path.exists()

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 3
    assert rows[0]["wavelength_nm"] == "650.0"
    assert rows[0]["average_count"] == "4"
    assert rows[0]["zero_before_sweep"] == "True"


def test_rotation_sweep_can_skip_initialization(tmp_path: Path, monkeypatch) -> None:
    """Rotation sweep can skip the initialization sequence when requested.

    Parameters:
        tmp_path: Temporary directory (units: none).
        monkeypatch: Pytest monkeypatch fixture (units: none).
    """
    _reset_fakes()
    cfg_path = _write_config(tmp_path)
    output_dir = tmp_path / "out_skip_init"

    monkeypatch.setattr(rotation_module, "KDC101Stage", _FakeStage)
    monkeypatch.setattr(rotation_module, "PM100D", _FakePM)
    monkeypatch.setattr(rotation_module, "plot_power_vs_angle", lambda *args, **kwargs: None)
    monkeypatch.setattr(rotation_module, "plot_cartesian_power", lambda *args, **kwargs: None)

    results = rotation_module.run_rotation_sweep(
        config_path=cfg_path,
        output_dir=str(output_dir),
        start_deg=5.0,
        stop_deg=5.0,
        step_deg=1.0,
        wavelength_nm=700.0,
        average_count=3,
        zero_before_sweep=True,
        initialize_devices=False,
    )

    assert len(results) == 1
    assert _FakeStage.home_calls == 0
    assert _FakeStage.moves == [5.0]
    assert _FakePM.wavelength_values == []
    assert _FakePM.averaging_values == []
    assert _FakePM.auto_range_values == []
    assert _FakePM.zero_calls == 0
    assert _FakePM.average_requests == [3]
