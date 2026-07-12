"""Statistical analysis: duration curves, pulses, monthly aggregates.

Python translation of iMHEA_FDC, iMHEA_IDC, iMHEA_Pulse, iMHEA_MonthlyFlow
and iMHEA_MonthlyRain (specs: docs/review/C_flow_analysis.md).

Percentile convention (load-bearing): Gringorten (1963) plotting positions
on ascending-sorted flows, interpolated with a not-a-knot cubic spline —
MATLAB ``spline`` semantics. ``np.percentile`` does NOT reproduce these.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.interpolate import CubicSpline

from . import mtime

#: IDC window lengths in 5-min steps: 5,10,15,30 min, 1,2,4,12,24,48 h
IDC_DURATIONS = np.array([1, 2, 3, 6, 12, 24, 48, 144, 288, 576])


# ------------------------------------------------------------------- FDC ---

@dataclass
class FDCResult:
    fdc: np.ndarray       #: k x 2 [exceedance %, sorted flow ascending]
    r2fdc: float          #: log-slope of the FDC between 33% and 66%
    irh: float            #: hydrological regulation index
    ptile: np.ndarray     #: flows at exceedance 95,75,66,50,33,25,10 %


def fdc(q) -> FDCResult:
    """Flow duration curve with Gringorten positions + cubic-spline
    percentiles (iMHEA_FDC). ``ptile[i]`` is the flow exceeded
    [95,75,66,50,33,25,10][i] percent of the time."""
    q = np.asarray(q, dtype=float)
    q = np.sort(q[~np.isnan(q)])
    k = len(q)
    if k < 2:
        raise ValueError("FDC needs at least 2 valid samples")
    exceed = 100.0 * (1 - (np.arange(1, k + 1) - 0.44) / (k + 0.12))
    curve = np.column_stack([exceed, q])

    # not-a-knot cubic spline of flow vs exceedance (x must be increasing)
    cs = CubicSpline(exceed[::-1], q[::-1])          # MATLAB spline default
    ptile = cs(np.array([95.0, 75, 66, 50, 33, 25, 10]))

    with np.errstate(divide="ignore", invalid="ignore"):
        if ptile[2] < 0 or ptile[4] < 0:             # complex in MATLAB
            r2fdc = -np.inf
        else:
            r2fdc = (np.log10(ptile[2]) - np.log10(ptile[4])) / (0.66 - 0.33)

    aux = np.where(exceed < 50, ptile[3], q)         # cap high-flow half
    irh = float(aux.sum() / q.sum()) if q.sum() else np.nan
    return FDCResult(curve, float(r2fdc), irh, ptile)


# ------------------------------------------------------------------- IDC ---

def idc(dates, p) -> tuple[np.ndarray, float, float]:
    """Maximum intensity-duration curve from a (nominally 5-min) rain series.

    Returns (10x4 array [duration_min, max, mean, median mm/h], iM15m, iM1hr).
    The MATLAB stale-buffer bug contaminating the mean/median columns
    (CODE_REVIEW.md issue 4) is fixed here: each duration uses its own
    full rolling-sum vector. Durations longer than the record yield NaN.
    """
    from .aggregate import aggregate  # deferred: module init order

    dates = mtime.to_datetime_index(dates)
    p = np.asarray(p, dtype=float)
    step_min = np.median(np.diff(dates.asi8)) / 60e9
    if round(step_min, 1) != 5.0:
        keep = ~np.isnan(p) & (p != 0)               # drop gaps & dry samples
        agg = aggregate(dates[keep], p[keep], 5)     # -> voidless 5-min grid
        vp = np.nan_to_num(agg.p)
    else:
        vp = np.nan_to_num(p)                        # gaps = dry periods

    out = np.full((len(IDC_DURATIONS), 4), np.nan)
    out[:, 0] = IDC_DURATIONS * 5.0
    kern_ones = np.ones
    for i, d in enumerate(IDC_DURATIONS):
        if len(vp) < d:
            continue
        u = np.convolve(vp, kern_ones(d), mode="valid")
        out[i, 1] = u.max() * 12.0 / d
        wet = u[u > 1e-12]
        if len(wet):
            out[i, 2] = wet.mean() * 12.0 / d
            out[i, 3] = np.median(wet) * 12.0 / d
    im15m = float(out[IDC_DURATIONS == 3, 1][0])
    im1hr = float(out[IDC_DURATIONS == 12, 1][0])
    return out, im15m, im1hr


# ----------------------------------------------------------------- Pulse ---

@dataclass
class PulseResult:
    """Stats vectors are ``[total, mean, min, max, cv]`` (iMHEA order)."""
    mh: np.ndarray  #: high-pulse peak magnitudes [unit of Q]
    vh: np.ndarray  #: high-pulse excess volumes [Q-unit x day]
    fh: np.ndarray  #: high pulses per calendar year
    dh: np.ndarray  #: high-pulse durations [day]
    th: float       #: longest spell without a high pulse [day]
    ml: np.ndarray
    vl: np.ndarray
    fl: np.ndarray
    dl: np.ndarray
    tl: float


def _stats5(x: np.ndarray) -> np.ndarray:
    if len(x) == 0:
        return np.zeros(5)
    m = x.mean()
    sd = x.std(ddof=1) if len(x) > 1 else 0.0          # MATLAB std (N-1)
    cv = sd / m if m else 0.0
    return np.array([x.sum(), m, x.min(), x.max(), cv])


def pulse(dates, q, lim: float, *, matlab_compat: bool = False) -> PulseResult:
    """High/low pulse statistics against a threshold (iMHEA_Pulse).

    High pulse: contiguous run with ``Q >= lim`` (threshold counts as high).
    Each sample owns the interval to the next timestamp; the final sample
    has zero width. Fixed vs MATLAB (CODE_REVIEW.md issue 3): calendar-year
    counts use the NaN-filtered series (no misalignment), and TH/TL report
    the *maximum* duration of the opposite pulse class ("longest spell
    without"); ``matlab_compat=True`` restores the minimum. Volumes across
    removed NaN gaps still span the gap interval (faithful).
    """
    dates = mtime.to_datetime_index(dates)
    q = np.asarray(q, dtype=float)
    keep = ~np.isnan(q)
    dates, q = dates[keep], q[keep]
    if len(q) == 0:
        z = np.zeros(5)
        return PulseResult(z, z, z, z, 0.0, z, z, z, z, 0.0)

    t = mtime.datenum(dates)                          # days, float
    t_next = np.append(t[1:], t[-1])                  # duplicated last stamp
    mod = q - lim
    is_high = mod >= 0

    # run-length encoding of the classification
    change = np.flatnonzero(np.diff(is_high.astype(np.int8))) + 1
    starts = np.concatenate(([0], change))
    ends = np.concatenate((change, [len(q)]))         # exclusive

    years_all = np.arange(dates.year.min(), dates.year.max() + 1)

    def _side(high: bool):
        sel = [(s, e) for s, e in zip(starts, ends) if is_high[s] == high]
        if not sel:
            z = np.zeros(5)
            return z, z, z.copy(), z.copy()
        peaks, vols, durs, yrs = [], [], [], []
        for s, e in sel:
            seg = mod[s:e]
            peaks.append(q[s:e].max() if high else q[s:e].min())
            nxt = np.append(seg[1:], mod[e] if e < len(mod) else seg[-1])
            w = t_next[s:e] - t[s:e]
            clip = np.maximum if high else np.minimum
            vols.append(np.sum(w * (clip(nxt, 0) + clip(seg, 0)) / 2))
            durs.append(t_next[e - 1] - t[s])
            yrs.append(dates[s].year)
        counts = np.array([np.sum(np.array(yrs) == y) for y in years_all],
                          dtype=float)
        return (_stats5(np.array(peaks)), _stats5(np.array(vols)),
                _stats5(counts), _stats5(np.array(durs)))

    mh, vh, fh, dh = _side(True)
    ml, vl, fl, dl = _side(False)
    i_dur = 2 if matlab_compat else 3                 # min vs max duration
    tl = float(dh[i_dur])                             # no-low spell ~ high dur
    th = float(dl[i_dur])
    return PulseResult(mh, vh, fh, dh, th, ml, vl, fl, dl, tl)


# --------------------------------------------------------------- Monthly ---

@dataclass
class MonthlyResult:
    years: np.ndarray        #: calendar years spanned (incl. empty ones)
    per_year: np.ndarray     #: annual mean (flow) or total (rain) per year
    avg_month: np.ndarray    #: 12 sample-count-weighted monthly values
    avg_year: float          #: mean of the annual values (NaN-skipping)
    matrix: np.ndarray       #: years x 12 monthly values
    ymin: np.ndarray         #: [year, annual min, day-of-year] per year
    ymax: np.ndarray         #: [year, annual max, day-of-year] per year


def _monthly(dates, v, how: str, *, matlab_compat: bool) -> MonthlyResult:
    dates = mtime.to_datetime_index(dates)
    v = np.asarray(v, dtype=float)
    yr, mo = dates.year.to_numpy(), dates.month.to_numpy()
    years = np.arange(yr.min(), yr.max() + 1)
    n = len(years)

    matrix = np.full((n, 12), np.nan)
    weights = np.zeros((n, 12))
    per_year = np.full(n, np.nan)
    ymin = np.full((n, 3), np.nan)
    ymax = np.full((n, 3), np.nan)

    for i, y in enumerate(years):
        my = yr == y
        vy = v[my]
        valid = ~np.isnan(vy)
        if how == "sum":
            # rain: fixed -> NaN for empty years (MATLAB nansum gives 0,
            # indistinguishable from dry: CODE_REVIEW.md issue 11)
            per_year[i] = (np.nansum(vy) if valid.any() or matlab_compat
                           else np.nan)
        else:
            per_year[i] = np.nanmean(vy) if valid.any() else np.nan
        if valid.any():
            dy = dates[my]
            jmin = np.nanargmin(vy)
            jmax = np.nanargmax(vy)
            ymin[i] = [y, vy[jmin], dy[jmin].dayofyear]  # fixed: issue 2
            ymax[i] = [y, vy[jmax], dy[jmax].dayofyear]
        for j in range(12):
            mm = my & (mo == j + 1)
            vm = v[mm]
            ok = ~np.isnan(vm)
            if how == "sum":
                matrix[i, j] = (np.nansum(vm)
                                if ok.any() or matlab_compat else np.nan)
            else:
                matrix[i, j] = np.nanmean(vm) if ok.any() else np.nan
            weights[i, j] = mm.sum() if matlab_compat else ok.sum()

    with np.errstate(invalid="ignore", divide="ignore"):
        num = np.nansum(np.where(np.isnan(matrix), np.nan, matrix) * weights,
                        axis=0)
        den = weights.sum(axis=0)
        avg_month = np.where(den > 0, num / den, np.nan)
    avg_year = float(np.nanmean(per_year)) if np.any(~np.isnan(per_year)) \
        else np.nan
    return MonthlyResult(years, per_year, avg_month, avg_year, matrix,
                         ymin, ymax)


def monthly_flow(dates, q, *, matlab_compat: bool = False) -> MonthlyResult:
    """Monthly/annual mean flows (iMHEA_MonthlyFlow). The MATLAB
    day-of-year subset-indexing bug is fixed (issue 2)."""
    return _monthly(dates, q, "mean", matlab_compat=matlab_compat)


def monthly_rain(dates, p, *, matlab_compat: bool = False) -> MonthlyResult:
    """Monthly/annual rainfall totals (iMHEA_MonthlyRain). Fixed: empty
    months/years yield NaN, not 0 mm (issue 11); ``matlab_compat=True``
    restores the 0-mm behaviour."""
    return _monthly(dates, p, "sum", matlab_compat=matlab_compat)
