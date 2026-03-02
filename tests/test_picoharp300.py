"""Unit tests for PicoHarp300."""

from __future__ import annotations

import pytest

from instruments.base import InstrumentCommandError
from instruments.picoharp300 import HISTCHAN, PicoHarp300


def test_simulate_acquire_shape():
    ph = PicoHarp300({"simulate": True, "binning": 0})
    ph.connect()
    hist = ph.acquire(200)
    assert hist.shape == (HISTCHAN,)
    assert str(hist.dtype) == "uint32"


def test_simulate_acquire_has_peak():
    ph = PicoHarp300({"simulate": True, "binning": 0})
    ph.connect()
    hist = ph.acquire(200)
    assert int(hist.max()) > 1000


def test_set_binning_invalid():
    ph = PicoHarp300({"simulate": True, "binning": 0})
    ph.connect()
    with pytest.raises(ValueError):
        ph.set_binning(10)


def test_set_sync_divider_invalid():
    ph = PicoHarp300({"simulate": True, "binning": 0})
    ph.connect()
    with pytest.raises(ValueError):
        ph.set_sync_divider(3)


def test_check_raises_on_negative():
    ph = PicoHarp300({"simulate": True, "binning": 0})
    ph.connect()

    class _FakeDll:
        @staticmethod
        def PH_GetErrorString(retcode, buf):
            _ = retcode
            buf.value = b"fake error"

    ph._dll = _FakeDll()
    with pytest.raises(InstrumentCommandError):
        ph._check(-1, "test_func")


def test_get_resolution_simulate():
    ph = PicoHarp300({"simulate": True, "binning": 0})
    ph.connect()
    assert ph.get_resolution() > 0.0


def test_simulate_count_rate_range():
    ph = PicoHarp300({"simulate": True, "binning": 0})
    ph.connect()
    rate = ph.get_count_rate(0)
    assert 50000 <= rate <= 200000
