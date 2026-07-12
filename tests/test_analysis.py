"""Phase-3 unit tests: FDC, IDC, pulse, monthly, baseflow (synthetic data)."""

import numpy as np
import pandas as pd
import pytest

from imhea import (baseflow_chapman, baseflow_ukih, fdc, idc, monthly_flow,
                   monthly_rain, pulse)


# ------------------------------------------------------------------- FDC ---

def test_fdc_gringorten_and_ordering():
    q = np.arange(1.0, 101.0)                       # 1..100
    f = fdc(q)
    assert f.fdc[0, 1] == 1.0 and f.fdc[-1, 1] == 100.0
    # smallest flow: exceedance 100*(1-0.56/100.12)
    assert f.fdc[0, 0] == pytest.approx(100 * (1 - 0.56 / 100.12))
    # Q95 (low flow) < Q50 < Q10 (high flow)
    assert f.ptile[0] < f.ptile[3] < f.ptile[6]
    assert f.ptile[3] == pytest.approx(50.5, abs=0.5)   # ~median
    assert f.r2fdc < 0                              # decreasing in exceedance
    assert 0 < f.irh < 1


def test_fdc_constant_flow_irh():
    f = fdc(np.full(100, 5.0))
    assert f.irh == pytest.approx(1.0)              # perfectly regulated


# ------------------------------------------------------------------- IDC ---

def test_idc_uniform_rain():
    d = pd.date_range("2020-01-01", periods=12 * 48, freq="5min")
    p = np.full(len(d), 0.5)                        # 6 mm/h steady
    arr, im15m, im1hr = idc(d, p)
    assert im15m == pytest.approx(6.0)
    assert im1hr == pytest.approx(6.0)
    assert arr[0, 1] == pytest.approx(6.0)          # 5-min max intensity
    # mean intensity columns are duration-consistent (stale-buffer fix)
    assert arr[5, 2] == pytest.approx(6.0)


def test_idc_short_record_yields_nan_not_crash():
    d = pd.date_range("2020-01-01", periods=100, freq="5min")
    arr, _, _ = idc(d, np.random.default_rng(1).random(100))
    assert np.isnan(arr[-1, 1])                     # 2-day window > record


# ----------------------------------------------------------------- Pulse ---

def test_pulse_counts_merging_and_durations():
    d = pd.date_range("2020-01-01", periods=20, freq="D")
    q = np.array([1, 1, 5, 6, 5, 1, 1, 1, 7, 1, 1, 1, 1, 1, 1, 1, 1, 8, 9, 1],
                 dtype=float)
    r = pulse(d, q, 4.0)
    assert r.fh[0] == 3                             # three high pulses
    assert r.dh[3] == pytest.approx(3.0)            # longest: days 3-5
    assert r.mh[3] == 9.0                           # max peak
    assert r.tl == pytest.approx(3.0)               # fixed: max high duration
    rc = pulse(d, q, 4.0, matlab_compat=True)
    assert rc.tl == pytest.approx(1.0)              # MATLAB: min duration


def test_pulse_volume_trapezoid():
    d = pd.date_range("2020-01-01", periods=5, freq="D")
    q = np.array([0, 10, 10, 0, 0], dtype=float)    # square 2-day excess
    r = pulse(d, q, 5.0)
    # samples 1,2 high: vol = 1d*(5+5)/2 + 1d*(0+5)/2 = 7.5 (unit x day)
    assert r.vh[0] == pytest.approx(7.5)


def test_pulse_cv_uses_sample_std():
    d = pd.date_range("2020-01-01", periods=8, freq="D")
    q = np.array([9, 1, 9, 1, 1, 1, 9, 1], dtype=float)   # 3 pulses, 1 day
    r = pulse(d, q, 5.0)
    counts = np.array([3.0])                        # one calendar year
    assert r.fh[4] == 0.0                           # single year -> CV 0


# --------------------------------------------------------------- Monthly ---

def test_monthly_rain_empty_month_nan_vs_compat_zero():
    d = pd.DatetimeIndex(["2020-01-10", "2020-01-20", "2020-03-05"])
    p = [5.0, 3.0, 2.0]
    r = monthly_rain(d, p)
    assert r.matrix[0, 0] == pytest.approx(8.0)
    assert np.isnan(r.matrix[0, 1])                 # empty Feb -> NaN (fixed)
    rc = monthly_rain(d, p, matlab_compat=True)
    assert rc.matrix[0, 1] == 0.0                   # MATLAB: 0 mm


def test_monthly_flow_day_of_year_fix():
    d = pd.date_range("2020-01-01", "2021-12-31", freq="D")
    rng = np.random.default_rng(7)
    q = rng.random(len(d)) + 1
    q[400] = 0.01                                   # 2021 minimum
    r = monthly_flow(d, q)
    assert r.ymin[1, 2] == d[400].dayofyear         # correct year-2 doy


# -------------------------------------------------------------- Baseflow ---

def _synthetic_flow(n_days=730, seed=3):
    """Storm spikes + exponential recessions on a stable base."""
    rng = np.random.default_rng(seed)
    d = pd.date_range("2019-01-01", periods=n_days, freq="D")
    q = np.full(n_days, 5.0)
    peak = 0.0
    for i in range(n_days):
        if rng.random() < 0.05:
            peak = rng.uniform(20, 80)
        q[i] += peak
        peak *= 0.75                                # recession k=0.75
    return d, q


def test_chapman_filter_properties():
    d, q = _synthetic_flow()
    r = baseflow_chapman(d, q)
    assert np.all(r.bq <= q + 1e-9)                 # BQ never exceeds Q
    assert 0 < r.bfi < 1
    assert 0 < r.k < 1


def test_ukih_properties():
    d, q = _synthetic_flow()
    r = baseflow_ukih(d, q)
    ok = ~np.isnan(r.bq)
    dq = pd.Series(q, index=d).resample("D").mean().to_numpy()
    assert np.all(r.bq[ok] <= dq[ok] + 1e-9)
    assert np.all(r.bq[ok] >= 0)                    # fixed: no negative BQ
    assert 0 < r.bfi < 1


def test_chapman_no_recession_returns_nan():
    d = pd.date_range("2020-01-01", periods=50, freq="D")
    q = np.tile([1.0, 9.0], 25)                     # pure noise, no recession
    r = baseflow_chapman(d, q)
    assert np.isnan(r.bfi) and np.isnan(r.k)
