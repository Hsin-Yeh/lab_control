# Lab Instrument Control

Python-based laboratory automation system for photonics/optics research.

## Instruments Supported

| Variable | Class           | Interface        | Description                   |
|----------|-----------------|------------------|-------------------------------|
| `stage`  | `KDC101Stage`   | Thorlabs Kinesis | Rotation stage controller     |
| `pm`     | `PM100D`        | USBTMC / pyvisa  | Optical power meter           |
| `supply` | `E36300Supply`  | VISA / SCPI      | Triple-output power supply    |
| `smu`    | `GSM20H10`      | VISA / SCPI      | Source-measure unit (±210V)   |
| `tcspc`  | `PicoHarp300`   | ctypes / PHLib   | Time-correlated single photon |

## Setup

```bash
# Create virtual environment
python3.10 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Edit config (replace placeholder serial numbers/VISA addresses)
nano config/instruments.yaml
```

## Simulation Mode (No Hardware Required)

All instruments run in simulation mode by default (`simulate: true` in config). This allows:
- Code development and testing without physical instruments
- Workflow validation before equipment arrives
- Continuous integration testing in automated pipelines

To switch to hardware mode after connecting equipment, set `simulate: false` and populate addresses.

## Usage

### Command-Line Interface

```bash
# Discover connected VISA/Kinesis devices
python main.py discover

# Check configured instruments
python main.py check-config

# Run rotation sweep (stage + power meter)
python main.py rotation-sweep --start 0 --stop 360 --step 5

# Run I-V curve (SMU)
python main.py iv-curve --v_start -5 --v_stop 5 --v_step 0.1 --i_limit 0.05

# Run TCSPC scan (stage + PicoHarp)
python main.py tcspc-scan --angles 0 45 90 135 180 --acq_time_ms 1000
```

### Programmatic API

```python
from instruments.kdc101 import KDC101Stage
from instruments.pm100d import PM100D
import yaml

config = yaml.safe_load(open("config/instruments.yaml"))

with KDC101Stage(config["kdc101"]) as stage, PM100D(config["pm100d"]) as pm:
    stage.home()
    stage.move_to(45.0)
    power = pm.read_power_average(n=20)
    print(f"Power at 45°: {power:.4e} W")
```

## Testing

```bash
# Run unit tests (hardware-free mocks)
pytest tests -v

# Run manual live tests when hardware connected
python tests/manual/test_kdc101_live.py
python tests/manual/test_pm100d_live.py
python tests/manual/test_e36300_live.py
python tests/manual/test_gsm20h10_live.py
python tests/manual/test_picoharp300_live.py
```

## Output

Experiments save timestamped outputs to `output/YYYYMMDD_HHMMSS/`:
- **CSV**: Tabular measurement data
- **PNG**: Publication-ready plots
- **HDF5**: Raw histogram/array data (TCSPC)
- **Logs**: Debug-level logs in `logs/`

## Architecture Principles

- **SI units everywhere**: angles in deg, power in W, voltage in V, current in A, time in s
- **Context managers**: All instruments support `with` statement for safe cleanup
- **Logging only**: No `print()` calls; use logging module with configurable levels
- **Config-driven**: All addresses/parameters live in `config/instruments.yaml`
- **Simulate-first**: Every instrument has a hardware-free simulation mode

## Hardware Connections

### Before First Use

1. **KDC101**: Install Thorlabs Kinesis software (required for USB drivers)
   - Run `discover` to find serial number → update `config/instruments.yaml`
2. **PM100D/E36300/GSM20H10**: VISA-compatible (USB or LAN)
   - Run `main.py discover` to list resources → copy address to config
3. **PicoHarp300**: Install PicoQuant software (provides PHLib.dll)
   - Confirm DLL path in config matches installation directory

## License

MIT

## Contact

Issues/questions: open an issue in this repository
