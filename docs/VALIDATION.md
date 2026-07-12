# Validation report — Python `imhea` vs published MATLAB outputs

**Date:** 2026-07-11 · **Package:** imhea v0.4.0 · **Phase 4 deliverable**

The full network (28 catchments/stations, 9 sites) was reprocessed from the
raw sensor CSVs with the Python pipeline (`validation/run_network.py`,
`matlab_compat=True`) and compared against the published dataset
(`iMHEA_processed/`, `iMHEA_indices/`) of Ochoa-Tocachi et al. (2018).
Metrics: `validation/series_metrics.csv` (177 series comparisons) and
`validation/index_metrics.csv` (1,728 index comparisons). The complete
driver structure of `iMHEA_Raw2Processed.m` was replicated, including the
JTU cascade filling, the HUA logger merges and HUA_02 legacy-area rescale,
JTU_04's eight rain gauges, and the PIU_05/06 cross-fill.

## 1. Time-series products

| Variable | Resolution | Catchments | Median corr | Min corr | Median MAE |
|---|---|---|---|---|---|
| Flow Q      | daily / hourly / HRes | 24 | **1.0000** | 1.0000 | **0.0000** |
| Baseflow BQ | daily                 | 24 | **1.0000** | 1.0000 | **0.0000** |
| Rainfall P  | daily                 | 27 | **1.0000** | 0.9990 | 0.0002 mm |
| Rainfall P  | hourly                | 27 | 1.0000 | 0.9646 | 0.0002 mm |
| Rainfall P  | HRes                  | 27 | 0.9998 | 0.9386 | 0.0001 mm |

- **Discharge and baseflow reproduce the published values bit-level at every
  resolution for all 24 flow catchments** (baseflow via the documented
  `matlab_compat` emulation, see §3.1).
- Rainfall daily totals match everywhere (bias ≤ 0.001%, mass conserved
  exactly). Sub-daily rainfall differences are confined to CHA (a 30-min
  logger site where within-day mass placement by the spline disaggregation
  is sensitive to the sentinel fix, §3.3) and are bias-free: they move
  rainfall by one or two sub-daily bins, never create or destroy volume.

## 2. Indices (59 hydrological + 13 climate × 28 stations)

| Tolerance | Fraction of 1,640 comparisons |
|---|---|
| within 0.1% | **89.9%** |
| within 1%   | 93.4% |
| within 5%   | 96.3% |

Residual deviations by cause:

| Indices | Median dev. | Cause (see §3) |
|---|---|---|
| TL1, TL2 | 34% / 54% | MATLAB day-of-year bug not emulated (§3.2) |
| MH22 | 5.7% | published values inconsistent with current MATLAB source (§3.4) |
| TH3 | 1.5% | pulse-spell definition residual (§3.4) |
| all others | ≤ 0.2% | float-level differences |

## 3. Explained deviations

### 3.1 Published BFI1/K1 contain a gap artifact (flag for erratum?)
`iMHEA_BaseFlowUK.m` marks data gaps as `+Inf` before the 5-day block-minima
search. Blocks that fall entirely inside a gap yield `Inf` minima which can
survive as baseflow "turning points"; MATLAB's linear interpolation then
sets baseflow = total flow on the rising side of every such point and NaN
on the falling side. Published BFI1 values for gappy records are therefore
**inflated** (e.g. CHA_01: 0.277 published vs 0.233 without the artifact;
CHA_02 daily baseflow correlates only 0.49 with the artifact-free series).
Python default excludes gap blocks; `baseflow_ukih(..., matlab_compat=True)`
reproduces the published behaviour exactly (bit-level, §1).

### 3.2 TL1/TL2 (timing of annual minimum)
`iMHEA_MonthlyFlow.m` finds the annual minimum's position within a
year-subset but reads the date from the full array — the published Julian
days are wrong for every year after the first. The Python version computes
correct day-of-year values and does not emulate the bug (reproducing it
would validate garbage against garbage). Expect published TL1/TL2 to be
unreliable network-wide.

### 3.3 Sub-daily rainfall at CHA + intensity indices
The event sentinel in `iMHEA_AggregationCS.m` sits exactly `MaxT` before
the first tip, leaving an event-break decision to float rounding; combined
with 30-min tip stamps at CHA this can move half of a storm's first tip by
up to 30 minutes. Python uses an unambiguous 2·MaxT sentinel. Daily totals
are unaffected; short-duration intensity indices (iMAX1H etc.) differ at
CHA only. The IDC algorithm itself reproduces published intensities exactly
when fed MATLAB's own rainfall series.

### 3.4 MH22 / TH3
On identical (bit-level) daily flow series, a literal transcription of the
current `iMHEA_Pulse.m` gives MH22 = 36.65 for CHA_01 while the published
CSV holds 35.12 — the published pulse-volume indices appear to come from an
earlier code version and cannot be reproduced from the current MATLAB
source. TH3 has a comparable ±1.5% residual.

## 4. Fixed-by-default behaviours (matlab_compat escape hatches)

FillGaps cutend restore (issue 8), Level2Flow NaN→0 (7), UKIH Inf turning
points (§3.1), Pulse year misalignment & TH/TL min-vs-max (3), IDC stale
buffer (4), FH7 double normalisation (5), QYEAR fallback units (6),
MonthlyRain empty-month 0 mm (11), monthly day-of-year (2), RA6/RA7 log(0)
(13), single-tip mass conservation for 0.254 mm buckets, CS sentinel.
Numbers refer to CODE_REVIEW.md §4.

## 5. Reproducing this validation

```bash
python validation/run_network.py <folder with iMHEA_raw etc.> <out_dir>
```
Runtime: ~3 minutes for the full network (MATLAB original: hours).
