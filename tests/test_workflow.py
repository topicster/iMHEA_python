"""Phase-4 tests: workflow orchestrators (synthetic + CHA regression)."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import imhea
from imhea.registry import CATCHMENTS, load_areas, load_catchment


def _synthetic_catchment(seed=0, days=400):
    rng = np.random.default_rng(seed)
    dq = pd.date_range("2020-01-01", periods=days * 288, freq="5min")
    q = 10 + 5 * np.sin(np.arange(len(dq)) / 5000) + rng.random(len(dq))
    tips = pd.date_range("2020-01-01", periods=days * 4, freq="6h")
    p = np.full(len(tips), 0.2)
    return dq, q, [(tips, p), (tips + pd.Timedelta("2min"), p)]


def test_workflow_synthetic_end_to_end():
    dq, q, gauges = _synthetic_catchment()
    r = imhea.workflow(2.0, dq, q, 0.2, gauges, compute_indices=True)
    assert r.scale_min == 5
    assert list(r.hres.columns) == ["P", "Q"]
    assert list(r.daily.columns) == ["P", "Q", "BQ"]
    # Q normalised on output (l/s/km2): input ~10-16 l/s over 2 km2
    assert 4 < np.nanmedian(r.hres["Q"]) < 9
    assert len(r.indices.hydro) == 59 and len(r.climate) == 13
    # BQ never exceeds Q where both exist
    m = r.daily[["Q", "BQ"]].notna().all(axis=1)
    assert (r.daily.loc[m, "BQ"] <= r.daily.loc[m, "Q"] + 1e-9).all()


def test_workflow_pair_synthetic():
    dq, q, gauges = _synthetic_catchment(1)
    r1 = imhea.workflow(2.0, dq, q, 0.2, gauges, compute_indices=False)
    r2 = imhea.workflow(1.5, dq, q * 0.8, 0.2, gauges,
                        compute_indices=False)
    pr = imhea.workflow_pair(r1.hres, r2.hres, compute_indices=False)
    assert list(pr.hres.columns) == ["P1", "Q1", "P2", "Q2"]
    assert list(pr.daily.columns) == ["P1", "Q1", "BQ1", "P2", "Q2", "BQ2"]


ROOT = None
for base in [Path(__file__).resolve().parents[2],
             Path("/sessions/brave-gifted-pascal/mnt/Scripts")]:
    if (base / "iMHEA_raw").is_dir():
        ROOT = base
        break


@pytest.mark.skipif(ROOT is None, reason="iMHEA dataset not available")
def test_cha_pair_reproduces_published_daily():
    """Full CHA pair vs published daily products (matlab_compat)."""
    load_areas(ROOT / "iMHEA_indices")
    res = {}
    for code in ("CHA_01", "CHA_02"):
        dq, q, gauges = load_catchment(ROOT / "iMHEA_raw", code)
        res[code] = imhea.workflow(CATCHMENTS[code].area, dq, q,
                                   CATCHMENTS[code].bucket, gauges,
                                   compute_indices=False,
                                   matlab_compat=True)
    pr = imhea.workflow_pair(res["CHA_01"].hres, res["CHA_02"].hres,
                             compute_indices=False, matlab_compat=True)
    for code, n in (("CHA_01", "1"), ("CHA_02", "2")):
        ref = imhea.read_processed_csv(
            ROOT / f"iMHEA_processed/Daily/iMHEA_{code}_1day_processed.csv")
        # P tolerance 0.5 mm: day-boundary allocation at the 30-min CHA
        # site (bias-free; see docs/VALIDATION.md §3.3)
        for pv, rv, tol in ((f"P{n}", "Rainfall mm", 0.5),
                            (f"Q{n}", "Flow l/s/km2", 1e-3),
                            (f"BQ{n}", "Baseflow l/s/km2", 1e-3)):
            a, b = pr.daily[pv], ref[rv]
            j = a.index.intersection(b.index)
            m = a[j].notna() & b[j].notna()
            assert m.sum() > 400
            assert (a[j][m] - b[j][m]).abs().max() < tol, (code, pv)
