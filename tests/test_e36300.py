"""Unit tests for E36300Supply."""

from __future__ import annotations

import types

import pytest

from instruments.e36300 import E36300Supply


def _install_fake_pyvisa(monkeypatch, mocker):
    fake_inst = mocker.Mock()
    fake_inst.query.return_value = "5.0010\n"
    fake_rm = mocker.Mock()
    fake_rm.open_resource.return_value = fake_inst
    fake_pyvisa = types.SimpleNamespace(ResourceManager=mocker.Mock(return_value=fake_rm))

    import sys

    monkeypatch.setitem(sys.modules, "pyvisa", fake_pyvisa)
    return fake_inst


def test_set_voltage_sends_scpi(monkeypatch, mocker):
    fake_inst = _install_fake_pyvisa(monkeypatch, mocker)
    supply = E36300Supply({"simulate": False, "visa_resource": "USB::INSTR"})
    supply.connect()
    supply.set_voltage(1, 5.0)
    assert fake_inst.write.call_args_list[0].args[0] == ":INST:SEL CH1"
    assert fake_inst.write.call_args_list[1].args[0] == ":VOLT 5.0000"


def test_invalid_channel_raises(monkeypatch, mocker):
    _install_fake_pyvisa(monkeypatch, mocker)
    supply = E36300Supply({"simulate": False, "visa_resource": "USB::INSTR"})
    supply.connect()
    with pytest.raises(ValueError):
        supply.set_voltage(5, 5.0)


def test_output_on_all(monkeypatch, mocker):
    fake_inst = _install_fake_pyvisa(monkeypatch, mocker)
    supply = E36300Supply({"simulate": False, "visa_resource": "USB::INSTR"})
    supply.connect()
    supply.output_on()
    assert fake_inst.write.call_args.args[0] == ":OUTP:STAT ON"


def test_output_on_channel(monkeypatch, mocker):
    fake_inst = _install_fake_pyvisa(monkeypatch, mocker)
    supply = E36300Supply({"simulate": False, "visa_resource": "USB::INSTR"})
    supply.connect()
    supply.output_on(2)
    assert fake_inst.write.call_args.args[0] == ":OUTP:SEL CH2,ON"


def test_measure_voltage(monkeypatch, mocker):
    _install_fake_pyvisa(monkeypatch, mocker)
    supply = E36300Supply({"simulate": False, "visa_resource": "USB::INSTR"})
    supply.connect()
    assert supply.measure_voltage(1) == pytest.approx(5.001)


def test_simulate_measure():
    supply = E36300Supply({"simulate": True, "sim_voltage": 3.3, "sim_current": 0.2})
    supply.connect()
    assert supply.measure_voltage(1) == pytest.approx(3.3)
