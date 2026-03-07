# Cross-Platform Development Guide — Mac Development, Windows Production

> **Scope**: This document addresses Mac vs Windows differences for developing and testing the GUI.
> You will develop and dry-test on **macOS**, then deploy to **Windows** for production hardware.

---

## 1. Critical Differences to Handle

### File Paths

| Aspect | macOS | Windows | Solution |
|---|---|---|---|
| Path separators | `/` | `\` | **Always use `pathlib.Path`** |
| Config example | `config/instruments.yaml` | `config\instruments.yaml` | `Path("config") / "instruments.yaml"` |
| DLL paths | N/A | `C:\Program Files\...` | Store in config, use `Path(cfg["dll_path"])` |
| Kinesis DLL | Not available on Mac | Required on Windows | Skip KDC101 tests on Mac |
| PicoHarp DLL | Not available on Mac | Required on Windows | Skip PicoHarp tests on Mac |

**Rule**: Never hardcode `"C:\\..."` or `"/usr/..."` in source code. All paths come from config or use `Path.home()`, `Path.cwd()`, etc.

### VISA/GPIB Drivers

| Driver | macOS | Windows | Workaround for Mac |
|---|---|---|---|
| NI-VISA | Can install but devices won't enumerate | Native support | `simulate: true` for all VISA instruments |
| Keysight VISA | Same limitation | Native support | Same |
| pyvisa-py (pure Python) | Works for TCPIP, fails for USB | Limited | Use for LAN instruments only |

**Testing strategy on Mac**:
- Set `simulate: true` for `pm100d`, `e36300`, `gsm20h10` in your Mac config
- ConnectionsWidget will show "SIMULATED" (orange dot)
- GUI logic and layout still testable

### Platform-Specific Libraries

| Library | macOS | Windows | Impact |
|---|---|---|---|
| `pylablib` (Kinesis) | Fails to import (DLL missing) | Works | Wrap imports in try/except |
| `ctypes` (PicoHarp) | Fails to load DLL | Works | Same |
| `pyqtgraph` | Works | Works | ✅ No issue |
| `PySide6` | Works | Works | ✅ No issue |

---

## 2. Mac Development Setup

### Install GUI dependencies
```bash
pip install PySide6>=6.6 pyqtgraph>=0.13
```

### Create Mac-specific config
Copy `config/instruments.yaml` to `config/instruments_mac.yaml`:

```yaml
kdc101:
  simulate: true  # DLL not available on Mac
  serial_number: "27xxxxxx"
  kinesis_path: null  # Not used in simulate mode

pm100d:
  simulate: true  # VISA devices won't enumerate on Mac without hardware
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
  simulate: true  # DLL not available on Mac
  dll_path: null
```

Run GUI on Mac:
```bash
python gui_main.py --config config/instruments_mac.yaml
```

(Add `--config` arg support in `gui_main.py` if not already present.)

### Expected Mac behavior
- All ConnectionsWidget tests show "SIMULATED"
- Experiment tabs run with fake data
- GSM/E36300 panels show controls but use stub values
- No actual instrument communication

---

## 3. Windows Production Setup

### Driver installation order (Windows only)
1. **NI-VISA** or **Keysight IO Libraries Suite** (for VISA instruments)
2. **Thorlabs Kinesis** software (installs KDC101 DLLs to `C:\Program Files\Thorlabs\Kinesis\`)
3. **PicoQuant PHLib** (installs `phlib64.dll` to `C:\Program Files\PicoQuant\PicoHarp300\`)
4. Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Windows-specific config
`config/instruments.yaml` on Windows:

```yaml
kdc101:
  simulate: false  # Real hardware
  serial_number: "27xxxxxx"  # Actual device serial
  kinesis_path: "C:\\Program Files\\Thorlabs\\Kinesis"

pm100d:
  simulate: false
  resource: "USB0::0x1313::0x8072::P0012345::INSTR"  # From NI-MAX or discover
  wavelength_nm: 532
  averaging_count: 10

e36300:
  simulate: false
  resource: "TCPIP0::192.168.1.100::inst0::INSTR"  # LAN address

gsm20h10:
  simulate: false
  resource: "GPIB0::5::INSTR"  # GPIB address from instrument front panel

picoharp300:
  simulate: false
  dll_path: "C:\\Program Files\\PicoQuant\\PicoHarp300\\PHLib64.dll"
```

### Finding resource strings on Windows
Run the discovery tool:
```bash
python main.py discover --config config/instruments.yaml
```

This will list all VISA resources and Kinesis devices. Copy the exact strings to your config.

---

## 4. Code Patterns for Cross-Platform Compatibility

### Wrap platform-specific imports

**Bad** (crashes on Mac):
```python
from instruments.kdc101 import KDC101Stage  # imports pylablib, fails on Mac
```

**Good**:
```python
try:
    from instruments.kdc101 import KDC101Stage
    KDC101_AVAILABLE = True
except (ImportError, OSError) as e:
    KDC101_AVAILABLE = False
    KDC101Stage = None  # Use None as placeholder
```

Then in ConnectionsWidget:
```python
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

### Path handling

**Bad**:
```python
config_path = "config\\instruments.yaml"  # Windows-only
output_dir = "C:\\lab_data\\output"       # Hardcoded drive letter
```

**Good**:
```python
from pathlib import Path

config_path = Path("config") / "instruments.yaml"
output_dir = Path.home() / "lab_data" / "output"  # Cross-platform home dir
```

### Opening file browser (for output dir link)

**Cross-platform approach**:
```python
import sys
import subprocess
from pathlib import Path

def open_folder(path: Path) -> None:
    """Open folder in OS file browser."""
    if sys.platform == "darwin":  # macOS
        subprocess.run(["open", str(path)])
    elif sys.platform == "win32":  # Windows
        subprocess.run(["explorer", str(path)])
    else:  # Linux
        subprocess.run(["xdg-open", str(path)])
```

Use this in experiment tabs when user clicks output dir label.

---

## 5. Testing Strategy

### Phase 1: Mac development (GUI structure only)
**Goal**: Validate layout, signal/slot wiring, threading, and simulate-mode logic.

**Test checklist** (all in simulate mode):
- ✅ Window opens, no crashes
- ✅ All 5 tabs switch correctly
- ✅ LogViewer captures Python logging
- ✅ ConfigEditor loads/saves YAML
- ✅ ConnectionsWidget shows "SIMULATED" for all instruments
- ✅ Experiment tabs run and plot fake data
- ✅ GSM/E36300 panels: controls enable/disable correctly
- ✅ No hardcoded Windows paths in error messages

**Acceptance**: `pytest tests/test_gui_smoke.py -v` passes on Mac.

If running tests from a headless macOS shell session, GUI smoke tests are skipped by default to avoid Qt abort during `QApplication` startup.
Run full GUI smoke tests from an active desktop session with:

```bash
LAB_CONTROL_GUI_TESTS=1 python -m pytest tests/test_gui_smoke.py -v
```

### Phase 2: Windows VM testing (optional pre-deployment)
If you have access to a Windows VM:
1. Install drivers (VISA, Kinesis, PHLib)
2. Keep `simulate: true` initially
3. Verify GUI works identically to Mac
4. Flip one instrument to `simulate: false` and connect real hardware
5. Test that instrument's connection test + panel

### Phase 3: Windows production deployment
1. Copy repo to Windows lab PC
2. Install drivers + Python deps
3. Run `python main.py discover` → update config with real resource strings
4. Set `simulate: false` for connected instruments
5. Test each instrument individually:
   - ConnectionsWidget [Test] → green PASS
   - Instrument panel Connect → shows real ID
   - Single read → real values
6. Run full experiment workflows

---

## 6. Config Management Strategy

### Option A: Separate config files (recommended)
```
config/
├── instruments_mac.yaml      # All simulate: true
├── instruments_windows.yaml  # Real hardware addresses
└── instruments.yaml          # Symlink or copy of active config
```

On Mac:
```bash
cp config/instruments_mac.yaml config/instruments.yaml
```

On Windows:
```bash
copy config\instruments_windows.yaml config\instruments.yaml
```

### Option B: Environment-based switching
Add to top of `gui_main.py`:
```python
import sys
from pathlib import Path

if sys.platform == "darwin":
    DEFAULT_CONFIG = "config/instruments_mac.yaml"
else:
    DEFAULT_CONFIG = "config/instruments.yaml"

window = MainWindow(config_path=DEFAULT_CONFIG)
```

---

## 7. Continuous Integration (Optional)

If you set up GitHub Actions CI:

```yaml
# .github/workflows/gui_tests.yml
name: GUI Tests
on: [push, pull_request]
jobs:
  test-mac:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: pytest tests/test_gui_smoke.py -v
  
  test-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: pytest tests/test_gui_smoke.py -v
```

This ensures GUI code doesn't break on either platform.

---

## 8. Common Pitfalls

### Pitfall 1: DLL path with backslashes in config
**Problem**:
```yaml
picoharp300:
  dll_path: "C:\Program Files\PicoQuant\..."  # YAML treats \P as escape
```

**Fix**: Double backslashes or use forward slashes (Python Path handles both):
```yaml
picoharp300:
  dll_path: "C:\\Program Files\\PicoQuant\\..."  # Escaped
  # OR
  dll_path: "C:/Program Files/PicoQuant/..."     # Forward slashes work on Windows
```

### Pitfall 2: VISA timeout differences
Windows NI-VISA default timeout: 2000 ms
macOS pyvisa-py: often infinite

**Fix**: Explicitly set timeout in instrument constructors:
```python
inst = rm.open_resource(resource, timeout=2000)  # 2 seconds
```

### Pitfall 3: Case sensitivity
macOS filesystem: case-insensitive by default
Windows: case-insensitive
Linux (if deploying there): case-sensitive

**Fix**: Keep consistent casing in imports:
```python
from instruments.gsm20h10 import GSM20H10  # File is gsm20h10.py (lowercase)
```

---

## 9. Pre-Deployment Checklist

Before moving GUI to Windows production:

**On Mac**:
- [ ] All tests pass: `pytest tests/ -v`
- [ ] No TODO/FIXME comments in critical paths
- [ ] No `print()` statements (use `logging` only)
- [ ] Config file uses `Path` for all file paths
- [ ] No hardcoded `/Users/...` or `C:\...` paths in code

**On Windows (first run)**:
- [ ] Drivers installed (NI-VISA, Kinesis, PHLib)
- [ ] `python main.py discover` finds all instruments
- [ ] Config updated with real resource strings
- [ ] Each instrument passes ConnectionsWidget test individually
- [ ] Smoke tests pass: `pytest tests/test_gui_smoke.py -v`
- [ ] One experiment runs end-to-end with real hardware

**Safety checks (Windows)**:
- [ ] Panic buttons actually disable outputs (test with multimeter)
- [ ] Closing GUI with output ON shows warning dialog
- [ ] Abort during experiment safely returns instruments to safe state

---

## 10. Troubleshooting

### "No module named 'pylablib'" on Mac
**Cause**: Kinesis drivers not available.
**Fix**: This is expected. Ensure simulate mode is on for `kdc101`.

### "VISA resource not found" on Windows
**Cause**: Instrument not powered, wrong address, or driver issue.
**Fix**:
1. Check instrument is on and connected (USB/LAN/GPIB)
2. Run NI-MAX (VISA tool) → Scan for instruments
3. Copy exact resource string to config

### GUI freezes when connecting instrument
**Cause**: Instrument I/O running on main thread (forgot QThread).
**Fix**: Review worker implementation — all instrument objects must be created inside `QThread.run()`.

### pyqtgraph chart is blank
**Cause**: OpenGL backend issue (common on some Windows VMs).
**Fix**: Add to `gui_main.py` before imports:
```python
import pyqtgraph as pg
pg.setConfigOption('useOpenGL', False)
```

### Different behavior Mac vs Windows
**Cause**: Simulate mode data stubs differ, or path separator issues.
**Fix**: Run both with identical simulate-mode config; use `Path` everywhere.
