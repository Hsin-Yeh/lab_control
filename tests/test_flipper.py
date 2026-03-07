"""Unit tests for KinesisFlipper."""

from __future__ import annotations

import types

import pytest

from instruments.base import InstrumentConnectionError
from instruments.flipper import KinesisFlipper


def _install_fake_pylablib(monkeypatch, mocker):
    fake_pll = types.SimpleNamespace(par={})
    fake_device = mocker.Mock()
    fake_device.get_state.return_value = 1
    fake_thorlabs = types.SimpleNamespace(
        list_kinesis_devices=mocker.Mock(return_value=[("37000001", "APT Filter Flipper")]),
        MFF=mocker.Mock(return_value=fake_device),
    )
    fake_devices = types.SimpleNamespace(Thorlabs=fake_thorlabs)

    import sys

    monkeypatch.setitem(sys.modules, "pylablib", fake_pll)
    monkeypatch.setitem(sys.modules, "pylablib.devices", fake_devices)
    return fake_thorlabs, fake_device


def test_connect_calls_mff(monkeypatch, mocker):
    fake_thorlabs, _ = _install_fake_pylablib(monkeypatch, mocker)
    flipper = KinesisFlipper(
        {
            "simulate": False,
            "serial": "37000001",
            "kinesis_path": "C:/Program Files/Thorlabs/Kinesis",
            "settle_time_s": 0.01,
        }
    )
    flipper.connect()
    fake_thorlabs.MFF.assert_called_once_with("37000001")


def test_connect_missing_serial_raises(monkeypatch, mocker):
    fake_pll = types.SimpleNamespace(par={})
    fake_thorlabs = types.SimpleNamespace(list_kinesis_devices=mocker.Mock(return_value=[]))
    fake_devices = types.SimpleNamespace(Thorlabs=fake_thorlabs)

    import sys

    monkeypatch.setitem(sys.modules, "pylablib", fake_pll)
    monkeypatch.setitem(sys.modules, "pylablib.devices", fake_devices)

    flipper = KinesisFlipper(
        {
            "simulate": False,
            "serial": "37000001",
            "kinesis_path": "C:/Program Files/Thorlabs/Kinesis",
            "settle_time_s": 0.01,
        }
    )
    with pytest.raises(InstrumentConnectionError):
        flipper.connect()


def test_set_position_out_of_range():
    flipper = KinesisFlipper({"simulate": True, "serial": "SIM", "settle_time_s": 0.0})
    flipper.connect()
    with pytest.raises(ValueError):
        flipper.set_position(3)


def test_simulate_toggle():
    flipper = KinesisFlipper({"simulate": True, "serial": "SIM", "settle_time_s": 0.0})
    flipper.connect()
    assert flipper.get_position() == 1
    assert flipper.toggle() == 2
    assert flipper.get_position() == 2


def test_context_manager_disconnects(monkeypatch, mocker):
    _, fake_device = _install_fake_pylablib(monkeypatch, mocker)
    cfg = {
        "simulate": False,
        "serial": "37000001",
        "kinesis_path": "C:/Program Files/Thorlabs/Kinesis",
        "settle_time_s": 0.01,
    }
    with KinesisFlipper(cfg):
        pass
    fake_device.close.assert_called_once()
