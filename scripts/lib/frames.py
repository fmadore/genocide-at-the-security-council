"""Reading and writing the pipeline's parquet files.

One place for the conventions every step shares: zstd compression, no index,
and a consistent line in the log saying what was written and how big it is.

Also home to :func:`body`, which reconstructs the speech text without its
opening form of address. The normalised table stores the *offset* where the
body starts rather than a second copy of 389 MB of text; this turns that offset
back into strings in one call, so downstream steps never re-implement it.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import console
from .artifacts import atomic_path
from .paths import rel


def read(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    """Read a parquet file, reporting its shape."""
    if not path.exists():
        console.fail(f"{rel(path)} is missing — run the earlier pipeline steps first")
    frame = pd.read_parquet(path, columns=columns)
    console.info(f"read {rel(path)}  {frame.shape[0]:,} x {frame.shape[1]}")
    return frame


def write(frame: pd.DataFrame, path: Path) -> None:
    """Atomically write a parquet file, reporting its size.

    Through `artifacts.atomic_path` rather than its own temp-file dance:
    `to_parquet` wants a filename where `atomic_write_bytes` wants bytes, which
    is the only reason this looked like a different problem.
    """
    with atomic_path(path) as temp:
        frame.to_parquet(temp, index=False, compression="zstd")
    size = path.stat().st_size / 1e6
    console.info(f"wrote {rel(path)}  {frame.shape[0]:,} x {frame.shape[1]}  ({size:.1f} MB)")


def body(frame: pd.DataFrame) -> pd.Series:
    """The speech text with its opening form of address removed.

    Requires the ``text`` and ``body_start`` columns written by 02_normalise.
    """
    missing = {"text", "body_start"} - set(frame.columns)
    if missing:
        raise KeyError(
            f"body() needs {', '.join(sorted(missing))}; read speeches_norm.parquet, "
            f"not speeches.parquet"
        )
    return pd.Series(
        [
            text[start:]
            for text, start in zip(frame["text"], frame["body_start"], strict=True)
        ],
        index=frame.index,
        dtype="object",
    )
