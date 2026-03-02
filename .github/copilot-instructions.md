# Lab Instrument Control — Global Copilot Context

## Project
Python-based laboratory automation system for a photonics/optics lab.
Controls 5 instruments over USB/VISA/Kinesis DLL.

## Instrument Registry
| Variable Name | Class           | File                       | Interface        |
|---------------|-----------------|----------------------------|------------------|
| `stage`       | `KDC101Stage`   | instruments/kdc101.py      | Thorlabs Kinesis |
| `pm`          | `PM100D`        | instruments/pm100d.py      | USBTMC / pyvisa  |
| `supply`      | `E36300Supply`  | instruments/e36300.py      | VISA / SCPI      |
| `smu`         | `GSM20H10`      | instruments/gsm20h10.py    | VISA / SCPI      |
| `tcspc`       | `PicoHarp300`   | instruments/picoharp300.py | ctypes / PHLib   |

## Non-Negotiable Rules
- ALL instrument classes inherit from `BaseInstrument` (instruments/base.py)
- ALL config (VISA addresses, serials, paths) lives in config/instruments.yaml — never hardcode
- ALL units are SI: angles in degrees, power in Watts, voltage in Volts, time in seconds
- Use `logging` module only — never `print()`
- Every method must have a docstring that includes parameter units
- Every instrument must support `with` statement (context manager)
- Every instrument must have a `simulate: bool` mode that works without hardware

## Tech Stack
- pylablib (Thorlabs Kinesis)
- pyvisa + pyvisa-py (SCPI instruments)
- ThorlabsPM100 (PM100D wrapper)
- ctypes (PicoHarp 300 PHLib.dll)
- pyyaml, numpy, matplotlib, tqdm, pytest

## Error Handling
- Connection failure  → raise `InstrumentConnectionError(instrument_name, resource)`
- Bad command        → raise `InstrumentCommandError(instrument_name, command, response)`
- Out-of-range param → raise `ValueError` with message that includes valid range

## File Structure
```
instruments/base.py        — Abstract base class + custom exceptions
instruments/kdc101.py      — KDC101 + PRM1/MZ8 rotation stage
instruments/pm100d.py      — Thorlabs PM100D power meter
instruments/e36300.py      — Keysight E36300 power supply
instruments/gsm20h10.py    — GW Instek GSM-20H10 SMU
instruments/picoharp300.py — PicoHarp 300 TCSPC
config/instruments.yaml    — All addresses and parameters (edit this first)
experiments/               — Multi-instrument experiment scripts
utils/                     — logger.py, plotter.py, data_writer.py
tests/                     — pytest test files
```
