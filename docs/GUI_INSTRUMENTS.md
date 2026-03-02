# Instrument Panels & Connection Testing

> This document specifies the "Instruments" and "Connections" tabs.
> Read `GUI_SPEC.md` first for overall architecture and Phase 1 constraints.
> All instrument I/O must run in `QThread`. No blocking calls on the main thread.

---

## 1. Tab Map

MainWindow QTabWidget:
- **Experiments** → sub-tabs: Rotation Sweep | I-V Curve | TCSPC Scan
- **Instruments** → sub-tabs: GSM20H10 | E36300
- **Connections** → single widget (all 5 instruments)
- **Config** → YAML editor
- **Log** → log viewer

KDC101, PM100D, and PicoHarp300 have NO manual control panels — only connection tests in the Connections tab.

---

## 2. ConnectionsWidget Specification

### Layout (per instrument row)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ● KDC101 Stage      Address: 27xxxxxx (from config)   [Test]  [Clear]  │
│    ✓ PASS  —  PRM1Z8 SN:27xxxxxx  Firmware: 1.2.3                       │
├─────────────────────────────────────────────────────────────────────────┤
│  ● PM100D            Address: USB0::0x1313::...        [Test]  [Clear]  │
│    ✓ PASS  —  Thorlabs PM100D  SN:P123456  FW:1.4.0                     │
├─────────────────────────────────────────────────────────────────────────┤
│  ● E36300            Address: TCPIP0::...              [Test]  [Clear]  │
│    ✗ FAIL  —  Timeout after 2s                                           │
├─────────────────────────────────────────────────────────────────────────┤
│  ● GSM20H10          Address: GPIB0::...               [Test]  [Clear]  │
│    ✓ PASS  —  GW INSTEK,GSM-20H10,...                                   │
├─────────────────────────────────────────────────────────────────────────┤
│  ● PicoHarp300       DLL: C:\Program Files\...         [Test]  [Clear]  │
│    ✓ PASS  —  PicoHarp 300  HW Serial: 1044xxx                           │
└─────────────────────────────────────────────────────────────────────────┘
                                                         [Test All]
```

### Dot colors
- Grey (`#444444`): not tested
- Orange (`#ff8800`): running or simulated
- Green (`#44cc44`): PASS
- Red (`#cc4444`): FAIL

### Safe test actions (read-only, never enable outputs)

| Instrument | Actions |
|---|---|
| KDC101 | Connect → read `instrument_id` → disconnect |
| PM100D | Connect → `*IDN?` → read 1 power sample → disconnect |
| E36300 | Connect → `*IDN?` → read output state (do NOT enable) → disconnect |
| GSM20H10 | Connect → `*IDN?` → confirm output OFF (do NOT enable) → disconnect |
| PicoHarp300 | Open → read HW serial + model → close |

### Class outline

```python
class ConnectionsWidget(QWidget):
    def __init__(self, config_path: str, parent: QWidget | None = None) -> None: ...
    def set_config(self, config_path: str) -> None: ...  # reload on config change
    def _on_test_all(self) -> None: ...

class InstrumentRow(QWidget):
    def __init__(self, key: str, label: str, cls: type, cfg: dict) -> None: ...
    def run_test(self) -> None: ...
    def _update_status(self, ok: bool, detail: str) -> None: ...

class ConnectionTestWorker(QThread):
    result = Signal(bool, str)  # (ok, detail_message)
    def __init__(self, cls: type, cfg: dict) -> None: ...
    def run(self) -> None: ...
```

---

## 3. GSM20H10 SMU Panel

### File
`gui/instruments/gsm20h10_panel.py`

### Layout

```
┌── Left (280px fixed) ─────────────────────────┬── Right (expandable) ────────────┐
│  ── Source ──────────────────────────────────  │  ┌────────────────────────────┐  │
│  Mode:  [● Voltage] [ Current]                 │  │  Measured V:  0.00000  V   │  │
│  Setpoint: [ 0.000 ] V                         │  │  Measured I:  0.00000  A   │  │
│  Compliance: [ 0.010 ] A                       │  │  Power:       0.00000  W   │  │
│                                                │  │                            │  │
│  ── Output ─────────────────────────────────── │  │  ─ History (last 200 pts) ─ │  │
│  [Output ON]  [Output OFF]                     │  │  [pyqtgraph strip chart]    │  │
│   Status: ● OFF                                │  │  V vs time or I vs time     │  │
│                                                │  └────────────────────────────┘  │
│  ── Read ───────────────────────────────────── │                                  │
│  [Read Once]                                   │                                  │
│                                                │                                  │
│  ── Live Mode ──────────────────────────────── │                                  │
│  Poll interval: [ 500 ] ms                     │                                  │
│  [▶ Start Live]  [■ Stop Live]                 │                                  │
│  Log to CSV: [ ] (toggle)                      │                                  │
│                                                │                                  │
│  ── Connect ────────────────────────────────── │                                  │
│  [Connect]  [Disconnect]                       │                                  │
│  ID: (read-only label)                         │                                  │
│                                                │                                  │
│  [🛑 OUTPUT OFF (panic)]  ← always enabled     │                                  │
└────────────────────────────────────────────────┴──────────────────────────────────┘
```

### Rules
- Mode switch only enabled when output OFF
- Setpoint/compliance only editable when output OFF
- [Output ON] applies setpoint first, then enables
- Panic button always clickable (fire-and-forget thread)
- Live mode uses `ContinuousPollWorker` with configurable interval
- Strip chart auto-scrolls, keeps last 200 points, auto-ranges Y axis

### Workers needed

In `gui/instruments/workers.py`:

```python
class ConnectWorker(QThread):
    connected = Signal(bool, str)  # (ok, instrument_id_or_error)
    ...

class SingleReadWorker(QThread):
    data = Signal(dict)  # {"voltage_V": ..., "current_A": ..., "power_W": ..., "timestamp_s": ...}
    error = Signal(str)
    ...

class ContinuousPollWorker(QThread):
    data = Signal(dict)
    error = Signal(str)
    stopped = Signal(str)  # reason: "user" | "error" | "disconnect"
    def __init__(self, cls: type, cfg: dict, interval_ms: int, output_off_on_stop: bool = False) -> None: ...
    def abort(self) -> None: ...
    def run(self) -> None: ...
```

---

## 4. E36300 Power Supply Panel

### File
`gui/instruments/e36300_panel.py`

### Layout

```
┌── Left (280px fixed) ─────────────────────────┬── Right ─────────────────────────┐
│  Channel: [CH1 ▼]  [CH2]  [CH3]               │  Measured V (CH1):  0.000  V     │
│                                                │  Measured I (CH1):  0.000  A     │
│  Set V: [ 0.00 ] V                             │                                  │
│  I limit: [ 0.10 ] A                           │  (no live plot needed here)      │
│                                                │                                  │
│  [Apply]   (applies V+I limit to channel)      │                                  │
│  [Output ON]  [Output OFF]                     │                                  │
│  Status: ● OFF                                 │                                  │
│                                                │                                  │
│  [Read CH]  (single readback of selected ch)   │                                  │
│                                                │                                  │
│  [Connect]  [Disconnect]                       │                                  │
│  ID: (read-only label)                         │                                  │
│                                                │                                  │
│  [🛑 ALL OUTPUT OFF (panic)]                   │                                  │
└────────────────────────────────────────────────┴──────────────────────────────────┘
```

### Rules
- [Apply] only enabled when connected AND output OFF
- Channel switch triggers immediate readback for new channel
- No continuous polling in Milestone 1 (single read on demand)
- Panic button disables all channels

### Workers
Uses same `ConnectWorker` and `SingleReadWorker` from `gui/instruments/workers.py`.
`SingleReadWorker` for E36300 returns `{"voltage_V": ..., "current_A": ..., "channel": ..., "timestamp_s": ...}`.

---

## 5. Safety Requirements (mandatory)

1. **Connection tests never enable outputs** — ConnectionTestWorker is read-only.
2. **Panic buttons always visible and always enabled** regardless of worker state.
3. **ContinuousPollWorker** only calls `output_off()` on stop if explicitly configured via `output_off_on_stop` flag.
4. **MainWindow.closeEvent** must check if GSM/E36300 have outputs ON; show warning dialog and call panic-off before accepting close.
5. **Error during live mode** → auto-stop, disable live controls, do NOT auto-restart.

---

## 6. Milestone Plan

### Milestone 1 — Connections Tab (all 5 instruments)
- `gui/widgets/connections_widget.py`
- `gui/instruments/workers.py` (ConnectionTestWorker + ConnectWorker)

Acceptance: All instruments testable; simulate mode shows orange "SIMULATED"; failures show red with error.

### Milestone 2 — GSM20H10 Panel (source + single read)
- `gui/instruments/gsm20h10_panel.py`
- Add `SingleReadWorker` to workers

Acceptance: Can set V-source, enable output, read V/I/P, disable. Simulate mode works.

### Milestone 3 — GSM20H10 Continuous + Strip Chart
- Add `ContinuousPollWorker`
- Add pyqtgraph strip chart to panel

Acceptance: Live polling updates display and chart; CSV logging works.

### Milestone 4 — E36300 Panel
- `gui/instruments/e36300_panel.py`

Acceptance: Channel selection, set V/I, toggle output, read back.

### Milestone 5 — Phase 2 Live Experiments
- Iterator variants for experiments
- Per-step live plotting
