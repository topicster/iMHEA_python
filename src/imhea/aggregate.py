"""Aggregation of event/irregular series onto regular grids.

Python translation of iMHEA_Aggregation (tip sums), iMHEA_Average (sample
means) and iMHEA_AggregationCS / iMHEA_AggregationLI (event-based rainfall
disaggregation via cubic splines or linear interpolation on cumulative
curves, after Sadler & Busscher 1989 and Wang et al. 2008).

Conventions (see docs/review/A_preprocessing.md):
- right-closed, right-labelled bins of ``scale`` minutes;
- gaps are NaN *marker rows*; re-imposed on output with strict inequalities;
- timestamps shifted -0.25 s before binning (MATLAB float-boundary guard).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.interpolate import CubicSpline

from . import mtime
from .clean import voids as _voids

log = logging.getLogger(__name__)

# Physical constants (iMHEA_AggregationCS/LI lines 28-39)
MININT = 0.2       #: mm/h  minimum intensity separating events (Padron 2015)
MAXINT = 127.0     #: mm/h  maximum plausible intensity (Onset 2013)
MEANINT = 3.0      #: mm/h  rate at which single tips are spread (Wang 2008)
LOWINT = min(0.1 / 60, MININT / 120)  #: mm/min minimum accepted rate (1/600)
BIAS_MAX = 0.25    #: relative volume-error threshold to abandon the spline

_MS_MIN = 60_000
_MS_DAY = 86_400_000


def _shifted_ms(dates) -> np.ndarray:
    return mtime.epoch_ms(dates) + mtime._EPOCH_MS - mtime.SHIFT_MS


def _mask_voids(grid_dates: pd.DatetimeIndex, vd: pd.DataFrame,
                *arrays: np.ndarray) -> None:
    """NaN-mask grid points strictly inside void intervals (in place).

    Void bounds derive from -0.25 s-shifted timestamps, as in MATLAB.
    """
    if not len(vd):
        return
    t = grid_dates.asi8
    starts = (vd["start"].astype("datetime64[ns]").to_numpy().astype("int64")
              - mtime.SHIFT_MS * 1_000_000)
    ends = (vd["end"].astype("datetime64[ns]").to_numpy().astype("int64")
            - mtime.SHIFT_MS * 1_000_000)
    # strict inequalities via searchsorted interval arithmetic (O(v log n))
    lo = np.searchsorted(t, starts, side="right")   # first index with t > s
    hi = np.searchsorted(t, ends, side="left")      # first index with t >= e
    delta = np.zeros(len(t) + 1, dtype=np.int32)
    np.add.at(delta, lo, 1)
    np.add.at(delta, np.minimum(hi, len(t)), -1)
    mask = np.cumsum(delta[:-1]) > 0
    for a in arrays:
        a[mask] = np.nan


@dataclass
class AggResult:
    """Regular-grid series (right-labelled bin ends)."""
    dates: pd.DatetimeIndex
    p: np.ndarray            #: aggregated values; NaN inside voids
    cum: np.ndarray          #: cumulative (flat through voids); NaN in voids
    voids: pd.DataFrame      #: gap inventory used for masking
    max: float = np.nan
    mean: float = np.nan
    min: float = np.nan
    single: np.ndarray | None = None   #: CS/LI: portion from single tips
    max_bias: float = np.nan           #: CS/LI: worst per-event volume bias
    n_biased_events: int = 0           #: CS/LI: events that fell back/flagged


def aggregate(dates, p, scale_min: float) -> AggResult:
    """Sum tip/interval values onto a regular grid (iMHEA_Aggregation).

    Bins are ``(t-scale, t]``; input NaNs define voids that are re-masked
    on the output with strict inequalities.
    """
    dates = mtime.to_datetime_index(dates)
    p = np.asarray(p, dtype=float)
    vd = _voids(dates - pd.Timedelta(milliseconds=mtime.SHIFT_MS), p)

    idx = mtime.interval_index(dates, scale_min)
    di, df_ = int(idx.min()), int(idx.max())
    n = df_ - di + 1
    keep = ~np.isnan(p) & (p != 0)
    newp = np.bincount(idx[keep] - di, weights=p[keep], minlength=n)

    cum = np.cumsum(newp)
    grid = mtime.grid_datetimes(np.arange(di, df_ + 1), scale_min)
    _mask_voids(grid, vd, newp, cum)
    # trailing grid point created by ceil after a gap is void too (l.84-88)
    if n >= 2 and newp[-1] == 0 and np.isnan(newp[-2]):
        newp[-1] = np.nan
        cum[-1] = np.nan
    return AggResult(grid, newp, cum, vd, max=np.nanmax(newp))


def average(dates, q, scale_min: float) -> AggResult:
    """Average samples onto a regular grid (iMHEA_Average).

    Empty bins: isolated ones are patched with the neighbour mean, longer
    runs become 0 unless covered by a declared void (NaN marker rows) —
    MATLAB behaviour, see CODE_REVIEW.md issue 10. Edge bins holding a
    solitary zero next to nonzero flow are declared void (heuristic).
    """
    dates = mtime.to_datetime_index(dates)
    q = np.asarray(q, dtype=float)
    vd = _voids(dates - pd.Timedelta(milliseconds=mtime.SHIFT_MS), q)

    idx = mtime.interval_index(dates, scale_min)
    di, df_ = int(idx.min()), int(idx.max())   # bounds include NaN rows
    n = df_ - di + 1
    keep = ~np.isnan(q)
    sums = np.bincount(idx[keep] - di, weights=q[keep], minlength=n)
    counts = np.bincount(idx[keep] - di, minlength=n)
    with np.errstate(invalid="ignore", divide="ignore"):
        newq = sums / counts                       # empty bin -> NaN

    # patch isolated empty bins with the neighbour mean (lines 69-73)
    if n >= 3:
        nan_ = np.isnan(newq)
        iso = nan_.copy()
        iso[[0, -1]] = False
        iso[1:-1] &= ~nan_[:-2] & ~nan_[2:]
        newq[iso] = 0.5 * (np.roll(newq, 1)[iso] + np.roll(newq, -1)[iso])
    newq[np.isnan(newq)] = 0.0                     # remaining empties -> 0

    cum = np.cumsum(newq)
    grid = mtime.grid_datetimes(np.arange(di, df_ + 1), scale_min)
    _mask_voids(grid, vd, newq, cum)
    # edge heuristics (lines 89-98): solitary edge zero next to nonzero flow
    if n >= 2:
        if newq[0] == 0 and newq[1] != 0:
            newq[0] = np.nan
            cum[0] = np.nan
        if newq[-1] == 0 and newq[-2] != 0:
            newq[-1] = np.nan
            cum[-1] = np.nan
    return AggResult(grid, newq, cum, vd, max=np.nanmax(newq),
                     mean=np.nanmean(newq), min=np.nanmin(newq))


# ---------------------------------------------------------------------------
# Event-based rainfall disaggregation (AggregationCS / AggregationLI)
# ---------------------------------------------------------------------------

def aggregate_events(dates, p=None, scale_min: int = 1, bucket: float = 0.2,
                     *, mintip: bool = True, halves: bool = True,
                     method: str = "spline",
                     matlab_compat: bool = False) -> AggResult:
    """Disaggregate tipping-bucket events onto a regular rainfall grid.

    method='spline' translates iMHEA_AggregationCS (clamped cubic spline on
    the event cumulative curve; natural spline when ``halves=False``; linear
    fallback when the volume bias exceeds 25%). method='linear' translates
    iMHEA_AggregationLI (linear interpolation only).

    matlab_compat=True additionally reproduces two LI-specific quirks
    (sentinel without the -MaxT offset; ``floor`` start cut) and the
    hard-coded ``bucket/2`` first output value for CS/LI alike; by default
    the corrected CS conventions are used for both methods and the first
    output bin is only given ``bucket/2`` when ``halves=True`` (as in CS).
    """
    if method not in ("spline", "linear"):
        raise ValueError("method must be 'spline' or 'linear'")
    dates = mtime.to_datetime_index(dates)
    p = (np.full(len(dates), bucket) if p is None
         else np.asarray(p, dtype=float))

    all_ms = _shifted_ms(dates)                    # shifted integer ms
    vd = _voids(dates - pd.Timedelta(milliseconds=mtime.SHIFT_MS), p)

    keep = ~np.isnan(p) & (p != 0)
    tip_ms, tip_mm = all_ms[keep].astype(float), p[keep].copy()
    if len(tip_ms) < 1:
        raise ValueError("no volume-bearing tips in the record")

    max_t_ms = bucket / MININT * 3_600_000         # event separation
    min_t_ms = bucket / MAXINT * 3_600_000         # merge threshold

    # -- pre-conditioning -------------------------------------------------
    if mintip:                                     # 1-min tip counting
        m_idx = -(-tip_ms.astype("int64") // _MS_MIN)
        di0 = int(m_idx.min())
        counts = np.bincount(m_idx - di0, weights=tip_mm)
        nz = np.flatnonzero(counts)
        tip_ms = ((nz + di0) * _MS_MIN).astype(float)
        tip_mm = counts[nz]
    else:                                          # merge fast tips forward
        gaps = np.diff(tip_ms)
        grp = np.concatenate(([0], np.cumsum(gaps > min_t_ms)))
        # runs with gaps <= MinT collapse into the run's LAST tip
        sums = np.bincount(grp, weights=tip_mm)
        last = np.searchsorted(grp, np.arange(grp[-1] + 1), side="right") - 1
        tip_ms, tip_mm = tip_ms[last], sums

    # -- sentinel + half-tip splitting of borderline-slow tips ------------
    # MATLAB places the sentinel exactly MaxT before the first tip, leaving
    # the "is this gap an event break?" test to float rounding (spec A §6.6).
    # 2*MaxT makes the intent (a definite break) unambiguous.
    sent_offset = 0.0 if (matlab_compat and method == "linear") \
        else 2 * max_t_ms
    tip_ms = np.concatenate(([tip_ms[0] - sent_offset], tip_ms))
    tip_mm = np.concatenate(([0.0], tip_mm))
    tip_ms, tip_mm = _divide_events(tip_ms, tip_mm, max_t_ms)
    tip_ms, tip_mm = tip_ms[1:], tip_mm[1:]        # drop sentinel

    # -- event segmentation ------------------------------------------------
    starts = np.flatnonzero(
        np.concatenate(([True], np.diff(tip_ms) > max_t_ms)))
    bounds = np.append(starts, len(tip_ms))

    # -- 1-minute master grid (whole-day aligned, iMHEA lines 153-159) ----
    di_g = int(all_ms.min() // _MS_DAY) * 1440
    df_g = int(-(-all_ms.max() // _MS_DAY)) * 1440
    n1 = df_g - di_g + 1
    cum1 = np.zeros(n1)
    single1 = np.zeros(n1)
    biases: list[float] = []
    n_bad = 0

    for e in range(len(starts)):
        lo, hi = bounds[e], bounds[e + 1]
        ems, emm = tip_ms[lo:hi], tip_mm[lo:hi]
        if hi - lo >= 2:
            de, df_e, y2m, bias, bad = _multi_tip_event(
                ems, emm, bucket, halves, method, di_g)
        else:
            de, df_e, y2m = _single_tip_event(ems[0], emm[0], di_g)
            bias, bad = 0.0, 0
        a, b = de - di_g, df_e - di_g
        cum1[a:b + 1] += y2m
        cum1[b + 1:] = cum1[b]
        if hi - lo < 2:
            single1[a:b + 1] += y2m
            single1[b + 1:] = single1[b]
        biases.append(bias)
        n_bad += bad

    # -- rescale to `scale_min` minutes (lines 324-348) --------------------
    s = int(scale_min)
    first = bucket / 2 if halves else 0.0
    newp = np.concatenate(([first], cum1[s::s] - cum1[:-s:s]))
    single = np.concatenate(([first if halves else 0.0],
                             single1[s::s] - single1[:-s:s]))
    grid_idx = np.arange(di_g, df_g + 1, s, dtype="int64")
    newp[np.round(newp, 8) == 0] = 0.0
    single[np.round(single, 8) == 0] = 0.0

    # cut to the actual record span (CS: ceil/ceil; LI compat: floor start)
    ndv_ceil = lambda ms: int(-(-int(ms) // (s * _MS_MIN))) * s
    if matlab_compat and method == "linear":
        di_c = int(int(all_ms.min()) // (s * _MS_MIN)) * s
    else:
        di_c = ndv_ceil(all_ms.min())
    df_c = ndv_ceil(all_ms.max())
    m = (grid_idx >= di_c) & (grid_idx <= df_c)
    grid_idx, newp, single = grid_idx[m], newp[m], single[m]

    cum = np.cumsum(newp)
    grid = mtime.grid_datetimes(grid_idx, 1)
    _mask_voids(grid, vd, newp, cum, single)

    max_bias = float(np.nanmax(biases)) if biases else np.nan
    if n_bad:
        log.info("aggregate_events: %d/%d events exceeded %.0f%% bias",
                 n_bad, len(starts), 100 * BIAS_MAX)
    return AggResult(grid, newp, cum, vd, max=np.nanmax(newp),
                     single=single, max_bias=max_bias, n_biased_events=n_bad)


def _divide_events(t: np.ndarray, v: np.ndarray,
                   max_t: float) -> tuple[np.ndarray, np.ndarray]:
    """Split borderline-slow tips into two half-tips (DivideEvents).

    A tip whose preceding gap d satisfies MaxT/2 < d <= MaxT, when an
    adjacent gap is also short, contributes half its volume at the gap
    midpoint. Out-of-range neighbour lookups are treated as event breaks
    (fixing the acknowledged MATLAB ``EventDiff(0)`` hazard).
    """
    d = np.diff(t)
    ev = d > max_t                       # event-separating gaps
    half = (d > max_t / 2) & ~ev
    out_t, out_v = [t[0]], [v[0]]
    for i in range(1, len(t)):
        prev_short = half[i - 1]
        nxt = ev[i] if i < len(d) else True
        prv2 = ev[i - 2] if i >= 2 else True
        if prev_short and (not nxt or not prv2):
            mid = t[i] - d[i - 1] / 2
            out_t += [mid, t[i]]
            out_v += [v[i] / 2, v[i] / 2]
        else:
            out_t.append(t[i])
            out_v.append(v[i])
    return np.asarray(out_t), np.asarray(out_v)


def _multi_tip_event(ems, emm, bucket, halves, method, di_g):
    """Interpolate one multi-tip event onto the 1-min grid; return
    (DI_e, DF_e, cumulative mm per grid minute, bias, flagged)."""
    x = (ems - ems[0]) / 1000.0                    # seconds from first tip
    y = np.cumsum(emm)
    if halves:
        x0 = bucket * (x[1] - x[0]) / (y[1] - y[0]) - 0.5
        xf = bucket * (x[-1] - x[-2]) / (y[-1] - y[-2])
        if x0 < 0:                                 # keep abscissae monotone
            log.warning("event start padding x0=%.2fs clipped to 0", x0)
            x0 = 0.0
        xe = np.round(np.concatenate(([0.0], x + x0, [x[-1] + x0 + xf])))
        ye = np.concatenate(([0.0], y - bucket / 2, [y[-1]]))
        di_e = max(di_g, int((ems[0] - x0 * 1000) // _MS_MIN))
        df_e = int(-(-(ems[-1] + xf * 1000) // _MS_MIN))
    else:
        xe, ye = x, y
        x0 = 0.0
        di_e = max(di_g, int((ems[0] + 500) // _MS_MIN))
        df_e = int(-(-ems[-1] // _MS_MIN))
    x1m = np.round(
        (np.arange(di_e, df_e + 1) * _MS_MIN - ems[0] + x0 * 1000) / 1000.0)

    xe, uniq = np.unique(xe, return_index=True)
    ye = ye[uniq]                                  # spline needs distinct x
    if method == "spline":
        bc = "clamped" if halves else "natural"
        y1m = CubicSpline(xe, ye, bc_type=bc)(x1m)
    else:
        y1m = np.interp(x1m, xe, ye, left=0.0, right=0.0)
    if halves and len(y1m) >= 2:
        y1m[0] = 0.0
        y1m[-1] = y1m[-2]
    r1m = np.diff(y1m, prepend=0.0)

    total = ye[-1]
    r2m, bias, bad = _int_correction(r1m, total, halves, method, xe, ye, x1m)
    y2m = np.cumsum(r2m)
    y2m[-1] = total
    if halves and len(y2m) >= 2:
        y2m[-2] = total
    return di_e, df_e, y2m, bias, bad


def _int_correction(r, total, halves, method, xe, ye, x1m):
    """Bias check, optional linear fallback, and the 11-pass clamp/rescale
    volume-conservation loop (intCorrection subfunction)."""
    bias = abs(total - r[r > 0].sum()) / total if total else 0.0
    bad = 0
    if bias > BIAS_MAX:
        bad = 1
        if method == "spline":                     # abandon the spline
            y = np.interp(x1m, xe, ye, left=0.0, right=0.0)
            if halves and len(y) >= 2:
                y[0] = 0.0
                y[-1] = y[-2]
            r = np.diff(y, prepend=0.0)
            bias = abs(total - r[r > 0].sum()) / total if total else 0.0
    r = r.copy()
    it = 0
    while it <= 10 and (abs(total - r.sum()) > LOWINT
                        or np.any(np.round(r[r != 0], 8) < LOWINT)):
        r[r < 0] = 0.0
        r[(r > 0) & (r < LOWINT)] = LOWINT
        low_sum = r[r < LOWINT].sum()
        big = r >= LOWINT
        denom = r.sum() - low_sum
        if denom > 0:
            r[big] *= (total - low_sum) / denom
        it += 1
    return r, bias, bad


def _single_tip_event(tms, vol, di_g):
    """Spread a single tip backwards at MEANINT (3 mm/h) onto 1-min bins."""
    x0 = vol / MEANINT * 60 - 1                    # spread length [min] - 1
    xf = tms / _MS_MIN                             # tip time in minutes
    n_pts = int(np.floor(x0)) + 1                  # one point per minute,
    pts = xf - np.arange(n_pts - 1, -1, -1.0)      # ending at the tip
    per = vol / n_pts                              # mass-conserving split
    # (MATLAB uses vol/(x0+1): identical for 0.1/0.2 mm buckets where x0 is
    #  an integer; for 0.254 mm buckets MATLAB loses ~1.6% of the tip volume)
    di_e = max(di_g, int(np.floor(xf - x0)))
    df_e = int(np.ceil(xf))
    b = np.ceil(pts - 1e-6).astype(int) - di_e     # right-closed minute bins
    b = np.clip(b, 0, df_e - di_e)
    r = np.bincount(b, weights=np.full(n_pts, per),
                    minlength=df_e - di_e + 1)
    return di_e, df_e, np.cumsum(r)
