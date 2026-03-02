---
applyTo: "instruments/picoharp300.py,tests/test_picoharp300.py,tests/manual/test_picoharp300_live.py"
---

# Step 05 — PicoHarp 300 TCSPC Module

## Recommended Model
> **Use: Claude 3.7 Sonnet Thinking**
> ctypes DLL wrapping requires careful type mapping, pointer arithmetic,
> and async polling logic. The simulate mode must generate physically realistic
> TCSPC histograms. This is the most complex driver in the project.

## Hardware Facts
- Base resolution: 4 ps (resolution = 4 × 2^binning ps)
- Histogram depth: 65536 channels
- Modes: 0 = Histogram, 2 = T2 (time-tag), 3 = T3
- CFD on both sync (ch 0) and input (ch 1)
- Sync divider values: 1, 2, 4, 8 only
- PHLib.dll is Windows-only; Python bitness must match DLL bitness (both 64-bit)

## Critical ctypes Type Mappings
```
PH_OpenDevice(c_int, c_char_p)               → c_int
PH_Initialize(c_int, c_int)                  → c_int
PH_Calibrate(c_int)                          → c_int
PH_SetSyncDiv(c_int, c_int)                  → c_int
PH_SetInputCFD(c_int, c_int, c_int, c_int)  → c_int
PH_SetBinning(c_int, c_int)                  → c_int
PH_SetOffset(c_int, c_int)                   → c_int
PH_ClearHistMem(c_int, c_int)               → c_int
PH_StartMeas(c_int, c_int)                  → c_int
PH_StopMeas(c_int)                          → c_int
PH_CTCStatus(c_int, POINTER(c_int))         → c_int  ← polling
PH_GetHistogram(c_int, POINTER(c_uint), c_int) → c_int
PH_GetCountRate(c_int, c_int, POINTER(c_int)) → c_int
PH_GetResolution(c_int, POINTER(c_double))  → c_int
PH_GetErrorString(c_int, c_char_p)          → c_int
PH_CloseDevice(c_int)                       → c_int
```
Return code: 0 = success, negative = error (use PH_GetErrorString to decode)

---

## STEP 5.1 — Verify PHLib.dll is accessible

**Run in VS Code terminal:**
```python
import ctypes, os, struct
dll_path = "C:/Windows/System32/PHLib.dll"
print("Python bitness:", struct.calcsize("P") * 8, "bit")
assert os.path.exists(dll_path), f"Not found: {dll_path}"
lib = ctypes.CDLL(dll_path)
print("PHLib loaded OK:", lib)
```

### ✅ Checkpoint 5.1
- [ ] DLL loads without OSError
- [ ] Python is 64-bit (required to match PicoQuant DLL)
- [ ] If error: install PicoHarp 300 software from https://www.picoquant.com
- [ ] Update `phlib_path` in `config/instruments.yaml` if DLL is elsewhere
- [ ] Device connected via USB and powered on

---

## STEP 5.2 — Implement `PicoHarp300` class

**Prompt to run in Copilot Agent Mode:**
```
In instruments/picoharp300.py, implement class PicoHarp300(BaseInstrument).

Load DLL via ctypes.CDLL(self.config["phlib_path"]). Store as self._dll.
HISTCHAN = 65536 (module constant).

Implement helper first:
  _check(self, retcode: int, func_name: str) -> None
    - If retcode < 0:
        err_buf = ctypes.create_string_buffer(40)
        self._dll.PH_GetErrorString(retcode, err_buf)
        raise InstrumentCommandError(
            "PicoHarp300", func_name, err_buf.value.decode()
        )

Required methods:

  connect(self) -> None
    - Load DLL, store as self._dll
    - serial_buf = ctypes.create_string_buffer(8)
    - _check(dll.PH_OpenDevice(dev_idx, serial_buf), "OpenDevice")
    - _check(dll.PH_Initialize(dev_idx, 0), "Initialize")    # 0 = histogram mode
    - _check(dll.PH_Calibrate(dev_idx), "Calibrate")
    - Apply config: set_sync_divider, set_cfd(0,...), set_cfd(1,...), set_binning
    - Store serial as self._serial = serial_buf.value.decode()
    - Log "PicoHarp300 connected, serial={serial}, resolution={get_resolution():.1f} ps"

  disconnect(self) -> None
    - _check(dll.PH_CloseDevice(dev_idx), "CloseDevice")

  is_connected / instrument_id: standard pattern
    instrument_id returns f"PicoHarp300:dev{index}:{serial}"

  set_sync_divider(self, divider: int) -> None
    - Validate divider in {1, 2, 4, 8}
    - _check(dll.PH_SetSyncDiv(dev_idx, divider), "SetSyncDiv")

  set_cfd(self, channel: int, level_mv: int, zerocross_mv: int) -> None
    - channel 0 = sync, 1 = input; validate in {0, 1}
    - _check(dll.PH_SetInputCFD(dev_idx, channel, level_mv, zerocross_mv), "SetInputCFD")

  set_binning(self, binning: int) -> None
    - Validate 0 <= binning <= 7
    - _check(dll.PH_SetBinning(dev_idx, binning), "SetBinning")

  set_offset(self, offset_ps: int) -> None
    - _check(dll.PH_SetOffset(dev_idx, offset_ps), "SetOffset")

  get_resolution(self) -> float
    - res = ctypes.c_double()
    - _check(dll.PH_GetResolution(dev_idx, ctypes.byref(res)), "GetResolution")
    - Return res.value  (picoseconds)

  get_count_rate(self, channel: int) -> int
    - rate = ctypes.c_int()
    - _check(dll.PH_GetCountRate(dev_idx, channel, ctypes.byref(rate)), "GetCountRate")
    - Return rate.value  (counts/second)

  acquire(self, acq_time_ms: int = None) -> np.ndarray
    - Use acq_time_ms or self.config["acq_time_ms"]
    - counts_buf = (ctypes.c_uint * HISTCHAN)()
    - _check(PH_ClearHistMem(dev_idx, 0), "ClearHistMem")
    - _check(PH_StartMeas(dev_idx, acq_time_ms), "StartMeas")
    - ctc = ctypes.c_int(0)
    - while ctc.value == 0:
        PH_CTCStatus(dev_idx, ctypes.byref(ctc))
        time.sleep(0.05)
    - _check(PH_StopMeas(dev_idx), "StopMeas")
    - _check(PH_GetHistogram(dev_idx, counts_buf, 0), "GetHistogram")
    - Return np.array(counts_buf[:], dtype=np.uint32)

Simulate mode:
  - connect(): set self._serial = "SIM0001"
  - get_resolution(): return 4.0 * (2 ** self.config.get("binning", 0))
  - get_count_rate(): return random.randint(50000, 200000)
  - acquire():
      channels = np.arange(HISTCHAN)
      peak_ch = 1000
      sigma = 50
      amplitude = 10000
      # IRF peak (Gaussian)
      signal = amplitude * np.exp(-0.5 * ((channels - peak_ch) / sigma) ** 2)
      # Exponential decay tail
      decay_mask = channels > peak_ch
      signal[decay_mask] += amplitude * np.exp(-(channels[decay_mask] - peak_ch) / 3000)
      # Poisson noise
      return np.random.poisson(signal).astype(np.uint32)
```

### ✅ Checkpoint 5.2
- [ ] Simulate: histogram shape is (65536,) with dtype uint32
- [ ] Simulate: peak visible near channel 1000 — `np.argmax(hist)` returns ~1000
- [ ] `_check(-1, "test")` raises InstrumentCommandError

---

## STEP 5.3 — Manual hardware verification

**Prompt to run in Copilot inline chat (GPT-4.1):**
```
Write tests/manual/test_picoharp300_live.py (standalone, not pytest):
1. Load config, connect PicoHarp300 with context manager
2. Print instrument_id
3. Print get_resolution() in ps
4. Print count rate: sync (ch 0) and input (ch 1)
5. Acquire 1-second histogram
6. Print peak channel index and peak count value
7. Print total integrated counts
8. Save: np.save("tcspc_test.npy", histogram)
9. Print "Test complete. Saved tcspc_test.npy"
```

### ✅ Checkpoint 5.3
- [ ] Count rates > 0 with laser connected
- [ ] Peak channel aligns with expected time-zero position
- [ ] tcspc_test.npy saved successfully
- [ ] No DLL errors or crashes

---

## STEP 5.4 — Unit tests (no hardware required)

**Prompt to run in Copilot Agent Mode (Claude Sonnet 4):**
```
Create tests/test_picoharp300.py. Mock ctypes.CDLL.

Test cases:
1. test_simulate_acquire_shape
   Shape is (65536,) with dtype uint32

2. test_simulate_acquire_has_peak
   max value > 1000 in simulated histogram

3. test_set_binning_invalid
   set_binning(10) raises ValueError

4. test_set_sync_divider_invalid
   set_sync_divider(3) raises ValueError

5. test_check_raises_on_negative
   _check(-1, "test_func") raises InstrumentCommandError

6. test_get_resolution_simulate
   simulate=True returns float > 0

7. test_simulate_count_rate_range
   get_count_rate(0) returns int between 50000 and 200000
```

### ✅ Checkpoint 5.4
- [ ] `pytest tests/test_picoharp300.py -v` — all green
