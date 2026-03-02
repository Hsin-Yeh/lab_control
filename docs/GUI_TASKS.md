# GUI Implementation Tasks — Lab Instrument Control (Updated Plan)

> **Read this first**: This task list supersedes the original assumptions about per-instrument GUI panels.
> We will keep the existing "Experiments GUI wraps the existing `run_*` functions" approach.
> We will add:
> - A **Connections** tab to test all instruments individually (read-only, safe).
> - An **Instruments** tab with **manual panels ONLY** for:
>   - **GSM20H10 SMU**
>   - **E36300 power supply**
> We will NOT build full manual control panels for KDC101, PM100D, PicoHarp300 (connections test only).
>
> **🍎 Mac Development / 🖥️ Windows Production**: Read `GUI_CROSS_PLATFORM.md` for Mac vs Windows setup.
> Development and dry testing will happen on **macOS** with all instruments in `simulate: true` mode.
> Production deployment will be on **Windows** with real hardware.

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

## Task 0 — Package skeleton + cross-platform setup

### Create empty files
Create (module docstring + `from __future__ import annotations`):
- `gui/__init__.py`
- `gui/widgets/__init__.py`
- `gui/tabs/__init__.py`
- `gui/instruments/__init__.py`

### Add platform-specific imports pattern
In `gui/__init__.py`, add:
```python
"""GUI package for lab instrument control.

Cross-platform notes:
- macOS: KDC101 and PicoHarp300 imports will fail (DLLs not available). This is expected.
- Windows: All instruments supported.
- Always use pathlib.Path for file paths, never hardcode C:\\ or /usr/...
"""
from __future__ import annotations

# Platform-specific instrument imports with graceful fallback
try:
    from instruments.kdc101 import KDC101Stage
    KDC101_AVAILABLE = True
except (ImportError, OSError):
    KDC101Stage = None
    KDC101_AVAILABLE = False

try:
    from instruments.picoharp300 import PicoHarp300
    PICOHARP_AVAILABLE = True
except (ImportError, OSError):
    PicoHarp300 = None
    PICOHARP_AVAILABLE = False

# These should always import (no platform-specific deps)
from instruments.pm100d import PM100D
from instruments.e36300 import E36300Supply
from instruments.gsm20h10 import GSM20H10
```

### Acceptance (Mac)
- Files created, `import gui` does not crash on Mac (KDC101/PicoHarp imports fail gracefully)

---

## Task 1 — Log viewer

Create `gui/widgets/log_viewer.py`:
- `SignalRelay(QObject)` with `message = Signal(str, int)`  # text, levelno
- `GuiLogHandler(logging.Handler)` that formats records and emits relay.message
- `LogViewerWidget(QWidget)` with:
  - read-only `QPlainTextEdit` (monospace), max 2000 lines
  - buttons: Clear, Save Log…
  - method `append_message(text: str, levelno: int)`
  - method `install_on_logger(logger_name: str)` (attach handler to named logger and root)

### Cross-platform notes
- **Save Log** button: Use `Path` for file paths, test on both Mac and Windows

### Acceptance (Mac)
- logging to `logging.getLogger("rotation_sweep").info("hello")` shows in widget
- Save Log writes to user-selected path

---

## Task 2 — Config editor

Create `gui/widgets/config_editor.py`:
- `ConfigEditorWidget(QWidget)`:
  - shows current YAML path (read-only QLineEdit)
  - Load…, Save
  - validates YAML on save (`yaml.safe_load`)
  - emits `config_saved = Signal(str)` when saved

### Cross-platform notes
- Use `Path` for all file operations
- Display path with forward slashes for consistency (use `path.as_posix()`)

### Acceptance (Mac)
- YAML syntax errors are shown; valid YAML saves and emits signal
- Paths display correctly with forward slashes

---

## Task 3 — Connections tab (NEW, priority)

### Goal
Provide a structured, **non-destructive** connection test for each instrument, individually and with [Test All].

### Create file
- `gui/widgets/connections_widget.py`

### Instruments to test
Build instrument list dynamically based on availability:
```python
from gui import KDC101_AVAILABLE, PICOHARP_AVAILABLE, KDC101Stage, PicoHarp300, PM100D, E36300Supply, GSM20H10

INSTRUMENTS = [
    ("pm100d", "PM100D", PM100D),
    ("e36300", "E36300", E36300Supply),
    ("gsm20h10", "GSM20H10", GSM20H10),
]

if KDC101_AVAILABLE:
    INSTRUMENTS.insert(0, ("kdc101", "KDC101 Stage", KDC101Stage))
if PICOHARP_AVAILABLE:
    INSTRUMENTS.append(("picoharp300", "PicoHarp300", PicoHarp300))
```

### UI (per instrument row)
- Dot indicator: grey (not tested), orange (running or SIMULATED), green (PASS), red (FAIL)
- Labels:
  - instrument name
  - address/resource summary from YAML
- Buttons:
  - [Test] per row
  - [Clear] per row (reset status to grey)
- Bottom:
  - [Test All] button

### Worker
Create `ConnectionTestWorker(QThread)`:
- Signal: `result = Signal(str, bool, str)`  # key, ok, detail
- `run()`:
  - If `simulate: true`, do NOT connect; emit ok with detail "SIMULATED — no hardware test"
  - Else `with cls(cfg) as inst:` then read `inst.instrument_id`
  - Do **read-only** commands only
  - emit PASS with ID string, or FAIL with exception text

### Cross-platform notes
- On Mac: All instruments show "SIMULATED" (orange) if `simulate: true`
- If instrument class is None (e.g., KDC101 on Mac), skip that row or show "Not available on this platform"

### Acceptance (Mac)
- All available instruments show "SIMULATED" in orange
- KDC101/PicoHarp300 either hidden or show "Not available" if imports failed

---

## Task 4 — Experiment workers (keep "wrap run_*")

Create `gui/workers.py`:
- `_BaseWorker(QThread)` with signals:
  - `log_message = Signal(str, int)`
  - `progress = Signal(int, int)`
  - `status_text = Signal(str)`
  - `finished = Signal(list)`      # list[dict]
  - `error = Signal(str)`
- Implement:
  - `RotationSweepWorker` calls `experiments.rotation_sweep.run_rotation_sweep(...)`
  - `IVCurveWorker` calls `experiments.iv_curve.run_iv_curve(...)`
  - `TCSPCScanWorker` calls `experiments.tcspc_scan.run_tcspc_scan(...)`
- Attach `GuiLogHandler` to experiment loggers

### Cross-platform notes
- Output directory: use `Path(output_dir)` to handle path separators
- Workers must create instrument objects **inside `run()`**, not in `__init__`

### Acceptance (Mac)
- Each worker `.start()` runs in simulate mode and emits `finished(results)`
- Output written to `output/YYYYMMDD_HHMMSS/` with proper path separators

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

### Parameter forms and plot types

#### RotationSweepTab
- Parameters: start_deg, stop_deg, step_deg, output_dir
- Plot: angle vs power (W) line, optional dBm secondary axis

#### IVCurveTab
- Parameters: v_start, v_stop, v_step, i_limit, output_dir
- Plot: voltage vs current scatter+line

#### TCSPCScanTab
- Parameters: angles (space-separated), acq_time_ms, output_dir
- Plot: histogram bar chart (if data available)

### Cross-platform notes
- Output dir label: clickable to open folder in OS file browser
- Add helper function:
```python
import sys
import subprocess
from pathlib import Path

def open_folder(path: Path) -> None:
    """Open folder in OS file browser (cross-platform)."""
    if sys.platform == "darwin":  # macOS
        subprocess.run(["open", str(path)])
    elif sys.platform == "win32":  # Windows
        subprocess.run(["explorer", str(path)])
    else:  # Linux
        subprocess.run(["xdg-open", str(path)])
```

### Acceptance (Mac)
- Running each tab works in simulate mode
- Clicking output dir opens Finder (Mac) / Explorer (Windows)

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
- Never change output state in polling worker
- Panic OFF is a separate immediate action

### Acceptance (Mac)
- Workers run with simulate mode, emit stub data

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

### Cross-platform notes
- CSV log path: use `Path` for cross-platform compatibility

### Acceptance (Mac)
- In simulate mode: values update; controls behave (disable/enable rules)
- Chart updates smoothly (test pyqtgraph rendering on Mac)

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

### Acceptance (Mac)
- In simulate mode: readback works; channel switching works

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

### Cross-platform notes
- Default config path: use platform detection or command-line arg
```python
import sys
from pathlib import Path

if sys.platform == "darwin":
    DEFAULT_CONFIG = Path("config") / "instruments_mac.yaml"
else:
    DEFAULT_CONFIG = Path("config") / "instruments.yaml"
```

### Acceptance (Mac)
- App starts, switching tabs works, and config path propagation works

---

## Task 10 — Entry point

Create `gui_main.py` at repo root:

```python
"""GUI entry point for lab instrument control."""
from __future__ import annotations

import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow

# Optional: pyqtgraph OpenGL fallback for some Windows VMs
try:
    import pyqtgraph as pg
    pg.setConfigOption('useOpenGL', False)  # Safer default
    pg.setConfigOption('antialias', True)
except ImportError:
    pass


def main() -> None:
    """Launch the GUI application.

    Parameters:
        None (units: none).
    """
    # Platform-specific default config
    if sys.platform == "darwin":
        default_config = Path("config") / "instruments_mac.yaml"
    else:
        default_config = Path("config") / "instruments.yaml"
    
    app = QApplication(sys.argv)
    app.setApplicationName("Lab Instrument Control")
    window = MainWindow(config_path=str(default_config))
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

### Acceptance (Mac)
- `python gui_main.py` opens the window with no errors (works in simulate mode)
- Loads `config/instruments_mac.yaml` automatically on Mac

---

## Task 11 — Dependencies / scripts

Update:
- `requirements.txt` add:
  - `PySide6>=6.6`
  - `pyqtgraph>=0.13`
- `pyproject.toml` add script:
  - `lab-gui = "gui_main:main"`

### Create Mac config template
Add `config/instruments_mac.yaml` with all instruments in simulate mode:
```yaml
kdc101:
  simulate: true
  serial_number: "27xxxxxx"
  kinesis_path: null

pm100d:
  simulate: true
  resource: "USB0::0x1313::0x8072::P0012345::INSTR"
  wavelength_nm: 532
  averaging_count: 10

e36300:
  simulate: true
  resource: "TCPIP0::192.168.1.100::INSTR"

gsm20h10:
  simulate: true
  resource: "GPIB0::5::INSTR"

picoharp300:
  simulate: true
  dll_path: null
```

### Acceptance (Mac)
- `pip install -e .` succeeds
- `lab-gui` command launches GUI

---

## Task 12 — Smoke tests

Create/Update `tests/test_gui_smoke.py`:
- window opens
- log viewer appends
- config editor loads
- connections widget constructs without hardware

### Cross-platform acceptance
- **Mac**: `pytest tests/test_gui_smoke.py -v` passes with simulate mode
- **Windows**: Same tests pass (run after deployment)

---

## Pre-Windows Deployment Checklist

Before moving code to Windows production system:

### Mac Development Complete
- [ ] All 12 tasks implemented
- [ ] `pytest tests/test_gui_smoke.py -v` passes on Mac
- [ ] All experiment tabs run and plot fake data
- [ ] No hardcoded paths (`C:\\` or `/Users/...`) in source code
- [ ] All file operations use `pathlib.Path`
- [ ] No `print()` statements (logging only)

### Windows Deployment Steps (see `GUI_CROSS_PLATFORM.md`)
1. Install drivers (NI-VISA, Kinesis, PHLib)
2. Run `python main.py discover` to find resource strings
3. Update `config/instruments.yaml` with real addresses
4. Set `simulate: false` for connected instruments
5. Test ConnectionsWidget [Test All] → all green
6. Test each instrument panel individually
7. Run one full experiment end-to-end

---

## Phase 2 Tasks (Future — Do Not Implement Now)

These tasks are for future reference only:

- **Phase 2-A**: Add `iter_rotation_sweep()`, `iter_iv_curve()`, `iter_tcspc_scan()` iterator variants to `experiments/` that `yield` one `dict` per step.
- **Phase 2-B**: Update workers to call `iter_*` variants and emit `data_point(dict)` signal per step.
- **Phase 2-C**: Update tabs to call `plot_widget.update_point()` on each `data_point` signal for true live plotting.
- **Phase 2-D**: Merge CLI and GUI config handling.
- **Phase 2-E**: Add a `SequenceTab` for chaining experiments.
