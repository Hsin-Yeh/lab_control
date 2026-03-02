"""Unit tests for KDC101Stage."""

from __future__ import annotations

import types

import pytest

from instruments.kdc101 import KDC101Stage


def _install_fake_pylablib(monkeypatch, mocker):
    fake_pll = types.SimpleNamespace(par={})
    fake_motor = mocker.Mock()
    fake_thorlabs = types.SimpleNamespace(
        list_kinesis_devices=mocker.Mock(return_value=[("27000000", "Brushed DC Motor Controller")]),
        KinesisMotor=mocker.Mock(return_value=fake_motor),
    )
    fake_devices = types.SimpleNamespace(Thorlabs=fake_thorlabs)

    import sys

    monkeypatch.setitem(sys.modules, "pylablib", fake_pll)
    monkeypatch.setitem(sys.modules, "pylablib.devices", fake_devices)
    return fake_thorlabs, fake_motor


def test_connect_calls_kinesis_motor(monkeypatch, mocker):
    fake_thorlabs, _ = _install_fake_pylablib(monkeypatch, mocker)
    stage = KDC101Stage(
        {
            "simulate": False,
            "serial": "27000000",
            "scale": "PRM1-Z8",
            "kinesis_path": "C:/Program Files/Thorlabs/Kinesis",
            "velocity_deg_per_s": 10.0,
        }
    )
    stage.connect()
    fake_thorlabs.KinesisMotor.assert_called_once_with("27000000", scale="PRM1-Z8")


def test_move_to_valid(monkeypatch, mocker):
    _, fake_motor = _install_fake_pylablib(monkeypatch, mocker)
    fake_motor.get_position.return_value = 90.0
    stage = KDC101Stage(
        {
            "simulate": False,
            "serial": "27000000",
            "scale": "PRM1-Z8",
            "kinesis_path": "",
            "velocity_deg_per_s": 10.0,
        }
    )
    stage.connect()
    stage.move_to(90.0)
    fake_motor.move_to.assert_called_once_with(90.0)
    fake_motor.wait_move.assert_called_once()


def test_move_to_out_of_range():
    stage = KDC101Stage({"simulate": True, "serial": "0", "scale": "PRM1-Z8", "kinesis_path": "", "velocity_deg_per_s": 10.0})
    stage.connect()
    with pytest.raises(ValueError):
        stage.move_to(400.0)


def test_home_calls_home_sync(monkeypatch, mocker):
    _, fake_motor = _install_fake_pylablib(monkeypatch, mocker)
    fake_motor.get_position.return_value = 0.0
    stage = KDC101Stage(
        {
            "simulate": False,
            "serial": "27000000",
            "scale": "PRM1-Z8",
            "kinesis_path": "",
            "velocity_deg_per_s": 10.0,
        }
    )
    stage.connect()
    stage.home()
    fake_motor.home.assert_called_once_with(sync=True)


def test_simulate_move_to():
    stage = KDC101Stage({"simulate": True, "serial": "0", "scale": "PRM1-Z8", "kinesis_path": "", "velocity_deg_per_s": 1000.0})
    stage.connect()
    stage.move_to(45.0)
    assert stage.get_angle() == pytest.approx(45.0)


def test_context_manager_disconnects(monkeypatch, mocker):
    _, fake_motor = _install_fake_pylablib(monkeypatch, mocker)
    cfg = {"simulate": False, "serial": "27000000", "scale": "PRM1-Z8", "kinesis_path": "", "velocity_deg_per_s": 10.0}
    with KDC101Stage(cfg):
        pass
    fake_motor.close.assert_called_once()
