# GUI Design Specification — Lab Instrument Control

> **Scope**: This document defines the architecture and constraints for adding a graphical user interface to `lab_control`. The GUI lives in a new `gui/` package and `gui_main.py` entry point. **All existing files** (`instruments/`, `experiments/`, `utils/`, `config/`, `main.py`) are left untouched. The GUI wraps the existing code; it does not replace it.

---

## 1. Technology Choices

| Component | Choice | Rationale |
|---|---|---|
| UI framework | **PySide6** | LGPL license (compatible with this repo's MIT). Same Qt6 API as PyQt6 but no GPL implications. |
| Live plotting | **pyqtgraph** | GPU-accelerated, native Qt widget, zero-copy numpy array updates. Ideal for live TCSPC histogram and sweep curves. |
| Threading | **`QThread` + `Signal`** | Keeps instrument I/O off the main thread; Qt signal/slot safely marshals data back to the UI thread. |
| Config editing | **`QPlainTextEdit`** (raw YAML) | Simple, no external deps, matches the repo's config-driven philosophy. |

---

## 2. New Files to Create

```
lab_control/
├── gui/                          # NEW — entire GUI package
│   ├── __init__.py               # empty
│   ├── workers.py                # QThread subclasses, one per experiment
│   ├── widgets/
│   │   ├── __init__.py           # empty
│   │   ├── status_bar.py         # InstrumentStatusBar widget
│   │   ├── log_viewer.py         # LogViewerWidget (QTextEdit sink)
│   │   └── config_editor.py      # ConfigEditorWidget (YAML viewer/editor)
│   └── tabs/
│       ├── __init__.py           # empty
│       ├── rotation_sweep_tab.py # RotationSweepTab
│       ├── iv_curve_tab.py       # IVCurveTab
│       └── tcspc_scan_tab.py     # TCSPCScanTab
├── gui_main.py                   # NEW — GUI entry point (mirrors main.py)
└── docs/
    ├── GUI_SPEC.md               # this file
    └── GUI_TASKS.md              # Copilot task list
```

**Do NOT modify**: `main.py`, `instruments/`, `experiments/`, `utils/`, `config/`, `tests/`.

---

## 3. Main Window Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  Lab Instrument Control  v0.1          [Load Config ▼]          │
├──────────[InstrumentStatusBar]──────────────────────────────────┤
│  KDC101 ●  PM100D ●  E36300 ●  GSM20H10 ●  PicoHarp300 ●      │
│                                         [Check All]  [Discover] │
├─────────────────────────────────────────────────────────────────┤
│  [Rotation Sweep] [I-V Curve] [TCSPC Scan] [Config] [Log]      │
│ ┌───────────────────────────────────────────────────────────┐   │
│ │                     <Tab Content>                         │   │
│ │  [Parameters Panel]        [Live Plot / pyqtgraph]        │   │
│ │                                                           │   │
│ │  [Run] [Abort]  Progress: ████████░░ 80%  ETA: 12s       │   │
│ └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Widget Descriptions

### 4.1 InstrumentStatusBar

A horizontal row of colored indicator dots (●) and labels, one per instrument. Green = connected/OK, red = error/disconnected, grey = not yet checked.

- Uses a `QTimer` polling every **5 seconds** when the window is idle (no experiment running).
- Polling calls `instrument.is_connected` in a lightweight `QThread` to avoid blocking the UI.
- Instruments polled: `KDC101Stage`, `PM100D`, `E36300Supply`, `GSM20H10`, `PicoHarp300`.
- Each indicator is a `QLabel` with a colored Unicode circle (`●`) set via stylesheet.
- Colour mapping: `"green"` → connected, `"red"` → error, `"#888888"` → unknown.
- The **[Check All]** button triggers an immediate poll of all instruments.
- The **[Discover]** button runs `main.discover()` in a worker and streams output to the Log tab.

### 4.2 LogViewerWidget

A `QPlainTextEdit` (read-only) that acts as a Python `logging.Handler`. Every `logging` call anywhere in the application (from `utils/logger.py` loggers) is appended to this widget in the GUI thread via a `Signal(str)`.

- Max line buffer: 2000 lines (auto-scroll to bottom).
- Log level colours: DEBUG = grey, INFO = white, WARNING = orange, ERROR = red.
- A **[Clear]** button clears the display.
- A **[Save Log]** button opens a `QFileDialog` and writes the buffer to a `.log` file.

### 4.3 ConfigEditorWidget

A `QPlainTextEdit` pre-loaded with the raw text of `config/instruments.yaml`.

- A **[Load]** button opens a `QFileDialog` to pick a different YAML file.
- A **[Save]** button writes the current text back to the loaded file path.
- On save, the widget validates YAML (`yaml.safe_load`); shows a red status label on parse error.
- The currently loaded config path is shown as a read-only `QLineEdit` above the editor.
- This widget does **not** hot-reload running experiments; it only writes to disk.

### 4.4 Experiment Tabs (common structure)

All three experiment tabs share this layout pattern:

```
┌── Left Panel (fixed 260px) ──┬── Right Panel (expandable) ────┐
│  [Parameter Form]            │  [pyqtgraph PlotWidget]        │
│                              │                                │
│  [Run]  [Abort]              │                                │
│  QProgressBar                │                                │
│  Status label                │                                │
│  Output dir label            │                                │
└──────────────────────────────┴────────────────────────────────┘
```

- Parameter fields are `QDoubleSpinBox` / `QSpinBox` / `QLineEdit` as appropriate.
- **[Run]** is disabled while a worker is running. **[Abort]** is only enabled while running.
- `QProgressBar` shows `0–100%` based on step index from the worker.
- Status label shows the last emitted log message from the worker.
- Output dir label shows the timestamped output path after a run completes.

---

## 5. Phase 1 — "Paired" Approach (Implement First)

Phase 1 keeps the existing blocking `run_*` functions **completely unchanged**. Each function runs inside a `QThread`. Live feedback comes from a `QueueHandler` that intercepts log messages, not from per-step callbacks.

**Data flow:**
```
QThread.run()
  └─ calls existing run_rotation_sweep() / run_iv_curve() / run_tcspc_scan()
       └─ emits log records via Python logging
            └─ GuiLogHandler.emit() → Signal(str) → LogViewerWidget.append()
```

After the run function returns, the worker emits a `finished(results: list[dict])` signal. The tab then:
1. Redraws the pyqtgraph plot from the full `results` list.
2. Displays the output directory path.
3. Re-enables [Run], disables [Abort].

**This means Phase 1 plots are post-run, not live.** Live plotting is Phase 2.

---

## 6. Phase 2 — Live Plotting (Future, Do Not Implement Yet)

Phase 2 adds iterator variants to each experiment:

```python
# experiments/rotation_sweep.py — NEW function (do not add yet)
def iter_rotation_sweep(...) -> Iterator[dict]:
    """Yield one result dict per angle step for live GUI consumption."""
    ...
```

Workers will be updated to call `iter_*` and emit `data_point(dict)` per step. Tabs will call `plot_widget.update_point()` on each signal. This is described in `GUI_TASKS.md` as a future task.

---

## 7. Design Constraints

1. **SI units everywhere** — same as the rest of the repo. Angles in deg, power in W, voltage in V, current in A, time in s. Label every input field with its unit.
2. **No `print()` calls** — use `logging` only. The GUI captures the logging stream; `print()` is invisible.
3. **Config-driven** — the GUI reads `config/instruments.yaml` on startup. The config path is shown in the header and editable in the Config tab.
4. **Simulate mode respected** — if `simulate: true` in config, the status bar shows instruments as "SIMULATED" (grey dot, label text `SIM`), not green.
5. **Thread safety** — all instrument calls happen in `QThread`. No instrument objects are created on the main thread.
6. **Context managers** — instruments are opened via `with` blocks inside `QThread.run()`, exactly as the CLI does.
7. **Abort** — the `QThread` sets a `threading.Event` (`_abort_event`). Each worker checks this event between steps. On abort, the worker cleans up (moves stage to 0° if applicable, turns off SMU output) before emitting `finished`.
8. **Output directory** — use the same `output/YYYYMMDD_HHMMSS/` scheme as the existing experiments. After a run, display the path as a clickable `QLabel` that opens the folder in the OS file browser.
9. **No extra dependencies beyond PySide6 and pyqtgraph** — do not introduce other UI-related packages.

---

## 8. New Dependencies

Add to `requirements.txt`:

```
PySide6>=6.6
pyqtgraph>=0.13
```

---

## 9. Entry Point

`gui_main.py` (repo root, alongside `main.py`):

```python
"""GUI entry point for lab instrument control."""
import sys
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow  # to be implemented

def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Lab Instrument Control")
    window = MainWindow(config_path="config/instruments.yaml")
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
```

Add a corresponding entry in `pyproject.toml`:
```toml
[project.scripts]
lab-gui = "gui_main:main"
```

---

## 10. File Naming and Style

- All new files follow the existing repo style: `snake_case` modules, Google-style docstrings, type annotations, `from __future__ import annotations`.
- Every class and public method has a docstring with a `Parameters:` block using the `(units: ...)` convention already used in `instruments/base.py`.
- Max line length: 100 characters (match existing files).
