"""CLI orchestrator for lab instrument control workflows."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import yaml

from experiments.iv_curve import run_iv_curve
from experiments.rotation_sweep import run_rotation_sweep
from experiments.tcspc_scan import run_tcspc_scan
from instruments.e36300 import E36300Supply
from instruments.gsm20h10 import GSM20H10
from instruments.kdc101 import KDC101Stage
from instruments.pm100d import PM100D
from instruments.picoharp300 import PicoHarp300


def _print_banner() -> None:
    """Print startup banner.

    Parameters:
        None (units: none).
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("╔══════════════════════════════════╗")
    print("║   Lab Instrument Control v0.1   ║")
    print(f"║   {now}   ║")
    print("╚══════════════════════════════════╝")


def discover(config_path: str = "config/instruments.yaml") -> None:
    """Discover VISA and Kinesis resources.

    Parameters:
        config_path: YAML config path for optional DLL settings (units: none).
    """
    print("VISA Resources:")
    try:
        import pyvisa  # type: ignore

        rm = pyvisa.ResourceManager()
        resources = rm.list_resources()
        if not resources:
            print("  (none)")
        for resource in resources:
            try:
                inst = rm.open_resource(resource, timeout=800)
                idn = inst.query("*IDN?").strip()
                inst.close()
                print(f"  {resource:<50} -> {idn}")
            except Exception as exc:
                print(f"  {resource:<50} -> {exc}")
    except Exception as exc:
        print(f"  VISA unavailable: {exc}")

    print("\nKinesis Devices:")
    try:
        with Path(config_path).open("r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle) or {}
        kinesis_path = config.get("kdc101", {}).get("kinesis_path")
        import pylablib as pll  # type: ignore

        if kinesis_path:
            pll.par["devices/dlls/kinesis"] = kinesis_path
        from pylablib.devices import Thorlabs  # type: ignore

        devices = Thorlabs.list_kinesis_devices()
        if not devices:
            print("  (none)")
        for serial, model in devices:
            print(f"  {serial} -> {model}")
    except Exception as exc:
        print(f"  Kinesis unavailable: {exc}")


def check_config(config_path: str = "config/instruments.yaml") -> None:
    """Check connectivity based on current config.

    Parameters:
        config_path: YAML config path (units: none).
    """
    with Path(config_path).open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}

    checks = [
        ("kdc101", KDC101Stage),
        ("pm100d", PM100D),
        ("e36300", E36300Supply),
        ("gsm20h10", GSM20H10),
        ("picoharp300", PicoHarp300),
    ]

    for key, cls in checks:
        cfg = config.get(key, {})
        if cfg.get("simulate", False):
            print(f"{key:<10} : SIMULATED")
            continue
        try:
            with cls(cfg) as inst:
                print(f"{key:<10} : OK ({inst.instrument_id})")
        except Exception as exc:
            print(f"{key:<10} : FAIL ({exc})")


def _build_parser() -> argparse.ArgumentParser:
    """Build top-level CLI parser.

    Parameters:
        None (units: none).
    """
    parser = argparse.ArgumentParser(description="Lab instrument control CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_rot = subparsers.add_parser("rotation-sweep")
    p_rot.add_argument("--config", default="config/instruments.yaml")
    p_rot.add_argument("--output", default="output")
    p_rot.add_argument("--start", type=float, default=0.0)
    p_rot.add_argument("--stop", type=float, default=360.0)
    p_rot.add_argument("--step", type=float, default=5.0)

    p_iv = subparsers.add_parser("iv-curve")
    p_iv.add_argument("--config", default="config/instruments.yaml")
    p_iv.add_argument("--output", default="output")
    p_iv.add_argument("--v_start", type=float, default=-5.0)
    p_iv.add_argument("--v_stop", type=float, default=5.0)
    p_iv.add_argument("--v_step", type=float, default=0.1)
    p_iv.add_argument("--i_limit", type=float, default=0.05)

    p_tcspc = subparsers.add_parser("tcspc-scan")
    p_tcspc.add_argument("--config", default="config/instruments.yaml")
    p_tcspc.add_argument("--output", default="output")
    p_tcspc.add_argument("--angles", nargs="+", type=float, default=None)
    p_tcspc.add_argument("--acq_time_ms", type=int, default=None)

    p_discover = subparsers.add_parser("discover")
    p_discover.add_argument("--config", default="config/instruments.yaml")

    p_check = subparsers.add_parser("check-config")
    p_check.add_argument("--config", default="config/instruments.yaml")

    return parser


def main() -> None:
    """CLI entry point.

    Parameters:
        None (units: none).
    """
    _print_banner()
    args = _build_parser().parse_args()

    if args.command == "rotation-sweep":
        run_rotation_sweep(
            config_path=args.config,
            output_dir=args.output,
            start_deg=args.start,
            stop_deg=args.stop,
            step_deg=args.step,
        )
    elif args.command == "iv-curve":
        run_iv_curve(
            config_path=args.config,
            output_dir=args.output,
            v_start=args.v_start,
            v_stop=args.v_stop,
            v_step=args.v_step,
            i_limit=args.i_limit,
        )
    elif args.command == "tcspc-scan":
        run_tcspc_scan(
            config_path=args.config,
            output_dir=args.output,
            angles=args.angles,
            acq_time_ms=args.acq_time_ms,
        )
    elif args.command == "discover":
        discover(args.config)
    elif args.command == "check-config":
        check_config(args.config)


if __name__ == "__main__":
    main()