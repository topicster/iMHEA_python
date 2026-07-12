"""Command-line interface for the imhea pipeline.

Examples:
  imhea process --code MYC_01 --area 2.63 --bucket 0.2 \\
      --flow flow.csv --gauge rg1.csv --gauge rg2.csv --out ./processed
  imhea pair --hres1 A_HRes.csv --hres2 B_HRes.csv --site XYZ --out ./out
  imhea network --data-root ./Scripts --out ./reprocessed
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd


def _cmd_process(a) -> int:
    import imhea
    from imhea.workflow import export_catchment

    gauges = []
    for f in a.gauge:
        df = imhea.read_raw_csv(f)
        gauges.append((df.index, df["value"].to_numpy()))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    if a.flow:
        fdf = imhea.read_raw_csv(a.flow)
        if a.level_to_flow:
            q = imhea.level2flow(fdf["Level cm"].to_numpy(),
                                 tuple(a.weir), tuple(a.coeff))
        else:
            col = "Flow l/s" if "Flow l/s" in fdf else "value"
            q = fdf[col].to_numpy()
        res = imhea.workflow(a.area, fdf.index, q, a.bucket, gauges,
                             name=a.code, matlab_compat=a.matlab_compat)
        idx = pd.concat([res.indices.hydro, res.indices.climate])
        idx.to_csv(out / f"iMHEA_{a.code}_indices.csv",
                   header=["value"])
    else:
        res = imhea.workflow_rain(a.bucket, gauges, name=a.code)
        if res.climate is not None:
            res.climate.to_csv(out / f"iMHEA_{a.code}_indices.csv",
                               header=["value"])
    paths = export_catchment(out, a.code, res)
    for p in paths:
        print(p)
    return 0


def _cmd_pair(a) -> int:
    import imhea

    def _load(path):
        df = imhea.read_processed_csv(path)
        df.columns = ["P", "Q"][: len(df.columns)]
        return df

    res = imhea.workflow_pair(_load(a.hres1), _load(a.hres2),
                              matlab_compat=a.matlab_compat)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    imhea.export_pair(out, a.site, res)
    pd.concat([res.hydro, res.climate]).to_csv(
        out / f"iMHEA_{a.site}_pair_indices.csv")
    print(f"exported to {out}")
    return 0


def _cmd_network(a) -> int:
    """Reprocess the built-in iMHEA network registry."""
    sys.argv = ["run_network", a.data_root, a.out]
    root = Path(__file__).resolve().parents[2] / "validation"
    sys.path.insert(0, str(root.parent))
    script = root / "run_network.py"
    if not script.exists():
        print("validation/run_network.py not found (repository checkout "
              "required)", file=sys.stderr)
        return 2
    import runpy
    runpy.run_path(str(script), run_name="__main__")
    return 0


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser(prog="imhea", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    from imhea import __version__
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("process", help="process one catchment/station")
    pr.add_argument("--code", required=True)
    pr.add_argument("--area", type=float, help="catchment area [km2]")
    pr.add_argument("--bucket", type=float, default=0.2)
    pr.add_argument("--flow", help="discharge raw CSV (omit for rain-only)")
    pr.add_argument("--gauge", action="append", default=[], required=True)
    pr.add_argument("--level-to-flow", action="store_true",
                    help="convert the Level column via the rating curve")
    pr.add_argument("--weir", nargs=2, type=float, default=[0.30, 1.00],
                    metavar=("A", "B"))
    pr.add_argument("--coeff", nargs=4, type=float,
                    default=[1.37, 2.5, 1.77, 1.5],
                    metavar=("C1", "E1", "C2", "E2"))
    pr.add_argument("--matlab-compat", action="store_true")
    pr.add_argument("--out", default="./processed")
    pr.set_defaults(func=_cmd_process)

    pp = sub.add_parser("pair", help="paired-catchment assimilation from "
                                     "two HRes processed CSVs")
    pp.add_argument("--hres1", required=True)
    pp.add_argument("--hres2", required=True)
    pp.add_argument("--site", required=True, help="3-letter site code")
    pp.add_argument("--matlab-compat", action="store_true")
    pp.add_argument("--out", default="./processed")
    pp.set_defaults(func=_cmd_pair)

    pn = sub.add_parser("network", help="reprocess + validate the full "
                                        "iMHEA network")
    pn.add_argument("--data-root", required=True)
    pn.add_argument("--out", default="./valout")
    pn.set_defaults(func=_cmd_network)

    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
