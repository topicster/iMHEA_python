# imhea — iMHEA hydrometeorological data processing

Python translation of the iMHEA MATLAB scripts (Ochoa-Tocachi et al. 2018,
*Scientific Data* 5:180080): processing of rainfall and streamflow data from
the Regional Initiative for Hydrological Monitoring of Andean Ecosystems.

**Validated against the published dataset**: discharge and baseflow
reproduce the published CSVs bit-level for all 24 flow catchments; 89.9% of
1,640 index comparisons agree within 0.1% — every residual explained
(`docs/VALIDATION.md`). Nine bugs found in the original MATLAB are fixed by
default with `matlab_compat=True` escape hatches (`docs/CODE_REVIEW.md`).
The full 28-station network reprocesses in ~3 minutes.

## Three ways to use it

**1. Python library**
```python
import imhea

raw = imhea.read_raw_csv("iMHEA_CHA_01_PT_01_raw.csv")   # BOM/CR/flag-aware
tips = imhea.depure(raw.index, raw["value"])
r5 = imhea.aggregate_events(raw.index, tips, scale_min=5, bucket=0.2)

res = imhea.workflow(area_km2, dates_q, q_lps, bucket, gauges, name="MYC_01")
res.daily          # [P, Q, BQ] DataFrame        res.indices.hydro   # 59
fig = imhea.plots.plot_catchment(res.daily)      # publication figure
```

**2. Command line**
```bash
pip install imhea
imhea process --code MYC_01 --area 2.63 --bucket 0.2 \
    --flow flow.csv --gauge rg1.csv --gauge rg2.csv --out ./processed
imhea network --data-root ./Scripts --out ./valout   # full-network rerun
```

**3. Desktop app** — the *iMHEA Data Processor* (Windows/macOS/Linux):
projects, guided setup, background processing, interactive figures, the
72-index table, rating-curve editor, gap-filling report, EN/ES. Run from
source (`pip install -e ".[gui]" && python gui/run_gui.py`) or build
standalone bundles (`packaging/README.md` — one command locally, or
automatic via GitHub Actions).

## Repository map

| Path | Content |
|---|---|
| `src/imhea/` | library: io, clean, aggregate, flow, stats, indices, workflow, plots, registry, cli |
| `gui/` | PySide6 desktop app |
| `tests/` | 50 tests incl. regression vs the published dataset |
| `validation/` | full-network validation harness + metrics |
| `docs/CODE_REVIEW.md` | MATLAB spec: architecture, call graph, issues (specs in `docs/review/`) |
| `docs/VALIDATION.md` | validation report |
| `packaging/` | PyInstaller spec + build guide; CI in `.github/workflows/` |
| `PLAN.md` | project log (7 phases) |

## Citation

If you use this software, cite: Ochoa-Tocachi, B.F. et al. (2018)
High-resolution hydrometeorological data from a network of headwater
catchments in the tropical Andes. *Scientific Data* 5, 180080.
