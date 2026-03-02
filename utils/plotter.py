"""Plot helper functions for experiments."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def _finalize(save_path: str | None) -> None:
    """Finalize and optionally save current figure.

    Parameters:
        save_path: Optional output PNG path (units: none).
    """
    plt.tight_layout()
    if save_path:
        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(path, dpi=150)
    plt.close()


def plot_power_vs_angle(angles, powers, title: str = "Rotation Sweep", save_path: str | None = None):
    """Create a polar power-vs-angle plot.

    Parameters:
        angles: Sequence of angles (units: deg).
        powers: Sequence of powers (units: W).
        title: Plot title string (units: none).
        save_path: Optional output PNG path (units: none).
    """
    theta = np.radians(np.asarray(angles, dtype=float))
    r = np.asarray(powers, dtype=float)
    fig = plt.figure(figsize=(6, 5))
    ax = fig.add_subplot(111, projection="polar")
    ax.plot(theta, r, marker="o")
    ax.set_title(title)
    _finalize(save_path)


def plot_cartesian_power(angles, powers, title: str = "Power vs Angle", save_path: str | None = None):
    """Create cartesian power-vs-angle plot.

    Parameters:
        angles: Sequence of angles (units: deg).
        powers: Sequence of powers (units: W).
        title: Plot title string (units: none).
        save_path: Optional output PNG path (units: none).
    """
    plt.figure(figsize=(7, 4))
    plt.plot(angles, powers, marker="o")
    plt.title(title)
    plt.xlabel("Angle (deg)")
    plt.ylabel("Power (W)")
    plt.grid(True)
    _finalize(save_path)


def plot_iv_curve(voltages, currents, save_path: str | None = None):
    """Create I-V line plot.

    Parameters:
        voltages: Sequence of voltages (units: V).
        currents: Sequence of currents (units: A).
        save_path: Optional output PNG path (units: none).
    """
    plt.figure(figsize=(7, 4))
    plt.plot(voltages, currents, marker="o")
    plt.xlabel("Voltage (V)")
    plt.ylabel("Current (A)")
    plt.grid(True)
    _finalize(save_path)


def plot_tcspc_histogram(histogram: np.ndarray, resolution_ps: float, save_path: str | None = None):
    """Create TCSPC histogram plot.

    Parameters:
        histogram: Histogram counts array (units: counts).
        resolution_ps: Time resolution per channel (units: ps).
        save_path: Optional output PNG path (units: none).
    """
    channels = np.arange(histogram.size)
    time_ns = channels * float(resolution_ps) / 1000.0

    plt.figure(figsize=(7, 4))
    plt.plot(time_ns, histogram)
    plt.yscale("log")
    plt.xlabel("Time (ns)")
    plt.ylabel("Counts")
    plt.grid(True)
    _finalize(save_path)
