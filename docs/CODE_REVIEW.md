# iMHEA MATLAB Code Review — Phase 1 Deliverable

**Date:** 2026-07-11 · **Status:** Complete
**Purpose:** Full understanding of the 35 MATLAB scripts before translation. Detailed
function-by-function specifications live in `docs/review/` (A–F). This master document gives
the architecture, conventions, and the consolidated list of issues requiring Boris's decision.

## 1. Detailed specification files

| File | Covers |
|---|---|
| `review/A_preprocessing.md` | Depure, Voids, MonitoringGaps, FillGaps, Aggregation, AggregationCS, AggregationLI, Average |
| `review/B_processing_io.md` | ProcessP, ProcessQ, Level2Flow, Raw2Processed, SaveDailyCSV, SaveDoubleCSV, SaveSingleCSV |
| `review/C_flow_analysis.md` | BaseFlow, BaseFlowUK, FDC, IDC, Pulse, MonthlyFlow, MonthlyRain |
| `review/D_indices.md` | Indices, IndicesPlus, IndicesTotal, ClimateP, ClimateTotal, Pair |
| `review/E_workflows_plots.md` | Workflow, WorkflowPair, WorkflowRain, Plot2/3/4, PlotPair + full call graph |
| `review/F_paper.md` | Ochoa-Tocachi et al. 2018 methods summary |

## 2. Pipeline architecture

```
raw sensor CSVs (PD tips / HW level or flow; flags I,D,X,P,V)
        │
        ▼
iMHEA_Raw2Processed (driver SCRIPT: hard-coded stations, buckets 0.1/0.2/0.254 mm,
        │            site one-offs: HUA merge, HUA_02 area rescale Area/2.71, JTU cascade)
        ▼
iMHEA_Workflow / WorkflowPair / WorkflowRain (per catchment / pair / rain-only)
   1. iMHEA_Depure          – zero out tips ≤1.1 s apart (HOBO artefact)
   2. grid selection        – rounded median discharge interval (Workflow) or 5 min (WorkflowRain)
   3. iMHEA_AggregationCS   – tips → cumulative curve → clamped cubic spline → interval rain
                              (events split at MaxT=bucket/0.2mm·h⁻¹; bias>25% → linear fallback;
                               11-pass clamp/rescale; single tips at 3 mm/h; half-tip padding)
   4. iMHEA_FillGaps        – double-mass regression between gauges, fill only if R²≥0.99
   5. nanmean across gauges → catchment precipitation
   6. iMHEA_Average         – align discharge to grid (two-pointer mean over bins)
   7. iMHEA_Aggregation     – P to 1hr & 1day; iMHEA_Average – Q to 1hr & 1day, /AREA
   8. iMHEA_BaseFlowUK      – UKIH smoothed minima (5-day blocks, 0.9 factor) → daily BQ
   9. iMHEA_IndicesTotal    – 59 hydrological + 13 climate indices
        ├─ iMHEA_Indices / IndicesPlus (magnitude/frequency/duration/timing/flashiness)
        │    ├─ iMHEA_FDC   – Gringorten (i−0.44)/(k+0.12), spline percentile interpolation
        │    ├─ iMHEA_Pulse – high/low pulse counts & durations vs thresholds
        │    ├─ iMHEA_BaseFlow – Chapman filter BQ=min(k/(1+C)·BQ₋₁+C/(1+C)·(Q+αQ₋₁), Q),
        │    │                   C=0.085·Δt(days), k from 7-day log-recession regressions (R²≥0.8)
        │    └─ iMHEA_MonthlyFlow
        └─ iMHEA_ClimateP / ClimateTotal (seasonality, intensities)
             ├─ iMHEA_IDC   – max intensities for durations 5 min–2 days
             └─ iMHEA_MonthlyRain
        ▼
Save*CSV (HighRes/1hr/1day processed CSVs; dd/mm/yyyy HH:MM:SS + %8.4f, NaN literal)
```

Full caller→callee table: see `review/E_workflows_plots.md`.

## 3. Cross-cutting conventions (must be handled globally in Python)

- **Time:** MATLAB `datenum` (float days). Interval index `nd = 1440/scale_minutes`. Bins are
  right-closed/right-labelled. A global −0.25 s shift dodges float boundary errors. Python:
  pandas DatetimeIndex end-labelled resampling; the −0.25 s hack becomes unnecessary but must be
  remembered when reproducing MATLAB output exactly.
- **Gaps:** encoded as NaN *marker rows* inserted in the series (flag V), not by timestamp
  inspection. `iMHEA_Voids` extracts/reapplies them with strict inequalities.
- **Percentiles:** Gringorten plotting position + full cubic `spline` interpolation everywhere.
  `np.percentile` will NOT reproduce these; we implement `imhea.stats.gringorten_percentile`.
- **Years:** calendar years, 365 days (never 366/365.25), Feb=28 in monthly math.
- **Units:** P mm per interval; Q l/s raw → l/s/km² after area normalisation (timing of the
  normalisation differs between outputs — see Issue 12).
- **Toolbox dependency:** `regression` (Deep Learning Toolbox) used in BaseFlow/FillGaps —
  replaced by `numpy.polyfit`/`scipy.stats.linregress` (mathematically identical).
- **Raw file format:** UTF-8 BOM, CR-only line endings, `dd/mm/yyyy HH:MM:SS`, Flag column
  (I=launch, D=download, X=bad tip, P=anomalous intensity, V=gap).

## 4. Consolidated issues for Boris — decide: reproduce or fix

**Confirmed bugs (spot-checked in source):**
1. `WorkflowPair:104` captures `iMHEA_Pair` outputs in the wrong order (`IDC1,FDC1,IDC2,FDC2`
   vs declared `FDC1,FDC2,IDC1,IDC2`) → returned duration/flow curves are scrambled.
2. `MonthlyFlow`/`MonthlyRain`: day-of-year of annual min/max uses a subset index against the
   full date array → wrong for every year after the first (affects timing indices TL1/TL2/TH1).
3. `Pulse`: per-year frequencies use pre-NaN-filter year indexing → wrong when NaNs exist;
   TL/TH report minimum opposite-pulse duration rather than intended quantity (SUSPECTED intent).
4. `IDC`: moving-sum buffer only partially overwritten per duration → mean/median intensity
   columns contain stale values (max column is safe — and only max is published).
5. `IndicesPlus:201`: FH7 uses per-year-mean element then divides by record length again
   (double normalisation); FH6 and siblings use the count element.
6. `Indices:86`: QYEAR NaN-fallback missing ×365 (gives mm/day not mm/yr) and computed after
   RRa, leaving RRa NaN in that branch.
7. `Level2Flow`: NaN water level → Q=0 instead of NaN; negative stage → complex numbers.
8. `FillGaps` with `cutend=true`: restore step re-injects original NaNs (undoing fills) and can
   crash on dimension mismatch.
9. `BaseFlowUK`: returns block count as `k` unless recession flag passed; last turning point
   unconditionally deleted.

**Design quirks / inconsistencies (probably reproduce, flag in docs):**
10. `Average`: bins with no samples and no NaN marker become 0 (not NaN) — silent zero flow.
11. `MonthlyRain` empty month/year → 0 mm (looks dry); `MonthlyFlow` → NaN. Asymmetric.
12. HRes Q normalised by area only on the last line of Workflow (after indices/plots); hourly
    and daily normalised earlier. Inconsistent but published output depends on it.
13. Record-length denominators vary between indices (span vs span+1 days); RA6/RA7 take
    log(0)=−Inf on intermittent streams; zero median silently replaced by mean.
14. No minimum-data-completeness thresholds anywhere (partial years/months count as full).
15. `AggregationCS` vs `LI`: floor/ceil start-cut difference and sentinel offset difference.
16. O(n²) loops in Voids, BaseFlow, FillGaps, Pair (recomputation) — will be vectorised;
    results unchanged.

**Recommendation:** implement the *intended* (fixed) behaviour as default, with a
`matlab_compat=True` option where feasible for validation against published outputs; document
every deviation in the validation report. Items 1–9 are clear fixes; items 10–15 need Boris's
call on scientific intent.

## 5. Proposed Python package layout (Phase 2 target)

```
src/imhea/
  io.py         # raw CSV readers (BOM/CR/flags), processed CSV writers (MATLAB-format compatible)
  clean.py      # depure, voids, monitoring_gaps, fill_gaps
  aggregate.py  # aggregation (linear/CS/LI), average, event→series
  flow.py       # level2flow (Kindsvater–Shen), baseflow (Chapman, UKIH)
  stats.py      # gringorten percentiles, FDC, IDC, pulse, monthly
  indices.py    # hydrological (59) + climate (13) indices, pair comparisons
  workflow.py   # catchment / pair / rain-only pipelines
  plots.py      # Phase 5
  cli.py        # Phase 4+
```
