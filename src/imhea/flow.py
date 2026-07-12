"""Discharge processing: stage-discharge rating and baseflow separation.

- level2flow: iMHEA_Level2Flow (compound sharp-crested weir: 90-degree
  V-notch, Kindsvater-Shen, inside a rectangular section).
- baseflow_chapman: iMHEA_BaseFlow (Chapman 1999 two-parameter filter).
- baseflow_ukih: iMHEA_BaseFlowUK (UKIH/Gustard 1992 smoothed minima).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d

from . import mtime

log = logging.getLogger(__name__)

#: default rating coefficients (C1, e1, C2, e2) for a 90-degree V-notch
DEFAULT_COEFF = (1.37, 2.5, 1.77, 1.5)
#: default weir dimensions (a = V-notch height, b = rectangular width) [m]
DEFAULT_WEIR = (0.30, 1.00)


def level2flow(wl_cm, weir=DEFAULT_WEIR, coeff=DEFAULT_COEFF, *,
               matlab_compat: bool = False) -> np.ndarray:
    """Water level [cm] -> discharge [l/s] through a compound weir.

    Within the V-notch (WL <= a):  Q = C1 * WL^e1            [m3/s]
    Above it:  Q = C1*(WL^e1 - (WL-a)^e1) + C2*b*(WL-a)^e2   [m3/s]

    Fixed behaviour (default): NaN levels stay NaN; negative levels are
    clipped to zero discharge with a warning. ``matlab_compat=True``
    reproduces the MATLAB zero-fill of NaN samples (CODE_REVIEW.md issue 7;
    negative stages, which produce complex numbers in MATLAB, are still
    clipped here).
    """
    a, b = weir[0], weir[1]
    c1, e1, c2, e2 = coeff
    wl = np.asarray(wl_cm, dtype=float) / 100.0     # cm -> m

    neg = wl < 0
    if neg.any():
        log.warning("level2flow: %d negative stage values clipped to 0 l/s",
                    int(neg.sum()))
    wlc = np.where(neg, 0.0, wl)

    with np.errstate(invalid="ignore"):
        low = c1 * wlc ** e1
        high = c1 * (wlc ** e1 - (wlc - a) ** e1) + c2 * b * (wlc - a) ** e2
        q = np.where(wlc > a, high, low) * 1000.0   # m3/s -> l/s

    if matlab_compat:
        q = np.where(np.isnan(wl), 0.0, q)
    return q


# ---------------------------------------------------------------------------
# Baseflow separation
# ---------------------------------------------------------------------------

def recession_constant(dates, q, window_days: float, *,
                       r2_min: float = 0.8) -> float:
    """Master recession constant k [-] per time step (iMHEA convention).

    For every sample, log-flow is regressed on time over the forward
    date-bounded window; behavioural windows need R^2 >= 0.8 and negative
    slope; k = exp(max behavioural slope x timestep) — the *slowest*
    recession. Returns NaN if no behavioural window exists.
    """
    t = mtime.datenum(dates)                          # days
    with np.errstate(divide="ignore", invalid="ignore"):
        y = np.log(np.asarray(q, dtype=float))
    step = t[1] - t[0]
    ends = np.searchsorted(t, t + window_days, side="left")
    best = -np.inf
    for i in range(len(t)):
        j = ends[i]
        if j - i < 2:
            continue
        xs, ys = t[i:j], y[i:j]
        if not np.all(np.isfinite(ys)):
            continue                                  # zero/NaN flows: as in
        n = j - i                                     # MATLAB, non-behavioural
        sx, sy = xs.sum(), ys.sum()
        vx = n * (xs * xs).sum() - sx * sx
        vy = n * (ys * ys).sum() - sy * sy
        cov = n * (xs * ys).sum() - sx * sy
        if vx <= 0 or vy <= 0:
            continue
        r2 = cov * cov / (vx * vy)
        slope = cov / vx
        if r2 >= r2_min and slope < 0:
            best = max(best, slope)
    return float(np.exp(best * step)) if np.isfinite(best) else np.nan


@dataclass
class BaseflowResult:
    dates: pd.DatetimeIndex
    bq: np.ndarray        #: baseflow
    sq: np.ndarray        #: stormflow (q - bq)
    bfi: float            #: baseflow index
    k: float              #: recession constant per time step


def baseflow_chapman(dates, q) -> BaseflowResult:
    """Chapman (1999) two-parameter filter baseflow (iMHEA_BaseFlow).

    ``BQ_i = min(k/(1+C) BQ_{i-1} + C/(1+C) Q_i, Q_i)`` with C = 0.085 x
    timestep [days] and BQ_1 = Q_1; k from 7-day recession regressions.
    Expects a regular, NaN-free series (as produced by ProcessQ).
    Returns all-NaN when no behavioural recession exists.
    """
    dates = mtime.to_datetime_index(dates)
    q = np.asarray(q, dtype=float)
    k = recession_constant(dates, q, 7.0)
    step = float(np.diff(mtime.datenum(dates[:2]))[0])
    if np.isnan(k):
        log.warning("baseflow_chapman: no behavioural recession found")
        nan = np.full(len(q), np.nan)
        return BaseflowResult(dates, nan, nan.copy(), np.nan, np.nan)
    c = 0.085 * step
    a, b = k / (1 + c), c / (1 + c)
    bq = np.empty(len(q))
    bq[0] = q[0]
    for i in range(1, len(q)):                        # inherently sequential
        bq[i] = min(a * bq[i - 1] + b * q[i], q[i])
    sq = q - bq
    sq[0] = 0.0
    bfi = float(bq.sum() / q.sum()) if q.sum() else np.nan
    return BaseflowResult(dates, bq, sq, bfi, k)


def baseflow_ukih(dates, q, *,
                  matlab_compat: bool = False) -> BaseflowResult:
    """UKIH / Gustard et al. (1992) smoothed-minima baseflow
    (iMHEA_BaseFlowUK), on daily-averaged flow.

    5-day non-overlapping blocks; block minima (labelled at block END
    dates, as in MATLAB) are turning points iff 0.9 x min <= both
    neighbours; the baseflow line linearly interpolates turning points
    (with extrapolation), clipped to total flow and to >= 0 (the >=0 clip
    is a fix; matlab_compat allows negative extrapolation). The last
    turning point is dropped (MATLAB behaviour, kept: affects published
    BFI). The recession constant is always computed (5-day windows on
    log-baseflow), fixing the k/block-count output overload (issue 9).
    """
    from .aggregate import average

    daily = average(dates, np.asarray(q, dtype=float), 1440)
    ddate, dq1 = daily.dates, daily.p
    dnum = mtime.datenum(ddate)
    dq = np.where(np.isnan(dq1), np.inf, dq1)         # gaps never minima

    edges = np.arange(dnum[0], dnum[-1] + 1e-9, 5.0)  # DI:5:DF
    if len(edges) < 4:
        nan = np.full(len(dq1), np.nan)
        return BaseflowResult(ddate, nan, nan.copy(), np.nan, np.nan)
    qmin = np.array([np.nanmin(dq[(dnum >= edges[i - 1]) & (dnum < edges[i])])
                     if np.any((dnum >= edges[i - 1]) & (dnum < edges[i]))
                     else np.inf
                     for i in range(1, len(edges))])
    tdate = edges[1:]                                  # block END labels

    keep = np.ones(len(qmin), dtype=bool)
    for i in range(1, len(qmin) - 1):                  # first & last untested
        if 0.9 * qmin[i] > qmin[i - 1] or 0.9 * qmin[i] > qmin[i + 1]:
            keep[i] = False
    tp_t, tp_q = tdate[keep], qmin[keep]
    tp_t, tp_q = tp_t[:-1], tp_q[:-1]                  # drop last (MATLAB)
    if not matlab_compat:
        # fix: all-gap blocks (Inf minima) are not turning points
        finite = np.isfinite(tp_q)
        tp_t, tp_q = tp_t[finite], tp_q[finite]
    if len(tp_t) < 2:
        nan = np.full(len(dq1), np.nan)
        return BaseflowResult(ddate, nan, nan.copy(), np.nan, np.nan)

    if matlab_compat:
        # MATLAB interp1 with Inf knots (from all-gap 5-day blocks), IEEE
        # semantics: days on the rising side of an Inf knot -> Inf (then
        # clipped to total flow: baseflow == total flow, the artifact that
        # inflates published BFI1); falling side -> NaN.
        seg = np.clip(np.searchsorted(tp_t, dnum, side="right") - 1,
                      0, len(tp_t) - 2)
        x0, x1 = tp_t[seg], tp_t[seg + 1]
        y0, y1 = tp_q[seg], tp_q[seg + 1]
        with np.errstate(invalid="ignore"):
            bq = y0 + (y1 - y0) * (dnum - x0) / (x1 - x0)
    else:
        bq = interp1d(tp_t, tp_q, kind="linear",
                      fill_value="extrapolate")(dnum)
    with np.errstate(invalid="ignore"):
        bq = np.where(bq > dq, dq, bq)                 # clip to total flow
    if not matlab_compat:
        bq = np.maximum(bq, 0.0)                       # fix: no negative BQ
    bq[np.isnan(dq1)] = np.nan
    sq = dq1 - bq

    k = recession_constant(ddate, np.where(bq <= 0, np.nan, bq), 5.0)
    span = (dnum >= tp_t[0]) & (dnum <= tp_t[-1])
    va = np.nansum(dq1[span])
    bfi = float(np.nansum(bq[span]) / va) if va else np.nan
    return BaseflowResult(ddate, bq, sq, bfi, k)
