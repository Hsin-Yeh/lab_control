"""Smoke tests for GUI — run in simulate mode, no hardware required."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

if sys.platform != "darwin":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
 
# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication once for the entire test session.

    Parameters:
        None (units: none).
    """
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def mac_config(tmp_path) -> str:
    """Write a minimal simulate-mode config to a temp file.

    Parameters:
        tmp_path: Temporary path fixture (units: none).
    """
    import yaml

    cfg = {
        "pm100d": {"simulate": True, "resource": "USB0::dummy", "wavelength_nm": 532, "averaging_count": 1},
        "e36300": {"simulate": True, "resource": "TCPIP0::dummy"},
        "gsm20h10": {"simulate": True, "resource": "GPIB0::5::INSTR"},
        "picoharp300": {"simulate": True, "dll_path": None},
        "kdc101": {"simulate": True, "serial_number": "27000001", "kinesis_path": None},
    }
    path = tmp_path / "instruments_test.yaml"
    path.write_text(yaml.dump(cfg), encoding="utf-8")
    return str(path)


def test_log_viewer_appends(qapp):
    """Log viewer captures Python log messages.

    Parameters:
        qapp: QApplication fixture (units: none).
    """
    from gui.widgets.log_viewer import LogViewerWidget

    widget = LogViewerWidget()
    widget.install_on_logger("smoke_test")
    logging.getLogger("smoke_test").info("hello from smoke test")
    qapp.processEvents()
    assert "hello from smoke test" in widget._text.toPlainText()


def test_config_editor_loads(qapp, mac_config):
    """Config editor opens a YAML file without error.

    Parameters:
        qapp: QApplication fixture (units: none).
        mac_config: Temporary config path (units: none).
    """
    _ = qapp
    from gui.widgets.config_editor import ConfigEditorWidget

    widget = ConfigEditorWidget(mac_config)
    assert widget is not None


def test_connections_widget_builds(qapp, mac_config):
    """Connections widget constructs rows for all available instruments.

    Parameters:
        qapp: QApplication fixture (units: none).
        mac_config: Temporary config path (units: none).
    """
    _ = qapp
    from gui.widgets.connections_widget import ConnectionsWidget

    widget = ConnectionsWidget(mac_config)
    assert len(widget._rows) >= 3


def test_connections_resource_summary(qapp, mac_config):
    """Resource summary shows the correct address, not N/A.

    Parameters:
        qapp: QApplication fixture (units: none).
        mac_config: Temporary config path (units: none).
    """
    _ = qapp
    from gui.widgets.connections_widget import ConnectionsWidget

    widget = ConnectionsWidget(mac_config)
    row = widget._rows["gsm20h10"]
    assert "N/A" not in row._summary.text()


def test_gsm_panel_builds(qapp):
    """GSM20H10 panel constructs in simulate mode.

    Parameters:
        qapp: QApplication fixture (units: none).
    """
    _ = qapp
    from gui.instruments.gsm20h10_panel import GSM20H10Panel

    cfg = {"simulate": True, "resource": "GPIB0::5::INSTR"}
    panel = GSM20H10Panel(cfg)
    assert panel._panic_btn is not None


def test_e36300_panel_no_auto_read_on_init(qapp):
    """E36300 panel does not auto-read when channel changes before connect.

    Parameters:
        qapp: QApplication fixture (units: none).
    """
    _ = qapp
    from gui.instruments.e36300_panel import E36300Panel

    cfg = {"simulate": True, "resource": "TCPIP0::dummy"}
    panel = E36300Panel(cfg)
    panel._channel.setCurrentIndex(1)
    assert panel._single_worker is None or not panel._single_worker.isRunning()


def test_main_window_opens(qapp, mac_config):
    """MainWindow constructs without raising errors.

    Parameters:
        qapp: QApplication fixture (units: none).
        mac_config: Temporary config path (units: none).
    """
    _ = qapp
    from gui.main_window import MainWindow

    window = MainWindow(config_path=mac_config)
    assert window is not None
    window.close()
