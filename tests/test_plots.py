"""Phase-5 smoke tests: every plot function builds a Figure (Agg backend)."""

import matplotlib

matplotlib.use("Agg")

import numpy as np
import pandas as pd
import pytest

from imhea import fdc, idc, no_voids
from imhea import plots


@pytest.fixture
def daily():
    idx = pd.date_range("2020-01-01", periods=400, freq="D")
    rng = np.random.default_rng(2)
    p = rng.gamma(0.4, 5, len(idx)).round(1)
    q = 5 + rng.random(len(idx)) * 10
    bq = q * 0.4
    return pd.DataFrame({"P": p, "Q": q, "BQ": bq,
                         "P1": p, "Q1": q, "BQ1": bq,
                         "P2": p * 1.2, "Q2": q * 0.7, "BQ2": bq * 0.7},
                        index=idx)


def test_plot_series(daily):
    f = plots.plot_series(daily.index, {"P [mm]": daily["P"],
                                        "Q [l/s]": daily["Q"]}, "t")
    assert len(f.axes) == 2


def test_plot_catchment(daily):
    f = plots.plot_catchment(daily, title="X")
    assert len(f.axes) == 2  # twin axes


def test_plot_pair(daily):
    f = plots.plot_pair(daily, names=("A", "B"))
    assert len(f.axes) == 3


def test_plot_fdc_idc(daily):
    f = plots.plot_fdc({"A": fdc(daily["Q"]).fdc})
    assert f.axes[0].get_yscale() == "log"
    d5 = pd.date_range("2020-01-01", periods=3000, freq="5min")
    arr, _, _ = idc(d5, np.random.default_rng(0).gamma(0.2, 1, 3000))
    f = plots.plot_idc({"A": arr})
    assert f.axes[0].get_xscale() == "log"


def test_plot_monthly_and_network(daily):
    pm = np.linspace(50, 200, 12)
    f = plots.plot_monthly_regime(pm, pm * 0.3)
    assert f.axes
    f = plots.plot_network(pd.DataFrame({"A": pm}),
                           pd.DataFrame({"A": pm * 0.3}), None,
                           {"A": fdc(daily["Q"]).fdc})
    assert len(f.axes) == 4


def test_plot_double_mass_and_gaps(daily):
    f = plots.plot_double_mass(daily["P"].cumsum(), daily["Q"].cumsum())
    assert f.axes
    q = daily["Q"].copy()
    q.iloc[100:150] = np.nan
    f = plots.plot_gaps({"A": no_voids(daily.index, q.to_numpy())})
    assert f.axes
