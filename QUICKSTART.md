# Quick Start Guide

## Immediate Next Steps (No Hardware)

1. **Verify installation**
   ```bash
   pytest tests -v
   ```
   Expected: 30 passing tests

2. **Try simulated experiment**
   ```bash
   python main.py rotation-sweep --start 0 --stop 90 --step 10
   ```
   Check: `output/<timestamp>/` folder contains CSV + 2 PNGs

3. **Import in Python REPL**
   ```python
   from instruments import KDC101Stage, PM100D, E36300Supply, GSM20H10, PicoHarp300
   from instruments.base import BaseInstrument
   ```
   → No ImportError means all drivers loaded successfully

## When Hardware Arrives

### Step 1: Discover Instruments

```bash
python main.py discover
```

Copy:
- **VISA addresses** (USB::... or TCPIP::...)
- **Kinesis serial numbers** (27xxxxxx)

### Step 2: Update Config

Edit `config/instruments.yaml`:
- Replace `REPLACE_WITH_SERIAL` → actual serial
- Replace `REPLACE_WITH_VISA_ADDR` → actual VISA resource string
- Set `simulate: false` for connected instruments

### Step 3: Verify Connectivity

```bash
python main.py check-config
```

Expected output:
```
kdc101     : OK (KDC101:27000001)
pm100d     : OK (THORLABS,PM100D,P0001234,1.0.0)
...
```

If FAIL: check cables, driver installation, VISA timeout

### Step 4: Manual Hardware Test

```bash
# Test stage only
python tests/manual/test_kdc101_live.py

# Test power meter only
python tests/manual/test_pm100d_live.py
```

⚠️ **Safety**: Confirm loads are rated before running live tests

## Common Dry-Run Commands

```bash
# Full test suite
pytest tests -v

# Single instrument test
pytest tests/test_pm100d.py -v

# Simulated rotation sweep (7 points, ~5 seconds)
python experiments/rotation_sweep.py --start 0 --stop 30 --step 5

# Simulated I-V sweep
python experiments/iv_curve.py --v_start -1 --v_stop 1 --v_step 0.2

# Simulated TCSPC scan
python experiments/tcspc_scan.py --angles 0 90 180 --acq_time_ms 200
```

## File Locations

| What                  | Where                                  |
|-----------------------|----------------------------------------|
| Config                | `config/instruments.yaml`             |
| Instrument drivers    | `instruments/kdc101.py`, etc.         |
| Experiment scripts    | `experiments/rotation_sweep.py`, etc. |
| Unit tests            | `tests/test_*.py`                     |
| Manual tests (live)   | `tests/manual/test_*_live.py`         |
| Output data           | `output/<timestamp>/`                 |
| Debug logs            | `logs/`                               |

## Modifying Experiments

Example: change rotation sweep angle range in production run:

```bash
python main.py rotation-sweep --start 0 --stop 360 --step 1
```

Or modify programmatically:

```python
from experiments.rotation_sweep import run_rotation_sweep
run_rotation_sweep(start_deg=0, stop_deg=180, step_deg=2.5)
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'instruments'"

**Fix**: Activate virtual environment
```bash
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows
```

### "ConnectionError" in live test

**Check**:
1. Instrument powered on
2. USB cable connected
3. VISA address correct in config
4. Drivers installed (Kinesis/VISA/PicoQuant)

### "Compliance at X.X V" in I-V sweep

**Cause**: Current limit reached (expected behavior when DUT draws too much current)

**Fix**: Increase `--i_limit` if safe for your device

## Daily Workflow

1. Activate venv: `source .venv/bin/activate`
2. Check config: `python main.py check-config`
3. Run experiment: `python main.py rotation-sweep --start ... --stop ...`
4. Data auto-saved to `output/<timestamp>/`
5. Review CSV/plots in output folder

## Code Structure Philosophy

- All instruments inherit from `BaseInstrument`
- All config in YAML (never hardcode addresses)
- All units SI (deg, W, V, A, s)
- All I/O logged, never printed
- All instruments support `with` statement
- All instruments have `simulate` mode

## Adding New Instrument

1. Create `instruments/my_instrument.py`
2. Subclass `BaseInstrument`
3. Implement: `connect()`, `disconnect()`, `is_connected`, `instrument_id`
4. Add to `instruments/__init__.py` safe imports
5. Add config section to `config/instruments.yaml`
6. Write test in `tests/test_my_instrument.py`
7. Write manual test in `tests/manual/test_my_instrument_live.py`
