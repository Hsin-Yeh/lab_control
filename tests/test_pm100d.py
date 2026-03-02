"""Unit tests for PM100D."""

from __future__ import annotations

import types

import pytest

from instruments.pm100d import PM100D


def _install_fake_pm(monkeypatch, mocker, read_value=1e-5):
    fake_raw = mocker.Mock()
    fake_raw.query.return_value = "THORLABS,PM100D,SN,1.0\n"
    fake_rm = mocker.Mock()
    fake_rm.open_resource.return_value = fake_raw

    fake_pyvisa = types.ModuleType("pyvisa")
    fake_pyvisa.ResourceManager = mocker.Mock(return_value=fake_rm)

    fake_pm = mocker.Mock()
    fake_pm.instrument = fake_raw
    fake_pm.read = read_value

    def ctor(inst):
        _ = inst
        return fake_pm

    import sys

    fake_thorlabs_pm100 = types.ModuleType("ThorlabsPM100")
    fake_thorlabs_pm100.ThorlabsPM100 = ctor

    monkeypatch.setitem(sys.modules, "pyvisa", fake_pyvisa)
    monkeypatch.setitem(sys.modules, "ThorlabsPM100", fake_thorlabs_pm100)
    return fake_pm


def test_set_wavelength_valid(monkeypatch, mocker):
    fake_pm = _install_fake_pm(monkeypatch, mocker)
    meter = PM100D({"simulate": False, "visa_resource": "USB::INSTR", "wavelength_nm": 780.0, "averaging_count": 10})
    meter.connect()
    meter.set_wavelength(780.0)
    assert fake_pm.sense.correction.wavelength == 780.0


def test_set_wavelength_out_of_range():
    meter = PM100D({"simulate": True, "wavelength_nm": 780.0, "averaging_count": 10})
    meter.connect()
    with pytest.raises(ValueError):
        meter.set_wavelength(200)


def test_read_power_returns_float(monkeypatch, mocker):
    _install_fake_pm(monkeypatch, mocker, read_value=1e-5)
    meter = PM100D({"simulate": False, "visa_resource": "USB::INSTR", "wavelength_nm": 780.0, "averaging_count": 10})
    meter.connect()
    assert meter.read_power() == pytest.approx(1e-5)


def test_read_power_dbm(monkeypatch, mocker):
    _install_fake_pm(monkeypatch, mocker, read_value=1e-3)
    meter = PM100D({"simulate": False, "visa_resource": "USB::INSTR", "wavelength_nm": 780.0, "averaging_count": 10})
    meter.connect()
    assert meter.read_power_dbm() == pytest.approx(0.0, abs=1e-9)


def test_read_power_average(mocker):
    meter = PM100D({"simulate": True, "wavelength_nm": 780.0, "averaging_count": 10})
    meter.connect()
    mocker.patch.object(meter, "read_power", side_effect=[1e-6, 2e-6, 3e-6])
    assert meter.read_power_average(n=3) == pytest.approx(2e-6)


def test_simulate_read_power():
    meter = PM100D({"simulate": True, "wavelength_nm": 780.0, "averaging_count": 10})
    meter.connect()
    assert meter.read_power() > 0.0
