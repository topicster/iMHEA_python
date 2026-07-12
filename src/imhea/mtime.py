"""Time-base helpers reproducing the MATLAB datenum/interval-index conventions.

The MATLAB scripts represent time as ``datenum`` (float days since 0000-01-00)
and bin data onto right-closed, right-labelled intervals via integer interval
indices ``i = ceil(datenum * nd)`` with ``nd = 1440 / scale_minutes``.
A global shift of -0.25 s is applied before binning so that timestamps landing
exactly on a bin boundary stay in the interval that *ends* there, despite
float rounding (iMHEA_Aggregation.m line 26 and siblings).

Here all binning is done in exact integer milliseconds, which removes the
float hazard entirely; the -0.25 s shift is still applied for bit-level
equivalence with MATLAB on sub-second-offset timestamps.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

#: MATLAB datenum of the Unix epoch (1970-01-01)
EPOCH_DATENUM = 719_529
_DAY_MS = 86_400_000
_EPOCH_MS = EPOCH_DATENUM * _DAY_MS
#: MATLAB boundary-protection shift (iMHEA convention), in milliseconds
SHIFT_MS = 250


def to_datetime_index(dates) -> pd.DatetimeIndex:
    """Coerce any datetime-like sequence to a pandas DatetimeIndex (ns).

    The nanosecond normalisation matters: pandas >= 3.0 defaults to
    microsecond resolution, and all integer-timestamp arithmetic in this
    package (``.asi8``) assumes nanoseconds.
    """
    idx = pd.DatetimeIndex(dates)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    if idx.dtype != "datetime64[ns]":
        idx = idx.as_unit("ns")
    return idx


def epoch_ms(dates) -> np.ndarray:
    """Integer milliseconds since the Unix epoch."""
    return to_datetime_index(dates).asi8 // 1_000_000


def datenum(dates) -> np.ndarray:
    """MATLAB datenum (float days) for datetime-like input."""
    return EPOCH_DATENUM + epoch_ms(dates) / _DAY_MS


def from_datenum(dn) -> pd.DatetimeIndex:
    """Datetimes from MATLAB datenum floats (rounded to the nearest ms)."""
    ms = np.rint((np.asarray(dn, dtype=float) - EPOCH_DATENUM) * _DAY_MS)
    return pd.DatetimeIndex(ms.astype("int64").view("datetime64[ms]")).astype(
        "datetime64[ns]"
    )


def interval_index(dates, scale_min: float, *, shift: bool = True) -> np.ndarray:
    """Right-closed interval index: ``ceil(datenum * nd)`` in exact arithmetic.

    Interval ``i`` covers the half-open window ``((i-1)*scale, i*scale]``
    (times measured from the datenum origin). A timestamp exactly on a
    boundary belongs to the interval that ends there.
    """
    ms = epoch_ms(dates) + _EPOCH_MS
    if shift:
        ms = ms - SHIFT_MS
    width = int(round(scale_min * 60_000))
    return -(-ms // width)  # exact integer ceil-division


def grid_datetimes(indices, scale_min: float) -> pd.DatetimeIndex:
    """Datetimes of grid interval indices (right-labelled bin ends)."""
    width = int(round(scale_min * 60_000))
    ms = np.asarray(indices, dtype="int64") * width - _EPOCH_MS
    return pd.DatetimeIndex(ms.view("datetime64[ms]")).astype("datetime64[ns]")


def day_floor_index(dates, *, shift: bool = True) -> int:
    """``floor(min(datenum)) * 1440``: first whole-day-aligned minute index.

    Used by the 1-minute pre-aggregation grid in AggregationCS/LI.
    """
    ms = int(epoch_ms(dates).min()) + _EPOCH_MS
    if shift:
        ms -= SHIFT_MS
    return (ms // _DAY_MS) * 1440
