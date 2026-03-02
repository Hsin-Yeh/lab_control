"""Data persistence helpers."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

import h5py
import numpy as np

logger = logging.getLogger(__name__)


def save_csv(data: list[dict], filepath: str) -> None:
    """Save list-of-dict records to CSV.

    Parameters:
        data: Tabular rows represented as dict records (units: per key definition).
        filepath: Destination file path (units: none).
    """
    if not data:
        raise ValueError("data must contain at least one row")

    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(data[0].keys())

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

    logger.info("Saved CSV: %s (%d rows)", path, len(data))


def save_hdf5(data: dict[str, np.ndarray], filepath: str) -> None:
    """Save arrays into an HDF5 file.

    Parameters:
        data: Mapping of dataset name to ndarray (units: per dataset definition).
        filepath: Destination file path (units: none).
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    with h5py.File(path, "w") as handle:
        for name, values in data.items():
            handle.create_dataset(name, data=values)

    logger.info("Saved HDF5: %s (datasets: %s)", path, ", ".join(data.keys()))
