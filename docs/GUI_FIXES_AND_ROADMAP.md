# GUI Fixes and Roadmap — Copilot Implementation Guide

> **Purpose**: This document is a step-by-step implementation guide for fixing known bugs and extending the GUI.
> Each section lists the exact files to change, what is wrong, and what the correct implementation should be.
> Work through **Part 1** completely before starting **Part 2**. Do not implement **Part 3** until the hardware is tested.
>
> **Context files to read first**:
> - `gui/instruments/gsm20h10_panel.py`
> - `gui/instruments/e36300_panel.py`
> - `gui/instruments/workers.py`
> - `gui/widgets/connections_widget.py`
> - `gui/main_window.py`
> - `gui/workers.py`
> - `gui/tabs/rotation_sweep_tab.py`
> - `gui/tabs/iv_curve_tab.py`
> - `gui/tabs/tcspc_scan_tab.py`

---

# Part 1 — Immediate Fixes (Critical)

These bugs will cause the GUI to freeze or show wrong data. Fix all of these before running any hardware test.

---

## Fix 1-A: Add write workers to `gui/instruments/workers.py`

**Problem**: `gsm20h10_panel.py` and `e36300_panel.py` call instrument I/O directly on the main thread for Output ON, Output OFF, Apply, and Panic. This freezes the GUI window during VISA communication.

**File to modify**: `gui/instruments/workers.py`

**Action**: Add the following three new worker classes at the bottom of the file. Do not modify existing classes.

### Add `WriteCommandWorker`

A generic one-shot worker that opens an instrument, calls a single write method, then closes.

```python
class WriteCommandWorker(QThread):
    """One-shot worker for a single instrument write command.

    Parameters:
        cls: Instrument class to instantiate (units: none).
        cfg: Instrument config mapping (units: none).
        command: Callable accepting the open instrument instance (units: none).
    """

    success = Signal()           # emitted when command completes without exception
    error = Signal(str)          # emitted with error message on exception

    def __init__(self, cls: type, cfg: dict, command) -> None:
        super().__init__()
        self._cls = cls
        self._cfg = cfg
        self._command = command

    def run(self) -> None:
        """Execute command inside instrument context.

        Parameters:
            None (units: none).
        """
        try:
            with self._cls(self._cfg) as inst:
                self._command(inst)
            self.success.emit()
        except Exception as exc:
            self.error.emit(str(exc))
```

### Add `PanicWorker`

A fire-and-forget panic worker. Uses daemon `threading.Thread` so it does not block app exit.

```python
class PanicWorker(QThread):
    """Fire-and-forget panic-off worker.

    Connects to the instrument and calls output_off().
    Emits done(ok, message) on completion.

    Parameters:
        cls: Instrument class to instantiate (units: none).
        cfg: Instrument config mapping (units: none).
    """

    done = Signal(bool, str)  # (success, message)

    def __init__(self, cls: type, cfg: dict) -> None:
        super().__init__()
        self._cls = cls
        self._cfg = cfg

    def run(self) -> None:
        """Attempt output_off and emit result.

        Parameters:
            None (units: none).
        """
        try:
            with self._cls(self._cfg) as inst:
                if hasattr(inst, "output_off"):
                    inst.output_off()
            self.done.emit(True, "Output OFF")
        except Exception as exc:
            self.done.emit(False, str(exc))
```

---

## Fix 1-B: Rewrite blocking calls in `gui/instruments/gsm20h10_panel.py`

**Problem**: `_on_output_on`, `_on_output_off`, and `_on_panic` block the GUI thread.

**File to modify**: `gui/instruments/gsm20h10_panel.py`

**Action**: Add import for new workers. Replace the three blocking methods.

### Add import at top

```python
from gui.instruments.workers import ConnectWorker, ContinuousPollWorker, PanicWorker, SingleReadWorker, WriteCommandWorker
```

### Add worker reference in `__init__`

In `__init__`, add after the existing worker declarations:
```python
self._write_worker: WriteCommandWorker | None = None
self._panic_worker: PanicWorker | None = None
```

### Replace `_on_output_on`

```python
def _on_output_on(self) -> None:
    """Enable output in worker thread.

    Parameters:
        None (units: none).
    """
    setpoint = float(self._setpoint.value())
    compliance = float(self._compliance.value())

    def _cmd(inst) -> None:
        inst.set_source_voltage(setpoint, compliance)
        inst.output_on()

    self._output_on_btn.setEnabled(False)
    self._write_worker = WriteCommandWorker(GSM20H10, self._config, _cmd)
    self._write_worker.success.connect(lambda: self._status_label.setText("Status: ON"))
    self._write_worker.success.connect(lambda: self._output_on_btn.setEnabled(True))
    self._write_worker.error.connect(self._on_write_error)
    self._write_worker.error.connect(lambda: self._output_on_btn.setEnabled(True))
    self._write_worker.start()
```

### Replace `_on_output_off`

```python
def _on_output_off(self) -> None:
    """Disable output in worker thread.

    Parameters:
        None (units: none).
    """
    self._output_off_btn.setEnabled(False)
    self._write_worker = WriteCommandWorker(GSM20H10, self._config, lambda inst: inst.output_off())
    self._write_worker.success.connect(lambda: self._status_label.setText("Status: OFF"))
    self._write_worker.success.connect(lambda: self._output_off_btn.setEnabled(True))
    self._write_worker.error.connect(self._on_write_error)
    self._write_worker.error.connect(lambda: self._output_off_btn.setEnabled(True))
    self._write_worker.start()
```

### Replace `_on_panic`

```python
def _on_panic(self) -> None:
    """Fire-and-forget panic output off.

    Parameters:
        None (units: none).
    """
    self._on_stop_live()  # abort poll worker first (non-blocking)
    self._panic_worker = PanicWorker(GSM20H10, self._config)
    self._panic_worker.done.connect(
        lambda ok, msg: self._status_label.setText("Status: OFF" if ok else f"Panic FAIL: {msg}")
    )
    self._panic_worker.start()
```

### Add error handler method

```python
def _on_write_error(self, message: str) -> None:
    """Show write error in a dialog.

    Parameters:
        message: Error description (units: none).
    """
    QMessageBox.warning(self, "Command Failed", message)
```

---

## Fix 1-C: Rewrite blocking calls in `gui/instruments/e36300_panel.py`

**Problem**: `_on_apply`, `_on_output_on`, `_on_output_off`, and `_on_panic` block the GUI thread. Also `_on_read` fires on channel-change before connection.

**File to modify**: `gui/instruments/e36300_panel.py`

### Add import

```python
from gui.instruments.workers import ConnectWorker, PanicWorker, SingleReadWorker, WriteCommandWorker
```

### Add state and worker references in `__init__`

In `__init__`, after existing worker declarations:
```python
self._is_connected: bool = False
self._write_worker: WriteCommandWorker | None = None
self._panic_worker: PanicWorker | None = None
```

### Guard `_on_read` against unconnected state

```python
def _on_read(self) -> None:
    """Trigger single channel readback if connected.

    Parameters:
        None (units: none).
    """
    if not self._is_connected:
        return  # do NOT fire while not connected
    channel = self._channel_value()
    self._single_worker = SingleReadWorker(E36300Supply, self._config, channel=channel)
    self._single_worker.data.connect(self._on_data)
    self._single_worker.error.connect(lambda message: QMessageBox.warning(self, "Read Error", message))
    self._single_worker.start()
```

### Update `_on_connected` to track state

```python
def _on_connected(self, ok: bool, message: str) -> None:
    """Update connection state and label.

    Parameters:
        ok: Connection success (units: boolean).
        message: Instrument ID or error text (units: none).
    """
    self._is_connected = ok
    if ok:
        self._id_label.setText(f"ID: {message}")
    else:
        QMessageBox.warning(self, "Connect Failed", message)
```

### Update `_on_disconnect` to track state

```python
def _on_disconnect(self) -> None:
    """Clear connection state.

    Parameters:
        None (units: none).
    """
    self._is_connected = False
    self._id_label.setText("ID: (not connected)")
    self._status.setText("Status: OFF")
```

### Replace `_on_apply`

```python
def _on_apply(self) -> None:
    """Apply voltage and current limit in worker thread.

    Parameters:
        None (units: none).
    """
    channel = self._channel_value()
    voltage = float(self._voltage.value())
    current = float(self._current.value())

    def _cmd(inst) -> None:
        inst.set_voltage(channel, voltage)
        inst.set_current_limit(channel, current)

    self._apply_btn.setEnabled(False)
    self._write_worker = WriteCommandWorker(E36300Supply, self._config, _cmd)
    self._write_worker.success.connect(lambda: self._apply_btn.setEnabled(True))
    self._write_worker.error.connect(lambda msg: QMessageBox.warning(self, "Apply Failed", msg))
    self._write_worker.error.connect(lambda: self._apply_btn.setEnabled(True))
    self._write_worker.start()
```

### Replace `_on_output_on`

```python
def _on_output_on(self) -> None:
    """Enable channel output in worker thread.

    Parameters:
        None (units: none).
    """
    channel = self._channel_value()
    self._output_on_btn.setEnabled(False)
    self._write_worker = WriteCommandWorker(
        E36300Supply, self._config, lambda inst: inst.output_on(channel)
    )
    self._write_worker.success.connect(lambda: self._status.setText("Status: ON"))
    self._write_worker.success.connect(lambda: self._output_on_btn.setEnabled(True))
    self._write_worker.error.connect(lambda msg: QMessageBox.warning(self, "Output ON Failed", msg))
    self._write_worker.error.connect(lambda: self._output_on_btn.setEnabled(True))
    self._write_worker.start()
```

### Replace `_on_output_off`

```python
def _on_output_off(self) -> None:
    """Disable channel output in worker thread.

    Parameters:
        None (units: none).
    """
    channel = self._channel_value()
    self._output_off_btn.setEnabled(False)
    self._write_worker = WriteCommandWorker(
        E36300Supply, self._config, lambda inst: inst.output_off(channel)
    )
    self._write_worker.success.connect(lambda: self._status.setText("Status: OFF"))
    self._write_worker.success.connect(lambda: self._output_off_btn.setEnabled(True))
    self._write_worker.error.connect(lambda msg: QMessageBox.warning(self, "Output OFF Failed", msg))
    self._write_worker.error.connect(lambda: self._output_off_btn.setEnabled(True))
    self._write_worker.start()
```

### Replace `_on_panic`

```python
def _on_panic(self) -> None:
    """Fire-and-forget panic all outputs off.

    Parameters:
        None (units: none).
    """
    self._panic_worker = PanicWorker(E36300Supply, self._config)
    self._panic_worker.done.connect(
        lambda ok, msg: self._status.setText("Status: OFF" if ok else f"Panic FAIL: {msg}")
    )
    self._panic_worker.start()
```

---

## Fix 1-D: Fix config key mismatches in `gui/widgets/connections_widget.py`

**Problem**: `InstrumentRow._resource_summary()` uses wrong YAML key names so the address column always shows "N/A".

**File to modify**: `gui/widgets/connections_widget.py`

**Action**: Replace `_resource_summary` method body in `InstrumentRow`.

```python
def _resource_summary(self) -> str:
    """Build short resource/address summary from config.

    Parameters:
        None (units: none).
    """
    if self.key == "kdc101":
        serial = self.cfg.get("serial_number") or self.cfg.get("serial", "N/A")
        return f"Serial: {serial}"
    if self.key == "picoharp300":
        dll = self.cfg.get("dll_path") or self.cfg.get("phlib_path", "N/A")
        return f"DLL: {dll}"
    # VISA instruments: pm100d, e36300, gsm20h10
    resource = self.cfg.get("resource") or self.cfg.get("visa_resource", "N/A")
    return f"Resource: {resource}"
```

---

## Fix 1-E: Fix `closeEvent` blocking in `gui/main_window.py`

**Problem**: `closeEvent` opens two VISA connections on the main thread before closing, causing a "Not Responding" hang for 3–5 seconds on Windows.

**File to modify**: `gui/main_window.py`

**Action**: Add import and replace the `closeEvent` method.

### Add import at top

```python
import threading
```

### Replace `closeEvent`

```python
def closeEvent(self, event) -> None:
    """Warn user, run panic-off in background, then accept close.

    Parameters:
        event: Qt close event (units: none).
    """
    reply = QMessageBox.question(
        self,
        "Exit",
        "Attempt panic OFF for GSM20H10 and E36300 before exit?",
        QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
        QMessageBox.Yes,
    )
    if reply == QMessageBox.Cancel:
        event.ignore()
        return

    if reply == QMessageBox.Yes:
        # Run panic-off in background threads so the GUI does not freeze.
        # Daemon=True ensures threads do not prevent interpreter exit.
        gsm_cfg = dict(self._config.get("gsm20h10", {}))
        e36_cfg = dict(self._config.get("e36300", {}))

        def _panic_gsm() -> None:
            try:
                with GSM20H10(gsm_cfg) as smu:
                    smu.output_off()
            except Exception:
                pass

        def _panic_e36() -> None:
            try:
                with E36300Supply(e36_cfg) as supply:
                    supply.output_off()
            except Exception:
                pass

        t1 = threading.Thread(target=_panic_gsm, daemon=True)
        t2 = threading.Thread(target=_panic_e36, daemon=True)
        t1.start()
        t2.start()
        # Wait up to 3 seconds for both to finish; do not block forever.
        t1.join(timeout=3.0)
        t2.join(timeout=3.0)

    event.accept()
```

---

## Fix 1-F: Create `config/instruments_mac.yaml`

**Problem**: The app tries to load `config/instruments_mac.yaml` on macOS (set in `main_window.py`) but this file does not exist in the repo.

**File to create**: `config/instruments_mac.yaml`

```yaml
# Mac development config — all instruments in simulate mode.
# Use this on macOS where DLLs and VISA hardware are not available.
# On Windows, use config/instruments.yaml with simulate: false.

kdc101:
  simulate: true
  serial_number: "27000001"   # placeholder — not used in simulate mode
  kinesis_path: null

pm100d:
  simulate: true
  resource: "USB0::0x1313::0x8072::P0000001::INSTR"
  wavelength_nm: 532
  averaging_count: 10

e36300:
  simulate: true
  resource: "TCPIP0::192.168.1.100::inst0::INSTR"

gsm20h10:
  simulate: true
  resource: "GPIB0::5::INSTR"

picoharp300:
  simulate: true
  dll_path: null
```

---

## Fix 1-G: Smoke test to validate all fixes

**File to create or update**: `tests/test_gui_smoke.py`

If the file already exists, extend it. If not, create it from scratch.

```python
"""Smoke tests for GUI — run in simulate mode, no hardware required."""
from __future__ import annotations

import sys
import logging
from pathlib import Path

import pytest

# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication once for the entire test session."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture()
def mac_config(tmp_path) -> str:
    """Write a minimal simulate-mode config to a temp file."""
    import yaml
    cfg = {
        "pm100d":    {"simulate": True, "resource": "USB0::dummy", "wavelength_nm": 532, "averaging_count": 1},
        "e36300":    {"simulate": True, "resource": "TCPIP0::dummy"},
        "gsm20h10":  {"simulate": True, "resource": "GPIB0::5::INSTR"},
        "picoharp300": {"simulate": True, "dll_path": None},
        "kdc101":    {"simulate": True, "serial_number": "27000001", "kinesis_path": None},
    }
    p = tmp_path / "instruments_test.yaml"
    p.write_text(yaml.dump(cfg), encoding="utf-8")
    return str(p)


def test_log_viewer_appends(qapp):
    """Log viewer captures Python log messages."""
    from gui.widgets.log_viewer import LogViewerWidget
    widget = LogViewerWidget()
    widget.install_on_logger("smoke_test")
    logging.getLogger("smoke_test").info("hello from smoke test")
    # Process events to flush signals
    qapp.processEvents()
    assert "hello from smoke test" in widget._text.toPlainText()


def test_config_editor_loads(qapp, mac_config):
    """Config editor opens a YAML file without error."""
    from gui.widgets.config_editor import ConfigEditorWidget
    widget = ConfigEditorWidget(mac_config)
    assert widget is not None


def test_connections_widget_builds(qapp, mac_config):
    """Connections widget constructs rows for all available instruments."""
    from gui.widgets.connections_widget import ConnectionsWidget
    widget = ConnectionsWidget(mac_config)
    assert len(widget._rows) >= 3  # pm100d, e36300, gsm20h10 always present


def test_connections_resource_summary(qapp, mac_config):
    """Resource summary shows the correct address, not N/A."""
    from gui.widgets.connections_widget import ConnectionsWidget
    widget = ConnectionsWidget(mac_config)
    row = widget._rows["gsm20h10"]
    assert "N/A" not in row._summary.text()


def test_gsm_panel_builds(qapp):
    """GSM20H10 panel constructs in simulate mode."""
    from gui.instruments.gsm20h10_panel import GSM20H10Panel
    cfg = {"simulate": True, "resource": "GPIB0::5::INSTR"}
    panel = GSM20H10Panel(cfg)
    assert panel._panic_btn is not None


def test_e36300_panel_no_auto_read_on_init(qapp):
    """E36300 panel does not auto-read when channel changes before connect."""
    from gui.instruments.e36300_panel import E36300Panel
    cfg = {"simulate": True, "resource": "TCPIP0::dummy"}
    panel = E36300Panel(cfg)
    # Trigger a channel change — should not raise or launch worker
    panel._channel.setCurrentIndex(1)
    assert panel._single_worker is None or not panel._single_worker.isRunning()


def test_main_window_opens(qapp, mac_config):
    """MainWindow constructs without raising errors."""
    from gui.main_window import MainWindow
    window = MainWindow(config_path=mac_config)
    assert window is not None
    window.close()
```

**Acceptance**: `pytest tests/test_gui_smoke.py -v` passes with all 7 tests green on macOS.

---

# Part 2 — Moderate Fixes (Before Hardware Validation)

Complete these before plugging in real instruments on Windows.

---

## Fix 2-A: Replace `QThread.terminate()` with cooperative abort in experiment workers

**Problem**: All three experiment tabs call `self._worker.terminate()` on Abort, which kills the thread instantly without running `finally` blocks or closing instrument connections.

### Step 1 — Add `_BaseWorker` abort support in `gui/workers.py`

Add to `_BaseWorker.__init__`:
```python
import threading
self._abort_event = threading.Event()
```

Add method to `_BaseWorker`:
```python
def request_abort(self) -> None:
    """Signal the worker to stop at next checkpoint.

    Parameters:
        None (units: none).
    """
    self._abort_event.set()
```

### Step 2 — Thread the abort event to the experiment run functions

Each experiment worker's `run()` should pass the abort event into the underlying `run_*` function:

```python
# In RotationSweepWorker.run():
results = run_rotation_sweep(
    config_path=self._config_path,
    output_dir=self._output_dir,
    start_deg=self._start_deg,
    stop_deg=self._stop_deg,
    step_deg=self._step_deg,
    abort_event=self._abort_event,  # add this
)
```

The underlying `experiments/rotation_sweep.py` (and iv_curve, tcspc_scan) must then check `abort_event.is_set()` between steps and raise `RuntimeError("Aborted")` or return partial results early. See `Fix 2-B`.

### Step 3 — Update Abort buttons in all experiment tabs

In `rotation_sweep_tab.py`, `iv_curve_tab.py`, `tcspc_scan_tab.py`, replace:
```python
# OLD — dangerous
self._worker.terminate()
```
With:
```python
# NEW — cooperative
self._worker.request_abort()
self._status.setText("Aborting…")
# Do NOT re-enable Run button here; wait for worker.finished or worker.error signal
```

Make sure `_on_finished` and `_on_error` always re-enable the Run button (they already do).

---

## Fix 2-B: Add abort checkpoint support to experiment run functions

**Files to modify**: `experiments/rotation_sweep.py`, `experiments/iv_curve.py`, `experiments/tcspc_scan.py`

For each experiment, update the function signature to accept an optional `abort_event`:

```python
import threading

def run_rotation_sweep(
    config_path: str,
    output_dir: str,
    start_deg: float,
    stop_deg: float,
    step_deg: float,
    abort_event: threading.Event | None = None,  # add this
) -> list[dict]:
```

Inside the measurement loop, add a check at the top of each iteration:
```python
for angle in angles:
    if abort_event is not None and abort_event.is_set():
        logger.warning("Sweep aborted at angle=%.2f deg", angle)
        break
    # ... existing measurement code ...
```

Apply the same pattern to `run_iv_curve` and `run_tcspc_scan`.

**Acceptance**: Clicking Abort during a sweep stops at the next angle step and returns partial results to the plot, instead of hanging or leaving the instrument in an unknown state.

---

## Fix 2-C: Add connection state tracking to `GSM20H10Panel`

**Problem**: The GSM panel does not track `_is_connected`. The status label can show "Status: ON" while disconnected, and the panel does not know to block `Read Once` when not connected.

**File to modify**: `gui/instruments/gsm20h10_panel.py`

### Add state tracking in `__init__`

```python
self._is_connected: bool = False
```

### Update `_on_connected`

```python
def _on_connected(self, ok: bool, message: str) -> None:
    """Update connection state and ID label.

    Parameters:
        ok: Connection success (units: boolean).
        message: Instrument ID or error text (units: none).
    """
    self._is_connected = ok
    if ok:
        self._id_label.setText(f"ID: {message}")
    else:
        QMessageBox.warning(self, "Connect Failed", message)
```

### Update `_on_disconnect`

```python
def _on_disconnect(self) -> None:
    """Clear connection state and stop live polling.

    Parameters:
        None (units: none).
    """
    self._on_stop_live()
    self._is_connected = False
    self._id_label.setText("ID: (not connected)")
    self._status_label.setText("Status: OFF")
```

### Guard `_on_read_once` and `_on_output_on/off`

Add at the top of `_on_read_once`, `_on_output_on`, `_on_output_off`, `_on_start_live`:
```python
if not self._is_connected:
    QMessageBox.information(self, "Not Connected", "Connect to the instrument first.")
    return
```

---

## Fix 2-D: Timestamped CSV for GSM20H10 live log

**Problem**: `_append_live_csv` writes to a fixed file `output/gsm20h10_live.csv` that accumulates across all sessions. On Windows, this path is relative to the working directory, which may not be the repo root.

**File to modify**: `gui/instruments/gsm20h10_panel.py`

### Add CSV file path attribute set at `_on_start_live`

In `__init__`:
```python
self._live_csv_path: Path | None = None
```

In `_on_start_live` (before starting the worker):
```python
if self._log_csv.isChecked():
    from datetime import datetime
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    self._live_csv_path = Path("output") / f"gsm20h10_live_{stamp}.csv"
    self._live_csv_path.parent.mkdir(parents=True, exist_ok=True)
else:
    self._live_csv_path = None
```

Update `_append_live_csv` to accept and use this path:
```python
def _append_live_csv(self, voltage: float, current: float, power: float) -> None:
    """Append a line to live CSV log.

    Parameters:
        voltage: Measured voltage (units: V).
        current: Measured current (units: A).
        power: Measured power (units: W).
    """
    if self._live_csv_path is None:
        return
    exists = self._live_csv_path.exists()
    with self._live_csv_path.open("a", encoding="utf-8") as handle:
        if not exists:
            handle.write("timestamp_s,voltage_V,current_A,power_W\n")
        handle.write(f"{time.time():.6f},{voltage:.6f},{current:.6f},{power:.6f}\n")
```

---

## Fix 2-E: Add `gui_main.py` entry point at repo root (if missing)

**Check first**: If `gui_main.py` already exists at repo root, skip this fix.

**File to create**: `gui_main.py` (repo root)

```python
"""GUI entry point for lab instrument control."""
from __future__ import annotations

import sys
from pathlib import Path

# Add repo root to sys.path so 'gui', 'instruments', 'experiments' are importable
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    import pyqtgraph as pg
    pg.setConfigOption("useOpenGL", False)  # safer default for Windows VMs
    pg.setConfigOption("antialias", True)
except ImportError:
    pass

from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow


def main() -> None:
    """Launch the GUI application.

    Parameters:
        None (units: none).
    """
    app = QApplication(sys.argv)
    app.setApplicationName("Lab Instrument Control")

    # Allow override via command-line: python gui_main.py path/to/config.yaml
    if len(sys.argv) > 1 and Path(sys.argv[1]).suffix in (".yaml", ".yml"):
        config_path = sys.argv[1]
    else:
        config_path = None  # MainWindow will pick platform default

    window = MainWindow(config_path=config_path)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

---

# Part 3 — Roadmap (Phase 2, Do Not Implement Yet)

Implement Part 3 only after the hardware has been validated on Windows with real instruments.

---

## Plan 3-A: Live per-step plotting for experiments

**Goal**: Show each data point on the plot as it arrives, instead of plotting everything after the experiment finishes.

### Step 1 — Add iterator variants to `experiments/`

For each experiment, add an `iter_*` function that `yield`s one `dict` per step:

```python
# experiments/rotation_sweep.py
def iter_rotation_sweep(
    config_path: str,
    output_dir: str,
    start_deg: float,
    stop_deg: float,
    step_deg: float,
    abort_event: threading.Event | None = None,
) -> Iterator[dict]:
    """Yield one measurement dict per angle step."""
    for angle in angles:
        if abort_event and abort_event.is_set():
            return
        # ... move stage, read power ...
        yield {"angle_deg": angle, "power_W": power, ...}
```

Repeat for `iter_iv_curve` and `iter_tcspc_scan`.

### Step 2 — Add live-yield workers in `gui/workers.py`

```python
class RotationSweepLiveWorker(_BaseWorker):
    data_point = Signal(dict)  # emitted once per step

    def run(self) -> None:
        ...
        results = []
        for point in iter_rotation_sweep(..., abort_event=self._abort_event):
            results.append(point)
            self.data_point.emit(point)               # per-step signal
            self.progress.emit(len(results), total)
        self.finished.emit(results)
```

### Step 3 — Update experiment tabs to connect `data_point`

```python
self._worker.data_point.connect(self._on_data_point)

def _on_data_point(self, point: dict) -> None:
    self._angles.append(point["angle_deg"])
    self._powers.append(point["power_W"])
    self._curve.setData(self._angles, self._powers)
```

---

## Plan 3-B: TCSPC angle histogram viewer

**Goal**: Show per-angle histogram bar charts for TCSPC data.

The `TCSPCScanTab` currently only plots summary data. Extend it with:
- An angle selector `QComboBox` populated after the scan
- A second `pg.PlotWidget` showing the photon-count histogram for the selected angle
- Data sourced from the TCSPC result dict `{"angle_deg": ..., "histogram": [...], "time_bins_ns": [...]}`

---

## Plan 3-C: Sequence tab for chaining experiments

**Goal**: Run Rotation Sweep → I-V Curve → TCSPC Scan in sequence without manual intervention.

Create `gui/tabs/sequence_tab.py`:
- Checklist of experiments to run (checkboxes: Rotation Sweep, I-V Curve, TCSPC Scan)
- [Run Sequence] button
- Per-experiment status row (queued / running / done / error)
- Overall progress bar
- Uses `RotationSweepWorker`, `IVCurveWorker`, `TCSPCScanWorker` chained via `finished` signal

---

## Plan 3-D: Config validation on load

**Goal**: When a YAML config is loaded or saved, validate all required keys are present and show a structured warning if not.

Create `config/schema.py` (or use `pydantic` / `cerberus`):
```python
REQUIRED_KEYS = {
    "kdc101":      ["simulate", "serial_number"],
    "pm100d":      ["simulate", "resource", "wavelength_nm"],
    "e36300":      ["simulate", "resource"],
    "gsm20h10":    ["simulate", "resource"],
    "picoharp300": ["simulate"],
}
```

In `ConfigEditorWidget.save()`, run validation and emit `config_saved` only if valid. Show per-key errors inline in the editor.

---

## Plan 3-E: GSM20H10 current-source mode

**Goal**: Add current-source mode to the GSM panel (currently only voltage-source is implemented).

In `gsm20h10_panel.py`:
- Add mode radio buttons: `[● Voltage]  [ Current]`
- Mode buttons only enabled when output is OFF
- When current-source selected: `Setpoint` label changes to "Setpoint (A)", range changes to `[-1.05, 1.05]`; compliance label changes to "Compliance (V)"
- Call `inst.set_source_current(setpoint, compliance)` instead of `set_source_voltage`

---

## Part 3 Summary Table

| Plan | Priority | Effort | Requires |
|---|---|---|---|
| 3-A Live plotting | High | Medium | iter_* functions in experiments/ |
| 3-B TCSPC histogram | Medium | Small | Real TCSPC data format confirmed |
| 3-C Sequence tab | Low | Medium | All 3 experiments tested on hardware |
| 3-D Config validation | Medium | Small | None |
| 3-E GSM current mode | Medium | Small | GSM hardware tested |

---

# Acceptance Criteria Summary

## After Part 1 (Immediate fixes)

- [ ] `pytest tests/test_gui_smoke.py -v` — all 7 tests pass on Mac
- [ ] `python gui_main.py` opens without errors on Mac
- [ ] Connections tab shows real address (not "N/A") for all instruments
- [ ] Clicking "Output ON" on GSM panel does NOT freeze the window
- [ ] Clicking "Panic" fires instantly without freezing
- [ ] Switching E36300 channel on first load does NOT pop an error dialog

## After Part 2 (Before hardware)

- [ ] Clicking Abort during a sweep stops gracefully at the next step
- [ ] Partial sweep results are shown on the plot after abort
- [ ] GSM status label resets to "Status: OFF" after disconnect
- [ ] Live CSV creates a new timestamped file each session
- [ ] `python gui_main.py path/to/config.yaml` loads the specified config

## After Part 3 (Phase 2)

- [ ] Rotation sweep plot updates one point at a time during the sweep
- [ ] TCSPC tab shows histogram for each measured angle
- [ ] Sequence tab chains experiments automatically
