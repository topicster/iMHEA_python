"""Publication-quality figures for iMHEA data (Phase 5).

Reimagined replacements for iMHEA_Plot2/3/4 and iMHEA_PlotPair: same
information content, modern matplotlib design, shared by the CLI and GUI.
Every function returns a ``matplotlib.figure.Figure`` (nothing is shown or
saved here). Import requires the ``plots`` extra: ``pip install imhea[plots]``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import matplotlib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

#: consistent colours across figures
C_RAIN = "#1f77b4"
C_FLOW = "#0b6e4f"
C_BASE = "#8fc9b4"
C_ALT = "#c1442e"
C_ALT_BASE = "#e8a793"


def _style(ax, ylabel=None):
    ax.grid(True, alpha=0.3, linewidth=0.5)
    ax.spines[["top", "right"]].set_visible(False)
    if ylabel:
        ax.set_ylabel(ylabel)


def _date_axis(ax):
    loc = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(loc)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc))


def plot_series(dates, series: dict, title: str = "") -> plt.Figure:
    """Stacked quick-look plot of n series sharing one time axis
    (replaces iMHEA_Plot2 / iMHEA_Plot3)."""
    n = len(series)
    fig, axes = plt.subplots(n, 1, figsize=(11, 2.2 * n), sharex=True,
                             squeeze=False)
    for ax, (label, values) in zip(axes[:, 0], series.items()):
        ax.plot(dates, values, lw=0.7, color=C_FLOW)
        _style(ax, label)
    _date_axis(axes[-1, 0])
    if title:
        fig.suptitle(title)
    fig.tight_layout()
    return fig


def plot_catchment(daily: pd.DataFrame, title: str = "",
                   p_col: str = "P", q_col: str = "Q",
                   bq_col: str | None = "BQ") -> plt.Figure:
    """Catchment dashboard: inverted hyetograph over a hydrograph with
    baseflow shading (daily [P, Q, BQ] frame from the workflow)."""
    fig, ax_q = plt.subplots(figsize=(12, 5))
    ax_p = ax_q.twinx()

    ax_p.bar(daily.index, daily[p_col], width=1.0, color=C_RAIN,
             alpha=0.7, linewidth=0)
    ax_p.set_ylim(4 * np.nanmax(daily[p_col].to_numpy()) or 1, 0)  # inverted
    ax_p.set_ylabel("Rainfall [mm/day]", color=C_RAIN)
    ax_p.tick_params(axis="y", colors=C_RAIN)
    ax_p.spines[["top"]].set_visible(False)

    q = daily[q_col]
    ax_q.plot(daily.index, q, lw=0.8, color=C_FLOW, label="Streamflow")
    if bq_col and bq_col in daily:
        bq = daily[bq_col]
        ax_q.fill_between(daily.index, 0, bq.to_numpy(), color=C_BASE,
                          alpha=0.8, linewidth=0, label="Baseflow")
    ax_q.set_ylim(bottom=0)
    _style(ax_q, "Flow [l s$^{-1}$ km$^{-2}$]")
    _date_axis(ax_q)
    ax_q.legend(loc="center right", frameon=False)
    if title:
        ax_q.set_title(title)
    fig.tight_layout()
    return fig


def plot_pair(daily: pd.DataFrame, names=("Catchment 1", "Catchment 2"),
              title: str = "") -> plt.Figure:
    """Paired-catchment dashboard (replaces iMHEA_PlotPair): two inverted
    hyetographs and overlaid hydrographs with baseflow."""
    fig, (ax1, ax2, axq) = plt.subplots(
        3, 1, figsize=(12, 8), sharex=True,
        gridspec_kw={"height_ratios": [1, 1, 2.4]})
    for ax, col, colr, nm in ((ax1, "P1", C_RAIN, names[0]),
                              (ax2, "P2", C_ALT, names[1])):
        ax.bar(daily.index, daily[col], width=1.0, color=colr, alpha=0.75,
               linewidth=0)
        ax.invert_yaxis()
        _style(ax, f"P {nm}\n[mm/day]")
    for qc, bc, colr, colb, nm in (("Q1", "BQ1", C_FLOW, "#3f8a68",
                                    names[0]),
                                   ("Q2", "BQ2", C_ALT, "#d07b5a",
                                    names[1])):
        axq.plot(daily.index, daily[qc], lw=0.8, color=colr, label=nm)
        if bc in daily:
            axq.plot(daily.index, daily[bc], lw=0.9, color=colb, ls="--",
                     label=f"{nm} baseflow")
    axq.set_ylim(bottom=0)
    _style(axq, "Flow [l s$^{-1}$ km$^{-2}$]")
    _date_axis(axq)
    axq.legend(frameon=False, ncols=2)
    if title:
        ax1.set_title(title)
    fig.tight_layout()
    return fig


def plot_fdc(curves: dict, ylabel="Flow [l s$^{-1}$ km$^{-2}$]",
             title: str = "Flow duration curves") -> plt.Figure:
    """Overlay flow duration curves: ``curves = {label: FDC array}`` where
    each array is [exceedance %, flow] (imhea.fdc().fdc)."""
    fig, ax = plt.subplots(figsize=(7, 5))
    for label, arr in curves.items():
        arr = np.asarray(arr)
        ax.semilogy(arr[:, 0], arr[:, 1], lw=1.2, label=label)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Exceedance probability [%]")
    _style(ax, ylabel)
    ax.set_title(title)
    ax.legend(frameon=False)
    fig.tight_layout()
    return fig


def plot_idc(curves: dict,
             title: str = "Maximum intensity-duration curves") -> plt.Figure:
    """Overlay intensity-duration curves: ``curves = {label: IDC array}``
    ([duration min, max mm/h, ...] as returned by imhea.idc)."""
    fig, ax = plt.subplots(figsize=(7, 5))
    for label, arr in curves.items():
        arr = np.asarray(arr)
        ax.loglog(arr[:, 0], arr[:, 1], "o-", ms=3.5, lw=1.2, label=label)
    ax.set_xlabel("Duration [min]")
    ax.set_xticks([5, 15, 60, 240, 1440, 2880],
                  ["5m", "15m", "1h", "4h", "1d", "2d"])
    _style(ax, "Rainfall intensity [mm h$^{-1}$]")
    ax.set_title(title)
    ax.legend(frameon=False)
    fig.tight_layout()
    return fig


def plot_monthly_regime(pm=None, qm_mm=None, labels=("P", "Q"),
                        title: str = "Monthly regime") -> plt.Figure:
    """Monthly climatology: precipitation bars + flow line, both mm/month.

    ``pm``/``qm_mm`` are 12-vectors or dicts {label: 12-vector}."""
    months = np.arange(1, 13)
    names = list("JFMAMJJASOND")
    fig, ax = plt.subplots(figsize=(8, 4.5))

    def _as_dict(x, default):
        if x is None:
            return {}
        return x if isinstance(x, dict) else {default: np.asarray(x)}

    pms, qms = _as_dict(pm, labels[0]), _as_dict(qm_mm, labels[1])
    n = max(len(pms), 1)
    width = 0.8 / n
    for k, (label, v) in enumerate(pms.items()):
        ax.bar(months + (k - (n - 1) / 2) * width, v, width=width,
               alpha=0.7, label=label)
    for label, v in qms.items():
        ax.plot(months, v, "o-", lw=1.5, ms=4, label=label)
    ax.set_xticks(months, names)
    _style(ax, "mm / month")
    ax.set_title(title)
    ax.legend(frameon=False)
    fig.tight_layout()
    return fig


def plot_network(monthly_p: pd.DataFrame | None = None,
                 monthly_q: pd.DataFrame | None = None,
                 idcs: dict | None = None,
                 fdcs: dict | None = None) -> plt.Figure:
    """Network summary 2x2 (replaces the iMHEA_Plot4 script): monthly P and
    Q regimes (one line per station), all IDCs (log-x), all FDCs (log-y,
    mm/day). DataFrames: 12 rows x stations."""
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    months = np.arange(1, 13)
    names = list("JFMAMJJASOND")

    for ax, df, ttl in ((axes[0, 0], monthly_p, "Monthly precipitation"),
                        (axes[0, 1], monthly_q, "Monthly runoff")):
        if df is not None:
            for col in df.columns:
                ax.plot(months, df[col], lw=0.9, alpha=0.75, label=col)
        ax.set_xticks(months, names)
        _style(ax, "mm / month")
        ax.set_title(ttl)

    ax = axes[1, 0]
    if idcs:
        for label, arr in idcs.items():
            arr = np.asarray(arr)
            ax.loglog(arr[:, 0], arr[:, 1], lw=0.9, alpha=0.75, label=label)
    ax.set_xlabel("Duration [min]")
    ax.set_xticks([5, 60, 1440], ["5m", "1h", "1d"])
    _style(ax, "Intensity [mm h$^{-1}$]")
    ax.set_title("Maximum intensity-duration curves")

    ax = axes[1, 1]
    if fdcs:
        for label, arr in fdcs.items():
            arr = np.asarray(arr)
            ax.semilogy(arr[:, 0], arr[:, 1] * 86400 / 1e6, lw=0.9,
                        alpha=0.75, label=label)
    ax.set_xlim(-5, 105)
    ax.set_xlabel("Exceedance probability [%]")
    _style(ax, "Flow [mm day$^{-1}$]")
    ax.set_title("Flow duration curves")

    h, l = axes[0, 0].get_legend_handles_labels()
    if h:
        fig.legend(h, l, loc="lower center", ncols=min(len(l), 9),
                   frameon=False, fontsize=7)
        fig.tight_layout(rect=(0, 0.06, 1, 1))
    else:
        fig.tight_layout()
    return fig


def plot_double_mass(cum_p: pd.Series, cum_q_mm: pd.Series,
                     title: str = "Double-mass curve") -> plt.Figure:
    """Cumulative rainfall vs cumulative runoff (both mm)."""
    j = cum_p.index.intersection(cum_q_mm.index)
    a, b = cum_p[j], cum_q_mm[j]
    m = a.notna() & b.notna()
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot(a[m], b[m], lw=1.2, color=C_FLOW)
    lim = max(float(a[m].max()), float(b[m].max()))
    ax.plot([0, lim], [0, lim], ls=":", color="grey", lw=0.8, label="1:1")
    ax.set_xlabel("Cumulative rainfall [mm]")
    _style(ax, "Cumulative runoff [mm]")
    ax.set_title(title)
    ax.legend(frameon=False)
    fig.tight_layout()
    return fig


def plot_gaps(no_voids: dict, title: str = "Data coverage") -> plt.Figure:
    """Coverage timeline: ``no_voids = {station: DataFrame[start, end]}``
    (from imhea.no_voids). One horizontal bar lane per station."""
    fig, ax = plt.subplots(figsize=(11, 0.5 + 0.42 * len(no_voids)))
    labels = []
    for i, (name, nv) in enumerate(no_voids.items()):
        labels.append(name)
        for _, r in nv.iterrows():
            ax.barh(i, r["end"] - r["start"], left=r["start"], height=0.6,
                    color=C_FLOW, linewidth=0)
    ax.set_yticks(range(len(labels)), labels)
    ax.invert_yaxis()
    _date_axis(ax)
    ax.grid(True, axis="x", alpha=0.3, linewidth=0.5)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title(title)
    fig.tight_layout()
    return fig
