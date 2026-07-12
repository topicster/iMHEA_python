"""Hydrological and climate indices (iMHEA ProcessP/ProcessQ, Indices,
IndicesPlus, IndicesTotal, ClimateP, ClimateTotal, Pair).

The output orders are load-bearing: they match the row order of the
published ``iMHEA_Indices_Hydro.csv`` (59 indices) and
``iMHEA_Indices_Climate.csv`` (rows 1-13). See docs/review/D_indices.md.

Deviations from MATLAB (defaults; each documented in CODE_REVIEW.md §4):
- FH7 uses the total pulse count like its siblings (not the double-
  normalised per-year mean) — issue 5;
- TL1/TL2 use correct day-of-year values (issue 2 fix in stats.monthly);
- QYEAR NaN-fallback is in mm/yr (x365) and RRa is computed after it
  (issue 6);
- RA6/RA7 exclude non-finite log-ratios (zero flows) instead of feeding
  +/-Inf medians (issue 13).
Set ``matlab_compat=True`` to restore MATLAB behaviour where feasible.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import mtime
from .aggregate import aggregate, average
from .flow import baseflow_chapman, baseflow_ukih
from .stats import fdc as _fdc
from .stats import idc as _idc
from .stats import monthly_flow, monthly_rain, pulse

log = logging.getLogger(__name__)

MDAYS = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])

HYDRO_NAMES = [
    "QDMIN", "Q95", "DAYQ0", "PQ0", "QMDRY", "QDMAX", "Q10", "QDMY", "QDML",
    "Q50", "BFI1", "K1", "BFI2", "K2", "RANGE", "R2FDC", "IRH", "RBI1",
    "RBI2", "DRYQMEAN", "DRYQWET", "SINDQ", "QYEAR", "RRa", "RRm", "RRl",
    "MA5", "MA41", "MA3", "MA11", "ML17", "ML21", "ML18", "MH16", "MH14",
    "MH22", "MH27", "FL3", "FL2", "FL1", "FH3", "FH6", "FH7", "FH2", "FH1",
    "DL17", "DL16", "DL13", "DH13", "DH16", "DH20", "DH15", "TH3", "TL2",
    "TL1", "RA8", "RA5", "RA6", "RA7",
]
CLIMATE_NAMES = [
    "PYEAR", "DAYP0", "PP0", "PMDRY", "SINDX", "PVAR", "RMED1D", "RMED2D",
    "RMED1H", "iMAX1D", "iMAX2D", "iMAX1H", "iMAX15M",
]

_LS_KM2_TO_MM_DAY = 86400.0 / 1e6   # 1 l/s/km2 = 0.0864 mm/day


@dataclass
class ProcessPResult:
    indices: pd.Series      #: PYEAR,DAYP0,PP0,PMDRY,SINDX,iM15m,iM1hr
    pm: np.ndarray          #: 12 monthly precipitation climatology [mm]
    idc: np.ndarray         #: intensity-duration curve (10x4)
    cum_p: pd.Series        #: daily cumulative precipitation [mm]
    dp: pd.Series           #: daily precipitation, NaN days removed [mm]


def process_p(dates, p) -> ProcessPResult:
    """Precipitation indices (iMHEA_ProcessP)."""
    dates = mtime.to_datetime_index(dates)
    p = np.asarray(p, dtype=float)

    daily = aggregate(dates, p, 1440)
    cum_p = pd.Series(daily.cum, index=daily.dates)
    valid = ~np.isnan(daily.p)
    new_p = daily.p[valid]
    k = len(new_p)
    dp = pd.Series(new_p, index=daily.dates[valid])

    day_p0 = int(np.floor(365 * (new_p == 0).sum() / k)) if k else 0
    pp0 = day_p0 / 365.0

    ok = ~np.isnan(p)
    mres = monthly_rain(dates[ok], p[ok])
    pm = mres.avg_month
    pm_dry = np.nanmin(pm)
    p_year = pm.sum()                                  # NaN-propagating
    if np.isnan(p_year):
        p_year = 365.0 * new_p.mean()
    sindx = (6 / 11) * np.abs(pm - p_year / 12).sum() / p_year

    idc_arr, im15m, im1hr = _idc(dates, p)
    s = pd.Series([p_year, day_p0, pp0, pm_dry, sindx, im15m, im1hr],
                  index=["PYEAR", "DAYP0", "PP0", "PMDRY", "SINDX",
                         "iM15m", "iM1hr"])
    return ProcessPResult(s, pm, idc_arr, cum_p, dp)


@dataclass
class ProcessQResult:
    indices: pd.Series      #: 22 flow indices (HYDRO_NAMES[:22])
    qm: np.ndarray          #: 12 monthly mean flows [l/s(/km2)]
    fdc: np.ndarray         #: flow duration curve
    cum_q: pd.Series        #: daily cumulative flow
    dq: pd.DataFrame        #: daily [Q, BQ, SQ] incl. NaN days


def process_q(dates, q, area: float | None = None) -> ProcessQResult:
    """Discharge indices (iMHEA_ProcessQ). ``area`` [km2] normalises to
    l/s/km2 when given."""
    dates = mtime.to_datetime_index(dates)
    q = np.asarray(q, dtype=float)
    if area is not None:
        q = q / area

    daily = average(dates, q, 1440)
    qdml, qdmax, qdmin = daily.mean, daily.max, daily.min
    rng = qdmax / qdmin if qdmin else np.inf
    cum_q = pd.Series(daily.cum, index=daily.dates)
    valid = ~np.isnan(daily.p)
    new_dates, new_q = daily.dates[valid], daily.p[valid]
    l = len(new_q)

    day_q0 = int(np.floor(365 * (new_q == 0).sum() / l)) if l else 0
    pq0 = day_q0 / 365.0

    ok = ~np.isnan(q)
    mres = monthly_flow(dates[ok], q[ok])
    qm, qdmy = mres.avg_month, mres.avg_year
    qm_dry = np.nanmin(qm)
    if np.isnan(qdmy):
        qdmy = qm.mean()
    if np.isnan(qdmy):
        qdmy = new_q.mean()
    dry_qmean = qm_dry / np.nanmean(qm)
    dry_qwet = qm_dry / np.nanmax(qm)
    sindq = (6 / 11) * np.abs(qm - qdmy).sum() / (12 * qdmy)

    f = _fdc(new_q)
    q95, q50, q10 = f.ptile[0], f.ptile[3], f.ptile[6]

    uk = baseflow_ukih(dates, q)                      # raw series (as MATLAB)
    ch = baseflow_chapman(new_dates, new_q)
    bfi1, k1, bfi2, k2 = uk.bfi, uk.k, ch.bfi, ch.k

    # Richards-Baker flashiness on the gap-stripped daily series (faithful:
    # diffs straddle removed gaps)
    dq_abs = np.abs(np.diff(new_q))
    rbi1 = dq_abs.sum() / new_q[1:].sum()
    rbi2 = (0.5 * (dq_abs[:-1] + dq_abs[1:])).sum() / new_q[1:-1].sum()

    # align UKIH baseflow onto the full daily grid
    bq = pd.Series(uk.bq, index=uk.dates).reindex(daily.dates).to_numpy()
    sq = pd.Series(uk.sq, index=uk.dates).reindex(daily.dates).to_numpy()
    dq_df = pd.DataFrame({"Q": daily.p, "BQ": bq, "SQ": sq},
                         index=daily.dates)

    vals = [qdmin, q95, day_q0, pq0, qm_dry, qdmax, q10, qdmy, qdml, q50,
            bfi1, k1, bfi2, k2, rng, f.r2fdc, f.irh, rbi1, rbi2,
            dry_qmean, dry_qwet, sindq]
    return ProcessQResult(pd.Series(vals, index=HYDRO_NAMES[:22]),
                          qm, f.fdc, cum_q, dq_df)


def indices_plus(dates, q, area: float | None = None, *,
                 matlab_compat: bool = False) -> pd.Series:
    """Olden & Poff (2003) magnitude/frequency/duration/timing/rate indices
    (iMHEA_IndicesPlus), from daily mean flow. Returns the 33 values in
    HYDRO_NAMES[26:] order (MA5..RA7)."""
    dates = mtime.to_datetime_index(dates)
    q = np.asarray(q, dtype=float)
    if area is not None:
        q = q / area
    daily = average(dates, q, 1440)
    qdml = daily.mean
    valid = ~np.isnan(daily.p)
    nd, nq = daily.dates[valid], daily.p[valid]
    t = mtime.datenum(nd)

    ma2 = float(np.median(nq))
    if ma2 == 0:
        ma2 = qdml
        log.warning("median flow is 0; using the mean (MA2)")
    ma3 = nq.std(ddof=1) / qdml
    ma5 = qdml / ma2

    pt = _fdc(nq).ptile
    q75, q25, q10 = pt[1], pt[5], pt[6]
    mh16 = q10 / ma2
    ma11 = (q25 - q75) / ma2

    mres = monthly_flow(nd, nq)
    month_median = float(np.median(mres.avg_month))
    ma41 = float(mres.per_year.mean())                 # NaN if empty years

    def _roll(win):
        ends = np.searchsorted(t, t + win, side="left")
        mx = np.array([nq[i:j].max() for i, j in enumerate(ends)])
        mn = np.array([nq[i:j].min() for i, j in enumerate(ends)])
        return mx, mn

    max30, min30 = _roll(30.0)
    dh13 = max30.mean() / ma2
    dl13 = min30.mean() / ma2
    ml21 = min30.std(ddof=1) / min30.mean()
    mh14 = float(np.median(max30)) / ma2
    _, min7 = _roll(7.0)
    ml17 = min7.min() / ma41
    ml18 = min7.std(ddof=1) / min7.mean()

    ymin_doy = mres.ymin[~np.isnan(mres.ymin[:, 2]), 2]
    tl1 = float(np.median(ymin_doy))
    tl2 = float(ymin_doy.std(ddof=1) / ymin_doy.mean())

    span = t[-1] - t[0]
    kw = dict(matlab_compat=matlab_compat)
    pu = pulse(nd, nq, q25, **kw)
    mh27 = pu.mh[1] / ma2
    fh1 = pu.fh[0] * 365 / (span + 1)
    fh2 = pu.fh[4]
    dh15, dh16 = pu.dh[1], pu.dh[4]
    pu = pulse(nd, nq, 3 * ma2, **kw)
    fh3 = pu.fh[0] * 365 / span                        # MATLAB: no +1 here
    mh22 = pu.vh[1] / ma2
    pu = pulse(nd, nq, 3 * month_median, **kw)
    fh6 = pu.fh[0] * 365 / (span + 1)
    pu = pulse(nd, nq, 7 * month_median, **kw)
    fh7 = (pu.fh[1] * 365 / (span + 1) if matlab_compat   # issue 5
           else pu.fh[0] * 365 / (span + 1))
    pu = pulse(nd, nq, q75, **kw)
    fl1 = pu.fl[0] * 365 / span                        # MATLAB: no +1 here
    fl2 = pu.fl[4]
    dl16, dl17 = pu.dl[1], pu.dl[4]
    pu = pulse(nd, nq, 0.05 * qdml, **kw)
    fl3 = pu.fl[0] * 365 / (span + 1)
    pu = pulse(nd, nq, ma2 / 0.75, **kw)
    dh20 = pu.dh[1]
    pu = pulse(nd, nq, q10, **kw)
    th3 = pu.th / 365.0

    with np.errstate(divide="ignore", invalid="ignore"):
        dlog = np.diff(np.log(nq))
    if not matlab_compat:
        dlog = dlog[np.isfinite(dlog)]                 # issue 13: log(0)
    ra6 = float(np.median(dlog[dlog > 0])) if np.any(dlog > 0) else np.nan
    ra7 = float(np.median(dlog[dlog < 0])) if np.any(dlog < 0) else np.nan
    d = np.diff(nq)
    ra5 = float((d > 0).sum()) / (span + 1)
    sgn = np.sign(d[d != 0])                           # equal flows: no flip
    reversals = 1 + int((np.diff(sgn) != 0).sum()) if len(sgn) else 0
    ra8 = reversals / (span + 1)

    vals = [ma5, ma41, ma3, ma11, ml17, ml21, ml18, mh16, mh14, mh22, mh27,
            fl3, fl2, fl1, fh3, fh6, fh7, fh2, fh1,
            dl17, dl16, dl13, dh13, dh16, dh20, dh15,
            th3, tl2, tl1, ra8, ra5, ra6, ra7]
    return pd.Series(vals, index=HYDRO_NAMES[26:])


def climate_p(dates, p) -> pd.Series:
    """Extreme-rainfall climate indices (iMHEA_ClimateP):
    RMED1D, RMED2D, RMED1H, iMAX1D, iMAX2D, iMAX1H, PVAR."""
    dates = mtime.to_datetime_index(dates)
    p = np.asarray(p, dtype=float)
    d_daily = aggregate(dates, p, 1440)
    d_hour = aggregate(dates, p, 60)

    vd = ~np.isnan(d_daily.p)
    nd, np_ = d_daily.dates[vd], d_daily.p[vd]
    vh = ~np.isnan(d_hour.p)
    nh, nph = d_hour.dates[vh], d_hour.p[vh]

    pvar = np_.std(ddof=1) / np_.mean()

    t = mtime.datenum(nd)
    ends = np.searchsorted(t, t + 2.0, side="left")
    sum2d = np.array([np_[i:j].sum() for i, j in enumerate(ends)])

    rmed1d = float(np.nanmedian(monthly_rain(nd, np_).ymax[:, 1]))
    rmed2d = float(np.nanmedian(monthly_rain(nd, sum2d).ymax[:, 1]))
    rmed1h = float(np.nanmedian(monthly_rain(nh, nph).ymax[:, 1]))

    from .stats import IDC_DURATIONS
    idc_arr, _, _ = _idc(dates, p)
    imax1d = float(idc_arr[IDC_DURATIONS == 288, 1][0])
    imax2d = float(idc_arr[IDC_DURATIONS == 576, 1][0])
    imax1h = float(idc_arr[IDC_DURATIONS == 12, 1][0])

    return pd.Series([rmed1d, rmed2d, rmed1h, imax1d, imax2d, imax1h, pvar],
                     index=["RMED1D", "RMED2D", "RMED1H", "iMAX1D",
                            "iMAX2D", "iMAX1H", "PVAR"])


def _compile_climate(ip: pd.Series, cp: pd.Series) -> pd.Series:
    """Shared 13-element climate compilation (IndicesTotal/ClimateTotal)."""
    vals = np.concatenate([ip.iloc[0:5], [cp.iloc[6]], cp.iloc[0:6],
                           [ip.iloc[5]]])
    return pd.Series(vals, index=CLIMATE_NAMES)


def climate_total(dates, p) -> pd.Series:
    """13 climate indices, rows 1-13 of iMHEA_Indices_Climate.csv
    (iMHEA_ClimateTotal)."""
    return _compile_climate(process_p(dates, p).indices, climate_p(dates, p))


@dataclass
class CatchmentIndices:
    hydro: pd.Series        #: 59 indices (HYDRO_NAMES order)
    climate: pd.Series      #: 13 indices (CLIMATE_NAMES order)
    pm: np.ndarray          #: monthly precipitation [mm]
    qm_mm: np.ndarray       #: monthly flow converted to [mm/month]
    fdc: np.ndarray
    idc: np.ndarray
    cum_p: pd.Series
    cum_q_mm: pd.Series
    dp: pd.Series
    dq: pd.DataFrame


def indices_total(dates, p, q, area: float, *,
                  matlab_compat: bool = False) -> CatchmentIndices:
    """Full 59-hydro + 13-climate index compilation for one catchment
    (iMHEA_Indices + iMHEA_IndicesTotal)."""
    rp = process_p(dates, p)
    rq = process_q(dates, q, area)
    iq = rq.indices

    qyear = iq["QDMY"] * 365 * _LS_KM2_TO_MM_DAY       # l/s/km2 -> mm/yr
    if np.isnan(qyear):
        fb = np.nanmean(rq.dq["Q"]) * _LS_KM2_TO_MM_DAY
        qyear = fb if matlab_compat else fb * 365      # issue 6 (units)
    rra = (np.nan if (matlab_compat and np.isnan(iq["QDMY"]))
           else qyear / rp.indices["PYEAR"])           # issue 6 (ordering)
    qm_mm = rq.qm * MDAYS * _LS_KM2_TO_MM_DAY
    rrm = np.nansum(qm_mm) / np.nansum(rp.pm)
    rrl = (np.nanmean(rq.dq["Q"]) * _LS_KM2_TO_MM_DAY
           / np.nanmean(rp.dp.to_numpy()))

    plus = indices_plus(dates, q, area, matlab_compat=matlab_compat)
    hydro = pd.concat([iq, pd.Series(
        [qyear, rra, rrm, rrl], index=["QYEAR", "RRa", "RRm", "RRl"]), plus])
    hydro.index = HYDRO_NAMES                           # canonical order

    climate = _compile_climate(rp.indices, climate_p(dates, p))
    cum_q_mm = rq.cum_q * _LS_KM2_TO_MM_DAY
    return CatchmentIndices(hydro, climate, rp.pm, qm_mm, rq.fdc, rp.idc,
                            rp.cum_p, cum_q_mm, rp.dp, rq.dq)


def pair(dates1, p1, q1, a1, dates2, p2, q2, a2, *,
         matlab_compat: bool = False
         ) -> tuple[pd.DataFrame, pd.DataFrame, CatchmentIndices,
                    CatchmentIndices]:
    """Paired-catchment index comparison (iMHEA_Pair): each catchment is
    processed independently over its own record (by design). Everything is
    computed once (MATLAB recomputes each index 2-3 times)."""
    c1 = indices_total(dates1, p1, q1, a1, matlab_compat=matlab_compat)
    c2 = indices_total(dates2, p2, q2, a2, matlab_compat=matlab_compat)
    hydro = pd.DataFrame({"catchment_1": c1.hydro, "catchment_2": c2.hydro})
    climate = pd.DataFrame({"catchment_1": c1.climate,
                            "catchment_2": c2.climate})
    return hydro, climate, c1, c2
