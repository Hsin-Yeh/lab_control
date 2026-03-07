# GUI Phase 3 Implementation Plan (Kinesis, PM100D, Resistance, GSM Monitor)

## Scope
This document defines the implementation roadmap for the next GUI and workflow iteration.

In scope:
- Kinesis tab improvement (KDC101 stage + flipper in one tab)
- PM100D tab improvement (live monitor UX)
- Long-term resistance measurement experiment (constant-voltage source)
- Continuous output + monitoring experiment (GSM20H10 only)

Out of scope:
- PicoHarp GUI/worker/experiment enhancements (deferred due to DLL issues)

## Constraints
- All instrument access stays in worker threads (no blocking GUI thread operations).
- SI units only: angle (deg), power (W), voltage (V), current (A), time (s).
- Use existing config-driven setup from `config/instruments.yaml` and `config/instruments_mac.yaml`.
- Simulate mode must remain fully functional on macOS.
- Use `logging`, not `print`.

## Phase A — Kinesis Tab Upgrade
Target file: `gui/instruments/kinesis_panel.py`

### Goals
1. Improve operator state clarity.
2. Prevent conflicting/overlapping commands.
3. Keep stage + flipper combined in one tab.

### Implementation
- Add command-busy state for stage and flipper sections.
- Disable conflicting controls while operations are in progress.
- Add explicit status text transitions: `connecting`, `busy`, `connected`, `error`.
- Make connect/disconnect button enablement consistent with state.
- Preserve platform availability behavior and show clear simulate/unavailable messaging.

### Acceptance
- Repeated rapid button clicks do not spawn overlapping stage/flipper operations.
- UI state returns to idle controls after success/failure.
- Simulate-mode actions remain available and responsive.

## Phase B — PM100D Monitor Mode Upgrade
Target file: `gui/instruments/pm100d_panel.py`

### Goals
1. Add live trend visibility.
2. Add rolling monitor statistics.
3. Add optional session CSV logging for continuous mode.

### Implementation
- Add pyqtgraph power-vs-time strip chart for continuous mode.
- Add rolling statistics over fixed-size buffer: min/max/mean/std (W).
- Add `Log to CSV while continuous` toggle.
- Add a CSV path label for active logging session.
- Keep one-shot read and settings workflows intact.
- Unify dBm handling by computing from W in one helper path.

### Acceptance
- Continuous mode updates labels + plot + rolling stats.
- CSV file is created and appended when logging is enabled.
- Start/Stop transitions are stable across repeated sessions.

## Phase C — Long-Term Resistance Experiment (New)
Target files:
- `experiments/resistance_log.py`
- `gui/workers.py`
- `gui/tabs/resistance_log_tab.py`

### Goals
- Provide constant-voltage long-duration resistance logging.

### Experiment behavior
- Use GSM20H10 as source/measure instrument.
- Apply fixed source voltage and compliance current.
- At each interval, read V and I and compute `R = V / I` (with safe handling when `|I|` is near zero).
- Stop when elapsed time reaches duration or abort is requested.
- Optional compliance stop condition.
- Always attempt output off on exit.
- Save CSV and optional quick plot in timestamped output directory.

### Worker/tab behavior
- New worker with abort event + log forwarding.
- New tab with parameter form, run/abort controls, progress/status, and post-run plot.

### Acceptance
- Works in simulate mode from GUI.
- Produces expected CSV schema and run output folder.
- Abort leaves instrument output off.

## Phase D — GSM Continuous Output + Monitoring Experiment (New)
Target files:
- `experiments/gsm_monitor.py`
- `gui/workers.py`
- `gui/tabs/gsm_monitor_tab.py`

### Goals
- Provide experiment-mode continuous output and monitoring (separate from manual panel).

### Experiment behavior
- Configure source setpoint + compliance.
- Enable output, stream periodic measurements for fixed duration.
- Save time series data (`timestamp_s`, `voltage_V`, `current_A`, `power_W`, `resistance_Ohm`).
- Disable output in cleanup.

### Worker/tab behavior
- New worker with abort event + log forwarding.
- New tab with live status/progress and post-run curve rendering.

### Acceptance
- Simulate-mode run executes cleanly.
- Output files generated with expected columns.
- Abort path is safe and deterministic.

## Phase E — Integration + Validation
Target files:
- `gui/main_window.py`
- `tests/test_gui_smoke.py`
- new focused tests under `tests/`

### Integration
- Add new experiment tabs under `Experiments`.
- Keep existing tabs and ordering stable where practical.

### Validation
- Add smoke coverage for new tabs/widgets construction.
- Add worker/experiment tests for simulate mode and abort behavior.
- Run focused test set before broader suite.

## Deferred Items
- PicoHarp (all GUI and experiment enhancements): deferred until DLL/toolchain issues are resolved on target Windows hardware.
