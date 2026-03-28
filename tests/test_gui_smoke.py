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
    if sys.platform == "darwin" and os.environ.get("LAB_CONTROL_GUI_TESTS", "0") != "1":
        pytest.skip(
            "Skipping Qt GUI smoke on macOS in headless mode. "
            "Set LAB_CONTROL_GUI_TESTS=1 when running from an active GUI session."
        )

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
        "flipper": {"simulate": True, "serial": "37000001", "kinesis_path": None},
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


def test_pm100d_panel_builds(qapp):
    """PM100D panel constructs in simulate mode.

    Parameters:
        qapp: QApplication fixture (units: none).
    """
    _ = qapp
    from gui.instruments.pm100d_panel import PM100DPanel

    cfg = {"simulate": True, "resource": "USB0::dummy", "wavelength_nm": 532, "averaging_count": 10}
    panel = PM100DPanel(cfg)
    assert panel._read_once_btn is not None
    assert panel._read_start_btn is not None
    assert panel._zero_btn is not None


def test_kinesis_panel_builds(qapp):
    """Kinesis panel constructs in simulate mode.

    Parameters:
        qapp: QApplication fixture (units: none).
    """
    _ = qapp
    from gui.instruments.kinesis_panel import KinesisPanel

    cfg = {
        "kdc101": {"simulate": True, "serial": "27000001", "kinesis_path": None},
        "flipper": {"simulate": True, "serial": "37000001", "kinesis_path": None},
    }
    panel = KinesisPanel(cfg)
    assert panel._stage_connect_btn is not None
    assert panel._flipper_connect_btn is not None


def test_rotation_sweep_tab_builds_with_pm_controls(qapp, mac_config):
    """Rotation sweep tab exposes PM controls and initialization option.

    Parameters:
        qapp: QApplication fixture (units: none).
        mac_config: Temporary config path (units: none).
    """
    _ = qapp
    from gui.tabs.rotation_sweep_tab import RotationSweepTab

    tab = RotationSweepTab(mac_config)
    assert tab._wavelength_nm is not None
    assert tab._average_count is not None
    assert tab._zero_before_sweep is not None
    assert tab._initialize_devices.isChecked()
    assert tab._covered_btn is not None
    assert tab._uncovered_btn is not None


def test_rotation_sweep_tab_zero_sequence_waits_for_user(qapp, mac_config):
    """Rotation sweep waits for cover/uncover confirmations before run.

    Parameters:
        qapp: QApplication fixture (units: none).
        mac_config: Temporary config path (units: none).
    """
    _ = qapp
    from gui.tabs.rotation_sweep_tab import RotationSweepTab

    tab = RotationSweepTab(mac_config)
    tab._zero_before_sweep.setChecked(True)

    captured: dict[str, object] = {}

    def _fake_start(kwargs: dict) -> None:
        captured.update(kwargs)

    tab._start_rotation_worker = _fake_start  # type: ignore[method-assign]

    tab._on_run()
    assert tab._zero_sequence_active is True
    assert not tab._covered_btn.isHidden()
    assert tab._uncovered_btn.isHidden()

    tab._on_zero_complete()
    assert tab._covered_btn.isHidden()
    assert not tab._uncovered_btn.isHidden()

    tab._on_zero_uncovered_start()
    assert captured["zero_before_sweep"] is False


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
    exp_labels = [window._experiments_widget.tabText(i) for i in range(window._experiments_widget.count())]
    assert "Resistance Log" in exp_labels
    assert "GSM Monitor" in exp_labels
    tab_labels = [window._instruments_widget.tabText(i) for i in range(window._instruments_widget.count())]
    assert "PM100D" in tab_labels
    assert "Kinesis" in tab_labels
    window.close()


def test_resistance_log_tab_builds(qapp, mac_config):
    """Resistance log tab constructs in simulate mode.

    Parameters:
        qapp: QApplication fixture (units: none).
        mac_config: Temporary config path (units: none).
    """
    _ = qapp
    from gui.tabs.resistance_log_tab import ResistanceLogTab

    tab = ResistanceLogTab(mac_config)
    assert tab._run is not None
    assert tab._abort is not None


def test_gsm_monitor_tab_builds(qapp, mac_config):
    """GSM monitor tab constructs in simulate mode.

    Parameters:
        qapp: QApplication fixture (units: none).
        mac_config: Temporary config path (units: none).
    """
    _ = qapp
    from gui.tabs.gsm_monitor_tab import GSMMonitorTab

    tab = GSMMonitorTab(mac_config)
    assert tab._run is not None
    assert tab._abort is not None
