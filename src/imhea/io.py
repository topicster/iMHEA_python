"""Readers for iMHEA raw sensor CSVs and MATLAB-format-compatible writers.

Raw file quirks handled here (see docs/review/F_paper.md):
- UTF-8 BOM; CR-only, CRLF or LF line endings
- timestamps ``dd/mm/yyyy HH:MM:SS``
- columns: Date, value (mm tip or level/flow), Flag
- flags: I=launched, D=downloaded, X=removed tip, P=anomalous intensity,
  V=data gap (value empty -> NaN gap-marker row, the convention every
  downstream function relies on)
"""

from __future__ import annotations

import io as _io
from pathlib import Path

import numpy as np
import pandas as pd

RAW_FLAGS = frozenset("IDXPV")


def read_raw_csv(path) -> pd.DataFrame:
    """Read an iMHEA raw sensor CSV.

    Layouts: rain gauges ``Date,Event mm,Flag``; level/flow stations
    ``Date,Level cm,Flow l/s,Flag`` (flags may be quoted lists, "D,P").
    Returns a DataFrame indexed by timestamp with the original numeric
    columns (NaN for gap-marker rows), a ``flag`` string column, and
    ``value`` aliasing the first numeric column. Rows are kept in file
    order (sorted ascending in all iMHEA files).
    """
    raw = Path(path).read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    text = raw.decode("utf-8", errors="replace")
    # normalise CR-only (classic Mac / logger export) and CRLF to LF
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    df = pd.read_csv(_io.StringIO(text), header=0, skipinitialspace=True)
    df.columns = [c.strip() for c in df.columns]
    date_col = df.columns[0]
    flag_cols = [c for c in df.columns if c.lower().startswith("flag")]
    num_cols = [c for c in df.columns if c != date_col and c not in flag_cols]

    dates = pd.to_datetime(df[date_col], format="%d/%m/%Y %H:%M:%S",
                           errors="raise")
    out = pd.DataFrame(index=pd.DatetimeIndex(dates, name="date"))
    for c in num_cols:
        out[c] = pd.to_numeric(df[c], errors="coerce").to_numpy(float)
    out["flag"] = (df[flag_cols[0]].fillna("").astype(str).str.strip()
                   if flag_cols else "")
    out["value"] = out[num_cols[0]] if num_cols else np.nan
    return out


def read_processed_csv(path) -> pd.DataFrame:
    """Read a MATLAB-produced ``*_processed.csv`` (validation reference).

    Columns are auto-detected from the header; 'NaN' literals parsed.
    """
    df = pd.read_csv(path, encoding="utf-8-sig", skipinitialspace=True)
    date_col = df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col], format="%d/%m/%Y %H:%M:%S")
    return df.set_index(date_col)


# ---------------------------------------------------------------------------
# MATLAB-format-compatible writers (iMHEA_Save*CSV.m)
# ---------------------------------------------------------------------------

def _fmt(v: float) -> str:
    """MATLAB ``%8.4f``: width-8 right-aligned, 4 decimals, ``     NaN``."""
    if np.isnan(v):
        return "     NaN"
    return f"{v:8.4f}"


def _write_series_csv(path, dates, columns: dict[str, np.ndarray]) -> None:
    dates = pd.DatetimeIndex(dates)
    heads = ",".join(["Date", *columns.keys()])
    cols = [np.asarray(c, dtype=float) for c in columns.values()]
    datestr = dates.strftime("%d/%m/%Y %H:%M:%S")
    with open(path, "w", newline="\n") as f:
        f.write(heads + "\n")
        for i, d in enumerate(datestr):
            f.write(d + "," + ",".join(_fmt(c[i]) for c in cols) + "\n")


def save_single_csv(path_dir, file_prefix: str, dates, p,
                    label: str = "Rainfall mm") -> Path:
    """iMHEA_SaveSingleCSV: one ``[Date, Var]`` file, full prefix verbatim."""
    path = Path(path_dir) / f"iMHEA_{file_prefix}_processed.csv"
    _write_series_csv(path, dates, {label: p})
    return path


def save_double_csv(path_dir, file_prefix: str, dates, data) -> tuple[Path, Path]:
    """iMHEA_SaveDoubleCSV: ``[Date,P1,Q1,P2,Q2]`` -> ``_01``/``_02`` files.

    ``file_prefix`` is ``'<3-char site>_<resolution>'`` e.g. ``'PAU_1hr'``.
    """
    data = np.asarray(data, dtype=float)
    site, rest = file_prefix[:3], file_prefix[3:]
    paths = []
    for tag, sl in (("_01", slice(0, 2)), ("_02", slice(2, 4))):
        path = Path(path_dir) / f"iMHEA_{site}{tag}{rest}_processed.csv"
        _write_series_csv(path, dates, {
            "Rainfall mm": data[:, sl.start],
            "Flow l/s/km2": data[:, sl.start + 1],
        })
        paths.append(path)
    return tuple(paths)


def save_daily_csv(path_dir, file_prefix: str, dates, data) -> tuple[Path, Path]:
    """iMHEA_SaveDailyCSV: ``[Date,P1,Q1,BQ1,P2,Q2,BQ2]`` -> two files."""
    data = np.asarray(data, dtype=float)
    site, rest = file_prefix[:3], file_prefix[3:]
    paths = []
    for tag, base in (("_01", 0), ("_02", 3)):
        path = Path(path_dir) / f"iMHEA_{site}{tag}{rest}_processed.csv"
        _write_series_csv(path, dates, {
            "Rainfall mm": data[:, base],
            "Flow l/s/km2": data[:, base + 1],
            "Baseflow l/s/km2": data[:, base + 2],
        })
        paths.append(path)
    return tuple(paths)
