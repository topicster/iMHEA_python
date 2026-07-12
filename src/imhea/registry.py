"""iMHEA network registry: catchment configurations and pairing structure.

Data-driven replacement for the hard-coded ``iMHEA_Raw2Processed.m`` driver
script. Every entry was transcribed from the driver's call lines (see
docs/review/B_processing_io.md and E_workflows_plots.md).

Special cases preserved:
- JTU_04 receives rainfall from ALL eight JTU gauges;
- HUA_01/02 concatenate two logger files; HUA_02's first logger stored
  specific discharge computed with a legacy area of 2.71 km2 and is
  rescaled by area/2.71;
- PIU_07 uses gauges PO_02 and PO_03 only (PO_01 skipped);
- PAU_05, PIU_05, PIU_06 are rain-only stations;
- JTU pairs are cascade-refilled (see ``JTU_CASCADE`` note) and PIU_05/06
  are cross-filled before their climate indices.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .io import read_raw_csv


@dataclass
class Catchment:
    code: str                     #: e.g. "LLO_01"
    area: float | None            #: km2 (None for rain-only)
    bucket: float                 #: tipping-bucket resolution [mm]
    flow_files: list[str] = field(default_factory=list)
    flow_scales: list[float] = field(default_factory=list)  #: per-file Q factor
    rain_files: list[str] = field(default_factory=list)

    @property
    def site(self) -> str:
        return self.code[:3]

    @property
    def rain_only(self) -> bool:
        return not self.flow_files


def _c(code, area, bucket, flow, rain, scales=None):
    site = code[:3]
    return Catchment(
        code, area, bucket,
        [f"{site}/iMHEA_{f}_raw.csv" for f in flow],
        scales or [1.0] * len(flow),
        [f"{r[:3]}/iMHEA_{r}_raw.csv" for r in rain])


#: legacy area used by HUA_02's first logger (l/s/km2 stored as l/s)
HUA02_LEGACY_AREA = 2.71
_HUA02_AREA = 2.38

CATCHMENTS: dict[str, Catchment] = {c.code: c for c in [
    _c("LLO_01", 1.79, 0.2, ["LLO_01_HI_01"],
       ["LLO_01_PO_01", "LLO_01_PO_02"]),
    _c("LLO_02", 2.21, 0.2, ["LLO_02_HI_01"],
       ["LLO_02_PO_01", "LLO_02_PO_02"]),
    _c("JTU_01", 0.648, 0.1, ["JTU_01_HI_01"],
       ["JTU_01_PT_01", "JTU_01_PT_02"]),
    _c("JTU_02", 2.416, 0.1, ["JTU_02_HI_01"],
       ["JTU_02_PT_01", "JTU_02_PT_02"]),
    _c("JTU_03", 2.247, 0.1, ["JTU_03_HI_01"],
       ["JTU_03_PT_01", "JTU_03_PT_02"]),
    _c("JTU_04", 16.048, 0.1, ["JTU_04_HI_01"],
       ["JTU_01_PT_01", "JTU_01_PT_02", "JTU_02_PT_01", "JTU_02_PT_02",
        "JTU_03_PT_01", "JTU_03_PT_02", "JTU_04_PT_01", "JTU_04_PT_02"]),
    _c("PAU_01", 2.633, 0.2, ["PAU_01_HW_01"],
       ["PAU_01_PD_01", "PAU_01_PD_02", "PAU_01_PD_03"]),
    _c("PAU_02", 1.002, 0.254, ["PAU_02_HW_01"],
       ["PAU_02_PD_01", "PAU_02_PD_02"]),
    _c("PAU_03", 0.59, 0.254, ["PAU_03_HW_01"],
       ["PAU_03_PD_01", "PAU_03_PD_02"]),
    _c("PAU_04", 1.5484, 0.2, ["PAU_04_HW_01"],
       ["PAU_04_PD_01", "PAU_04_PD_02", "PAU_04_PD_03"]),
    _c("PAU_05", None, 0.2, [],
       ["PAU_05_PD_01", "PAU_05_PD_02", "PAU_05_PD_03"]),
    _c("PIU_01", 6.6, 0.2, ["PIU_01_HI_01"],
       ["PIU_01_PO_01", "PIU_01_PO_02", "PIU_01_PO_03"]),
    _c("PIU_02", 0.94, 0.2, ["PIU_02_HI_01"],
       ["PIU_02_PO_01", "PIU_02_PO_02", "PIU_02_PO_03", "PIU_02_PO_04"]),
    _c("PIU_03", 5.83, 0.2, ["PIU_03_HI_01"],
       ["PIU_03_PO_01", "PIU_03_PO_02", "PIU_03_PO_03", "PIU_03_PO_04"]),
    _c("PIU_04", 10.72, 0.2, ["PIU_04_HI_01"],
       ["PIU_04_PO_01", "PIU_04_PO_02", "PIU_04_PO_03"]),
    _c("PIU_05", None, 0.2, [], ["PIU_05_PO_01"]),
    _c("PIU_06", None, 0.2, [],
       ["PIU_06_PO_01", "PIU_06_PO_02", "PIU_06_PO_03"]),
    _c("PIU_07", 12.54, 0.2, ["PIU_07_HI_01"],
       ["PIU_07_PO_02", "PIU_07_PO_03"]),
    _c("CHA_01", 0.9486, 0.1, ["CHA_01_HS_01"], ["CHA_01_PT_01"]),
    _c("CHA_02", 1.4054, 0.1, ["CHA_02_HS_01"], ["CHA_02_PT_01"]),
    _c("HUA_01", 2.5765, 0.2, ["HUA_01_HD_01", "HUA_01_HD_02"],
       ["HUA_01_PD_01", "HUA_01_PD_02", "HUA_01_PD_03"]),
    _c("HUA_02", _HUA02_AREA, 0.2, ["HUA_02_HD_01", "HUA_02_HD_02"],
       ["HUA_02_PD_01", "HUA_02_PD_02", "HUA_02_PD_03"],
       scales=[_HUA02_AREA / HUA02_LEGACY_AREA, 1.0]),
    _c("HMT_01", 7.7929, 0.2, ["HMT_01_HI_01"],
       ["HMT_01_PO_01", "HMT_01_PO_02"]),
    _c("HMT_02", 3.8242, 0.2, ["HMT_02_HI_01"],
       ["HMT_02_PO_01", "HMT_02_PO_02"]),
    _c("TAM_01", 1.6577, 0.2, ["TAM_01_HO_01"],
       ["TAM_01_PO_01", "TAM_01_PO_02", "TAM_01_PO_03"]),
    _c("TAM_02", 0.912, 0.2, ["TAM_02_HO_01"],
       ["TAM_02_PO_01", "TAM_02_PO_02", "TAM_02_PO_03"]),
    _c("TIQ_01", 0.8264, 0.2, ["TIQ_01_HD_01"],
       ["TIQ_01_PO_01", "TIQ_01_PO_02"]),
    _c("TIQ_02", 1.7202, 0.2, ["TIQ_02_HD_01"],
       ["TIQ_02_PO_01", "TIQ_02_PO_02"]),
]}

#: standard pairs processed with workflow_pair (driver order)
PAIRS: list[tuple[str, str]] = [
    ("LLO_01", "LLO_02"),
    ("PAU_01", "PAU_04"), ("PAU_02", "PAU_03"),
    ("PIU_01", "PIU_02"), ("PIU_03", "PIU_04"),
    ("CHA_01", "CHA_02"), ("HUA_01", "HUA_02"), ("HMT_01", "HMT_02"),
    ("TAM_01", "TAM_02"), ("TIQ_01", "TIQ_02"),
]

#: JTU is cascade-filled: Pair1(01,02), Pair2(03,04), Pair3(Pair1's
#: catchment-2 with Pair2's catchment-1), Pair4(Pair1's catchment-1 with
#: Pair3's filled catchment-2), then Pair1/Pair2 recomputed from the
#: filled series (driver lines 58-68). Handled in validation/run_network.py.
JTU_CASCADE = [("JTU_01", "JTU_02"), ("JTU_03", "JTU_04")]


def load_areas(indices_dir) -> dict[str, float]:
    """Read areas from ``iMHEA_Data_Areas.csv`` and update the registry."""
    df = pd.read_csv(Path(indices_dir) / "iMHEA_Data_Areas.csv",
                     encoding="utf-8-sig")
    areas = {str(r.iloc[0]).strip(): float(r.iloc[1])
             for _, r in df.iterrows()}
    for code, a in areas.items():
        if code in CATCHMENTS and CATCHMENTS[code].area is not None:
            CATCHMENTS[code].area = a
    return areas


def load_catchment(raw_root, code: str):
    """Load raw data for one catchment.

    Returns ``(dates_q, q_lps, gauges)`` where gauges is a list of
    (dates, tips_mm); dates_q/q are None for rain-only stations.
    Flow files are concatenated (HUA) with per-file scaling (HUA_02).
    """
    c = CATCHMENTS[code]
    root = Path(raw_root)
    dates_q = q = None
    if c.flow_files:
        parts = []
        for f, s in zip(c.flow_files, c.flow_scales):
            df = read_raw_csv(root / f)
            col = "Flow l/s" if "Flow l/s" in df else df.columns[0]
            parts.append(pd.Series(df[col].to_numpy() * s, index=df.index))
        ser = pd.concat(parts)
        dates_q, q = ser.index, ser.to_numpy()
    gauges = []
    for f in c.rain_files:
        df = read_raw_csv(root / f)
        gauges.append((df.index, df["value"].to_numpy()))
    return dates_q, q, gauges
