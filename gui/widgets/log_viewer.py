"""GUI log viewer widget and logging handler bridge."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SignalRelay(QObject):
    """Relay logging records from handler threads into Qt signal/slot system.

    Parameters:
        None (units: none).
    """

    message = Signal(str, int)


class GuiLogHandler(logging.Handler):
    """Logging handler that forwards formatted text into a Qt signal.

    Parameters:
        relay: Signal relay object receiving log text and level (units: none).
    """

    def __init__(self, relay: SignalRelay):
        super().__init__()
        self._relay = relay

    def emit(self, record: logging.LogRecord) -> None:
        """Format and emit a log record through the relay signal.

        Parameters:
            record: Python logging record (units: none).
        """
        try:
            message = self.format(record)
            self._relay.message.emit(message, record.levelno)
        except Exception:
            self.handleError(record)


class LogViewerWidget(QWidget):
    """Read-only GUI widget displaying application logs.

    Parameters:
        parent: Optional parent widget (units: none).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._relay = SignalRelay()
        self._relay.message.connect(self.append_message)
        self._handler = GuiLogHandler(self._relay)
        self._handler.setFormatter(
            logging.Formatter("%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s")
        )

        self._attached_loggers: set[str] = set()

        self._text = QPlainTextEdit(self)
        self._text.setReadOnly(True)
        self._text.setMaximumBlockCount(2000)
        self._text.setStyleSheet("font-family: Menlo, Consolas, monospace;")

        self._clear_button = QPushButton("Clear", self)
        self._save_button = QPushButton("Save Log…", self)
        self._clear_button.clicked.connect(self._text.clear)
        self._save_button.clicked.connect(self._save_log)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(self._clear_button)
        button_layout.addWidget(self._save_button)

        layout = QVBoxLayout(self)
        layout.addLayout(button_layout)
        layout.addWidget(self._text)

    def append_message(self, text: str, levelno: int) -> None:
        """Append a formatted log line to the viewer.

        Parameters:
            text: Log message text (units: none).
            levelno: Python logging level number (units: none).
        """
        if levelno <= logging.DEBUG:
            prefix = "[DEBUG]"
        elif levelno >= logging.ERROR:
            prefix = "[ERROR]"
        elif levelno >= logging.WARNING:
            prefix = "[WARN]"
        else:
            prefix = "[INFO]"

        self._text.appendPlainText(f"{prefix} {text}")
        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._text.setTextCursor(cursor)

    def install_on_logger(self, logger_name: str) -> None:
        """Attach GUI log handler to a named logger and to root logger.

        Parameters:
            logger_name: Logger name to attach to (units: none).
        """
        if logger_name not in self._attached_loggers:
            logger = logging.getLogger(logger_name)
            logger.addHandler(self._handler)
            logger.setLevel(logging.DEBUG)
            self._attached_loggers.add(logger_name)

        root_key = "__root__"
        if root_key not in self._attached_loggers:
            root_logger = logging.getLogger()
            root_logger.addHandler(self._handler)
            root_logger.setLevel(logging.DEBUG)
            self._attached_loggers.add(root_key)

    def _save_log(self) -> None:
        """Persist log viewer contents to a user-selected file.

        Parameters:
            None (units: none).
        """
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Log", "gui.log", "Log Files (*.log)")
        if not file_path:
            return
        path = Path(file_path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self._text.toPlainText(), encoding="utf-8")
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", f"Failed to save log:\n{exc}")
