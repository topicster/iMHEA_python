# Group B Specification: Processing pipeline & CSV output functions

Source directory: `/Users/boris/Library/CloudStorage/OneDrive-FundaciónBINARA/Projects/iMHEA/Protocolos/Scripts/iMHEA_scripts/`

Files covered (read in full):

| File | Lines | Type |
|---|---|---|
| `iMHEA_ProcessP.m` | 78 | function |
| `iMHEA_ProcessQ.m` | 149 | function |
| `iMHEA_Level2Flow.m` | 87 | function |
| `iMHEA_Raw2Processed.m` | 317 | **script** (not a function) |
| `iMHEA_SaveDailyCSV.m` | 41 | function (no outputs) |
| `iMHEA_SaveDoubleCSV.m` | 40 | function (no outputs) |
| `iMHEA_SaveSingleCSV.m` | 29 | function (no outputs) |

General conventions used throughout:
- Dates are MATLAB **datenum** values (fractional days since 0000-01-00; 1 unit = 1 day, 1/1440 = 1 minute).
- `Date` inputs to Process* are datetime/date-format vectors; they are converted to datenum with `datenum()` only when packed into output matrices.
- Precipitation `P` is in **mm per interval** (tipping-bucket increments); discharge `Q` is in **l/s**, normalized to **l/s/km2** when catchment area is given.
- Missing data is represented by **NaN** (no sentinel values, no explicit flag columns in these 7 files).

---

## 1. `iMHEA_ProcessP.m`

### 1.1 Signature

```matlab
function [IndicesP,PM,IDC,CumP,DP] = iMHEA_ProcessP(Date,P,varargin)
```

Inputs:
- `Date` — timestamps `dd/mm/yyyy hh:mm:ss` [date format] (event or interval times of precipitation records).
- `P` — precipitation depth [mm] per record.
- `varargin` (the doc calls it `flag`) — **presence-only flag**: if a 3rd argument is passed (any value), plotting is enabled in the downstream calls. Tested purely via `nargin >= 3`; the value itself is never read.

Outputs:
- `IndicesP` — 7x1 column vector `[PYear; DayP0; PP0; PMDry; SINDX; iM15m; iM1hr]`:
  - `PYear` = annual precipitation [mm]
  - `DayP0` = number of days with zero precipitation per year [day]
  - `PP0` = proportion of days with zero precipitation per year [-]
  - `PMDry` = precipitation of driest month [mm]
  - `SINDX` = Seasonality Index [-] (named `Sindx` in header comment)
  - `iM15m` = max precipitation intensity at 15-min scale [mm/h]
  - `iM1hr` = max precipitation intensity at 1-hour scale [mm/h]
- `PM` — monthly precipitation [mm] per month number (Jan=1 … Dec=12), 12-element vector (long-term monthly climatology from `iMHEA_MonthlyRain`).
- `IDC` — Maximum Intensity–Duration Curve [mm/h vs duration].
- `CumP` — `[datenum(DDate), DCumP]` two-column matrix: daily date vs cumulative precipitation [mm].
- `DP` — daily precipitation **only for days where data exist**: `[datenum(NewDate), NewP]` (NaN days removed).

### 1.2 Algorithm

1. **Daily aggregation** (line 32): `[DDate,DP,DCumP] = iMHEA_Aggregation(Date,P,1440);` — aggregates the (possibly event-based) rainfall series to a regular 1440-minute (daily) grid, returning daily dates `DDate`, daily totals `DP` (NaN where no data), and cumulative rainfall `DCumP`. **Note: the event-to-continuous conversion itself lives inside `iMHEA_Aggregation`, not in this file** — ProcessP only passes the interval `1440` minutes.
2. **Cumulative output** (line 33): `CumP = [datenum(DDate),DCumP];`
3. **Restrict to days with data** (lines 36–39):
   ```matlab
   NewDate = DDate(~isnan(DP));
   NewP = DP(~isnan(DP));
   k = length(NewP);
   DP = [datenum(NewDate),NewP];
   ```
   (`DP` the output variable is *re-used*: first as the daily vector, then overwritten with the 2-column matrix.)
4. **Zero-precipitation days** (lines 42–44):
   ```matlab
   ZeroP = NewP(NewP==0);
   DayP0 = floor(365*length(ZeroP)/k);
   PP0 = DayP0/365;
   ```
   Zero-days count is scaled to a 365-day year and floored to an integer; `PP0` is that integer divided by 365 (so `PP0` inherits the flooring granularity, resolution 1/365).
5. **Monthly climatology** (lines 47–51): calls `iMHEA_MonthlyRain(Date(~isnan(P)), P(~isnan(P)) [,1])` on the **raw** (not daily) series with NaNs stripped; third output is `PM`. The literal `1` is passed only when `nargin >= 3` (plot flag).
6. **Driest month & annual total** (lines 53–58):
   ```matlab
   PMDry = nanmin(PM);
   PYear = sum(PM);
   if isnan(PYear)
       PYear = 365*mean(NewP); % Equivalent to sum(newP)*365/Days
   end
   ```
   `sum(PM)` is NaN if *any* month of the 12 has NaN (uses plain `sum`, not `nansum`); fallback annualizes the mean daily rainfall over data-days.
7. **Seasonality Index** (line 61) — Walsh & Lawler formulation:
   ```matlab
   SINDX = (1/PYear)*(sum(abs(PM-PYear/12)))*6/11;
   ```
   i.e. `SI = (6/11) * Σ_m |PM_m − PYear/12| / PYear`.
8. **Intensity–Duration Curve** (lines 64–69): `[IDC,iM15m,iM1hr] = iMHEA_IDC(Date,P [,1]);` on the raw series (NaNs *not* stripped here); flag `1` passed when `nargin >= 3`.
9. **Assemble** `IndicesP` in the fixed order listed above (lines 72–78).

### 1.3 NaN / gap handling
- Daily values are NaN wherever `iMHEA_Aggregation` finds no data; those days are excluded from `NewP`/`DP` and from all statistics.
- Raw NaNs are stripped before `iMHEA_MonthlyRain` but **not** before `iMHEA_IDC` (line 66/68 receives full `Date,P` including NaNs — SUSPECTED inconsistency; `iMHEA_IDC` must handle NaN internally).
- `PMDry` uses `nanmin`; `PYear` uses plain `sum` with an explicit NaN fallback.
- No quality flags are read in this file.

### 1.4 Dependencies
- iMHEA: `iMHEA_Aggregation`, `iMHEA_MonthlyRain`, `iMHEA_IDC`.
- MATLAB built-ins: `datenum`, `isnan`, `length`, `floor`, `nanmin` (Statistics Toolbox / legacy), `sum`, `mean`, `nargin`, `abs`.

### 1.5 Edge cases, quirks, suspected bugs
- Flag semantics: any third argument (even `0` or `false`) enables plotting because only `nargin` is tested. Docstring "leave empty NOT to graph" is literal — you must omit the argument.
- `DayP0 = floor(365*ZeroCount/k)` biases downward by up to 1 day; `PP0` is quantized to multiples of 1/365. (SUSPECTED minor inefficiency, intentional design unclear.)
- If the record is empty, `k=0` gives division by zero → NaN/Inf propagation; no guard.
- `SINDX` divides by `PYear`; if `PYear = 0` (all-dry record) → Inf/NaN.
- The fallback comment `% Equivalent to sum(newP)*365/Days` case-mismatches variable `NewP` (comment only).
- `PM` from `iMHEA_MonthlyRain` is a long-term average per calendar month; exact NaN behaviour is defined there, not here.

### 1.6 Python notes
Implement as a function returning a dataclass/dict plus pandas Series. Use `np.nansum`? No — replicate `sum` semantics exactly (NaN-propagating) with `np.sum`, then apply the fallback. `nanmin` → `np.nanmin`. Keep dates as `datetime64` but preserve the datenum columns if binary output parity is needed (`datenum = unix_days + 719529` at day resolution).

---

## 2. `iMHEA_ProcessQ.m`

### 2.1 Signature

```matlab
function [IndicesQ,QM,FDC,CumQ,DQ] = iMHEA_ProcessQ(Date,Q,A,varargin)
```

Inputs:
- `Date` — timestamps `dd/mm/yyyy hh:mm:ss` [date format].
- `Q` — discharge [l/s].
- `A` — catchment area [km2], **optional** (docstring). If given (`nargin >= 3`), `Q` is divided by `A` (line 56) so all results are in l/s/km2; otherwise l/s.
- `varargin`: two presence-only plot flags. `flag1` (4th arg, `nargin >= 4`) enables plots in `iMHEA_MonthlyFlow` and `iMHEA_FDC`; `flag2` (5th arg, `nargin >= 5`) enables plots in the two baseflow routines. Values never read.

Outputs:
- `IndicesQ` — 22x1 column vector, exact order (lines 128–149):
  `[QDMin; Q95; DayQ0; PQ0; QMDry; QDMax; Q10; QDMY; QDML; Q50; BFI1; k1; BFI2; k2; RANGE; R2FDC; IRH; RBI1; RBI2; DRYQMEAN; DRYQWET; SINDQ]`
  - Low flows: `QDMin` min daily flow; `Q95` = 5th percentile; `DayQ0` days of zero flow per year; `PQ0` proportion of zero-flow days; `QMDry` mean daily flow of driest month.
  - High flows: `QDMax` max daily flow; `Q10` = 90th percentile.
  - Mean flows: `QDMY` annual mean daily flow; `QDML` long-term mean daily flow; `Q50` median.
  - Regulation: `BFI1`,`k1` (Gustard et al. 1992 UK handbook); `BFI2`,`k2` (Chapman 1999, 2-parameter); `RANGE` = QDMax/QDMin; `R2FDC` = FDC slope 33–66% / mean flow; `IRH` Hydrological Regulation Index; `RBI1` annual and `RBI2` seasonal Richards–Baker flashiness; `DRYQMEAN` = min monthly / mean monthly; `DRYQWET` = min monthly / max monthly; `SINDQ` seasonality index of flows.
- `QM` — monthly mean daily flow per calendar month (12 values), [l/s or l/s/km2].
- `FDC` — flow duration curve [flow vs exceedance %].
- `CumQ` — `[datenum(DDate), DCumQ]` daily date vs cumulative discharge.
- `DQ` — `[datenum(DDate), DQ, BQ1, SQ1]` 4-column matrix: daily date, daily mean flow, baseflow (UK method), stormflow. **Contrary to ProcessP, NaN days are NOT removed from DQ** (built from full `DDate`, line 119).

### 2.2 Algorithm

1. **Normalize by area** (lines 55–57): `if nargin >= 3, Q = Q/A; end`.
2. **Daily averaging** (line 60): `[DDate,DQ,DCumQ,~,QDML,QDMax,QDMin] = iMHEA_Average(Date,Q,1440);` — averages the irregular series onto a 1440-min (daily) grid; `iMHEA_Average` also returns long-term mean (`QDML`), max (`QDMax`), min (`QDMin`) daily flows (4th output ignored).
3. `RANGE = QDMax/QDMin;` (line 61). `CumQ = [datenum(DDate),DCumQ];` (line 62).
4. **Restrict to data days** (lines 65–67): `NewDate/NewQ` = non-NaN daily values, `l = length(NewQ)`.
5. **Zero-flow days** (lines 70–72):
   ```matlab
   ZeroQ = NewQ(NewQ==0);
   DayQ0 = floor(365*length(ZeroQ)/l);
   PQ0 = DayQ0/365;
   ```
6. **Monthly flows** (lines 75–79): `[~,~,QM,QDMY] = iMHEA_MonthlyFlow(Date(~isnan(Q)),Q(~isnan(Q)) [,1]);` on raw series with NaNs stripped; flag when `nargin >= 4`.
7. **Driest month & annual mean fallbacks** (lines 81–89):
   ```matlab
   QMDry = nanmin(QM);
   if isnan(QDMY), QDMY = mean(QM); end
   if isnan(QDMY), QDMY = mean(NewQ); end
   ```
   Two-stage fallback: monthly means first, then daily means. (Comment on line 80 says "Precipitation in the driest month" — copy-paste from ProcessP; it is discharge.)
8. **Monthly ratios** (lines 92–93): `DRYQMEAN = QMDry/nanmean(QM); DRYQWET = QMDry/nanmax(QM);`
9. **Seasonality Index for flows** (line 96):
   ```matlab
   SINDQ = (1/(12*QDMY))*(sum(abs(QM-QDMY)))*6/11;
   ```
   Note the difference vs. ProcessP: divisor is `12*QDMY` (annual mean daily flow appears both as reference level and in the normalizer) and deviations are taken from `QDMY` itself, not from an annual-total/12.
10. **FDC and percentiles** (lines 99–107): `[FDC,R2FDC,IRH,Ptile] = iMHEA_FDC(NewQ [,1]);` then `Q95 = Ptile(1); Q50 = Ptile(4); Q10 = Ptile(7);` — `Ptile` is a percentile vector of which elements 1, 4, 7 are the 5th, 50th, 90th percentile flows (exceedance naming: Q95/Q50/Q10).
11. **Baseflow separation** (lines 110–116):
    ```matlab
    [~,BQ1,SQ1,BFI1,k1] = iMHEA_BaseFlowUK(Date,Q,1[,1]); % Gustard et al., 1992
    [~,~,BFI2,k2] = iMHEA_BaseFlow(NewDate,NewQ[,1]);     % Chapman, 1999
    ```
    UK method gets the **raw** `Date,Q` (with NaNs, plus a literal `1` third argument — aggregation interval of 1 day) and returns daily baseflow `BQ1` and stormflow `SQ1` aligned to `DDate`; Chapman method gets the NaN-free daily series.
12. **Compile daily matrix** (line 119): `DQ = [datenum(DDate),DQ,BQ1,SQ1];`
13. **Richards–Baker flashiness** (lines 122–125), computed on consecutive non-NaN daily values (gaps were removed, so `diff` can straddle real gaps):
    ```matlab
    Qi_1 = abs(diff(NewQ));
    RBI1 = sum(Qi_1)/sum(NewQ(2:end));
    Qi_2 = 0.5*(Qi_1(1:end-1)+Qi_1(2:end));
    RBI2 = sum(Qi_2)/sum(NewQ(2:end-1));
    ```
    RBI1 = Σ|ΔQ| / ΣQ(2:end) (denominator omits the first day — the classic index uses ΣQ over all days; SUSPECTED deliberate variant). RBI2 uses centered two-step averaging of |ΔQ|.
14. **Assemble** `IndicesQ` (22 rows, order above).

### 2.3 NaN / gap handling
- `iMHEA_Average` yields NaN daily means where no data; those days excluded from `NewQ` for FDC, RBI, zero-day counts, Chapman baseflow — but retained (as NaN rows) in output `DQ` and in `CumQ`.
- Raw NaNs stripped before `iMHEA_MonthlyFlow`, **not** before `iMHEA_BaseFlowUK` (receives raw `Date,Q`).
- `nanmin/nanmean/nanmax` used on `QM`; plain `mean` in fallbacks (line 84 `mean(QM)` is still NaN if any month is NaN — hence the second fallback at line 87).
- `diff(NewQ)` across removed gaps treats non-adjacent days as adjacent → RBI inflated/deflated across gaps (SUSPECTED bug, or accepted approximation).
- No quality flags read.

### 2.4 Dependencies
- iMHEA: `iMHEA_Average`, `iMHEA_MonthlyFlow`, `iMHEA_FDC`, `iMHEA_BaseFlowUK`, `iMHEA_BaseFlow`.
- MATLAB built-ins: `datenum`, `isnan`, `floor`, `nanmin`, `nanmean`, `nanmax`, `mean`, `sum`, `abs`, `diff`, `nargin`.

### 2.5 Edge cases, quirks, suspected bugs
- `A` "optional" but positional: you cannot pass plot flags without passing `A`. If `A` omitted, results stay in l/s.
- `RANGE = QDMax/QDMin` → Inf when the record contains a zero-flow day (`QDMin = 0`). No guard.
- Docstring line 32 says `Range = Qmax/Qmin` "[-]"; it is dimensionless only as a ratio.
- Zero-day flooring quantization identical to ProcessP.
- Output `DQ` keeps NaN rows (asymmetry with ProcessP's `DP`, whose docstring claim "only when data exist" is true; ProcessQ's identical claim at line 43 is **false** — SUSPECTED doc bug).
- RBI denominators `sum(NewQ(2:end))` / `sum(NewQ(2:end-1))` (see above).
- `Ptile` index mapping (1→Q95, 4→Q50, 7→Q10) implies `iMHEA_FDC` returns at least 7 percentiles, presumably [5 10 25 50 75 90 95]-style ordering by flow percentile; confirm in `iMHEA_FDC` spec.

### 2.6 Python notes
Return an ordered dict for the 22 indices (order is load-bearing: columns of `iMHEA_Catchment_Indices_Hydro` depend on it via `iMHEA_Workflow`). Reproduce NaN-propagating `sum`/`mean` vs `nan*` variants exactly. Keep the l/s vs l/s/km2 switch as an optional `area` parameter defaulting to `None`.

---

## 3. `iMHEA_Level2Flow.m`

### 3.1 Signature

```matlab
function [HQ] = iMHEA_Level2Flow(WL,WEIR,COEFF,varargin)
```

Inputs:
- `WL` — stage / water level [cm].
- `WEIR` — weir dimensions vector `(a, b, c, d)` [m] (only `a`,`b` used):
  - `a` = V-notch section height, default **0.30 m** (iMHEA standard).
  - `b` = rectangular section width (total width minus V-notch width), default **1.00 m** ("This is variable, no standard" — a warning is printed asking the user to check).
- `COEFF` — rating-curve coefficients `(C1, e1, C2, e2)` [-]; defaults (90-degree V-notch): **C1 = 1.37, e1 = 2.5, C2 = 1.77, e2 = 1.5**.
- `varargin` (`flag`) — presence-only (`nargin > 3`): plot WL and HQ (docstring also mentions "data voids assessment" but the code only plots).

Output:
- `HQ` — discharge [l/s], same length as `WL`. **Note docstring bug: header line 3 shows a `Date` first argument (`iMHEA_Level2Flow(Date,WL,WEIR,CURVE)`) that does not exist in the actual signature.**

Defaults logic (lines 36–61):
- `if nargin < 3 || isempty(COEFF)` → default coefficients; else unpack `COEFF(1..4)`.
- `if nargin < 2 || isempty(WEIR)` → default `a=0.30, b=1.00`; else `a = WEIR(1); b = WEIR(2);` (`c`,`d` never read). **Note: `nargin < 2` can never be true if COEFF was checked with `nargin < 3` and WL is required; the `isempty(WEIR)` branch is the operative one** (in `Raw2Processed` line 24 it's called as `iMHEA_Level2Flow(WL, WEIR{...}, [], 1)`).

### 3.2 Algorithm (rating curve)

1. Print banner and the coefficients/equations via `fprintf` (`%8.4f` formats, lines 33–63). These console prints are part of observable behaviour.
2. **Unit conversion in** (line 69): `WL = WL/100;` — cm → m.
3. **Compound sharp-crested weir rating** (lines 70–71), applied element-wise by logical masking on the V-notch height `a`:
   ```matlab
   HQ(WL<=a) = C1*WL(WL<=a).^e1;
   HQ(WL>a) = C1*(WL(WL>a).^e1-(WL(WL>a)-a).^e1) + C2*b*(WL(WL>a)-a).^e2;
   ```
   - Within the V-notch (`WL <= a`): `Q = C1 * WL^e1` [m3/s] (Kindsvater–Shen-type, C1=1.37 for 90° notch).
   - Above the notch (`WL > a`): V-notch part saturates as `C1*(WL^e1 − (WL−a)^e1)` plus rectangular-section (Kindsvater–Carter-type) `C2*b*(WL−a)^e2`.
4. **Unit conversion out** (line 72): `HQ = 1000*HQ;` — m3/s → l/s.
5. Line 73: `WL = WL*100;` restores cm for plotting only (no effect on output).
6. Optional plot (lines 76–87): figure with 2 subplots, `plot(WL)` and `plot(HQ)` against sample index (not time).

### 3.3 NaN / gap handling
- NaN water levels: `NaN <= a` and `NaN > a` are both false, so **NaN samples are assigned by neither mask**. Because `HQ` is grown by masked assignment starting from a nonexistent variable, unassigned positions become **0, not NaN** (numeric arrays auto-fill with zeros). SUSPECTED BUG: NaN levels silently become `HQ = 0` — unless a NaN occupies the trailing positions and no later index is assigned (then `HQ` is shorter than `WL`).
- Negative WL: falls in the `WL<=a` branch; non-integer exponent 2.5 of a negative number → **complex** result in MATLAB. SUSPECTED BUG (no clamp to zero).

### 3.4 Output orientation quirk
`HQ` is created by linear-indexed assignment, so if `WL` is a column vector, `HQ(mask)=...` on a fresh variable produces a **row** vector (1xN). Callers assigning into table columns (Raw2Processed line 24: `[iMHEA_LLO_01_HI_01_raw{:,3}] = iMHEA_Level2Flow(...)`) rely on MATLAB's tolerance. In Python, return an array shaped like the input.

### 3.5 Dependencies
- iMHEA: none.
- MATLAB built-ins: `fprintf`, `isempty`, logical indexing, `.^`, `figure/subplot/plot/ylabel/hold` (plot branch only).

### 3.6 Edge cases, quirks, suspected bugs (summary)
- Docstring signature includes phantom `Date` argument (line 3).
- `WEIR` elements `c`,`d` documented but unused.
- NaN → 0 discharge (SUSPECTED bug, see 3.3).
- Negative stage → complex numbers (SUSPECTED bug).
- Output row/column orientation may differ from input.
- Docstring promises "data voids assessment" that is not implemented.

### 3.7 Python notes
```python
def level2flow(wl_cm, weir=(0.30, 1.00), coeff=(1.37, 2.5, 1.77, 1.5)) -> np.ndarray  # l/s
```
Use `np.where` on `wl_m <= a`; explicitly propagate NaN (deviating from the MATLAB zero-fill bug — document the deviation) and clip negative stages to 0.

---

## 4. `iMHEA_Raw2Processed.m`

### 4.1 Nature and signature
This is a **top-level script**, not a function — no signature. It expects the workspace to already contain, for every station, raw tables named `iMHEA_<SITE>_<NN>_<SENSOR>_<MM>_raw` (MATLAB `table` objects accessed with `{:,col}` brace indexing) plus cell arrays `iMHEA_Catchment_AREA` (rows: catchment, col 2 = area km2) and `iMHEA_Catchment_WEIR` (weir dims). Raw table column conventions inferred from usage:
- column 1 = Date;
- for rain gauges (`PO/PT/PD` codes) column 2 = precipitation [mm];
- for level/flow stations (`HI/HW/HS/HD/HO` codes) column 2 = level, column 3 = discharge [l/s] (`HW` stations use column 2 directly as flow input).

It produces, for each catchment: `*_DataHRes`, `*_Data1day`, `*_Data1hr` matrices; fills the index matrices; and writes CSVs.

### 4.2 Algorithm (structure)

1. **Initialise index matrices** (lines 10–14):
   ```matlab
   iMHEA_Catchment_Indices_Hydro = nan(59,25);
   iMHEA_Catchment_Indices_Climate = nan(13,28);
   iMHEA_Catchment_Indices_Hydro_Pair = nan(59,25);
   iMHEA_Catchment_Indices_Climate_Pair = nan(13,28);
   ```
   59 hydro-index rows x 25 flow catchments; 13 climate-index rows x 28 rain sites. (59 and 13 are the sizes returned by `iMHEA_Workflow`, not by ProcessP/ProcessQ alone.)
2. **Per-site blocks** (LLO, JTU, PAU, PIU, CHA, HUA, HMT, TAM, TIQ), each with `close all; clc` then:
   a. *Independent catchments*: `iMHEA_Workflow(Area, DateQ, Q, Vmin, DateP1, P1 [,DateP2,P2,...])` where the 4th positional argument is the **rain-gauge tipping-bucket resolution / minimum-event depth** in mm — values used: **0.2** (most sites), **0.1** (JTU, CHA), **0.254** (PAU_02, PAU_03 — 0.01-inch buckets). Returns `[DataHRes, Data1day, Data1hr, HydroIndices(:,col), ClimateIndices(:,col)]`.
   b. *Rain-only sites* use `iMHEA_WorkflowRain(Vmin, DateP1, P1, ...)` (PAU_05, PIU_05, PIU_06) returning `[DataHRes, Data1day, Data1hr, ClimateIndices(:,col)]`.
   c. *Paired catchments*: `iMHEA_WorkflowPair(DataHRes_1, DataHRes_2)` → `[Pair_DataHRes, Pair_Data1day, Pair_Data1hr, HydroPair(:,[c1,c2]), ClimatePair(:,[c1,c2])]`. Pair DataHRes columns: `[Date, P1, Q1, P2, Q2]` — evidenced by sub-selections like line 62 `iMHEA_JTU_Pair1_DataHRes(:,[1,4,5])` (catchment 2 of the pair) and line 64 `(:,[1,2,3])` (catchment 1).
   d. `drawnow` after pairing; then CSV export:
      - HRes: `iMHEA_SaveDoubleCSV(Pair_DataHRes,'<SITE>_HRes')`
      - Daily: `iMHEA_SaveDailyCSV(Pair_Data1day,'<SITE>_1day')` (daily pair data has 7 columns incl. baseflows)
      - Hourly: `iMHEA_SaveDoubleCSV(Pair_Data1hr,'<SITE>_1hr')`
      - Rain-only sites: `iMHEA_SaveSingleCSV` with full prefix e.g. `'PAU_05_HRes'`.
3. **Special cases worth reproducing exactly:**
   - Line 24 (commented out) shows Level2Flow usage: `[iMHEA_LLO_01_HI_01_raw{:,3}] = iMHEA_Level2Flow(iMHEA_LLO_01_HI_01_raw{:,2},iMHEA_Catchment_WEIR{1,[2,5]},[],1);` — weir dims taken from columns 2 and 5 of the WEIR cell array.
   - JTU_04 (line 55): fed rainfall from **all four** JTU catchments' gauges (8 gauges total).
   - JTU pairing (lines 57–68): iterative cross-filling — Pair1(01,02), Pair2(03,04), Pair3 = Pair(Pair1 cols[1,4,5], Pair2 cols[1,2,3]) i.e. (02,03), Pair4 = Pair(Pair1 cols[1,2,3], Pair3 cols[1,4,5]) i.e. (01,03-filled); then Pair1 and Pair2 are **recomputed** from the filled series and Pair3/Pair4 are cleared (line 69).
   - PAU_05 (line 101) is climate-only → its climate indices copied to the Pair matrix at line 108.
   - PIU 05/06 (lines 163–168): gap-filled against each other via `iMHEA_FillGaps(D5,P5,D6,P6,0,1)` then re-run through `iMHEA_WorkflowRain`; Pair4 DataHRes columns are `[Date, P5, P6]`.
   - PIU 0407 (lines 158–162): pairs Pair2's catchment-2 series with PIU_07; auxiliary index outputs are copied element-wise: `iMHEA_Catchment_Indices_Hydro_Pair(:,15) = iMHEA_Catchment_Indices_PairAux(:,2);` etc.
   - HUA_01 (line 238): concatenates two logger files vertically `[...HD_01_raw{:,1};...HD_02_raw{:,1}]`.
   - HUA_02 (line 240): rescales the first logger's discharge by `*iMHEA_Catchment_AREA{19,2}/2.71` — i.e., logger HD_01 stored specific discharge (l/s/km2) computed with an old area 2.71 km2, converted back to l/s using the current area. Constant **2.71** is load-bearing.
   - PIU_07 (line 152) uses gauges PO_02 and PO_03 (PO_01 skipped).
   - Index column map — Hydro columns 1–25: LLO01,LLO02,JTU01–04,PAU01–04,PIU01–04,PIU07,CHA01,CHA02,HUA01,HUA02,HMT01,HMT02,TAM01,TAM02,TIQ01,TIQ02. Climate columns 1–28: same order but with PAU_05 (11), PIU_05 (16), PIU_06 (17) inserted.
4. Final cell (line 317) is only the header comment `%% EXPORT HYDROLOGICAL AND CLIMATE INDICES` — **no export code follows** (script ends; SUSPECTED incomplete/exports done manually).

### 4.3 NaN/gap handling
- Only the `nan(...)` pre-allocation; gap logic delegated to `iMHEA_Workflow*`, `iMHEA_FillGaps`.

### 4.4 Dependencies
- iMHEA: `iMHEA_Workflow`, `iMHEA_WorkflowRain`, `iMHEA_WorkflowPair`, `iMHEA_FillGaps`, `iMHEA_SaveDoubleCSV`, `iMHEA_SaveDailyCSV`, `iMHEA_SaveSingleCSV`, (commented: `iMHEA_Average`, `iMHEA_Level2Flow`).
- MATLAB built-ins: `nan`, `disp`, `close all`, `clc`, `drawnow`, table brace-indexing, `clear`.

### 4.5 Edge cases, quirks, suspected bugs
- Hard-coded workspace variable names for every station → in Python this becomes a data-driven config (site table: name, area, bucket size, gauge list, weir).
- Hydro/Climate column indices diverge from PIU onward (Hydro col 11 = PIU_01 but Climate col 12 = PIU_01); easy to get wrong.
- Bucket resolutions per site (0.1 / 0.2 / 0.254 mm) are silent constants inside call lines.
- The `2.71` km2 legacy-area rescale (HUA_02) is undocumented in comments.
- JTU pair recomputation order matters (data filled in cascades); reproduce sequence exactly.
- No index export section despite the final header (SUSPECTED unfinished).

### 4.6 Python notes
Replace with a YAML/JSON site registry + a driver loop; keep an explicit ordered mapping of index-matrix columns to station IDs, and encode the special cases (JTU cascade, HUA merges/rescale, PIU fills) as declarative steps or documented one-off code.

---

## 5. `iMHEA_SaveDailyCSV.m`

### 5.1 Signature
```matlab
function iMHEA_SaveDailyCSV(Data,FilePrefix)
```
- `Data` — matrix `[Date, P1, Q1, BQ1, P2, Q2, BQ2]` (7 columns): datenum date, then rainfall [mm], flow [l/s/km2], baseflow [l/s/km2] for catchments 1 and 2, at daily resolution.
- `FilePrefix` — string `'<site name>_<temporal resolution>'`, e.g. `'LLO_1day'`. **The site code must be exactly 3 characters** (see filename construction).
- No return value; writes two files.

### 5.2 Algorithm
1. Filename 1 (line 19):
   ```matlab
   FileName = fullfile(pwd,['iMHEA_',FilePrefix(1:3),'_01',FilePrefix(4:end),'_processed.csv']);
   ```
   e.g. `LLO_1day` → `<cwd>/iMHEA_LLO_01_1day_processed.csv` (chars 1–3 = site, `_01` inserted, remainder `_1day` appended). Files written to the **current working directory**.
2. `fopen(FileName,'w')`; on failure (`fid == -1`) raise `error('Cannot open file for writing: %s', FileName)`.
3. `n = length(Data(:,1));`
4. Header (line 23): `fprintf(fid,'%s,%s,%s,%s\n','Date','Rainfall mm','Flow l/s/km2','Baseflow l/s/km2');` → literal line `Date,Rainfall mm,Flow l/s/km2,Baseflow l/s/km2`.
5. Row loop (line 26):
   ```matlab
   fprintf(fid,'%s,%8.4f,%8.4f,%8.4f\n',datestr(Data(i,1),'dd/mm/yyyy HH:MM:SS'),Data(i,2:4));
   ```
   Date formatted `dd/mm/yyyy HH:MM:SS`; numbers as `%8.4f` (min width 8 → **space-padded**, 4 decimals; e.g. ` 12.3456`, `  0.0000`; NaN prints as `     NaN`). Line terminator `\n` (LF only).
6. Repeat for catchment 2 (lines 31–41): filename with `_02`, columns `Data(i,5:7)`.

### 5.3 NaN handling
NaN values are written literally by `%8.4f` as `     NaN` (width-8, right-aligned). No filtering of NaN rows.

### 5.4 Dependencies
Built-ins only: `fullfile`, `pwd`, `fopen`, `fprintf`, `datestr`, `fclose`, `error`. (Commented-out `waitbar` UI.)

### 5.5 Edge cases, quirks
- Assumes 3-char site prefix; a 4-char site would split incorrectly.
- Row-by-row fprintf is slow for long series (inefficiency; vectorizable).
- Docstring first line says "iMHEA_SaveDoubleCSV" (copy-paste, line 3).
- Output values are space-padded, so CSV fields contain leading spaces.
- Daily rows carry time `00:00:00` (datenum at midnight).

### 5.6 Python notes
Write with a manual f-string loop or `np.savetxt`-style formatting to preserve `%8.4f` padding and `NaN` literals if byte-identical output is required; otherwise pandas `to_csv` with `float_format='%8.4f'` and `date_format='%d/%m/%Y %H:%M:%S'` (note pandas won't width-pad `nan` the same way — MATLAB emits `     NaN` with capital N).

---

## 6. `iMHEA_SaveDoubleCSV.m`

### 6.1 Signature
```matlab
function iMHEA_SaveDoubleCSV(Data,FilePrefix)
```
- `Data` — `[Date, P1, Q1, P2, Q2]` (5 columns) at any resolution (used for HRes and hourly pair data).
- `FilePrefix` — as in SaveDailyCSV (3-char site + `_<resolution>`).

### 6.2 Algorithm
Identical structure to SaveDailyCSV but 3 data columns per file:
1. File 1 (line 18): `['iMHEA_',FilePrefix(1:3),'_01',FilePrefix(4:end),'_processed.csv']` in `pwd`; error on open failure.
2. Header (line 22): `Date,Rainfall mm,Flow l/s/km2` (`'%s,%s,%s\n'`).
3. Rows (line 25): `fprintf(fid,'%s,%8.4f,%8.4f\n',datestr(Data(i,1),'dd/mm/yyyy HH:MM:SS'),Data(i,2:3));`
4. File 2 (lines 30–40): `_02` filename, columns `Data(i,4:5)`, same header/format.

### 6.3 NaN handling / dependencies / quirks
Same as SaveDailyCSV (NaN printed as text; built-ins only; 3-char prefix assumption; per-row loop; leading-space padding). Header says `Flow l/s/km2` even if data were never area-normalized (SUSPECTED mislabel in the l/s case).

### 6.4 Python notes
Share one implementation with SaveDailyCSV parameterized by column groups and header; only column slices differ ((2:3)/(4:5) vs (2:4)/(5:7)).

---

## 7. `iMHEA_SaveSingleCSV.m`

### 7.1 Signature
```matlab
function iMHEA_SaveSingleCSV(Data,FilePrefix)
```
- `Data` — `[Date, Var]` (2 columns; used for rain-only stations, `Var` = precipitation mm).
- `FilePrefix` — **full** prefix used verbatim, e.g. `'PAU_05_HRes'` (no 3-char splitting).

### 7.2 Algorithm
1. Filename (line 18): `fullfile(pwd,['iMHEA_',FilePrefix,'_processed.csv'])` → e.g. `iMHEA_PAU_05_HRes_processed.csv`; error on open failure.
2. Header (line 22): `Date,Rainfall mm` (`'%s,%s\n'`).
3. Rows (line 25): `fprintf(fid,'%s,%8.4f\n',datestr(Data(i,1),'dd/mm/yyyy HH:MM:SS'),Data(i,2));`
4. Close file. Single file only.

### 7.3 NaN handling / dependencies / quirks
- NaN printed as `     NaN`; built-ins only.
- Header hard-codes `Rainfall mm` even though docstring says generic `Var` (SUSPECTED limitation: unusable as-is for a single flow series without a wrong header).
- Docstring "a csv files" typo; per-row loop inefficiency.

### 7.4 Python notes
One-liner with pandas/`csv`; parameterize the header label instead of hard-coding "Rainfall mm" but default to it for output parity.

---

## Cross-cutting notes for the translation

1. **Datenum arithmetic**: all Save* files call `datestr(datenum_value, 'dd/mm/yyyy HH:MM:SS')`; Process* pack `datenum(Date)` into output matrices. Python equivalent: `matlab_datenum = days_since_epoch + 719529` (+ fractional day for time); beware float round-off at second resolution when converting back.
2. **Presence-only flags**: every optional plotting flag is tested with `nargin` comparisons, never by value. In Python use `plot: bool = False` keywords.
3. **Event-to-continuous conversion** (tipping-bucket events → regular grid) referenced by the task is *not* in these files; it is inside `iMHEA_Aggregation` (rainfall totals) and `iMHEA_Average` (flow means), called from ProcessP/ProcessQ with interval = 1440 minutes. Those functions define the NaN-gap semantics these functions rely on and must be specified separately.
4. **Bucket sizes** (0.1 / 0.2 / 0.254 mm) and the **HUA_02 legacy area 2.71 km2** are the only physical constants in Raw2Processed; the rating-curve constants (1.37, 2.5, 1.77, 1.5; a=0.30 m, b=1.00 m) live in Level2Flow.
5. **Index vector orders** (7 for P, 22 for Q) are positional contracts consumed by `iMHEA_Workflow` and the 59x25 / 13x28 index matrices; freeze them as named tuples/enums in Python.
