"""Unit tests for GSM20H10."""

from __future__ import annotations

import types

import pytest

from instruments.gsm20h10 import GSM20H10


def _install_fake_pyvisa(monkeypatch, mocker):
    fake_inst = mocker.Mock()
    fake_rm = mocker.Mock()
    fake_rm.open_resource.return_value = fake_inst
    fake_pyvisa = types.SimpleNamespace(ResourceManager=mocker.Mock(return_value=fake_rm))

    import sys

    monkeypatch.setitem(sys.modules, "pyvisa", fake_pyvisa)
    return fake_inst


def test_set_source_voltage_scpi(monkeypatch, mocker):
    fake_inst = _install_fake_pyvisa(monkeypatch, mocker)
    smu = GSM20H10({"simulate": False, "visa_resource": "USB::INSTR"})
    smu.connect()
    smu.set_source_voltage(1.0, current_limit=0.1)
    writes = [call.args[0] for call in fake_inst.write.call_args_list]
    assert ":SOUR:FUNC VOLT" in writes
    assert ":SOUR:VOLT 1.0" in writes


def test_voltage_out_of_range():
    smu = GSM20H10({"simulate": True})
    smu.connect()
    with pytest.raises(ValueError):
        smu.set_source_voltage(300, 0.1)


def test_sweep_returns_list_of_dicts():
    smu = GSM20H10({"simulate": True})
    smu.connect()
    result = smu.sweep_voltage(0, 1, 0.5)
    assert isinstance(result, list)
    assert result
    assert {"voltage", "current", "power", "set_voltage"}.issubset(result[0].keys())


def test_compliance_warning_logged(mocker):
    smu = GSM20H10({"simulate": True})
    smu.connect()
    warn_spy = mocker.patch.object(smu.logger, "warning")
    mocker.patch.object(smu, "measure_iv", return_value={"voltage": 1.0, "current": 0.099, "power": 0.099})
    smu.sweep_voltage(0, 1, 1, current_limit=0.1, delay_s=0)
    assert warn_spy.called


def test_output_off_on_disconnect(monkeypatch, mocker):
    fake_inst = _install_fake_pyvisa(monkeypatch, mocker)
    smu = GSM20H10({"simulate": False, "visa_resource": "USB::INSTR"})
    smu.connect()
    smu.disconnect()
    writes = [call.args[0] for call in fake_inst.write.call_args_list]
    assert ":OUTP OFF" in writes
