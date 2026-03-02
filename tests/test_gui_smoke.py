"""Smoke tests for GUI construction in simulate mode."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gui.main_window import MainWindow
from gui.widgets.config_editor import ConfigEditorWidget
from gui.widgets.connections_widget import ConnectionsWidget
from gui.widgets.log_viewer import LogViewerWidget


@pytest.fixture(scope="module")
def app():
    """Provide QApplication for tests.

    Parameters:
        None (units: none).
    """
    application = QApplication.instance() or QApplication([])
    yield application


def test_window_opens(app):
    """Main window constructs with default mac simulate config.

    Parameters:
        app: QApplication fixture (units: none).
    """
    _ = app
    window = MainWindow(config_path="config/instruments_mac.yaml")
    assert window is not None


def test_log_viewer_appends(app):
    """Log viewer receives forwarded log messages.

    Parameters:
        app: QApplication fixture (units: none).
    """
    _ = app
    viewer = LogViewerWidget()
    viewer.install_on_logger("rotation_sweep")
    logger = logging.getLogger("rotation_sweep")
    logger.info("hello from smoke")
    app.processEvents()
    assert "hello from smoke" in viewer._text.toPlainText()


def test_config_editor_loads(app):
    """Config editor loads YAML file text.

    Parameters:
        app: QApplication fixture (units: none).
    """
    _ = app
    editor = ConfigEditorWidget("config/instruments_mac.yaml")
    text = editor._editor.toPlainText()
    assert "simulate: true" in text


def test_connections_widget_constructs(app):
    """Connections widget builds rows without hardware.

    Parameters:
        app: QApplication fixture (units: none).
    """
    _ = app
    widget = ConnectionsWidget("config/instruments_mac.yaml")
    assert widget is not None
