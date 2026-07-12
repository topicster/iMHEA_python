"""Unit tests for imhea Phase-2 modules (synthetic data)."""

import numpy as np
import pandas as pd
import pytest

from imhea import (aggregate, aggregate_events, average, depure, fill_gaps,
                   level2flow, monitoring_gaps, voids)
from imhea import mtime


def ts(*items):
    return pd.DatetimeIndex([pd.Timestamp(i) for i in items])


# ---------------------------------------------------------------- mtime ----

def test_datenum_roundtrip():
    d = ts("2001-05-24 00:41:23", "2010-12-31 23:59:59")
    assert (mtime.from_datenum(mtime.datenum(d)) == d).all()


def test_interval_index_right_closed():
    # a stamp exactly on a 5-min boundary belongs to the bin ending there
    d = ts("2020-01-01 00:05:00", "2020-01-01 00:05:01",
           "2020-01-01 00:09:59", "2020-01-01 00:10:00")
    idx = mtime.interval_index(d, 5)
    assert idx[0] == idx[1] - 1        # boundary stamp in earlier bin
    assert idx[1] == idx[2] == idx[3]  # (05:00, 10:00] together


# --------------------------------------------------------------- depure ----

def test_depure_zeroes_fast_tips():
    d = ts("2020-01-01 00:00:00", "2020-01-01 00:00:01",
           "2020-01-01 00:00:02.5", "2020-01-01 00:01:00")
    out = depure(d, [0.2, 0.2, 0.2, 0.2])
    # tip2 is 1.0s after tip1 -> zeroed; tip3 is 1.5s after tip2 -> kept
    assert list(out) == [0.2, 0.0, 0.2, 0.2]


# ---------------------------------------------------------------- voids ----

def test_voids_runs_and_bounds():
    d = pd.date_range("2020-01-01", periods=6, freq="D")
    v = voids(d, [1.0, np.nan, np.nan, 2.0, np.nan, 3.0])
    assert len(v) == 2
    assert v.loc[0, "start"] == d[1] and v.loc[0, "end"] == d[3]
    assert v.loc[1, "start"] == d[4] and v.loc[1, "end"] == d[5]


def test_voids_trailing_nan():
    d = pd.date_range("2020-01-01", periods=3, freq="D")
    v = voids(d, [1.0, 2.0, np.nan])
    assert v.loc[0, "start"] == d[2] and v.loc[0, "end"] == d[2]


def test_monitoring_gaps_pct():
    d = pd.date_range("2020-01-01", periods=11, freq="D")  # 10-day span
    vals = [1.0] * 11
    vals[5] = np.nan                                       # 1-day void
    period, pct = monitoring_gaps(d, vals)
    assert period == "01/01/2020 - 11/01/2020"
    assert pct == pytest.approx(10.0)


# ------------------------------------------------------------ aggregate ----

def test_aggregate_sums_and_masks_voids():
    d = ts("2020-01-01 00:01:00", "2020-01-01 00:04:00",   # bin 1
           "2020-01-01 00:07:00",                          # bin 2
           "2020-01-01 00:12:00",                          # NaN marker, bin 3
           "2020-01-01 00:21:00")                          # bin 5
    p = [0.2, 0.2, 0.2, np.nan, 0.2]
    r = aggregate(d, p, 5)
    assert r.dates[0] == pd.Timestamp("2020-01-01 00:05:00")
    assert r.p[0] == pytest.approx(0.4)
    assert r.p[1] == pytest.approx(0.2)
    # void spans (00:12, 00:21): the 00:15 and 00:20 bins are masked
    assert np.isnan(r.p[2]) and np.isnan(r.p[3])
    assert r.p[4] == pytest.approx(0.2)
    assert np.nansum(r.p) == pytest.approx(0.8)            # mass conserved


def test_average_means_isolated_patch_and_zero_runs():
    d = ts("2020-01-01 00:02:00", "2020-01-01 00:04:00",   # bin 1: mean 2,4
           "2020-01-01 00:24:00")                          # bin 5
    r = average(d, [2.0, 4.0, 6.0], 5)
    assert r.p[0] == pytest.approx(3.0)
    # bins 2-4 empty: not isolated -> become 0 (MATLAB behaviour, issue 10)
    assert r.p[1] == 0 and r.p[2] == 0 and r.p[3] == 0
    assert r.p[4] == pytest.approx(6.0)


def test_average_isolated_empty_bin_interpolated():
    d = ts("2020-01-01 00:03:00", "2020-01-01 00:13:00")
    r = average(d, [2.0, 4.0], 5)
    assert r.p[1] == pytest.approx(3.0)                    # (2+4)/2


# ------------------------------------------------------------ fill_gaps ----

def test_fill_gaps_proportional():
    d = pd.date_range("2020-01-01", periods=200, freq="5min")
    rng = np.random.default_rng(42)
    base = rng.gamma(0.3, 1.0, 200).round(1)
    p1, p2 = base.copy(), (2 * base).copy()                # perfectly related
    p1[50:60] = np.nan                                     # one-sided gap
    p2[100:105] = np.nan
    res = fill_gaps(d, p1, d, p2)
    assert res.filled and res.r >= 0.99
    assert res.slope == pytest.approx(2.0, rel=1e-6)
    assert np.allclose(res.p1[50:60], base[50:60], atol=1e-9)
    assert np.allclose(res.p2[100:105], 2 * base[100:105], atol=1e-9)


def test_fill_gaps_rejects_uncorrelated():
    # divergent double-mass curves: gauge 2 dry half the record
    d = pd.date_range("2020-01-01", periods=100, freq="5min")
    p1 = np.ones(100)
    p2 = np.concatenate([np.zeros(50), np.full(50, 5.0)])
    p1[10:20] = np.nan
    res = fill_gaps(d, p1, d, p2)
    assert not res.filled
    assert np.isnan(res.p1[10:20]).all()


# ------------------------------------------------------ aggregate_events ---

def _storm(start, n_tips, gap_s, tip=0.2):
    t0 = pd.Timestamp(start)
    return pd.DatetimeIndex([t0 + pd.Timedelta(seconds=i * gap_s)
                             for i in range(n_tips)]), np.full(n_tips, tip)


@pytest.mark.parametrize("method", ["spline", "linear"])
def test_events_mass_conservation(method):
    d, p = _storm("2020-01-01 06:00:00", 30, 120)          # 6 mm in 1 h
    r = aggregate_events(d, p, scale_min=5, bucket=0.2, method=method)
    assert np.nansum(r.p) == pytest.approx(6.0, abs=0.2 + 1e-6)
    assert (r.p[~np.isnan(r.p)] >= 0).all()                # no negative rain
    assert r.max_bias <= 0.25 + 1e-9


@pytest.mark.parametrize("method", ["spline", "linear"])
def test_single_tip_spread_at_3mmh(method):
    # single tip between two storms: spread over 4 min ending at the tip
    d1, p1 = _storm("2020-01-01 06:00:00", 10, 60)
    d2, p2 = _storm("2020-01-01 20:00:00", 10, 60)
    d = d1.append(ts("2020-01-01 12:00:00")).append(d2)
    p = np.concatenate([p1, [0.2], p2])
    r = aggregate_events(d, p, scale_min=1, bucket=0.2, method=method)
    assert np.nansum(r.single) == pytest.approx(0.2, abs=1e-9)
    nz = np.flatnonzero(np.nan_to_num(r.single) > 0)
    assert len(nz) == 4                                    # 3 mm/h -> 4 min
    assert r.dates[nz[-1]] == pd.Timestamp("2020-01-01 12:00:00")


def test_events_two_storms_are_separated():
    d1, p1 = _storm("2020-01-01 06:00:00", 10, 60)
    d2, p2 = _storm("2020-01-01 12:00:00", 10, 60)         # >1h apart
    d = d1.append(d2)
    p = np.concatenate([p1, p2])
    r = aggregate_events(d, p, scale_min=5, bucket=0.2)
    mid = (r.dates > pd.Timestamp("2020-01-01 07:30:00")) & \
          (r.dates < pd.Timestamp("2020-01-01 10:30:00"))
    assert np.nansum(np.abs(r.p[mid])) == 0                # dry between events


def test_events_void_masking():
    d1, p1 = _storm("2020-01-01 06:00:00", 10, 60)
    dv = ts("2020-01-01 08:00:00")                         # gap marker
    d2, p2 = _storm("2020-01-01 20:00:00", 10, 60)
    d = d1.append(dv).append(d2)
    p = np.concatenate([p1, [np.nan], p2])
    r = aggregate_events(d, p, scale_min=5, bucket=0.2)
    inside = (r.dates > pd.Timestamp("2020-01-01 08:00:00")) & \
             (r.dates < pd.Timestamp("2020-01-01 20:00:00"))
    assert np.isnan(r.p[inside]).all()


# ------------------------------------------------------------ level2flow ---

def test_level2flow_vnotch_and_compound():
    q = level2flow(np.array([10.0]))                       # 0.1 m, in notch
    assert q[0] == pytest.approx(1.37 * 0.1 ** 2.5 * 1000)
    q = level2flow(np.array([40.0]))                       # 0.4 m, compound
    expect = (1.37 * (0.4 ** 2.5 - 0.1 ** 2.5) + 1.77 * 1.0 * 0.1 ** 1.5) * 1000
    assert q[0] == pytest.approx(expect)


def test_level2flow_nan_and_negative():
    q = level2flow(np.array([np.nan, -5.0]))
    assert np.isnan(q[0]) and q[1] == 0.0
    qc = level2flow(np.array([np.nan]), matlab_compat=True)
    assert qc[0] == 0.0
