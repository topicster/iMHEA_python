"""Catchment processing pipelines (iMHEA_Workflow, iMHEA_WorkflowRain,
iMHEA_WorkflowPair) and processed-CSV export.

Pipeline (iMHEA_Workflow):
  depure tips -> grid = rounded median discharge interval -> cubic-spline
  event disaggregation per gauge -> pairwise double-mass gap-filling ->
  gauge average -> discharge averaging -> daily/hourly products + UKIH
  baseflow -> 59+13 indices.

Fixed vs MATLAB (docs/review/E_workflows_plots.md):
- alignment by DatetimeIndex instead of the fragile whole-matrix ismember;
- WorkflowPair's scrambled FDC/IDC output capture (confirmed bug) cannot
  occur here: curves live in named CatchmentIndices fields.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd

from . import mtime
from .aggregate import aggregate, aggregate_events, average
from .clean import depure, fill_gaps
from .flow import baseflow_ukih
from .indices import CatchmentIndices, climate_total, indices_total
from .io import save_daily_csv, save_double_csv, save_single_csv

log = logging.getLogger(__name__)


@dataclass
class FillInfo:
    """Diagnostics of one double-mass gap-filling attempt."""
    pair: tuple[str, str]
    filled: bool
    r: float
    slope: float
    n_filled: tuple[int, int]
    notes: list


@dataclass
class WorkflowResult:
    hres: pd.DataFrame           #: [P mm, Q l/s/km2] at max resolution
    daily: pd.DataFrame          #: [P, Q, BQ]
    hourly: pd.DataFrame         #: [P, Q]
    scale_min: int               #: high-resolution interval [min]
    indices: CatchmentIndices | None = None
    climate: pd.Series | None = None
    fills: list[FillInfo] | None = None   #: gauge cross-fill diagnostics


@dataclass
class PairResult:
    hres: pd.DataFrame           #: [P1, Q1, P2, Q2]
    daily: pd.DataFrame          #: [P1, Q1, BQ1, P2, Q2, BQ2]
    hourly: pd.DataFrame         #: [P1, Q1, P2, Q2]
    scale_min: int
    hydro: pd.DataFrame | None = None     #: 59 x 2 indices
    climate: pd.DataFrame | None = None   #: 13 x 2 indices
    catchment_1: CatchmentIndices | None = None
    catchment_2: CatchmentIndices | None = None
    fills: list[FillInfo] | None = None   #: cross-catchment P fill diag


def _median_interval_min(dates) -> int:
    return int(round(np.nanmedian(np.diff(
        mtime.to_datetime_index(dates).asi8)) / 60e9))


def _gauge_average(gauges, scale_min: int, bucket: float,
                   fills: list | None = None) -> pd.Series:
    """Depure, disaggregate and cross-fill rain gauges; average them.

    ``gauges`` is a list of (dates, tips_mm). The average runs over all
    2*C(n,2) pairwise gap-filled columns, giving each gauge equal weight
    (iMHEA_Workflow lines 68-101). Fill diagnostics are appended to
    ``fills`` when a list is given.
    """
    series = []
    for dates, tips in gauges:
        d = mtime.to_datetime_index(dates)
        clean_tips = depure(d, np.asarray(tips, dtype=float))
        r = aggregate_events(d, clean_tips, scale_min=scale_min,
                             bucket=bucket)
        series.append(pd.Series(r.p, index=r.dates))
    if len(series) == 1:
        return series[0]
    cols = []
    for i, j in combinations(range(len(series)), 2):
        si, sj = series[i], series[j]
        r = fill_gaps(si.index, si.to_numpy(), sj.index, sj.to_numpy())
        if fills is not None:
            fills.append(FillInfo((f"gauge {i + 1}", f"gauge {j + 1}"),
                                  r.filled, r.r, r.slope, r.n_filled,
                                  r.notes))
        cols.append(pd.Series(r.p1, index=r.dates))
        cols.append(pd.Series(r.p2, index=r.dates))
    return pd.concat(cols, axis=1).mean(axis=1)      # nanmean across columns


def workflow(area: float, dates_q, q, bucket: float, gauges, *,
             name: str = "", compute_indices: bool = True,
             matlab_compat: bool = False) -> WorkflowResult:
    """Full single-catchment pipeline (iMHEA_Workflow).

    ``gauges`` = list of (dates, tips_mm) per rain gauge; ``q`` in l/s.
    """
    if not gauges:
        raise ValueError("at least one rain gauge is required")
    dq = mtime.to_datetime_index(dates_q)
    q = np.asarray(q, dtype=float)
    scale = _median_interval_min(dq)
    log.info("workflow %s: grid = %d min, %d gauges", name, scale,
             len(gauges))

    fills: list[FillInfo] = []
    p_hres = _gauge_average(gauges, scale, bucket, fills)
    qr = average(dq, q, scale)
    q_hres = pd.Series(qr.p, index=qr.dates)

    idx = p_hres.index.union(q_hres.index)
    hres = pd.DataFrame({"P": p_hres.reindex(idx),
                         "Q": q_hres.reindex(idx)})   # Q in l/s here

    daily, hourly = _products(hres, area, matlab_compat=matlab_compat)

    indices = climate = None
    if compute_indices:
        res = indices_total(idx, hres["P"].to_numpy(),
                            hres["Q"].to_numpy(), area,
                            matlab_compat=matlab_compat)
        indices, climate = res, res.climate

    hres["Q"] = hres["Q"] / area                     # l/s/km2 (last, as
    # in MATLAB line 141 — indices above received l/s + area)
    return WorkflowResult(hres, daily, hourly, scale, indices, climate,
                          fills)


def _products(hres: pd.DataFrame, area: float,
              p_col: str = "P", q_col: str = "Q", *,
              matlab_compat: bool = False) -> tuple[pd.DataFrame,
                                                    pd.DataFrame]:
    """Daily [P,Q,BQ] and hourly [P,Q] products from an hres frame."""
    idx = hres.index
    p = hres[p_col].to_numpy()
    qn = hres[q_col].to_numpy() / area
    out = []
    for scale in (1440, 60):
        ap = aggregate(idx, p, scale)
        aq = average(idx, qn, scale)
        df = pd.DataFrame({"P": ap.p}, index=ap.dates)
        df["Q"] = pd.Series(aq.p, index=aq.dates).reindex(ap.dates)
        out.append(df)
    daily, hourly = out
    uk = baseflow_ukih(idx, qn, matlab_compat=matlab_compat)
    daily["BQ"] = pd.Series(uk.bq, index=uk.dates).reindex(daily.index)
    return daily, hourly


def workflow_rain(bucket: float, gauges, *, scale_min: int = 5,
                  name: str = "", compute_climate: bool = True
                  ) -> WorkflowResult:
    """Precipitation-only pipeline (iMHEA_WorkflowRain), fixed 5-min grid."""
    fills: list[FillInfo] = []
    p = _gauge_average(gauges, scale_min, bucket, fills)
    hres = pd.DataFrame({"P": p})
    ad = aggregate(p.index, p.to_numpy(), 1440)
    ah = aggregate(p.index, p.to_numpy(), 60)
    daily = pd.DataFrame({"P": ad.p}, index=ad.dates)
    hourly = pd.DataFrame({"P": ah.p}, index=ah.dates)
    climate = (climate_total(p.index, p.to_numpy())
               if compute_climate else None)
    return WorkflowResult(hres, daily, hourly, scale_min, None, climate,
                          fills)


def workflow_pair(hres1: pd.DataFrame, hres2: pd.DataFrame, *,
                  compute_indices: bool = True,
                  matlab_compat: bool = False) -> PairResult:
    """Paired-catchment assimilation (iMHEA_WorkflowPair).

    Inputs are the ``hres`` frames of :func:`workflow` (columns P, Q with
    Q already in l/s/km2). The coarser catchment sets the grid; only
    precipitation is cross-filled (double-mass, R >= 0.99); discharge is
    never filled. Duration curves are returned correctly labelled per
    catchment (fixing the confirmed output-scramble bug in
    iMHEA_WorkflowPair line 104).
    """
    frames = [hres1.copy(), hres2.copy()]
    meds = [_median_interval_min(f.index) for f in frames]
    scale = int(max(meds))
    for i in (0, 1):                                  # resample finer one
        if meds[i] < scale:
            ap = aggregate(frames[i].index, frames[i]["P"].to_numpy(), scale)
            aq = average(frames[i].index, frames[i]["Q"].to_numpy(), scale)
            frames[i] = pd.DataFrame(
                {"P": ap.p,
                 "Q": pd.Series(aq.p, index=aq.dates).reindex(ap.dates)},
                index=ap.dates)
    f1, f2 = frames

    fill = fill_gaps(f1.index, f1["P"].to_numpy(),
                     f2.index, f2["P"].to_numpy())
    idx = fill.dates
    hres = pd.DataFrame({
        "P1": fill.p1, "Q1": f1["Q"].reindex(idx),
        "P2": fill.p2, "Q2": f2["Q"].reindex(idx)}, index=idx)

    d1, h1 = _products(hres, 1.0, "P1", "Q1", matlab_compat=matlab_compat)
    d2, h2 = _products(hres, 1.0, "P2", "Q2", matlab_compat=matlab_compat)
    daily = pd.DataFrame({"P1": d1["P"], "Q1": d1["Q"], "BQ1": d1["BQ"],
                          "P2": d2["P"], "Q2": d2["Q"], "BQ2": d2["BQ"]})
    hourly = pd.DataFrame({"P1": h1["P"], "Q1": h1["Q"],
                           "P2": h2["P"], "Q2": h2["Q"]})

    hydro = climate = c1 = c2 = None
    if compute_indices:
        from .indices import pair as _pair
        hydro, climate, c1, c2 = _pair(
            idx, hres["P1"].to_numpy(), hres["Q1"].to_numpy(), 1.0,
            idx, hres["P2"].to_numpy(), hres["Q2"].to_numpy(), 1.0,
            matlab_compat=matlab_compat)
    fills = [FillInfo(("catchment 1", "catchment 2"), fill.filled, fill.r,
                      fill.slope, fill.n_filled, fill.notes)]
    return PairResult(hres, daily, hourly, scale, hydro, climate, c1, c2,
                      fills)


# ---------------------------------------------------------------------------
# Export (replicating iMHEA_Save*CSV products)
# ---------------------------------------------------------------------------

def export_pair(out_dir, site: str, res: PairResult) -> list:
    """Write the six per-catchment processed CSVs for a pair
    (``iMHEA_<SITE>_0i_{HRes,1hr,1day}_processed.csv``)."""
    paths = []
    paths += save_double_csv(out_dir, f"{site}_HRes", res.hres.index,
                             res.hres[["P1", "Q1", "P2", "Q2"]].to_numpy())
    paths += save_double_csv(out_dir, f"{site}_1hr", res.hourly.index,
                             res.hourly.to_numpy())
    paths += save_daily_csv(out_dir, f"{site}_1day", res.daily.index,
                            res.daily.to_numpy())
    return paths


def export_catchment(out_dir, code: str, res: WorkflowResult) -> list:
    """Write single-catchment processed CSVs [Date, P, Q(, BQ)]."""
    from .io import _write_series_csv
    from pathlib import Path
    paths = []
    for tag, df in (("HRes", res.hres), ("1hr", res.hourly),
                    ("1day", res.daily)):
        path = Path(out_dir) / f"iMHEA_{code}_{tag}_processed.csv"
        cols = {"Rainfall mm": df["P"].to_numpy()}
        if "Q" in df:
            cols["Flow l/s/km2"] = df["Q"].to_numpy()
        if "BQ" in df:
            cols["Baseflow l/s/km2"] = df["BQ"].to_numpy()
        _write_series_csv(path, df.index, cols)
        paths.append(path)
    return paths


def export_single(out_dir, prefix: str, res: WorkflowResult) -> list:
    """Write rain-only processed CSVs (``iMHEA_<PREFIX>_*_processed.csv``)."""
    paths = [save_single_csv(out_dir, f"{prefix}_HRes", res.hres.index,
                             res.hres["P"].to_numpy())]
    paths.append(save_single_csv(out_dir, f"{prefix}_1hr",
                                 res.hourly.index,
                                 res.hourly["P"].to_numpy()))
    paths.append(save_single_csv(out_dir, f"{prefix}_1day",
                                 res.daily.index,
                                 res.daily["P"].to_numpy()))
    return paths
