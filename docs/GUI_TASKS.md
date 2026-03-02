# GUI Implementation Tasks — Lab Instrument Control

> **Instructions for GitHub Copilot**: Implement the tasks below **in order**. Each task references existing repo files and tells you exactly what to create or modify. Read `docs/GUI_SPEC.md` first for full context on layout, design constraints, and the two-phase approach. Do **not** modify any existing file outside the `gui/` package and `gui_main.py` unless a task explicitly says so.

---

## Task 0 — Create Package Skeleton

**Create the following empty files** (just a module docstring and `from __future__ import annotations`):

- `gui/__init__.py`
- `gui/widgets/__init__.py`
- `gui/tabs/__init__.py`

These make `gui` and its sub-packages importable.

---

## Task 1 — `gui/widgets/log_viewer.py`

Create `LogViewerWidget` and `GuiLogHandler`.

### `GuiLogHandler(logging.Handler)`

A Python `logging.Handler` that emits log records to the GUI via a Qt signal without blocking.

```python
class SignalRelay(QObject):
    message = Signal(str, int)  # (formatted text, levelno)

class GuiLogHandler(logging.Handler):
    def __init__(self, relay: SignalRelay) -> None: ...
    def emit(self, record: logging.LogRecord) -> None:
        # format the record and emit relay.message
        ...
```

### `LogViewerWidget(QWidget)`

```python
class LogViewerWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        # Creates:
        # - self._text: QPlainTextEdit (read-only, monospace font)
        # - self._clear_btn: QPushButton("Clear")
        # - self._save_btn: QPushButton("Save Log...")
        # Max block count: 2000
        ...

    def append_message(self, text: str, levelno: int) -> None:
        # Appends coloured HTML line based on levelno:
        # DEBUG -> #888888, INFO -> #ffffff, WARNING -> #ffaa00, ERROR -> #ff4444
        # Auto-scrolls to bottom.
        ...

    def _on_save(self) -> None:
        # Opens QFileDialog.getSaveFileName, writes plain text content
        ...

    def install_on_logger(self, logger_name: str) -> None:
        # Attaches GuiLogHandler to the named logger (and root logger)
        # so all existing utils/logger.py loggers are captured
        ...
```

**Acceptance**: After construction, calling `logging.getLogger("rotation_sweep").info("hello")` should appear in the widget.

---

## Task 2 — `gui/widgets/status_bar.py`

Create `InstrumentStatusBar`.

```python
class InstrumentStatusBar(QWidget):
    """Horizontal row of status indicators, one per instrument."""

    INSTRUMENTS: list[tuple[str, type]] = [
        ("kdc101",      KDC101Stage),
        ("pm100d",      PM100D),
        ("e36300",      E36300Supply),
        ("gsm20h10",    GSM20H10),
        ("picoharp300", PicoHarp300),
    ]
    # colour constants
    COLOR_OK  = "#44cc44"
    COLOR_SIM = "#888888"
    COLOR_ERR = "#cc4444"
    COLOR_UNK = "#444444"

    def __init__(self, config_path: str, parent: QWidget | None = None) -> None:
        # Builds one QLabel (dot) + QLabel (name) pair per instrument
        # Adds [Check All] QPushButton and [Discover] QPushButton
        # Starts self._timer = QTimer(interval=5000) -> self._check_all
        ...

    def set_config(self, config_path: str) -> None:
        # Reload config dict; restart polling
        ...

    def _check_all(self) -> None:
        # For each instrument:
        #   if config[key].get("simulate") -> set SIM colour, label "SIM"
        #   else: launch CheckWorker(QThread) -> result signal -> _update_indicator
        ...

    def _update_indicator(self, key: str, ok: bool, msg: str) -> None:
        # Sets dot colour and tooltip
        ...
```

#### `CheckWorker(QThread)`

```python
class CheckWorker(QThread):
    result = Signal(str, bool, str)  # (instrument_key, ok, message)

    def __init__(self, key: str, cls: type, cfg: dict) -> None: ...
    def run(self) -> None:
        # Opens instrument with `with cls(cfg)` and reads instrument_id
        # Emits result(key, True, instrument_id) on success
        # Emits result(key, False, str(exception)) on failure
        ...
```

**Acceptance**: Window startup shows grey dots; clicking [Check All] updates them based on simulate flags and actual connectivity.

---

## Task 3 — `gui/widgets/config_editor.py`

Create `ConfigEditorWidget`.

```python
class ConfigEditorWidget(QWidget):
    config_saved = Signal(str)  # emits the new file path after a successful save

    def __init__(self, config_path: str, parent: QWidget | None = None) -> None:
        # self._path: str = config_path
        # self._path_edit: QLineEdit (read-only, shows current path)
        # self._load_btn: QPushButton("Load...")
        # self._save_btn: QPushButton("Save")
        # self._editor: QPlainTextEdit (monospace, editable)
        # self._status_label: QLabel (shows parse errors in red)
        # Calls self._load_file(config_path)
        ...

    def _load_file(self, path: str) -> None:
        # Reads file text, sets self._editor.setPlainText
        # Clears status label
        ...

    def _on_load(self) -> None:
        # QFileDialog.getOpenFileName, filter "YAML (*.yaml *.yml)"
        # Calls self._load_file on selection
        ...

    def _on_save(self) -> None:
        # Validates YAML (yaml.safe_load); on error sets red status_label, returns
        # On success: writes to self._path, emits config_saved(self._path)
        ...
```

**Acceptance**: Loading and saving the file round-trips correctly; a deliberate YAML syntax error shows the error message.

---

## Task 4 — `gui/workers.py`

Create one `QThread` worker per experiment. All workers follow the same contract.

### Base contract

```python
class _BaseWorker(QThread):
    log_message  = Signal(str, int)    # (text, levelno)
    progress     = Signal(int, int)    # (current_step, total_steps)
    status_text  = Signal(str)         # short status for the tab label
    finished     = Signal(list)        # results: list[dict]
    error        = Signal(str)         # error message if exception escapes

    def __init__(self, config_path: str, output_dir: str) -> None:
        super().__init__()
        self._config_path = config_path
        self._output_dir  = output_dir
        self._abort       = threading.Event()

    def abort(self) -> None:
        """Request graceful abort."""
        self._abort.set()
```

### `RotationSweepWorker(_BaseWorker)`

```python
class RotationSweepWorker(_BaseWorker):
    def __init__(
        self,
        config_path: str,
        output_dir: str,
        start_deg: float,
        stop_deg: float,
        step_deg: float,
    ) -> None: ...

    def run(self) -> None:
        # 1. Attach a GuiLogHandler to the "rotation_sweep" logger so log_message fires
        # 2. Call experiments.rotation_sweep.run_rotation_sweep(...)
        # 3. Emit finished(results) on success, error(str(exc)) on exception
        # NOTE: abort is checked by monitoring self._abort between steps.
        #       For Phase 1, wrap the entire run_rotation_sweep in a try/except
        #       and rely on KeyboardInterrupt-style abort via thread termination.
        #       Phase 2 will replace this with the iterator variant.
        ...
```

### `IVCurveWorker(_BaseWorker)`

```python
class IVCurveWorker(_BaseWorker):
    def __init__(
        self,
        config_path: str,
        output_dir: str,
        v_start: float,
        v_stop: float,
        v_step: float,
        i_limit: float,
    ) -> None: ...

    def run(self) -> None:
        # 1. Attach GuiLogHandler to "iv_curve" logger
        # 2. Call experiments.iv_curve.run_iv_curve(...)
        # 3. Emit finished(results) / error(str)
        ...
```

### `TCSPCScanWorker(_BaseWorker)`

```python
class TCSPCScanWorker(_BaseWorker):
    def __init__(
        self,
        config_path: str,
        output_dir: str,
        angles: list[float] | None,
        acq_time_ms: int | None,
    ) -> None: ...

    def run(self) -> None:
        # 1. Attach GuiLogHandler to "tcspc_scan" logger
        # 2. Call experiments.tcspc_scan.run_tcspc_scan(...)
        # 3. Emit finished(results) / error(str)
        ...
```

**Acceptance**: Each worker can be constructed and `.start()`ed; it calls the corresponding `run_*` function; log messages fire on `log_message`; `finished` fires with the return value.

---

## Task 5 — `gui/tabs/rotation_sweep_tab.py`

Create `RotationSweepTab(QWidget)`.

### Parameter form fields

| Field label | Widget | Default | Range / step |
|---|---|---|---|
| Start angle (deg) | `QDoubleSpinBox` | 0.0 | −1000 – 1000, step 1.0 |
| Stop angle (deg) | `QDoubleSpinBox` | 360.0 | −1000 – 1000, step 1.0 |
| Step size (deg) | `QDoubleSpinBox` | 5.0 | 0.01 – 360, step 0.5 |
| Output dir | `QLineEdit` | `"output"` | — |

### pyqtgraph plot

- Use `pyqtgraph.PlotWidget` with a **polar-to-Cartesian line plot** (`PlotDataItem`).
- X-axis label: `angle (deg)`, Y-axis label: `power (W)`.
- On `finished(results)`, extract `angle_deg` and `power_W` columns and call `plot_item.setData(angles, powers)`.
- Add a second `PlotDataItem` in a different colour for `power_dBm` on a secondary Y axis (use `pyqtgraph.ViewBox` with `p1.scene().addItem(p2)`).
- Phase 1: plot is redrawn once after the run. Phase 2 will update per-step.

### Wiring

```python
class RotationSweepTab(QWidget):
    def __init__(self, config_path: str, log_viewer: LogViewerWidget, parent: QWidget | None = None) -> None:
        ...

    def _on_run(self) -> None:
        # Reads parameter widgets
        # Creates RotationSweepWorker and connects signals:
        #   worker.log_message  -> log_viewer.append_message
        #   worker.progress     -> self._progress_bar.setValue  (scale to %)
        #   worker.status_text  -> self._status_label.setText
        #   worker.finished     -> self._on_finished
        #   worker.error        -> self._on_error
        # Disables [Run], enables [Abort]
        # Calls worker.start()
        ...

    def _on_abort(self) -> None:
        # Calls self._worker.abort()
        # Sets status label to "Aborting..."
        ...

    def _on_finished(self, results: list[dict]) -> None:
        # Re-enables [Run], disables [Abort]
        # Updates plot
        # Sets output dir label (clickable, opens folder)
        ...

    def _on_error(self, msg: str) -> None:
        # Shows QMessageBox.critical
        # Re-enables [Run]
        ...

    def update_config(self, config_path: str) -> None:
        # Called by MainWindow when config is saved in ConfigEditorWidget
        self._config_path = config_path
```

**Acceptance**: Tab runs rotation sweep in simulate mode, logs appear in log_viewer, progress bar advances, plot fills in at the end.

---

## Task 6 — `gui/tabs/iv_curve_tab.py`

Create `IVCurveTab(QWidget)` following the same pattern as `RotationSweepTab`.

### Parameter form fields

| Field label | Widget | Default | Range / step |
|---|---|---|---|
| V start (V) | `QDoubleSpinBox` | −5.0 | −250 – 250, step 0.1 |
| V stop (V) | `QDoubleSpinBox` | 5.0 | −250 – 250, step 0.1 |
| V step (V) | `QDoubleSpinBox` | 0.1 | 0.001 – 10, step 0.01 |
| I limit (A) | `QDoubleSpinBox` | 0.05 | 1e-6 – 1.0, step 0.001 |
| Output dir | `QLineEdit` | `"output"` | — |

### pyqtgraph plot

- X-axis: `voltage (V)`, Y-axis: `current (A)`.
- Plot `voltage` vs `current` as a line+scatter (`PlotDataItem(pen=..., symbol='o', symbolSize=4)`).
- On `finished(results)`, call `setData(voltages, currents)`.

### Wiring

Same structure as `RotationSweepTab`. Use `IVCurveWorker`. Name methods `_on_run`, `_on_abort`, `_on_finished`, `_on_error`, `update_config`.

**Acceptance**: Tab runs iv_curve in simulate mode, shows V-I scatter after run.

---

## Task 7 — `gui/tabs/tcspc_scan_tab.py`

Create `TCSPCScanTab(QWidget)` following the same pattern.

### Parameter form fields

| Field label | Widget | Default | Notes |
|---|---|---|---|
| Angles (deg) | `QLineEdit` | `"0 45 90 135 180"` | Space-separated floats; parsed on Run |
| Acq time (ms) | `QSpinBox` | 1000 | Range 1 – 600000 |
| Output dir | `QLineEdit` | `"output"` | — |

### pyqtgraph plot

- Use a `pyqtgraph.BarGraphItem` or `PlotDataItem` for the TCSPC histogram at the last measured angle.
- X-axis: `time bin (ns)`, Y-axis: `counts`.
- After `finished(results)`, check if results contain a `histogram` key (list of counts).
  - If yes: `bar_item.setOpts(x=time_bins, height=histogram, width=bin_width_ns)`.
  - If no (simulate mode returns stub data): show a placeholder flat bar chart.

### Wiring

Same as above. Use `TCSPCScanWorker`.

**Acceptance**: Tab runs tcspc_scan in simulate mode; if histogram data is present it is plotted.

---

## Task 8 — `gui/main_window.py`

Create `MainWindow(QMainWindow)`.

```python
class MainWindow(QMainWindow):
    def __init__(self, config_path: str = "config/instruments.yaml") -> None:
        super().__init__()
        self._config_path = config_path
        self.setWindowTitle("Lab Instrument Control")
        self.resize(1280, 800)

        # --- Central layout ---
        # self._status_bar_widget: InstrumentStatusBar(config_path)
        # self._tab_widget:        QTabWidget
        #   tab 0: RotationSweepTab
        #   tab 1: IVCurveTab
        #   tab 2: TCSPCScanTab
        #   tab 3: ConfigEditorWidget  (label: "Config")
        #   tab 4: LogViewerWidget     (label: "Log")
        # Top bar: QLabel title + QPushButton "Load Config..."
        ...

    def _on_load_config(self) -> None:
        # QFileDialog.getOpenFileName
        # Updates self._config_path
        # Calls self._status_bar_widget.set_config(path)
        # Calls each tab's update_config(path)
        ...

    def _on_config_saved(self, path: str) -> None:
        # Connected to ConfigEditorWidget.config_saved signal
        # Same as _on_load_config effect (update status bar + tabs)
        ...

    def closeEvent(self, event) -> None:
        # If any worker is running, ask QMessageBox.question("Abort running experiment?")
        # Call worker.abort() and worker.wait(3000)
        # Then accept close
        ...
```

**Acceptance**: Window opens with all 5 tabs; status bar shows grey dots; switching to Log tab shows the log viewer; switching to Config tab shows the YAML editor.

---

## Task 9 — `gui_main.py` (repo root)

```python
"""GUI entry point for lab instrument control."""
from __future__ import annotations

import sys
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow


def main() -> None:
    """Launch the GUI application.

    Parameters:
        None (units: none).
    """
    app = QApplication(sys.argv)
    app.setApplicationName("Lab Instrument Control")
    window = MainWindow(config_path="config/instruments.yaml")
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

**Acceptance**: `python gui_main.py` opens the window with no errors (works in simulate mode with no hardware).

---

## Task 10 — Update `requirements.txt`

Append to `requirements.txt`:

```
PySide6>=6.6
pyqtgraph>=0.13
```

---

## Task 11 — Update `pyproject.toml`

Add the GUI script entry point alongside the existing `lab-control` script:

```toml
[project.scripts]
lab-control = "main:main"
lab-gui     = "gui_main:main"
```

---

## Task 12 — Smoke Test (no hardware required)

Create `tests/test_gui_smoke.py` with the following tests:

```python
import pytest
from PySide6.QtWidgets import QApplication

@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])

def test_main_window_opens(app, tmp_path):
    from gui.main_window import MainWindow
    w = MainWindow(config_path="config/instruments.yaml")
    assert w is not None
    w.close()

def test_log_viewer_appends(app):
    import logging
    from gui.widgets.log_viewer import LogViewerWidget
    lv = LogViewerWidget()
    lv.install_on_logger("rotation_sweep")
    logging.getLogger("rotation_sweep").info("test message")
    # Give Qt event loop a tick
    app.processEvents()
    assert "test message" in lv._text.toPlainText()

def test_config_editor_loads(app):
    from gui.widgets.config_editor import ConfigEditorWidget
    ce = ConfigEditorWidget(config_path="config/instruments.yaml")
    text = ce._editor.toPlainText()
    assert "kdc101" in text
```

**Acceptance**: `pytest tests/test_gui_smoke.py -v` passes with no hardware connected.

---

## Phase 2 Tasks (Future — Do Not Implement Now)

These tasks are listed for future reference only. Do **not** implement in this PR.

- **Phase 2-A**: Add `iter_rotation_sweep()`, `iter_iv_curve()`, `iter_tcspc_scan()` iterator variants to `experiments/` that `yield` one `dict` per step.
- **Phase 2-B**: Update workers to call `iter_*` variants and emit `data_point(dict)` signal per step.
- **Phase 2-C**: Update tabs to call `plot_widget.update_point()` on each `data_point` signal for true live plotting.
- **Phase 2-D**: Merge CLI and GUI config handling so `main.py` and `gui_main.py` share a single `AppConfig` object.
- **Phase 2-E**: Add a `SequenceTab` allowing chaining multiple experiments in a queue (drag-and-drop order).
