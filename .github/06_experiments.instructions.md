---
applyTo: "experiments/**,utils/**,main.py"
---

# Step 06 — Multi-Instrument Experiments

## Recommended Models
> **Utils (logger, plotter, data_writer): GPT-4.1**
> Simple, self-contained helper functions.

> **Experiment scripts (rotation_sweep, iv_curve, tcspc_scan): o3**
> Coordinating multiple instruments with timing, live error recovery,
> and data persistence requires deep planning across all modules.

> **main.py orchestrator: GPT-4.1**
> CLI wiring is mechanical — no deep reasoning needed.

---

## STEP 6.1 — Build utility modules

**Prompt to run in Copilot Agent Mode (GPT-4.1):**
```
Create three utility files:

--- utils/logger.py ---
def setup_logger(name: str, log_file: str = None, level=logging.DEBUG) -> logging.Logger:
  - Add StreamHandler at INFO level
  - If log_file given: add FileHandler at DEBUG level, create parent dirs
  - Format: "%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s"
  - Return logger

--- utils/data_writer.py ---
def save_csv(data: list[dict], filepath: str) -> None:
  - Create parent dirs with pathlib.Path(filepath).parent.mkdir(parents=True, exist_ok=True)
  - Write with csv.DictWriter using keys from data[0]
  - Log saved path and row count

def save_hdf5(data: dict[str, np.ndarray], filepath: str) -> None:
  - Use h5py.File in write mode
  - Create one dataset per key in data dict
  - Log saved path and dataset names

--- utils/plotter.py ---
def plot_power_vs_angle(angles, powers, title="Rotation Sweep", save_path=None):
  - Create polar subplot with matplotlib
  - Convert angles to radians for polar plot
  - Save PNG if save_path given

def plot_cartesian_power(angles, powers, title="Power vs Angle", save_path=None):
  - Simple line plot, x=angles (deg), y=powers (W), grid on
  - Save PNG if save_path given

def plot_iv_curve(voltages, currents, save_path=None):
  - Line plot V vs I, labelled axes in V and A, grid on
  - Save PNG if save_path given

def plot_tcspc_histogram(histogram: np.ndarray, resolution_ps: float, save_path=None):
  - X axis: channel * resolution_ps / 1000 (nanoseconds)
  - Y axis: log scale counts
  - Grid on, axis labels "Time (ns)" and "Counts"
  - Save PNG if save_path given
```

### ✅ Checkpoint 6.1
- [ ] `from utils.logger import setup_logger` works
- [ ] `from utils.data_writer import save_csv, save_hdf5` works
- [ ] `from utils.plotter import plot_power_vs_angle` works

---

## STEP 6.2 — Rotation + Power Sweep experiment

**Prompt to run in Copilot Agent Mode (o3):**
```
Create experiments/rotation_sweep.py.

Function signature:
  run_rotation_sweep(
    config_path: str = "config/instruments.yaml",
    output_dir: str = "output",
    start_deg: float = 0.0,
    stop_deg: float = 360.0,
    step_deg: float = 5.0,
  ) -> list[dict]

Implementation steps:
  1. Load YAML config
  2. Set up logger with setup_logger(), output to logs/rotation_sweep.log
  3. Create output subfolder: f"{output_dir}/{datetime.now():%Y%m%d_%H%M%S}/"
  4. Instantiate KDC101Stage and PM100D from config

  5. Inside nested with statements for BOTH instruments:
     a. stage.home()
     b. pm.set_wavelength(config["pm100d"]["wavelength_nm"])
     c. pm.set_averaging(config["pm100d"]["averaging_count"])
     d. pm.auto_range(True)
     e. angles = np.arange(start_deg, stop_deg + step_deg, step_deg)
     f. results = []
     g. For i, angle in enumerate(tqdm(angles, desc="Rotation Sweep")):
           stage.move_to(angle)
           time.sleep(config["kdc101"]["settle_time_s"])
           power = pm.read_power_average(n=config["pm100d"]["averaging_count"])
           power_dbm = pm.read_power_dbm()
           results.append({
               "angle_deg": angle,
               "power_W": power,
               "power_dBm": power_dbm
           })
           logger.info(f"[{i+1}/{len(angles)}] {angle:.1f}° → {power:.3e} W ({power_dbm:.1f} dBm)")

  6. Post-sweep (outside with blocks):
     - save_csv(results, f"{out_subdir}/rotation_sweep.csv")
     - plot_power_vs_angle(angles, powers, save_path=f"{out_subdir}/polar.png")
     - plot_cartesian_power(angles, powers, save_path=f"{out_subdir}/cartesian.png")
     - logger.info(f"Sweep complete. {len(results)} points. Results in {out_subdir}")

  7. Error handling:
     - Catch InstrumentConnectionError: logger.error, sys.exit(1)
     - Catch KeyboardInterrupt: logger.warning("Aborted — returning stage to 0°"), stage.move_to(0)
     - Always disconnect in finally

  8. CLI entry point:
     if __name__ == "__main__":
       argparse with: --config, --output, --start, --stop, --step
       Call run_rotation_sweep(**args)
```

### ✅ Checkpoint 6.2
- [ ] Set both instruments to `simulate: true` in config
- [ ] Run: `python experiments/rotation_sweep.py --start 0 --stop 30 --step 5`
- [ ] CSV with 7 rows in output/ subfolder
- [ ] Two PNG plots generated (polar and cartesian)
- [ ] Ctrl+C handled gracefully without traceback

---

## STEP 6.3 — I-V curve with GSM-20H10

**Prompt to run in Copilot Agent Mode (o3):**
```
Create experiments/iv_curve.py.

Function signature:
  run_iv_curve(
    config_path: str = "config/instruments.yaml",
    output_dir: str = "output",
    v_start: float = -5.0,
    v_stop: float = 5.0,
    v_step: float = 0.1,
    i_limit: float = 0.05,
  ) -> list[dict]

Implementation:
  1. Load config, setup logger, create timestamped output subdir
  2. Instantiate GSM20H10 from config
  3. Inside with block:
     a. results = smu.sweep_voltage(v_start, v_stop, v_step, i_limit, delay_s=0.1)
     b. After sweep: calculate and log:
        - Max power point: max(abs(r["power"]) for r in results)
        - Dynamic resistance at each point (dV/dI, numerical derivative)
  4. save_csv(results, output/iv_curve.csv)
  5. plot_iv_curve(voltages, currents, save_path=output/iv_curve.png)
  6. Always output_off() in finally

CLI: argparse with --config, --output, --v_start, --v_stop, --v_step, --i_limit
```

### ✅ Checkpoint 6.3
- [ ] `python experiments/iv_curve.py --v_start -5 --v_stop 5 --v_step 0.5` runs with simulate
- [ ] CSV and PNG in output/ subfolder

---

## STEP 6.4 — TCSPC angular scan

**Prompt to run in Copilot Agent Mode (o3):**
```
Create experiments/tcspc_scan.py.

Function signature:
  run_tcspc_scan(
    config_path: str = "config/instruments.yaml",
    output_dir: str = "output",
    angles: list[float] = None,     # default [0, 45, 90, 135, 180]
    acq_time_ms: int = None,        # default from config
  ) -> dict

Implementation:
  1. Load config, setup logger, timestamped output subdir
  2. Instantiate KDC101Stage and PicoHarp300

  3. Inside nested with blocks for both:
     a. stage.home()
     b. summary = []
     c. Open HDF5 file: h5py.File(output/tcspc_scan.h5, "w")
     d. For each angle in tqdm(angles, desc="TCSPC Scan"):
          stage.move_to(angle)
          time.sleep(config["kdc101"]["settle_time_s"])
          hist = tcspc.acquire(acq_time_ms)
          rate_sync = tcspc.get_count_rate(0)
          rate_input = tcspc.get_count_rate(1)
          peak_ch = int(np.argmax(hist))
          peak_counts = int(hist[peak_ch])
          total = int(hist.sum())
          # Save histogram as HDF5 dataset
          hdf5_file.create_dataset(f"angle_{angle:.1f}", data=hist)
          # Save individual histogram PNG
          plot_tcspc_histogram(
              hist, tcspc.get_resolution(),
              save_path=f"{out_subdir}/hist_angle_{angle:.0f}.png"
          )
          summary.append({
              "angle_deg": angle, "peak_channel": peak_ch,
              "peak_counts": peak_counts, "total_counts": total,
              "count_rate_sync": rate_sync, "count_rate_input": rate_input
          })
          logger.info(f"Angle {angle:.1f}°: peak={peak_ch}, total={total:,}, rates=({rate_sync},{rate_input})")

  4. save_csv(summary, output/tcspc_summary.csv)
  5. Return {"summary": summary, "hdf5_path": ..., "output_dir": out_subdir}

CLI: --config, --output, --angles (nargs="+", type=float), --acq_time_ms
```

### ✅ Checkpoint 6.4
- [ ] `python experiments/tcspc_scan.py --angles 0 90 180 --acq_time_ms 500` runs with simulate
- [ ] HDF5 file has one dataset per angle
- [ ] Summary CSV has correct columns

---

## STEP 6.5 — main.py orchestrator

**Prompt to run in Copilot Agent Mode (GPT-4.1):**
```
Create main.py at project root.

argparse subcommands:
  rotation-sweep  → calls experiments.rotation_sweep.run_rotation_sweep()
                    args: --config, --output, --start, --stop, --step
  iv-curve        → calls experiments.iv_curve.run_iv_curve()
                    args: --config, --output, --v_start, --v_stop, --v_step, --i_limit
  tcspc-scan      → calls experiments.tcspc_scan.run_tcspc_scan()
                    args: --config, --output, --angles, --acq_time_ms
  discover        → runs VISA resource discovery + Kinesis device listing, prints table
  check-config    → loads instruments.yaml, for each instrument:
                    - if simulate=false: ping *IDN? or equivalent, print OK/FAIL
                    - if simulate=true:  print "SIMULATED"

On startup (before any subcommand): print banner:
  ╔══════════════════════════════════╗
  ║   Lab Instrument Control v0.1   ║
  ║   {datetime.now():%Y-%m-%d %H:%M:%S}    ║
  ╚══════════════════════════════════╝
```

### ✅ Final System Checklist
- [ ] `python main.py discover` — lists all connected VISA instruments and Kinesis devices
- [ ] `python main.py check-config` — all simulate=false instruments respond OK
- [ ] `python main.py rotation-sweep --start 0 --stop 360 --step 5` — completes full sweep
- [ ] `pytest tests/ -v --tb=short` — all tests green
- [ ] Git commit with auto-generated Copilot message: `git add . && git commit`
