# E. Workflow orchestrators & plotting functions — MATLAB spec

Files covered (all read line-by-line):
`iMHEA_Workflow.m` (141 lines), `iMHEA_WorkflowPair.m` (104 lines), `iMHEA_WorkflowRain.m` (103 lines),
`iMHEA_Plot2.m` (39), `iMHEA_Plot3.m` (37), `iMHEA_Plot4.m` (167, **script not function**), `iMHEA_PlotPair.m` (78).

Source dir: `.../iMHEA/Protocolos/Scripts/iMHEA_scripts/`

Convention used below: dates internally are MATLAB `datenum` (days); `nd = 1440/int_HRes` = intervals per day; integer time index = `round(datenum * nd)`.

---

## 1. `iMHEA_Workflow` — full single-catchment pipeline

### 1.1 Signature

```matlab
function [DataHRes,Data1day,Data1hr,Indices,Climate] = iMHEA_Workflow(AREA,DateQ,Q,bucket,varargin)
```

Inputs:
| Arg | Meaning | Units |
|---|---|---|
| `AREA` | catchment area | km² |
| `DateQ` | discharge timestamps (datetime, `dd/mm/yyyy hh:mm:ss`) | — |
| `Q` | discharge | l/s |
| `bucket` | tipping-bucket resolution | mm/tip |
| `varargin` | pairs `DateP1,P1,DateP2,P2,...` — one **(date, mm-per-tip event)** pair per rain gauge | mm |

varargin logic (lines 36–48): `nrg = floor((nargin-4)/2)`. If `nrg>=1 && rem(nrg,1)==0` proceed, else print "incomplete rain gauge data", return all outputs `= []`. Note `rem(nrg,1)==0` is always true after `floor` — see bugs §1.4.

Outputs:
| Output | Columns (order!) | Units |
|---|---|---|
| `DataHRes` | `[datenum, P, Q]` at max resolution (= median discharge interval, e.g. 5 min) | P mm/interval (gauge-average), Q **l/s/km²** (normalised at the very end, line 141) |
| `Data1day` | `[datenum, P, Q, BQ]` | P mm/day, Q & BQ l/s/km² |
| `Data1hr` | `[datenum, P, Q]` | P mm/hr, Q l/s/km² |
| `Indices` | hydrological index vector (from `iMHEA_IndicesTotal`) | mixed |
| `Climate` | climate index vector | mixed |

### 1.2 Orchestration (exact call sequence)

1. **Print banner** using `inputname(1)` (the *caller's variable name* for AREA) — line 32. No Python equivalent of `inputname`; must be replaced by an explicit name argument.
2. **Depure tips** (lines 51–54), per gauge i:
   `[NewEvent_mm{i}] = iMHEA_Depure(varargin{2*i-1},varargin{2*i});`
3. **Determine max resolution from discharge** (lines 58–60):
   ```matlab
   int_HRes = diff(datenum(DateQ))*1440;
   int_HRes = round(nanmedian(int_HRes)); % Worst discharge interval defines the max resolution
   nd = 1440/int_HRes;
   ```
   Comment says "worst" but uses **median**, rounded to whole minutes.
4. **Aggregate each gauge to `int_HRes` with cubic-spline method** (lines 62–65):
   `[PrecHRes{i}] = iMHEA_AggregationCS(varargin{2*i-1},NewEvent_mm{i},int_HRes,bucket);`
   Single-output call → `PrecHRes{i}` is a packed matrix; cols 1–2 = [datenum, P] are used.
5. **Gap-fill and average across gauges** (lines 68–101), only if `nrg > 1`:
   - All pairwise combinations `combnk(1:nrg,2)`; for each pair
     `[PrecHResFill{i}] = iMHEA_FillGaps(a(:,1),a(:,2),b(:,1),b(:,2));`
     (nargout==1 → FillGaps returns packed `[datenum, P1filled, P2filled]`).
   - Build integer time axis `DateP_HRes = (round(min_start*nd) : round(max_end*nd))'` spanning the union of all pair periods; scatter each pair's 2 filled columns into `Precp_Fill_Compiled` (n × 2·C(nrg,2)) via `ismember(DateP_HRes, round(dates*nd))`.
   - **Averaging across gauges happens here** (line 94): `P_HRes = nanmean(Precp_Fill_Compiled,2);` — mean over all 2·C(nrg,2) gap-filled columns (each gauge appears nrg−1 times, so equal weight per gauge, but each occurrence is a *differently gap-filled* copy).
   - If `nrg == 1`: `DateP_HRes = PrecHRes{1}(:,1); P_HRes = PrecHRes{1}(:,2);` (no fill).
6. **Average discharge to same resolution** (lines 104–105):
   `[DateQ_HRes,Q_HRes] = iMHEA_Average(DateQ,Q,int_HRes); DateQ_HRes = datenum(DateQ_HRes);` (Q still l/s).
7. **Compile `DataHRes`** (lines 109–118): integer axis over union of P and Q periods; then
   ```matlab
   DataHRes(ismember(DataHRes,round(DateP_HRes*nd)),2) = P_HRes;    % line 115
   DataHRes(ismember(DataHRes,round(DateQ_HRes*nd)),3) = Q_HRes;    % line 116
   DataHRes(:,1) = DataHRes(:,1)/nd;                                % line 118
   ```
   Note `ismember` is applied to the **whole 3-column matrix**, not `DataHRes(:,1)` — see bugs §1.4.
8. **Aggregate to 1 day / 1 hr** (lines 122–128):
   ```matlab
   [Data1day] = iMHEA_Aggregation(DataHRes(:,1),DataHRes(:,2),1440);
   [Data1hr]  = iMHEA_Aggregation(DataHRes(:,1),DataHRes(:,2),60);
   Data1day(:,3:end) = []; Data1hr(:,3:end) = [];       % keep [Date,P] only
   [~,Data1day(:,3)] = iMHEA_Average(DataHRes(:,1),DataHRes(:,3)/AREA,1440);
   [~,Data1hr(:,3)]  = iMHEA_Average(DataHRes(:,1),DataHRes(:,3)/AREA,60);
   ```
   **Normalisation by area (l/s → l/s/km²) happens here** for the daily/hourly products (`/AREA` inline).
9. **Daily baseflow** (line 130): `[~,Data1day(:,4)] = iMHEA_BaseFlowUK(DataHRes(:,1),DataHRes(:,3)/AREA);` (Gustard et al. 1992 UK smoothed-minima; returns daily BQ, l/s/km²).
10. **Plot** (line 133): `iMHEA_Plot3(datetime(DataHRes(:,1),'ConvertFrom','datenum'),DataHRes(:,2),DataHRes(:,3))` — P and **un-normalised Q (l/s)**.
11. **Indices** (line 139): `[Climate,Indices] = iMHEA_IndicesTotal(DateFormatHRes,DataHRes(:,2),DataHRes(:,3),AREA,1);` — Q passed in **l/s** with AREA; trailing `1` = plot flag. Output order is `[Climate,Indices]` (matches `iMHEA_IndicesTotal`'s declared order).
12. **Only then** (line 141, last line): `DataHRes(:,3) = DataHRes(:,3)/AREA;` — the HRes Q is normalised to l/s/km² *after* plotting and index calculation. Order matters for translation.

### 1.3 Edge cases & quirks
- `int_HRes` derived from discharge only; rain is spline-resampled (AggregationCS) to that interval — a 15-min logger drags all 5-min rain data down to 15-min resolution.
- With gappy data the `nanmean` at line 94 silently averages however many filled columns exist at each timestep (1..2·C(nrg,2)); no minimum-gauge requirement.
- `combnk` is from the Statistics Toolbox (deprecated in favour of `nchoosek`).
- Alignment always via `round(datenum*nd)`; datenum float precision at 5-min resolution is fine, but any gauge timestamps not on the grid are shifted by rounding.
- Output `Data1day`/`Data1hr` date columns are datenum produced by `iMHEA_Aggregation`'s packed single-output form `[datenum(NewDate),NewP,CumP,VoidP]`.

### 1.4 Suspected bugs
- **SUSPECTED (validation no-op), line 37**: `if nrg>=1 && rem(nrg,1)==0` — `nrg` is already `floor`'d, so `rem(nrg,1)==0` is always true. An odd varargin count (a date without its P vector) is *not* detected; the trailing argument is silently ignored. Intended check was presumably `rem(nargin-4,2)==0`.
- **SUSPECTED (fragile indexing), lines 115–116**: `ismember(DataHRes, round(DateP_HRes*nd))` runs over all 3 columns and yields an n×3 logical, then used as a row subscript. It works only *by accident*: at line 115 cols 2–3 are all NaN (never members); at line 116 col 2 contains small mm values that can never equal the huge integer time indices (~2×10⁸). Any refactor (or a P value coinciding with a small `nd` index) breaks it. Should be `ismember(DataHRes(:,1), ...)`.
- **SUSPECTED (size mismatch risk), same lines**: assignment assumes the number of matched rows exactly equals `length(P_HRes)` / `length(Q_HRes)`; duplicate rounded indices in `DateP_HRes` would throw a MATLAB size error.

---

## 2. `iMHEA_WorkflowPair` — paired-catchment assimilation

### 2.1 Signature

```matlab
function [DataHRes,Data1day,Data1hr,Indices,Climate,PM,QM,FDC1,FDC2,IDC1,IDC2] = iMHEA_WorkflowPair(DataHRes1,DataHRes2)
```

Inputs: each `DataHResi = [datenum, P (mm, gauge-avg), Q (l/s/km², already normalised)]` — i.e. the `DataHRes` output of `iMHEA_Workflow`. No further area normalisation is done here (areas passed as 1 downstream).

Outputs (per docstring):
| Output | Columns | Units |
|---|---|---|
| `DataHRes` | `[Date, P1, Q1, P2, Q2]` at common max resolution | mm; l/s/km² |
| `Data1day` | `[Date, P1, Q1, BQ1, P2, Q2, BQ2]` | mm/day; l/s/km² |
| `Data1hr` | `[Date, P1, Q1, P2, Q2]` | mm/hr; l/s/km² |
| `Indices`, `Climate` | 2-column matrices (catchment 1, catchment 2) from `iMHEA_Pair` | mixed |
| `PM`, `QM` | monthly P (mm) / monthly mean flow, 12×2 [Jan..Dec] | mm; l/s/km² (docstring says l/s but Q is normalised) |
| `FDC1,FDC2,IDC1,IDC2` | duration curves — **scrambled, see bug below** | — |

### 2.2 Orchestration

1. **Common interval** (lines 40–44): `int_HRes = round(max([nanmedian(diff(D1)*1440), nanmedian(diff(D2)*1440)]))`; `nd = 1440/int_HRes`. The *coarser* catchment defines resolution.
2. **Resample the finer catchment** (lines 46–62): whichever catchment has the smaller interval gets
   `iMHEA_Aggregation(Date,P,int_HRes)` (sum P) + `iMHEA_Average(Date,Q,int_HRes)` (mean Q), reassembled as `[Date,P,Q]`.
3. **Cross-catchment precipitation gap-fill** (line 67):
   `[DataHRes] = iMHEA_FillGaps(DataHRes1(:,1),DataHRes1(:,2),DataHRes2(:,1),DataHRes2(:,2));`
   → packed `[Date, P1filled, P2filled]`. Comment notes gap-filling "not recommended for discharge" — Q is *not* filled.
4. **Reshape to `[Date,P1,Q1,P2,Q2]`** (lines 71–81):
   ```matlab
   DataHRes(:,4:5) = nan;
   DataHRes(:,1) = date_start:date_end;                 % line 75, integer index
   DataHRes(:,4) = DataHRes(:,3); DataHRes(:,3) = nan;  % move P2 to col 4
   DataHRes(ismember(DataHRes(:,1),round(DataHRes1*nd)),3) = DataHRes1(:,3);  % line 78, Q1
   DataHRes(ismember(DataHRes(:,1),round(DataHRes2*nd)),5) = DataHRes2(:,3);  % line 79, Q2
   DataHRes(:,1) = DataHRes(:,1)/nd;
   ```
5. **1-day / 1-hr products** (lines 85–100):
   - `[Data1day] = iMHEA_Aggregation(P1,1440)`; then `Data1day(:,3:end) = nan;` (note: **nan'ed, not deleted** — unlike `iMHEA_Workflow`); `[~,Data1day(:,5)] = iMHEA_Aggregation(P2,1440)`.
   - `[Data1hr]` same at 60 min with P2 into **col 4**.
   - Flows: `[~,Data1day(:,3)] = iMHEA_Average(Q1,1440)`, `col 6 = Average(Q2,1440)`, `Data1hr col 3 = Average(Q1,60)`, `col 5 = Average(Q2,60)`.
   - Baseflow: `[~,Data1day(:,4)] = iMHEA_BaseFlowUK(Q1)`, `col 7 = iMHEA_BaseFlowUK(Q2)`.
   - Final layouts confirmed: `Data1day = [Date,P1,Q1,BQ1,P2,Q2,BQ2]`, `Data1hr = [Date,P1,Q1,P2,Q2]`.
6. **Indices** (lines 103–104, last lines):
   ```matlab
   [Indices,Climate,PM,QM,IDC1,FDC1,IDC2,FDC2] = iMHEA_Pair(Date1,DataHRes(:,2),DataHRes(:,3),1,Date1,DataHRes(:,4),DataHRes(:,5),1);
   ```
   Areas = 1 (data pre-normalised). Comparative plots are produced inside `iMHEA_Pair`/`iMHEA_IndicesTotal`, not here.

### 2.3 Edge cases & quirks
- If both catchments already share the interval, no resampling branch runs (elseif chain, equality falls through).
- Q series are placed by date-matching only; leading/trailing periods where only one catchment has data are NaN.
- `Data1day` cols 3:end being `nan`-ed (not deleted) means the pre-existing CumP/VoidP columns from Aggregation's packed output are recycled as Q/BQ slots — column count works out to exactly 7, but only accidentally.

### 2.4 Suspected bugs
- **BUG (confirmed by signature comparison), line 104**: `iMHEA_Pair` is declared as
  `function [Indices,Climate,PM,QM,FDC1,FDC2,IDC1,IDC2] = iMHEA_Pair(...)` (iMHEA_Pair.m line 1),
  but WorkflowPair captures positions 5–8 as `IDC1,FDC1,IDC2,FDC2`. Therefore:
  `WorkflowPair.IDC1 = Pair.FDC1`, `WorkflowPair.FDC1 = Pair.FDC2` (catchment 2's FDC returned as catchment 1's!), `WorkflowPair.IDC2 = Pair.IDC1`, `WorkflowPair.FDC2 = Pair.IDC2`. All four curve outputs are mislabeled/scrambled.
- **SUSPECTED (whole-matrix ismember), lines 78–79**: `ismember(DataHRes(:,1), round(DataHRes1*nd))` — the second argument is the **entire 3-column matrix** (dates, P·nd, Q·nd), so membership is tested against scaled P and Q values too. Safe in practice only because scaled P/Q (≤ ~10⁵) never reach date-index magnitude (~10⁸). Should be `round(DataHRes1(:,1)*nd)`. Also assumes matched-row count equals `length(DataHRes1(:,3))`.
- **SUSPECTED (rigid length assumption), line 75**: `DataHRes(:,1) = date_start:date_end;` errors if FillGaps output length ≠ `date_end-date_start+1` (holds only because FillGaps emits a contiguous `(DI:DF)'` axis at the same `nd`).
- **SUSPECTED (docstring)**: header says `QM` is in l/s, but with pre-normalised inputs and A=1 it is l/s/km².

---

## 3. `iMHEA_WorkflowRain` — precipitation-only pipeline

### 3.1 Signature

```matlab
function [DataHRes,Data1day,Data1hr,Climate] = iMHEA_WorkflowRain(bucket,varargin)
```

Inputs: `bucket` [mm/tip]; varargin = `DateP1,P1,DateP2,P2,...` (same pairing as Workflow). `nrg = floor((nargin-1)/2)` with the same always-true `rem(nrg,1)==0` check (lines 28–39; same validation no-op as §1.4).

Outputs: `DataHRes = [datenum, P]` at **fixed 5-min** resolution; `Data1day`, `Data1hr = [datenum, P]`; `Climate` = climate index vector.

### 3.2 Orchestration
1. Banner uses `inputname(1)` — that is the **bucket** variable's name, printed as the "catchment" name (quirk).
2. `iMHEA_Depure` per gauge (lines 42–45) — identical to Workflow.
3. **`int_HRes = 5;` hard-coded** (line 49), `nd = 288`. Then `iMHEA_AggregationCS(DateP_i, NewEvent_mm{i}, 5, bucket)` per gauge (lines 52–55).
4. Gap-fill + averaging block (lines 57–90) is a verbatim copy of Workflow §1.2 step 5, ending `DataHRes(:,2) = nanmean(Precp_Fill_Compiled,2)` (line 85) or the single-gauge passthrough.
5. `iMHEA_Aggregation(...,1440)` and `(...,60)`, keep cols 1–2 (lines 94–97).
6. `iMHEA_Plot3(datetime(...), P)` (line 99).
7. `[Climate] = iMHEA_ClimateTotal(DateFormatHRes,DataHRes(:,2),1);` (line 103, last line; `1` = plot flag).

### 3.3 Edge cases, quirks, suspected bugs
- Docstring line 4 names the function `iMHEA_Workflow(bucket,...)` and mentions "discharge data" — copy-paste leftovers; there is no discharge here.
- Same varargin validation no-op as Workflow (SUSPECTED bug, line 29).
- Unlike Workflow, `DataHRes` here is built by growing assignment (`DataHRes(:,1) = ...`), not preallocated — equivalent result.
- No indices output besides `Climate` (no `Indices`).

---

## 4. Plot functions (to be reimagined, not cloned)

### 4.1 `iMHEA_Plot2(Date1,P1,Date2,P2,Date3,P3)` — 3 independent series
- `figure` + `subplot(3,1,i)`: three stacked line plots, each with its **own Date vector** (series may have different time bases).
- Y-labels come from `inputname(2/4/6)` — the caller's variable names (untranslatable; replace with explicit labels).
- After plotting, x-limits of all 3 subplots are unified to the min/max across the three (lines 33–37); `grid on; box on`.
- Linear axes, no inverted rainfall, no legends, no computations.
- Used internally by `iMHEA_Aggregation`/`iMHEA_Average` in debug mode as (original, aggregated, voids).

### 4.2 `iMHEA_Plot3(Date,varargin)` — n series sharing one Date vector
- `n = nargin-1` stacked subplots, `plot(Date,varargin{i})` each; guard `if nargin < 2 → return`.
- X-limits unified across subplots; seed `XLIM = [datetime([inf inf inf]) datetime([0 0 0])]` (line 23) — **assumes `Date` is a `datetime`**; callers must convert datenum first (the workflows do).
- No y-labels, no legends, linear axes, no inverted rainfall. Pure quick-look plot.
- This is the plot the workflows emit for `[P, Q]` (Workflow, with Q still in l/s) or `[P]` (WorkflowRain).

### 4.3 `iMHEA_Plot4` — **script, not a function** (network-wide summary figure)
- Operates on ~28 hard-coded workspace variables `iMHEA_<SITE>_DataHRes` (LLO, JTU, PAU, PIU, CHA, HUA, HMT, TAM, TIQ pairs) plus `iMHEA_Names_Text`.
- **Computations inside the script** (these matter):
  - `[~,MonthlyP(:,k),<site>_IDC] = iMHEA_ProcessP(D(:,1),D(:,2))` for 28 sites (12×28 monthly P, mm/month, and max intensity–duration curves).
  - `[~,MonthlyQ(:,k),<site>_FDC] = iMHEA_ProcessQ(D(:,1),D(:,3))` for 25 sites (monthly mean flow + flow duration curves). Note: `iMHEA_ProcessQ(Date,Q,A,...)` is called **without the area argument** — Q is already l/s/km².
  - Unit conversion line 70–71: `MDays = [31 28 ...]'; iMHEA_MonthlyQ = iMHEA_MonthlyQ.*MDays/1000000*86400;` → l/s/km² to **mm/month** (fixed 28-day February, no leap years).
- One `figure`, 2×2 layout:
  - `subplot(2,2,1)`: `parallelcoords(MonthlyP','group',iMHEA_Names_Text{:,4},'Labels',{'J','F',...})` — average monthly precipitation, mm/month, x = 12 months.
  - `subplot(2,2,2)`: same with `MonthlyQ'` grouped by `iMHEA_Names_Text{1:25,2}` — monthly discharge, mm/month.
  - `subplot(2,2,3)`: **semilogx** of all 28 IDCs — x = duration (min), `XLim [5 2880]`, XTicks copied from LLO_01's IDC durations; y = rainfall intensity [mm/h]. Title "Maximum Intensity-Duration Curves".
  - `subplot(2,2,4)`: **semilogy** of all 25 FDCs with inline conversion `FDC(:,2)/1000000*86400` (l/s/km² → mm/day); x = exceedance probability [%], `XLim [-5 105]`; `YLim` set to `[0.0001 1000]` (line 103) then immediately overridden to `[0.0001 100]` (line 106 — quirk, second wins). Title "Flow Duration Curves".
- Legends mostly commented out / `legend('boxoff')` without entries. Fully non-reusable as-is; in Python this becomes a parameterised multi-site summary function.

### 4.4 `iMHEA_PlotPair(iMHEA_DataPair)` — paired-catchment dashboard
- Input: `[Date(datenum), P1, Q1, P2, Q2]` (the `DataHRes` from WorkflowPair); converts col 1 with `datetime(...,'ConvertFrom','datenum')`.
- **No `figure` call** — draws into the current figure (quirk; deliberate `hold on` everywhere so multiple pairs can be overlaid).
- 4×4 subplot grid, two blocks:
  - Main (cols 1–3): `subplot(4,4,1:3)` P1 [mm] (panel "A"); `subplot(4,4,5:7)` P2 [mm], red (panel "B"); `subplot(4,4,[9:11,13:15])` Q1 (blue) & Q2 (red) overlaid [l s⁻¹ km⁻²] with legend 'Catchment 1'/'Catchment 2' (panel "C").
  - Right column (col 4): duplicates of the same three plots (`4`, `8`, `[12,16]`, panels "D","E","F") — intended as manual-zoom insets.
- Linear axes; rainfall **not** inverted; panel letters added via `text(...,'Units','normalized','FontWeight','bold')`. No computations besides datenum→datetime.

---

## 5. Complete call graph (all 35 scripts)

Extracted with `grep -o "iMHEA_[A-Za-z0-9]*" *.m` per file, then filtered manually to **actual code calls** (comment-only mentions and workspace variable names like `iMHEA_LLO_01_DataHRes`, `iMHEA_Names_Text` excluded; those exclusions are noted).

| Caller | Calls (code, not comments) |
|---|---|
| iMHEA_Aggregation | iMHEA_Voids; iMHEA_Plot2, iMHEA_Plot3 (debug-flag only) |
| iMHEA_AggregationCS | iMHEA_Voids |
| iMHEA_AggregationLI | iMHEA_Voids |
| iMHEA_Average | iMHEA_Voids; iMHEA_Plot2, iMHEA_Plot3 (debug-flag only) |
| iMHEA_BaseFlow | — |
| iMHEA_BaseFlowUK | iMHEA_Average |
| iMHEA_ClimateP | iMHEA_Aggregation, iMHEA_IDC, iMHEA_MonthlyRain |
| iMHEA_ClimateTotal | iMHEA_ClimateP, iMHEA_ProcessP |
| iMHEA_Depure | — (comment mentions non-existent `iMHEA_AggregationDepure`) |
| iMHEA_FDC | — |
| iMHEA_FillGaps | iMHEA_Aggregation (lines 36–42, resamples both inputs to a common scale), iMHEA_Voids, iMHEA_Plot3 |
| iMHEA_IDC | iMHEA_Aggregation |
| iMHEA_Indices | iMHEA_ProcessP, iMHEA_ProcessQ |
| iMHEA_IndicesPlus | iMHEA_Average, iMHEA_FDC, iMHEA_MonthlyFlow, iMHEA_Pulse |
| iMHEA_IndicesTotal | iMHEA_ClimateP, iMHEA_Indices, iMHEA_IndicesPlus |
| iMHEA_Level2Flow | — |
| iMHEA_MonitoringGaps | iMHEA_Voids |
| iMHEA_MonthlyFlow | — (MonthlyRain mention comment-only) |
| iMHEA_MonthlyRain | — |
| iMHEA_Pair | iMHEA_IndicesTotal, iMHEA_Indices |
| iMHEA_Plot2 | — |
| iMHEA_Plot3 | — |
| iMHEA_Plot4 (script) | iMHEA_ProcessP, iMHEA_ProcessQ (site-variable prefixes excluded) |
| iMHEA_PlotPair | — (`iMHEA_DataPair` is the argument name; Plot2 mention comment-only) |
| iMHEA_ProcessP | iMHEA_Aggregation, iMHEA_IDC, iMHEA_MonthlyRain |
| iMHEA_ProcessQ | iMHEA_Average, iMHEA_BaseFlow, iMHEA_BaseFlowUK, iMHEA_FDC, iMHEA_MonthlyFlow |
| iMHEA_Pulse | — |
| iMHEA_Raw2Processed (driver script) | iMHEA_Workflow, iMHEA_WorkflowPair, iMHEA_WorkflowRain, iMHEA_FillGaps, iMHEA_SaveSingleCSV, iMHEA_SaveDoubleCSV, iMHEA_SaveDailyCSV (Level2Flow/Average mentions comment-only; iMHEA_CHA/… are variable prefixes) |
| iMHEA_SaveDailyCSV | — (`iMHEA_` appears in output filename strings; SaveDoubleCSV mention comment-only) |
| iMHEA_SaveDoubleCSV | — |
| iMHEA_SaveSingleCSV | — |
| iMHEA_Voids | — |
| **iMHEA_Workflow** | iMHEA_Depure, iMHEA_AggregationCS, iMHEA_FillGaps, iMHEA_Average, iMHEA_Aggregation, iMHEA_BaseFlowUK, iMHEA_Plot3, iMHEA_IndicesTotal |
| **iMHEA_WorkflowPair** | iMHEA_Aggregation, iMHEA_Average, iMHEA_FillGaps, iMHEA_BaseFlowUK, iMHEA_Pair |
| **iMHEA_WorkflowRain** | iMHEA_Depure, iMHEA_AggregationCS, iMHEA_FillGaps, iMHEA_Aggregation, iMHEA_Plot3, iMHEA_ClimateTotal (Workflow mention comment-only) |

Roots: `iMHEA_Raw2Processed` (batch driver) → Workflow / WorkflowRain / WorkflowPair → everything else. Leaves: Voids, FDC, Pulse, MonthlyRain, BaseFlow, Level2Flow, Plot2/3, Save*CSV.

Note on `iMHEA_FillGaps`: verified real calls — `iMHEA_Aggregation` (lines 36–37 and 41–42: both input series are resampled to a common `scale` before gap-filling), `iMHEA_Voids` (lines 50, 52), `iMHEA_Plot3` (line 107). So the gauge data entering Workflow's pairwise fill are re-aggregated once more inside FillGaps.

---

## 6. Translation-critical summary

1. **Pipeline resolution logic**: Workflow's grid = rounded *median* discharge interval; WorkflowRain's grid = fixed 5 min; WorkflowPair's grid = *max* of the two catchments' median intervals (coarser wins), with the finer catchment resampled.
2. **Averaging across rain gauges** = `nanmean` over all pairwise gap-filled series (2·C(n,2) columns), not over raw gauges.
3. **Area normalisation timing** differs by product: daily/hourly Q normalised at aggregation time; HRes Q normalised on the very last line, *after* Plot3 and IndicesTotal (which receive l/s + AREA).
4. **Column orders** (must be preserved): Workflow `Data1day = [Date,P,Q,BQ]`; WorkflowPair `DataHRes = [Date,P1,Q1,P2,Q2]`, `Data1day = [Date,P1,Q1,BQ1,P2,Q2,BQ2]`, `Data1hr = [Date,P1,Q1,P2,Q2]`.
5. **Bugs to fix, not clone**: scrambled FDC/IDC outputs in WorkflowPair line 104; whole-matrix `ismember` alignment (Workflow 115–116, WorkflowPair 78–79); no-op varargin validation (`rem(floor(x),1)==0`); Plot4's overridden YLim and fixed 28-day February; `inputname`-based labels everywhere.
