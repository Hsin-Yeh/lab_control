---
applyTo: "requirements.txt,pyproject.toml,config/**,instruments/__init__.py,instruments/base.py"
---

# Step 00 — Project Scaffold & Base Architecture

## Recommended Model
> **Use: Claude Sonnet 4**
> Multi-file creation with consistent architecture decisions across the whole project.

## Goal
Create the entire project skeleton: dependency files, config, custom exceptions,
and the abstract base class that all instruments will inherit from.

---

## STEP 0.1 — Create `requirements.txt`

**Prompt to run in Copilot Agent Mode:**
```
Create requirements.txt with exact packages:
pylablib>=1.4.4
pyvisa>=1.13
pyvisa-py>=0.7
ThorlabsPM100>=0.3
pyyaml>=6.0
numpy>=1.24
matplotlib>=3.7
tqdm>=4.65
h5py>=3.9
pytest>=7.4
pytest-mock>=3.11
```

### ✅ Checkpoint 0.1
- [ ] File exists at project root
- [ ] Run `pip install -r requirements.txt` — no errors
- [ ] Run `python -c "import pyvisa, pylablib, ThorlabsPM100"` — no ImportError

---

## STEP 0.2 — Create `pyproject.toml`

**Prompt to run in Copilot Agent Mode:**
```
Create pyproject.toml with:
- [project] name="lab_control", version="0.1.0", python requires ">=3.10"
- [tool.pytest.ini_options]: testpaths=["tests"], addopts="-v"
- [tool.pylance] pythonVersion = "3.10"
```

### ✅ Checkpoint 0.2
- [ ] Parses without error:
      `python -c "import tomllib; tomllib.load(open('pyproject.toml','rb'))"`

---

## STEP 0.3 — Create `config/instruments.yaml`

**Prompt to run in Copilot Agent Mode:**
```
Create config/instruments.yaml exactly as below.
Placeholder values are clearly labeled — the user will replace them.

kdc101:
  serial: "REPLACE_WITH_SERIAL"           # Find with: Thorlabs.list_kinesis_devices()
  kinesis_path: "C:/Program Files/Thorlabs/Kinesis"
  scale: "PRM1-Z8"
  velocity_deg_per_s: 10.0
  settle_time_s: 0.3
  simulate: false

pm100d:
  visa_resource: "REPLACE_WITH_VISA_ADDR" # Find with: pyvisa.ResourceManager().list_resources()
  wavelength_nm: 780.0
  averaging_count: 10
  simulate: false

e36300:
  visa_resource: "REPLACE_WITH_VISA_ADDR"
  simulate: false

gsm20h10:
  visa_resource: "REPLACE_WITH_VISA_ADDR"
  simulate: false

picoharp300:
  device_index: 0
  phlib_path: "C:/Windows/System32/PHLib.dll"
  sync_divider: 1
  cfd_sync_level_mv: 100
  cfd_sync_zerocross_mv: 10
  cfd_input_level_mv: 100
  cfd_input_zerocross_mv: 10
  binning: 0
  acq_time_ms: 1000
  simulate: false
```

### ✅ Checkpoint 0.3
- [ ] File loads cleanly:
      `python -c "import yaml; yaml.safe_load(open('config/instruments.yaml'))"`

---

## STEP 0.4 — Create `instruments/base.py`

**Prompt to run in Copilot Agent Mode:**
```
Create instruments/base.py with:

1. Two custom exceptions at module level:
   - InstrumentConnectionError(Exception):
       __init__(self, instrument_name: str, resource: str)
       stores both as attributes, sets message
   - InstrumentCommandError(Exception):
       __init__(self, instrument_name: str, command: str, response: str)

2. Abstract base class BaseInstrument(ABC):
   - __init__(self, config: dict):
       self.config = config
       self.simulate = config.get("simulate", False)
       self.logger = logging.getLogger(self.__class__.__name__)
   - @abstractmethod connect(self) -> None
   - @abstractmethod disconnect(self) -> None
   - @abstractproperty is_connected(self) -> bool
   - @abstractproperty instrument_id(self) -> str
   - __enter__: calls connect(), returns self
   - __exit__: calls disconnect() regardless of exception, logs any exception
   - @classmethod from_yaml(cls, yaml_path: str, key: str) -> "BaseInstrument":
       loads yaml, returns cls(config[key])
```

### ✅ Checkpoint 0.4
- [ ] `from instruments.base import BaseInstrument, InstrumentConnectionError, InstrumentCommandError` works
- [ ] Concrete subclass with all abstract methods passes isinstance check
- [ ] `with` block calls connect() on enter and disconnect() on exit (test with a mock subclass)

---

## STEP 0.5 — Create `instruments/__init__.py`

**Prompt to run in Copilot inline chat (GPT-4.1 is sufficient):**
```
Create instruments/__init__.py that lazily imports and re-exports:
KDC101Stage, PM100D, E36300Supply, GSM20H10, PicoHarp300,
BaseInstrument, InstrumentConnectionError, InstrumentCommandError.
Use try/except ImportError on each so a missing DLL does not crash the whole package.
Log a warning for any failed import.
```

### ✅ Checkpoint 0.5
- [ ] `from instruments import BaseInstrument` works even without Kinesis DLL installed
- [ ] Missing DLL logs a warning, does not raise
