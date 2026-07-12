"""Data cleaning: tip depuration, gap inventories, gap filling.

Python translation of iMHEA_Depure, iMHEA_Voids, iMHEA_MonitoringGaps and
iMHEA_FillGaps (see docs/review/A_preprocessing.md for the source specs).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import mtime

log = logging.getLogger(__name__)

#: iMHEA_Depure: minimum physically possible inter-tip interval [s]
MIN_TIP_SECONDS = 1.1
#: iMHEA_FillGaps: double-mass correlation acceptance threshold
FILL_R_THRESHOLD = 0.99


def depure(dates, p) -> np.ndarray:
    """Zero out logger-repetition tips arriving <= 1.1 s after the previous.

    Volume is NOT conserved by design: repetitions are considered spurious.
    (iMHEA_Depure.m; the first tip can never be flagged.)
    """
    p = np.asarray(p, dtype=float)
    dt = np.concatenate(([np.inf],
                         np.diff(mtime.epoch_ms(dates)) / 1000.0))
    flagged = dt <= MIN_TIP_SECONDS  # the first tip can never be flagged
    out = p.copy()
    out[flagged] = 0.0
    n = int(flagged.sum())
    if n:
        log.info("depure: zeroed %d repetition tips (%.2f mm removed)",
                 n, np.nansum(p) - np.nansum(out))
    return out


def voids(dates, values) -> pd.DataFrame:
    """Gap inventory: one row per NaN run, columns ``start``/``end``.

    MATLAB semantics (iMHEA_Voids): a gap is a NaN *marker row*, never a
    timestamp jump. ``start`` = timestamp of the first NaN of the run;
    ``end`` = timestamp of the first valid sample after the run (or the last
    timestamp if the run reaches the end of the record).
    """
    dates = mtime.to_datetime_index(dates)
    isna = np.isnan(np.asarray(values, dtype=float))
    return _runs(dates, isna)


def no_voids(dates, values) -> pd.DataFrame:
    """Valid-data inventory (complement of :func:`voids`), same conventions."""
    dates = mtime.to_datetime_index(dates)
    isna = np.isnan(np.asarray(values, dtype=float))
    return _runs(dates, ~isna)


def _runs(dates: pd.DatetimeIndex, mask: np.ndarray) -> pd.DataFrame:
    if len(mask) == 0 or not mask.any():
        return pd.DataFrame(columns=["start", "end"], dtype="datetime64[ns]")
    m = mask.astype(np.int8)
    starts = np.flatnonzero(np.diff(m, prepend=0) == 1)
    ends = np.flatnonzero(np.diff(m, append=0) == -1)  # last index of each run
    end_pos = np.minimum(ends + 1, len(dates) - 1)  # sample after the run
    return pd.DataFrame({"start": dates[starts], "end": dates[end_pos]})


def monitoring_gaps(dates, values) -> tuple[str, float]:
    """Monitoring period string and percentage of the span that is gap.

    (iMHEA_MonitoringGaps single-column path.)
    """
    dates = mtime.to_datetime_index(dates)
    v = voids(dates, values)
    span = dates.max() - dates.min()
    gap = (v["end"] - v["start"]).sum() if len(v) else pd.Timedelta(0)
    pct = 100.0 * gap / span if span > pd.Timedelta(0) else 0.0
    period = f"{dates.min():%d/%m/%Y} - {dates.max():%d/%m/%Y}"
    return period, float(pct)


def pair_overlap(df: pd.DataFrame,
                 q_cols=("Q1", "Q2"), p_cols=("P1", "P2")) -> tuple[float, float]:
    """Percentages of rows where both flows / both flows+rains exist.

    (iMHEA_MonitoringGaps 'Pair' branch, with the row-count bug fixed:
    denominators use the row count, not ``max(shape)``.)
    """
    total = len(df)
    if total == 0:
        return np.nan, np.nan
    both_q = df[list(q_cols)].notna().all(axis=1)
    both_all = both_q & df[list(p_cols)].notna().all(axis=1)
    return 100.0 * both_q.sum() / total, 100.0 * both_all.sum() / total


@dataclass
class FillResult:
    """Output of :func:`fill_gaps`."""
    dates: pd.DatetimeIndex
    p1: np.ndarray
    p2: np.ndarray
    filled: bool
    r: float = np.nan          #: correlation coefficient of double-mass curves
    slope: float = np.nan      #: M such that cum(P2) ~ M * cum(P1)
    scale_min: float = np.nan  #: unified resolution [min]
    n_filled: tuple[int, int] = (0, 0)
    notes: list[str] = field(default_factory=list)


def fill_gaps(dates1, p1, dates2, p2, *, cutend: bool = False,
              matlab_compat: bool = False) -> FillResult:
    """Cross-fill gaps between two rain gauges via double-mass regression.

    Both series are put on a unified regular grid (the coarser of the two
    median resolutions); overlapping samples build cumulative (double-mass)
    curves; if their correlation R >= 0.99, one-sided gaps are filled
    proportionally with the regression slope (no intercept), P1 <- P2/M then
    P2 <- P1*M. Both-sided gaps stay NaN. (iMHEA_FillGaps.m)

    cutend=True does not fill beyond the earlier of the two series' last
    valid samples. MATLAB's cutend path contains two bugs (the "restore" step
    re-injects the original NaNs, undoing the fill, and can crash on grids
    trimmed shorter than the originals — CODE_REVIEW.md issue 8). By default
    this implementation restores only the tail *beyond* the cut, keeping the
    fills; ``matlab_compat=True`` reproduces the value-level MATLAB result
    (fills at original timestamps reverted to NaN, without the crash).
    """
    from .aggregate import aggregate  # local import: avoids a module cycle

    d1, d2 = mtime.to_datetime_index(dates1), mtime.to_datetime_index(dates2)
    v1 = np.asarray(p1, dtype=float).copy()
    v2 = np.asarray(p2, dtype=float).copy()
    notes: list[str] = []

    # -- resolution harmonisation (medians of timestamp diffs, minutes)
    med1 = np.nanmedian(np.diff(d1.asi8) / 60e9)
    med2 = np.nanmedian(np.diff(d2.asi8) / 60e9)
    scale = round(max(med1, med2))
    if med1 != med2:
        agg = aggregate(d1, v1, scale) if med1 < med2 else None
        if agg is not None:
            d1, v1 = agg.dates, agg.p
        agg = aggregate(d2, v2, scale) if med2 < med1 else None
        if agg is not None:
            d2, v2 = agg.dates, agg.p
    # (MATLAB re-aggregates both series; re-aggregating the one already at
    #  'scale' is an identity on regular series, so only the finer is done.)

    # -- unified integer grid (round, not ceil: series are already regular)
    width = int(scale * 60_000)
    i1 = (mtime.epoch_ms(d1) + mtime._EPOCH_MS + width // 2) // width
    i2 = (mtime.epoch_ms(d2) + mtime._EPOCH_MS + width // 2) // width
    di, df_ = min(i1[0], i2[0]), max(i1[-1], i2[-1])
    grid = np.arange(di, df_ + 1, dtype="int64")
    g1 = np.full(grid.shape, np.nan)
    g2 = np.full(grid.shape, np.nan)
    g1[i1 - di] = v1
    g2[i2 - di] = v2
    full_g1, full_g2 = g1.copy(), g2.copy()

    # -- optional end cut
    cut_at = None
    if cutend:
        last1 = np.flatnonzero(~np.isnan(g1))
        last2 = np.flatnonzero(~np.isnan(g2))
        if len(last1) and len(last2):
            cut_at = min(last1[-1], last2[-1])
            g1, g2 = g1[: cut_at + 1], g2[: cut_at + 1]

    def _result(gg1, gg2, filled, r=np.nan, m=np.nan, nf=(0, 0)):
        return FillResult(mtime.grid_datetimes(grid, scale), gg1, gg2, filled,
                          r, m, scale, nf, notes)

    # -- overlap & double-mass regression
    m_overlap = ~np.isnan(g1) & ~np.isnan(g2)
    if m_overlap.sum() <= 1:
        notes.append("no date coincidence between series; nothing filled")
        return _result(full_g1, full_g2, False)

    c1 = np.cumsum(g1[m_overlap])
    c2 = np.cumsum(g2[m_overlap])
    r = float(np.corrcoef(c1, c2)[0, 1])
    slope = float(np.polyfit(c1, c2, 1)[0])
    if not (r >= FILL_R_THRESHOLD):
        notes.append(f"correlation not significant (R={r:.4f} < "
                     f"{FILL_R_THRESHOLD}); nothing filled")
        return _result(full_g1, full_g2, False, r, slope)

    # -- proportional fill (sequential, as in MATLAB lines 147-148)
    na1 = np.isnan(g1)
    g1[na1] = g2[na1] / slope
    na2 = np.isnan(g2)
    g2[na2] = g1[na2] * slope
    n_filled = (int(na1.sum() - np.isnan(g1).sum()),
                int(na2.sum() - np.isnan(g2).sum()))

    # -- restore tails / compat behaviour
    if cutend and cut_at is not None:
        head1, head2 = g1, g2
        g1, g2 = full_g1.copy(), full_g2.copy()
        if matlab_compat:
            # MATLAB re-injects original values (incl. NaN) at original
            # positions: fills at original timestamps are reverted.
            g1[: cut_at + 1] = head1
            g2[: cut_at + 1] = head2
            g1[~np.isnan(full_g1)] = full_g1[~np.isnan(full_g1)]
            g2[~np.isnan(full_g2)] = full_g2[~np.isnan(full_g2)]
            notes.append("matlab_compat: original NaNs re-injected (MATLAB "
                         "cutend restore bug reproduced)")
        else:
            g1[: cut_at + 1] = head1
            g2[: cut_at + 1] = head2

    return _result(g1, g2, True, r, slope, n_filled)
