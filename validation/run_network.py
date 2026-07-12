"""Full-network validation: run the Python pipeline on all raw data and
compare against the published MATLAB outputs.

Usage:  python validation/run_network.py <data_root> <out_dir>

<data_root> must contain iMHEA_raw/, iMHEA_processed/, iMHEA_indices/.
Writes per-pair checkpoints (parquet), series metrics and index metrics
CSVs into <out_dir>. Runs with matlab_compat=True (goal: reproduce the
published dataset; the library defaults keep the fixed behaviour).
"""

from __future__ import annotations

import logging
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import imhea  # noqa: E402
from imhea.registry import (CATCHMENTS, JTU_CASCADE, PAIRS, load_areas,
                            load_catchment)  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
warnings.filterwarnings("ignore")
log = logging.getLogger("validate")

COMPAT = True   # reproduce published dataset as closely as possible


def run_catchment(root, code, cache):
    f = cache / f"{code}_wf.pkl"
    if f.exists():
        return pd.read_pickle(f)
    dq, q, gauges = load_catchment(root / "iMHEA_raw", code)
    c = CATCHMENTS[code]
    t0 = time.time()
    if c.rain_only:
        r = imhea.workflow_rain(c.bucket, gauges, name=code,
                                compute_climate=True)
        idx = pd.concat([r.climate], axis=1) if r.climate is not None else None
        out = {"hres": r.hres, "daily": r.daily, "hourly": r.hourly,
               "climate": r.climate, "hydro": None}
    else:
        r = imhea.workflow(c.area, dq, q, c.bucket, gauges, name=code,
                           compute_indices=True, matlab_compat=COMPAT)
        out = {"hres": r.hres, "daily": r.daily, "hourly": r.hourly,
               "climate": r.indices.climate, "hydro": r.indices.hydro}
    log.info("  %s workflow: %.1fs", code, time.time() - t0)
    pd.to_pickle(out, f)
    return out


def run_pair(root, c1, c2, cache, tag=None, hres1=None, hres2=None):
    tag = tag or f"{c1}__{c2}"
    f = cache / f"pair_{tag}.pkl"
    if f.exists():
        return pd.read_pickle(f)
    h1 = hres1 if hres1 is not None else run_catchment(root, c1, cache)["hres"]
    h2 = hres2 if hres2 is not None else run_catchment(root, c2, cache)["hres"]
    t0 = time.time()
    pr = imhea.workflow_pair(h1, h2, compute_indices=True,
                             matlab_compat=COMPAT)
    out = {"hres": pr.hres, "daily": pr.daily, "hourly": pr.hourly,
           "hydro": pr.hydro, "climate": pr.climate}
    log.info("  pair %s: %.1fs", tag, time.time() - t0)
    pd.to_pickle(out, f)
    return out


def series_metrics(py: pd.Series, ref: pd.Series) -> dict:
    j = py.index.intersection(ref.index)
    a, b = py[j], ref[j]
    m = a.notna() & b.notna()
    n = int(m.sum())
    if n < 2:
        return {"n": n}
    a, b = a[m].to_numpy(), b[m].to_numpy()
    d = np.abs(a - b)
    denom = np.abs(b).mean()
    return {
        "n": n,
        "corr": float(np.corrcoef(a, b)[0, 1]),
        "mae": float(d.mean()),
        "max_abs": float(d.max()),
        "rel_bias_%": float(100 * (a.mean() - b.mean()) / denom)
        if denom else np.nan,
        "pct_within_0.01": float(100 * (d <= 0.01).mean()),
        "nan_agree_%": float(100 * (py[j].isna() == ref[j].isna()).mean()),
    }


def compare_products(root, code, daily, hourly, hres, n, rows):
    """Compare one catchment's products against the published CSVs."""
    proc = root / "iMHEA_processed"
    specs = [("Daily", daily, {"P": "Rainfall mm", "Q": "Flow l/s/km2",
                               "BQ": "Baseflow l/s/km2"}, "1day"),
             ("Hourly", hourly, {"P": "Rainfall mm", "Q": "Flow l/s/km2"},
              "1hr"),
             ("HighRes", hres, {"P": "Rainfall mm", "Q": "Flow l/s/km2"},
              "HRes")]
    for sub, df, colmap, res in specs:
        fp = proc / sub / f"iMHEA_{code}_{res}_processed.csv"
        if not fp.exists() or df is None:
            continue
        ref = imhea.read_processed_csv(fp)
        for pcol, rcol in colmap.items():
            col = pcol + n if (pcol + n) in df else pcol
            if col not in df or rcol not in ref:
                continue
            rows.append({"catchment": code, "resolution": res,
                         "variable": pcol,
                         **series_metrics(df[col], ref[rcol])})


def main(root: Path, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    cache = out / "cache"
    cache.mkdir(exist_ok=True)
    load_areas(root / "iMHEA_indices")
    rows, idx_rows = [], []

    # --- standard pairs -------------------------------------------------
    for c1, c2 in PAIRS:
        log.info("PAIR %s / %s", c1, c2)
        pr = run_pair(root, c1, c2, cache)
        for code, n in ((c1, "1"), (c2, "2")):
            compare_products(root, code, pr["daily"], pr["hourly"],
                             pr["hres"].rename(columns={
                                 f"P{n}": f"P{n}", f"Q{n}": f"Q{n}"}),
                             n, rows)

    # --- JTU cascade (driver lines 58-68) --------------------------------
    log.info("JTU cascade")
    p1 = run_pair(root, "JTU_01", "JTU_02", cache, tag="JTU_p1")
    p2 = run_pair(root, "JTU_03", "JTU_04", cache, tag="JTU_p2")

    def sub(pr, n):
        return pr["hres"][[f"P{n}", f"Q{n}"]].rename(
            columns={f"P{n}": "P", f"Q{n}": "Q"})
    p3 = run_pair(root, "JTU_02f", "JTU_03f", cache, tag="JTU_p3",
                  hres1=sub(p1, "2"), hres2=sub(p2, "1"))
    p4 = run_pair(root, "JTU_01f", "JTU_03ff", cache, tag="JTU_p4",
                  hres1=sub(p1, "1"), hres2=sub(p3, "2"))
    p1f = run_pair(root, "f1", "f2", cache, tag="JTU_p1_final",
                   hres1=sub(p4, "1"), hres2=sub(p3, "1"))
    p2f = run_pair(root, "f3", "f4", cache, tag="JTU_p2_final",
                   hres1=sub(p4, "2"), hres2=sub(p2, "2"))
    for pr, codes in ((p1f, ("JTU_01", "JTU_02")),
                      (p2f, ("JTU_03", "JTU_04"))):
        for code, n in zip(codes, ("1", "2")):
            compare_products(root, code, pr["daily"], pr["hourly"],
                             pr["hres"], n, rows)

    # --- rain-only stations ----------------------------------------------
    log.info("RAIN-ONLY PAU_05")
    r = run_catchment(root, "PAU_05", cache)
    compare_products(root, "PAU_05", r["daily"], r["hourly"], r["hres"],
                     "", rows)
    # PIU_05/06 are cross-filled against each other, then re-run through
    # WorkflowRain on the filled series (driver lines 164-168)
    log.info("RAIN-ONLY PIU_05/06 (cross-filled)")
    r5 = run_catchment(root, "PIU_05", cache)
    r6 = run_catchment(root, "PIU_06", cache)
    from imhea.clean import fill_gaps as _fg
    fl = _fg(r5["hres"].index, r5["hres"]["P"].to_numpy(),
             r6["hres"].index, r6["hres"]["P"].to_numpy())
    for code, p in (("PIU_05", fl.p1), ("PIU_06", fl.p2)):
        f = cache / f"{code}_filled.pkl"
        if f.exists():
            rr = pd.read_pickle(f)
        else:
            rw = imhea.workflow_rain(0.2, [(fl.dates, p)], name=code)
            rr = {"daily": rw.daily, "hourly": rw.hourly, "hres": rw.hres}
            pd.to_pickle(rr, f)
        compare_products(root, code, rr["daily"], rr["hourly"], rr["hres"],
                         "", rows)

    # --- indices comparison (pair runs, matching the published matrices) --
    hyd = pd.read_csv(root / "iMHEA_indices/iMHEA_Indices_Hydro_Pair.csv",
                      encoding="utf-8-sig")
    cli = pd.read_csv(root / "iMHEA_indices/iMHEA_Indices_Climate_Pair.csv",
                      encoding="utf-8-sig")
    hyd.columns = [c.strip() for c in hyd.columns]
    cli.columns = [c.strip() for c in cli.columns]
    all_pairs = ([(f"pair_{a}__{b}.pkl", a, b) for a, b in PAIRS]
                 + [("pair_JTU_p1_final.pkl", "JTU_01", "JTU_02"),
                    ("pair_JTU_p2_final.pkl", "JTU_03", "JTU_04")])
    for fname, c1, c2 in all_pairs:
        pr = pd.read_pickle(cache / fname)
        for col, code in (("catchment_1", c1), ("catchment_2", c2)):
            for kind, df, refdf, names in (
                    ("hydro", pr["hydro"], hyd, imhea.HYDRO_NAMES),
                    ("climate", pr["climate"], cli, imhea.CLIMATE_NAMES)):
                if df is None or code not in refdf.columns:
                    continue
                ref = pd.Series(refdf[code].values[:len(names)],
                                index=names).astype(float)
                for name in names:
                    pv, rv = float(df[col][name]), float(ref[name])
                    idx_rows.append({
                        "catchment": code, "kind": kind, "index": name,
                        "python": pv, "matlab": rv,
                        "rel_%": 100 * (pv - rv) / abs(rv) if rv else np.nan})

    pd.DataFrame(rows).to_csv(out / "series_metrics.csv", index=False)
    pd.DataFrame(idx_rows).to_csv(out / "index_metrics.csv", index=False)
    log.info("DONE: %d series rows, %d index rows", len(rows), len(idx_rows))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
