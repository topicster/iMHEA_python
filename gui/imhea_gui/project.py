"""Project model and .imhea file persistence (JSON)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

import imhea
from imhea.flow import DEFAULT_COEFF, DEFAULT_WEIR


@dataclass
class CatchmentCfg:
    code: str
    area: float | None = None
    bucket: float = 0.2
    flow_files: list[str] = field(default_factory=list)
    flow_scales: list[float] = field(default_factory=list)
    flow_source: str = "flow"          #: 'flow' column or 'level' via rating
    weir: tuple = DEFAULT_WEIR
    coeff: tuple = DEFAULT_COEFF
    rain_files: list[str] = field(default_factory=list)

    @property
    def rain_only(self) -> bool:
        return not self.flow_files


@dataclass
class PairCfg:
    code1: str
    code2: str

    @property
    def label(self) -> str:
        return f"{self.code1} + {self.code2}"


class Project:
    """A processing project: catchment configs, pairs, options, results."""

    def __init__(self, name: str = "untitled"):
        self.name = name
        self.path: Path | None = None
        self.catchments: dict[str, CatchmentCfg] = {}
        self.pairs: list[PairCfg] = []
        self.matlab_compat = False
        self.results: dict[str, object] = {}      #: in-memory, not persisted

    # -- persistence -------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "version": 1,
            "name": self.name,
            "matlab_compat": self.matlab_compat,
            "catchments": {c: asdict(cfg)
                           for c, cfg in self.catchments.items()},
            "pairs": [[p.code1, p.code2] for p in self.pairs],
        }

    def save(self, path) -> None:
        self.path = Path(path)
        self.name = self.path.stem
        self.path.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path) -> "Project":
        d = json.loads(Path(path).read_text())
        p = cls(d.get("name", Path(path).stem))
        p.path = Path(path)
        p.matlab_compat = bool(d.get("matlab_compat", False))
        for code, c in d.get("catchments", {}).items():
            c.pop("rain_only", None)
            c["weir"] = tuple(c.get("weir", DEFAULT_WEIR))
            c["coeff"] = tuple(c.get("coeff", DEFAULT_COEFF))
            p.catchments[code] = CatchmentCfg(**c)
        p.pairs = [PairCfg(a, b) for a, b in d.get("pairs", [])]
        return p

    @classmethod
    def from_registry(cls, data_root) -> "Project":
        """Built-in 'Explore the iMHEA network' project."""
        from imhea.registry import CATCHMENTS, PAIRS, JTU_CASCADE, load_areas
        root = Path(data_root)
        try:
            load_areas(root / "iMHEA_indices")
        except Exception:
            pass
        p = cls("iMHEA-network")
        p.matlab_compat = True
        for code, c in CATCHMENTS.items():
            p.catchments[code] = CatchmentCfg(
                code=code, area=c.area, bucket=c.bucket,
                flow_files=[str(root / "iMHEA_raw" / f)
                            for f in c.flow_files],
                flow_scales=list(c.flow_scales),
                rain_files=[str(root / "iMHEA_raw" / f)
                            for f in c.rain_files])
        p.pairs = [PairCfg(a, b) for a, b in PAIRS + JTU_CASCADE]
        return p

    # -- data loading ------------------------------------------------------
    def load_raw(self, code: str):
        """(dates_q, q, gauges) for one catchment, honouring flow_source."""
        cfg = self.catchments[code]
        dates_q = q = None
        if cfg.flow_files:
            parts = []
            scales = cfg.flow_scales or [1.0] * len(cfg.flow_files)
            for f, s in zip(cfg.flow_files, scales):
                df = imhea.read_raw_csv(f)
                if cfg.flow_source == "level" and "Level cm" in df:
                    vals = imhea.level2flow(df["Level cm"].to_numpy(),
                                            cfg.weir, cfg.coeff)
                elif "Flow l/s" in df:
                    vals = df["Flow l/s"].to_numpy()
                else:
                    vals = df["value"].to_numpy()
                parts.append(pd.Series(vals * s, index=df.index))
            ser = pd.concat(parts)
            dates_q, q = ser.index, ser.to_numpy()
        gauges = []
        for f in cfg.rain_files:
            df = imhea.read_raw_csv(f)
            gauges.append((df.index, df["value"].to_numpy()))
        return dates_q, q, gauges

    def file_summary(self, path: str) -> str:
        """Short description of a raw file for the setup tab."""
        try:
            df = imhea.read_raw_csv(path)
            step = np.median(np.diff(df.index.asi8)) / 60e9
            cols = " + ".join(c for c in df.columns
                              if c not in ("flag", "value"))
            return (f"{len(df):,} rows · {step:.0f} min · {cols} · "
                    f"{df.index[0]:%Y-%m} → {df.index[-1]:%Y-%m}")
        except Exception as e:
            return f"unreadable: {e}"
