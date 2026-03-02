# GUI Implementation Tasks — Lab Instrument Control (Updated Plan)

> **Read this first**: This task list supersedes the original assumptions about per-instrument GUI panels.
> We will keep the existing "Experiments GUI wraps the existing `run_*` functions" approach.
> We will add:
> - A **Connections** tab to test all instruments individually (read-only, safe).
> - An **Instruments** tab with **manual panels ONLY** for:
>   - **GSM20H10 SMU**
>   - **E36300 power supply**
> We will NOT build full manual control panels for KDC101, PM100D, PicoHarp300 (connections test only).

## High-level Tab Layout (target)

MainWindow tabs:
1. Experiments (Rotation Sweep | I-V Curve | TCSPC Scan)  ✅ keep existing plan
2. Instruments (GSM20H10 | E36300)  ✅ new
3. Connections (all 5 instruments in rows) ✅ new
4. Config (YAML editor) ✅ keep
5. Log (GUI log viewer) ✅ keep

Header bar: Title + active config path label + [Load Config...] button
(No always-on status bar polling; Connections is the canonical health check)

---

## Task 0 — Package skeleton

Create empty files (module docstring + `from __future__ import annotations`):
- `gui/__init__.py`
- `gui/widgets/__init__.py`
- `gui/tabs/__init__.py`
- `gui/instruments/__init__.py`

---

## Task 1 — Log viewer (unchanged)

Create `gui/widgets/log_viewer.py`:
- `SignalRelay(QObject)` with `message = Signal(str, int)`  # text, levelno
- `GuiLogHandler(logging.Handler)` that formats records and emits relay.message
- `LogViewerWidget(QWidget)` with:
  - read-only `QPlainTextEdit` (monospace), max 2000 lines
  - buttons: Clear, Save Log…
  - method `append_message(text: str, levelno: int)`
  - method `install_on_logger(logger_name: str)` (attach handler to named logger and root)

Acceptance:
- logging to `logging.getLogger("rotation_sweep").info("hello")` shows in widget.

---

## Task 2 — Config editor (unchanged)

Create `gui/widgets/config_editor.py`:
- `ConfigEditorWidget(QWidget)`:
  - shows current YAML path (read-only QLineEdit)
  - Load…, Save
  - validates YAML on save (`yaml.safe_load`)
  - emits `config_saved = Signal(str)` when saved

Acceptance:
- YAML syntax errors are shown; valid YAML saves and emits signal.

---

## Task 3 — Connections tab (NEW, priority)

### Goal
Provide a structured, **non-destructive** connection test for each instrument, individually and with [Test All].

### Create file
- `gui/widgets/connections_widget.py`

### Instruments to test
- KDC101Stage
- PM100D
- E36300Supply
- GSM20H10
- PicoHarp300

### UI (per instrument row)
- Dot indicator: grey (not tested), orange (running), green (PASS), red (FAIL)
- Labels:
  - instrument name
  - address/resource summary from YAML (e.g., VISA string, serial, DLL path)
- Buttons:
  - [Test] per row
  - [Clear] per row (reset status to grey)
- Bottom:
  - [Test All] button

### Worker
Create `ConnectionTestWorker(QThread)` in same file (or `gui/instruments/workers.py` if you prefer):
- Signal: `result = Signal(str, bool, str)`  # key, ok, detail
- `run()`:
  - If `simulate: true`, do NOT connect; emit ok with detail "SIMULATED — no hardware test"
  - Else `with cls(cfg) as inst:` then read `inst.instrument_id`
  - Do **read-only** commands only; never enable output, never move stage, never acquire.
  - emit PASS with ID string, or FAIL with exception text

Per-instrument safe actions:
- KDC101: connect + read `instrument_id`
- PM100D: connect + read ID + 1 power sample (read-only)
- E36300: connect + read ID + read output state (do NOT enable output)
- GSM20H10: connect + read ID + confirm output is OFF (do NOT enable)
- PicoHarp300: open + read ID/serial + close

Acceptance:
- Clicking [Test] shows orange then PASS/FAIL; simulate mode shows "SIMULATED".

---

## Task 4 — Experiment workers (keep "wrap run_*")

Create `gui/workers.py`:
- `_BaseWorker(QThread)` with signals:
  - `log_message = Signal(str, int)`
  - `progress = Signal(int, int)`  # optional for Phase 1
  - `status_text = Signal(str)`
  - `finished = Signal(list)`      # list[dict]
  - `error = Signal(str)`
- Implement:
  - `RotationSweepWorker` calls `experiments.rotation_sweep.run_rotation_sweep(...)`
  - `IVCurveWorker` calls `experiments.iv_curve.run_iv_curve(...)`
  - `TCSPCScanWorker` calls `experiments.tcspc_scan.run_tcspc_scan(...)`
- Attach `GuiLogHandler` to the relevant experiment logger names (rotation_sweep / iv_curve / tcspc_scan).

Acceptance:
- Each worker `.start()` runs in simulate mode and emits `finished(results)`.

---

## Task 5 — Experiment tabs (keep Phase 1, post-run plot)

Create:
- `gui/tabs/rotation_sweep_tab.py`
- `gui/tabs/iv_curve_tab.py`
- `gui/tabs/tcspc_scan_tab.py`

Rules:
- Run/Abort buttons
- show progress (basic)
- redraw pyqtgraph plot on `finished(results)` (post-run)
- send worker log_message to LogViewerWidget

Parameter forms and plot types:

### RotationSweepTab
- Parameters: start_deg, stop_deg, step_deg, output_dir
- Plot: angle vs power (W) line, optional dBm secondary axis

### IVCurveTab
- Parameters: v_start, v_stop, v_step, i_limit, output_dir
- Plot: voltage vs current scatter+line

### TCSPCScanTab
- Parameters: angles (space-separated), acq_time_ms, output_dir
- Plot: histogram bar chart (if data available)

Acceptance:
- Running each tab works in simulate mode with no hardware.

---

## Task 6 — Instrument workers (NEW, for GSM/E36300)

Create `gui/instruments/workers.py`:

1) `ConnectWorker(QThread)`
- `connected = Signal(bool, str)`  # ok, id_or_error
- connect using `with cls(cfg)` just for ID, then disconnect

2) `SingleReadWorker(QThread)`
- `data = Signal(dict)`
- `error = Signal(str)`
- For GSM: returns dict with `voltage_V`, `current_A`, `power_W`, `timestamp_s`
- For E36300: returns `voltage_V`, `current_A`, `channel`, `timestamp_s`

3) `ContinuousPollWorker(QThread)` (for GSM first)
- `data = Signal(dict)`
- `error = Signal(str)`
- `stopped = Signal(str)`  # reason
- accepts `interval_ms` and `abort()` method (threading.Event)
- loops: read values -> emit data -> sleep -> check abort

Safety:
- Never change output state in polling worker.
- Panic OFF is a separate immediate action.

---

## Task 7 — GSM20H10 SMU panel (NEW, minimal but useful)

Create `gui/instruments/gsm20h10_panel.py`:

Must-have controls:
- Connect / Disconnect
- Mode: Voltage-source (Milestone 1). Current-source optional later.
- Setpoint (V) + compliance (A)
- Output ON / Output OFF
- Read Once
- Live mode:
  - interval (ms)
  - Start Live / Stop Live
  - optional "Log to CSV while live" toggle

Display:
- measured V, measured I, computed P
- small strip chart (last 200 points) using pyqtgraph (e.g., power vs time)

Safety:
- Always-visible **Panic Output OFF** button (works even while live polling)

Acceptance:
- In simulate mode: values update; controls behave (disable/enable rules).
- With hardware: output state changes correctly; panic works.

---

## Task 8 — E36300 power supply panel (NEW, keep simple)

Create `gui/instruments/e36300_panel.py`:

Must-have controls:
- Connect / Disconnect
- Channel select (CH1/CH2/CH3)
- Set voltage + current limit
- Apply (recommended only when output OFF)
- Output ON / Output OFF
- Read channel (single readback)
- Panic ALL OFF

Acceptance:
- In simulate mode: readback works; channel switching works.

---

## Task 9 — Main window assembly (update existing plan)

Create/Update `gui/main_window.py`:

- Tabs:
  - ExperimentsWidget (contains experiment tabs)
  - InstrumentsWidget (subtabs: GSM20H10Panel, E36300Panel)
  - ConnectionsWidget
  - ConfigEditorWidget
  - LogViewerWidget
- Wire config changes:
  - Load Config… updates: ConnectionsWidget + experiment tabs + instrument panels + ConfigEditorWidget
- closeEvent:
  - If GSM/E36300 outputs might be ON, warn and attempt panic-off before exit

Acceptance:
- App starts, switching tabs works, and config path propagation works.

---

## Task 10 — Entry point (unchanged)

Create `gui_main.py` at repo root:

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

Acceptance: `python gui_main.py` opens the window with no errors (works in simulate mode).

---

## Task 11 — Dependencies / scripts

Update:
- `requirements.txt` add:
  - `PySide6>=6.6`
  - `pyqtgraph>=0.13`
- `pyproject.toml` add script:
  - `lab-gui = "gui_main:main"`

---

## Task 12 — Smoke tests (update)

Create/Update `tests/test_gui_smoke.py`:
- window opens
- log viewer appends
- config editor loads
- connections widget constructs without hardware

Acceptance:
- `pytest tests/test_gui_smoke.py -v` passes in simulate mode.

---

## Phase 2 Tasks (Future — Do Not Implement Now)

These tasks are for future reference only:

- **Phase 2-A**: Add `iter_rotation_sweep()`, `iter_iv_curve()`, `iter_tcspc_scan()` iterator variants to `experiments/` that `yield` one `dict` per step.
- **Phase 2-B**: Update workers to call `iter_*` variants and emit `data_point(dict)` signal per step.
- **Phase 2-C**: Update tabs to call `plot_widget.update_point()` on each `data_point` signal for true live plotting.
- **Phase 2-D**: Merge CLI and GUI config handling.
- **Phase 2-E**: Add a `SequenceTab` for chaining experiments.
