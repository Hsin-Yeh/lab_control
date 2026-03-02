"""YAML config file viewer/editor widget."""

from __future__ import annotations

from pathlib import Path

import yaml
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


class ConfigEditorWidget(QWidget):
    """Simple YAML text editor for instrument configuration.

    Parameters:
        config_path: Initial config file path (units: none).
        parent: Optional parent widget (units: none).
    """

    config_saved = Signal(str)

    def __init__(self, config_path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config_path = Path(config_path)

        self._path_edit = QLineEdit(self)
        self._path_edit.setReadOnly(True)

        self._editor = QPlainTextEdit(self)
        self._status = QLabel("", self)
        self._status.setStyleSheet("color: #AAAAAA;")

        self._load_button = QPushButton("Load…", self)
        self._save_button = QPushButton("Save", self)
        self._load_button.clicked.connect(self._on_load)
        self._save_button.clicked.connect(self._on_save)

        button_layout = QHBoxLayout()
        button_layout.addWidget(QLabel("Config Path:", self))
        button_layout.addWidget(self._path_edit, 1)
        button_layout.addWidget(self._load_button)
        button_layout.addWidget(self._save_button)

        layout = QVBoxLayout(self)
        layout.addLayout(button_layout)
        layout.addWidget(self._editor, 1)
        layout.addWidget(self._status)

        self.set_config_path(str(self._config_path))

    def set_config_path(self, config_path: str) -> None:
        """Set active config path and load file contents.

        Parameters:
            config_path: YAML file path (units: none).
        """
        self._config_path = Path(config_path)
        self._path_edit.setText(self._config_path.as_posix())
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        """Load YAML text from current path into editor.

        Parameters:
            None (units: none).
        """
        try:
            text = self._config_path.read_text(encoding="utf-8")
            self._editor.setPlainText(text)
            self._status.setText(f"Loaded: {self._config_path.as_posix()}")
            self._status.setStyleSheet("color: #66BB66;")
        except Exception as exc:
            self._status.setText(f"Load failed: {exc}")
            self._status.setStyleSheet("color: #CC4444;")

    def _on_load(self) -> None:
        """Open file chooser and load selected YAML.

        Parameters:
            None (units: none).
        """
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Config", str(self._config_path), "YAML Files (*.yaml *.yml)")
        if not file_path:
            return
        self.set_config_path(file_path)

    def _on_save(self) -> None:
        """Validate YAML and save to disk.

        Parameters:
            None (units: none).
        """
        text = self._editor.toPlainText()
        try:
            yaml.safe_load(text)
        except yaml.YAMLError as exc:
            self._status.setText(f"YAML error: {exc}")
            self._status.setStyleSheet("color: #CC4444;")
            QMessageBox.warning(self, "Invalid YAML", f"YAML validation failed:\n{exc}")
            return

        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            self._config_path.write_text(text, encoding="utf-8")
            self._status.setText(f"Saved: {self._config_path.as_posix()}")
            self._status.setStyleSheet("color: #66BB66;")
            self.config_saved.emit(self._config_path.as_posix())
        except Exception as exc:
            self._status.setText(f"Save failed: {exc}")
            self._status.setStyleSheet("color: #CC4444;")
            QMessageBox.critical(self, "Save Error", f"Failed to save config:\n{exc}")
