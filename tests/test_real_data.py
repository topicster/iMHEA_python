"""Smoke tests against the real iMHEA dataset and MATLAB reference outputs.

Skipped automatically when the dataset folders are not present (the tests
locate them relative to this repository: ``../iMHEA_raw`` etc.).
Full reconciliation of the complete pipeline happens in Phase 4; these tests
guard the Phase-2 building blocks (reader, depure, event aggregation,
averaging, rating curve) against regressions using CHA_01, the only
single-rain-gauge catchment (no multi-gauge averaging in its reference).
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from imhea import (aggregate, aggregate_events, average, depure, level2flow,
                   read_processed_csv, read_raw_csv)


def _data_root() -> Path | None:
    for base in [Path(__file__).resolve().parents[2],
                 Path("/sessions/brave-gifted-pascal/mnt/Scripts")]:
        if (base / "iMHEA_raw").is_dir():
            return base
    return None


ROOT = _data_root()
pytestmark = pytest.mark.skipif(ROOT is None,
                                reason="iMHEA dataset not available")


def test_all_raw_files_parse():
    files = sorted((ROOT / "iMHEA_raw").glob("*/*.csv"))
    assert len(files) >= 90
    for f in files:
        df = read_raw_csv(f)
        assert len(df) > 0 and "value" in df


def test_cha01_daily_rainfall_vs_matlab():
    raw = read_raw_csv(ROOT / "iMHEA_raw/CHA/iMHEA_CHA_01_PT_01_raw.csv")
    p = depure(raw.index, raw["value"].to_numpy())
    r5 = aggregate_events(raw.index, p, scale_min=5, bucket=0.1)
    daily = aggregate(r5.dates, r5.p, 1440)
    py = pd.Series(daily.p, index=daily.dates)

    ref = read_processed_csv(
        ROOT / "iMHEA_processed/Daily/iMHEA_CHA_01_1day_processed.csv"
    )["Rainfall mm"]
    j = py.index.intersection(ref.index)
    both = (~py[j].isna()) & (~ref[j].isna())
    a, b = py[j][both], ref[j][both]

    assert both.sum() > 1500
    assert np.nansum(r5.p) == pytest.approx(np.nansum(raw["value"]), rel=1e-9)
    assert np.corrcoef(a, b)[0, 1] > 0.9999
    assert (a - b).abs().max() < 0.2          # day-boundary allocation only
    assert a.sum() == pytest.approx(b.sum(), abs=0.5)


def test_cha01_indices_vs_published():
    """Full indices_total run on CHA_01 vs the published index CSVs.

    Thresholds are loose where documented deviations apply (CODE_REVIEW.md
    §4 fixes; upstream P-grid reconciliation happens in Phase 4)."""
    import imhea

    rain = read_raw_csv(ROOT / "iMHEA_raw/CHA/iMHEA_CHA_01_PT_01_raw.csv")
    lvl = read_raw_csv(ROOT / "iMHEA_raw/CHA/iMHEA_CHA_01_HS_01_raw.csv")
    p = depure(rain.index, rain["value"].to_numpy())
    rp = aggregate_events(rain.index, p, scale_min=30, bucket=0.1)
    rq = average(lvl.index, lvl["Flow l/s"].to_numpy(), 30)
    P = pd.Series(rp.p, index=rp.dates)
    Q = pd.Series(rq.p, index=rq.dates)
    idx = P.index.union(Q.index)
    res = imhea.indices_total(idx, P.reindex(idx).to_numpy(),
                              Q.reindex(idx).to_numpy(), 0.9486)

    hyd = pd.read_csv(ROOT / "iMHEA_indices/iMHEA_Indices_Hydro.csv",
                      encoding="utf-8-sig")
    cli = pd.read_csv(ROOT / "iMHEA_indices/iMHEA_Indices_Climate.csv",
                      encoding="utf-8-sig")
    hyd.columns = [c.strip() for c in hyd.columns]
    cli.columns = [c.strip() for c in cli.columns]
    ref = pd.concat([
        pd.Series(hyd["CHA_01"].values[:59], index=imhea.HYDRO_NAMES),
        pd.Series(cli["CHA_01"].values[:13], index=imhea.CLIMATE_NAMES),
    ]).astype(float)
    py = pd.concat([res.hydro, res.climate])
    rel = (100 * (py - ref) / ref.abs()).replace([np.inf, -np.inf], np.nan)

    # documented intentional fixes / explained deviations
    explained = {"FH7", "TH3", "TL1", "TL2",       # bug fixes
                 "BFI1", "K1",                     # MATLAB Inf-turning-point
                 "MH22",                           # upstream sensitivity
                 "RMED1D", "RMED2D", "RMED1H",     # upstream P grid
                 "iMAX1D", "iMAX2D", "iMAX1H", "iMAX15M"}
    resid = rel[~rel.index.isin(explained)].dropna()
    assert (resid.abs() <= 1.0).all(), resid[resid.abs() > 1]
    assert (rel.dropna().abs() <= 0.1).sum() >= 55  # bulk matches tightly


def test_cha01_daily_flow_via_rating_curve_vs_matlab():
    raw = read_raw_csv(ROOT / "iMHEA_raw/CHA/iMHEA_CHA_01_HS_01_raw.csv")
    assert "Level cm" in raw and "Flow l/s" in raw
    # rating curve reproduces the stored Flow column (default iMHEA weir)
    q = level2flow(raw["Level cm"].to_numpy())
    stored = raw["Flow l/s"].to_numpy()
    m = ~np.isnan(stored) & ~np.isnan(q)
    assert np.corrcoef(q[m], stored[m])[0, 1] > 0.999

    daily = average(raw.index, q / 0.9486, 1440)      # area from Data_Areas
    py = pd.Series(daily.p, index=daily.dates)
    ref = read_processed_csv(
        ROOT / "iMHEA_processed/Daily/iMHEA_CHA_01_1day_processed.csv"
    )["Flow l/s/km2"]
    j = py.index.intersection(ref.index)
    both = (~py[j].isna()) & (~ref[j].isna())
    a, b = py[j][both], ref[j][both]
    assert np.corrcoef(a, b)[0, 1] > 0.999
    assert float((a / b).median()) == pytest.approx(1.0, abs=0.01)
