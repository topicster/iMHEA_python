# iMHEA Flow Analysis Functions — Translation Specification (Group C)

Source directory: `/Users/boris/Library/CloudStorage/OneDrive-FundaciónBINARA/Projects/iMHEA/Protocolos/Scripts/iMHEA_scripts/`

Files covered: `iMHEA_BaseFlow.m`, `iMHEA_BaseFlowUK.m`, `iMHEA_FDC.m`, `iMHEA_IDC.m`, `iMHEA_Pulse.m`, `iMHEA_MonthlyFlow.m`, `iMHEA_MonthlyRain.m`

All line numbers refer to the original MATLAB files. This document is intended to fully replace the source during translation.

---

## 1. iMHEA_BaseFlow.m — Chapman (1999) digital-filter baseflow separation

### 1.1 Signature

```matlab
function [BQ2,SQ2,BFI2,k] = iMHEA_BaseFlow(Date,Q,varargin)
```

| Arg | Direction | Type / Units | Notes |
|---|---|---|---|
| `Date` | in | datetime vector, dd/mm/yyyy hh:mm:ss | Must be at a **regular interval** (docstring says "Daily Discharge" but any regular step works; the step is inferred from `Date(2)-Date(1)`) |
| `Q` | in | discharge [l/s] | Same length as Date |
| `varargin` (flag) | in, optional | any value | If present (`nargin >= 3`, line 81) produce diagnostic plots. Default: no plots |
| `BQ2` | out | baseflow [l/s] | From the 2-parameter filter (alpha = 0) |
| `SQ2` | out | stormflow [l/s] | `Q - BQ2` element-wise |
| `BFI2` | out | baseflow index [-] | `sum(BQ2)/sum(Q)` |
| `k` | out | recession constant [-] per time step | `max` over behavioural recession fits |

### 1.2 Algorithm

**Step 1 — constants (lines 23–25):**
```matlab
23  n = length(Date);
24  Daycheck = 7; % Continuous days for recessions.
25  lim = 0.8; % Minimum R2 for linear fit.
```

**Step 2 — identify recession segments (lines 30–44).** `LogQ = log(Q)` (natural log). For **every** index `i = 1..n`, take the forward-looking window of all samples with `Date >= Date(i) & Date < Date(i)+7 days` and linearly regress `LogQ` against time-in-days:

```matlab
37  X = datenum(Date(and(Date>=Today,Date<Today+Daycheck)));
38  Y = LogQ(and(Date>=Today,Date<Today+Daycheck));
39  [R(i),M(i)] = regression(X',Y');
```

`regression(t,y)` is the **Deep Learning Toolbox** function: it fits `y = m*t + b` and returns the Pearson correlation coefficient `R` and slope `M` (units: log(l/s) per day since X is datenum days). Then:

```matlab
43  R = R.^2;
44  M = datenum(Date(2)-Date(1))*M;
```

Line 43 converts correlation to R². Line 44 rescales the slope from per-day to **per-time-step** (`datenum(duration)` gives the step length in days).

**Step 3 — recession constant (lines 46–50).** Behavioural windows are those with `R >= 0.8 AND M < 0`. For each, `K = exp(M_step)`; the reported constant is the **maximum** (slowest recession):

```matlab
49  K = exp(MTau);
50  k = max(K);
```

**Step 4 — filter parameters (lines 58–59):**
```matlab
58  C = datenum(Date(2)-Date(1))*.085;   % C = 0.085 * timestep-in-days
59  alpha = -0.1;                        % only used for the plotted 3-par variant
```
Commented notes (lines 54–57) record the intended parameter ranges (`k = 0.949 to 0.993`, `C = 1-k, or 0.018 to 0.085`, `alpha = -0.01 to -0.81`).

**Step 5 — guard (lines 62–67).** If no behavioural recession exists `k` is empty; then `BQ2 = []; SQ2 = []; BFI2 = []`, prints `'These time series do not allow the determination of base flow.'`, and returns (note: `k` is returned as empty `[]`).

**Step 6 — run the filter (lines 69–74).** Three variants of the same recursive filter `par3(Q,k,C,alpha)` are computed:
- `BQ1 = par3(Q,k,1-k,0)` — "linear" / one-parameter variant (plot only)
- `BQ2, SQ2 = par3(Q,k,C,0)` — **the returned 2-parameter result**
- `BQ3 = par3(Q,k,C*2,alpha)` — 3-parameter variant with alpha=-0.1 (plot only)

**Step 7 — the exact filter equation** (subfunction `par3`, lines 133–143). Single **forward** pass, one pass only, initial condition `BQ(1) = Q(1)`:

```matlab
137  BQ(1) = Q(1);
139  for i = 2:length(Q)
140      BQ(i) = min(k/(1+C)*BQ(i-1)+(C)/(1+C)*(Q(i)+alpha*Q(i-1)),Q(i));
141      SQ(i) = Q(i) - BQ(i);
142  end
```

i.e. `BQ_i = min( (k/(1+C))·BQ_{i-1} + (C/(1+C))·(Q_i + α·Q_{i-1}), Q_i )`, with the constraint that baseflow never exceeds total flow. **This is NOT Lyne–Hollick**; it is Chapman's generalised 2/3-parameter algorithm applied directly to baseflow (not to quickflow). `SQ(1)` stays 0 from initialisation.

**Step 8 — BFI (line 78):** `BFI2 = sum(BQ2)/sum(Q);` — plain `sum`, over the whole series.

**Step 9 — plots (lines 81–109)** if flag present: 3 subplots (Q with the three baseflow variants; log-space version; R²/slope diagnostics). Commented-out subfunctions `par1`/`par2` (lines 113–131) document the 1- and 2-parameter forms and are never executed.

### 1.3 NaN/gap handling
**None.** NaNs in `Q` produce NaN in `LogQ`; `regression` on windows containing NaN yields NaN R/M (those windows fail the `R>=lim` test, so they are just not behavioural). NaNs entering `par3` propagate forward **forever** through the recursion (`BQ(i-1)` NaN → all subsequent BQ NaN via `min(NaN,Q)=NaN` — actually `min(NaN,x)` in MATLAB returns `x`, so a single NaN resets `BQ` to `Q(i)` at the next step; but `Q(i)` NaN makes `BQ(i)=NaN` and `SQ(i)=NaN`). `sum` in BFI (line 78) is NOT nansum, so any NaN in Q or BQ2 makes `BFI2 = NaN`. Gaps in `Date` are not detected; the 7-day window simply spans them.

### 1.4 Dependencies
- iMHEA functions: none.
- MATLAB built-ins: `regression` (**Deep Learning Toolbox** — nonstandard!), `datenum`, `log`, `exp`, `max`, `min`, `sum`, `waitbar`, plotting.

### 1.5 Edge cases, quirks, suspected bugs
- **Quirk:** windows near the series end contain fewer points (down to 1 sample; regression of a single point gives NaN/degenerate results).
- **Quirk:** `k = max(K)` picks the *slowest* recession among behavioural windows, not a mean/median.
- **SUSPECTED inefficiency:** the recession loop is O(n²) — full-array logical comparisons for each of `n` iterations, plus a `waitbar` update per iteration. Very slow for 5-min data.
- **SUSPECTED inefficiency/bug:** `BQ1`, `BQ3`, `LogBQ1..3` (lines 69–74) are always computed even when plotting is off; `log(0)` gives `-Inf` silently.
- **Quirk:** `C` is hard-coded to `0.085 × timestep(days)`; for daily data C=0.085, for 5-min data C≈0.000295. `alpha=-0.1` affects only the plotted 3-par curve.
- **Edge:** `Q(1) = NaN` or 0 seeds the filter badly (`BQ(1)=Q(1)`).
- **Edge:** if `Q` contains zeros, `LogQ = -Inf` and regressions in windows touching them return degenerate slopes.

### 1.6 Python notes
Replace `regression` with `scipy.stats.linregress` (returns rvalue and slope directly). Vectorise the recession scan with a rolling regression (or keep the loop with numpy — still fast). The filter recursion is inherently sequential; implement with a simple loop or `numba`. Decide explicit NaN policy (MATLAB `min(NaN,x)` returns `x`; NumPy `min` propagates NaN — behaviour difference matters here).

---

## 2. iMHEA_BaseFlowUK.m — UKIH / Gustard et al. (1992) smoothed-minima baseflow separation

### 2.1 Signature

```matlab
function [DDate,BQ,SQ,BFI,k] = iMHEA_BaseFlowUK(Date,Q,varargin)
```

| Arg | Direction | Type / Units | Notes |
|---|---|---|---|
| `Date` | in | datetime | Any resolution; internally averaged to daily |
| `Q` | in | discharge [l/s] | |
| `varargin{1}` (flag1) | in, optional | any | If present (`nargin>=3`) compute recession constant `k` |
| `varargin{2}` (flag2) | in, optional | any | If present (`nargin>=4`) plot |
| `DDate` | out | datetime, daily | Daily datetimes (converted back from datenum at line 101) |
| `BQ` | out | daily baseflow [l/s] | |
| `SQ` | out | daily stormflow [l/s] | `DQ1 - BQ` |
| `BFI` | out | baseflow index [-] | |
| `k` | out | recession constant [-] OR **block count** (see bug) | |

### 2.2 Algorithm

**Step 1 — daily aggregation (lines 28–32):**
```matlab
28  [DDate,DQ1] = iMHEA_Average(Date,Q,1440);
29  DDate = datenum(DDate);
31  DQ = DQ1;
32  DQ(isnan(DQ1)) = inf;
```
Data are averaged to daily (1440 min) using `iMHEA_Average`. `DQ` is a copy where NaN → `+Inf` so gaps never become block minima.

**Step 2 — non-overlapping blocks (lines 24, 35–46).** Block size `Daycheck = 5` days (line 24). Block edges `nDate = (DI:5:DF)` where DI/DF are first/last daily datenums. For each block, the minimum of `DQ`:
```matlab
42  for i = 2:k
43      nQmin(i) = nanmin(DQ(DDate>=nDate(i-1)&DDate<nDate(i)));
44  end
45  nQmin(1) = [];
46  nDate(1) = [];
```
So block *i* covers `[nDate(i-1), nDate(i))` (5 days, half-open), and each block minimum is **labelled with the END date of the block** (after the shift at lines 45–46). `k = length(nDate)` (line 38) before deletion. Any tail days past the last edge are ignored.

**Step 3 — turning points (lines 49–58).** Start from `nBQ = nQmin` and reject non-turning points:
```matlab
50  for i = 2:(k-2)
51      if or(0.9*nQmin(i)>nQmin(i-1),0.9*nQmin(i)>nQmin(i+1))
52          nBQ(i) = NaN;
53      end
54  end
```
A block minimum is a **turning point iff `0.9·Qmin(i) <= Qmin(i-1)` AND `0.9·Qmin(i) <= Qmin(i+1)`** (standard UKIH condition; note ties pass because rejection uses strict `>`). The first block minimum is never tested (index starts at 2) and — because the array has `k-1` elements after line 45 while the loop stops at `k-2` — the last element is never tested either; both survive as turning points by default. Then NaNs are purged and **the last surviving turning point is deleted** (lines 55–58):
```matlab
55  nDate(isnan(nBQ)) = [];
56  nBQ(isnan(nBQ)) = [];
57  nBQ(end) = [];
58  nDate(end) = [];
```

**Step 4 — baseflow line (lines 61–64).** Linear interpolation between turning points, **with linear extrapolation** beyond them, evaluated at every daily date; then clipped to total flow and blanked on gaps:
```matlab
61  BQ = interp1(nDate,nBQ,DDate,'linear','extrap');
62  BQ(BQ>DQ) = DQ(BQ>DQ);
63  BQ(isnan(DQ1)) = NaN;
64  SQ = DQ1 - BQ;
```

**Step 5 — optional recession constant (lines 67–93, only if `nargin>=3`).** Same machinery as `iMHEA_BaseFlow` but applied to `LogBQ = log(BQ)` with **5-day** windows (`Daycheck=5`), `lim=0.8`, and daily data: sliding forward-window regression, `R=R.^2`, `M` rescaled by the daily step, behavioural set `R>=0.8 & M<0`, `k = max(exp(MTau))` (line 92).

**Step 6 — BFI (lines 96–98).** Restricted to the span between first and last turning point:
```matlab
96  Vb = nansum(BQ(DDate>=nDate(1) & DDate<=nDate(end)));
97  Va = nansum(DQ1(DDate>=nDate(1) & DDate<=nDate(end)));
98  BFI = Vb/Va;
```

**Step 7 —** `Date` and `DDate` converted back to datetime (lines 100–101); plots if `nargin>=4` (lines 104–133; the third subplot references `R`, `M`, `LogBQ`, `DateTau` which only exist if flag1 was also given).

### 2.3 NaN/gap handling
- Gaps become `+Inf` in `DQ` for the minima search (line 32), so all-gap blocks yield `nQmin = Inf` (nanmin over a vector of Inf = Inf), and Inf "minima" can survive as turning points (Inf*0.9 > neighbours rejects it only via the OR test against finite neighbours — an Inf central value IS rejected since `0.9*Inf > finite`; but an Inf at the never-tested first/last position survives).
- Final `BQ` is set NaN wherever the daily flow was NaN (line 63); `SQ` inherits NaN.
- BFI uses `nansum` (lines 96–97) so gaps are simply excluded.
- **Edge (SUSPECTED bug):** if a 5-day block contains no daily samples at all (possible only if `iMHEA_Average` leaves date holes), `nanmin(empty)` returns `[]` and the assignment `nQmin(i) = []` throws *"A null assignment can have only one non-colon index"*.

### 2.4 Dependencies
- iMHEA: `iMHEA_Average(Date,Q,1440)` (daily mean).
- Built-ins: `nanmin`, `nansum` (legacy Statistics Toolbox forms), `interp1`, `datenum`, `datetime`, `regression` (Deep Learning Toolbox, only if flag1), `waitbar`.

### 2.5 Edge cases, quirks, suspected bugs
- **SUSPECTED BUG (output semantics):** `k` is set to `length(nDate)` at line 38 and only overwritten with the recession constant when flag1 is given. Without flag1 the 5th output is the **number of block edges**, not a recession constant.
- **SUSPECTED BUG / quirk:** unconditional deletion of the last turning point (lines 57–58) discards valid information; presumably meant to drop an unreliable end block, but it also shortens the BFI window.
- **Quirk:** turning points are timestamped at block END dates, so the baseflow line is shifted right by up to 5 days relative to implementations that use the date of the actual minimum. Standard UKIH anchors the turning point at the day the minimum occurred; this code does not track that day.
- **Quirk:** the loop bound `k-2` is computed from the pre-deletion length; effectively elements 2..(len-1)-? — the last block minimum is never subjected to the 0.9 test.
- **Quirk:** linear **extrapolation** (line 61) before the first and after the last turning point can go negative; only the `BQ>DQ` clip (line 62) bounds it from above, nothing bounds it below 0.
- **Quirk:** comparison `BQ>DQ` where `DQ` has Inf at gaps is safe (never true), and those positions are NaN-ed at line 63 anyway.

### 2.6 Python notes
Implement with pandas daily resample + `numpy` reshape into 5-day blocks. Use `np.interp` for the baseflow line (it clamps at ends instead of extrapolating — replicate MATLAB `'extrap'` explicitly with `scipy.interpolate.interp1d(..., fill_value='extrapolate')`). Decide whether to fix the `k` output overload or reproduce it faithfully.

---

## 3. iMHEA_FDC.m — Flow Duration Curve

### 3.1 Signature

```matlab
function [FDC,R2FDC,IRH,Ptile] = iMHEA_FDC(Q,varargin)
```

| Arg | Direction | Type / Units | Notes |
|---|---|---|---|
| `Q` | in | discharge, any units (l/s, l/s/km², m³/s, mm…) | No Date needed |
| `varargin` (flag) | in, optional | any | If present (`nargin>=2`) plot |
| `FDC` | out | k×2 matrix `[exceedance% , sorted Q ascending]` | |
| `R2FDC` | out | log-slope of FDC between 33% and 66% exceedance, normalised [-] | |
| `IRH` | out | Hydrological Regulation Index [-] | |
| `Ptile` | out | 1×7 vector: flows at exceedance 95, 75, 66, 50, 33, 25, 10 % (named Q95, Q75, Q66, Q50, Q33, Q25, Q10) | |

### 3.2 Algorithm

**Step 1 — drop NaN (line 27):** `Q = Q(~isnan(Q));`, `k = length(Q)`.

**Step 2 — exceedance probabilities, Gringorten (1963) plotting position (lines 31–32):**
```matlab
31  FDC(:,1) = 100*(1-((1:k)-.44)/(k+.12)); % Gringorten (1963)
32  FDC(:,2) = sort(Q); % Vector of sorted discharge
```
Column 2 is Q sorted **ascending**; row *i* (the i-th smallest flow) gets exceedance `100·(1 − (i−0.44)/(k+0.12))` %. So the smallest flow has the highest exceedance (~100·(1−0.56/(k+0.12))) and the largest flow the lowest (~100·0.44/(k+0.12) if i=k... precisely `100·(1−(k−0.44)/(k+0.12))`).

**Step 3 — percentiles by CUBIC SPLINE interpolation (lines 37–43):**
```matlab
37  Ptile(1) = spline(FDC(:,1),FDC(:,2),95);
...
43  Ptile(7) = spline(FDC(:,1),FDC(:,2),10);
```
`spline` = not-a-knot cubic spline of sorted flow vs exceedance, evaluated at 95, 75, 66, 50, 33, 25, 10 %. NOT linear interpolation — this can overshoot/undershoot (including below zero for low flows).

**Step 4 — FDC slope index (lines 45–48):**
```matlab
45  R2FDC = (log10(Ptile(3)) - log10(Ptile(5)))/(.66-.33);
46  if ~isreal(R2FDC)
47      R2FDC = -inf;
48  end
```
`Ptile(3)` = flow at 66% exceedance (Q66, a low flow), `Ptile(5)` = flow at 33% (Q33, higher). Result is normally **negative**. If either flow is negative (spline undershoot), `log10` is complex and `R2FDC` is forced to `-inf`.

**Step 5 — IRH (lines 50–52):** replace all flows with exceedance < 50% (i.e. the high-flow half) by the median flow `Ptile(4)`, then
```matlab
52  IRH = sum(auxFDC) / sum(FDC(:,2));
```
i.e. area under the FDC capped at Q50, divided by total area.

**Step 6 —** plots if flag (lines 55–75): semilog FDC with the 33–66% chord, and the IRH area plot.

### 3.3 NaN/gap handling
NaNs removed up front (line 27). No time information at all — irregular sampling or gaps bias the curve silently (each retained sample carries equal weight).

### 3.4 Dependencies
- iMHEA: none.
- Built-ins: `sort`, `spline`, `log10`, `isreal`, `sum`, plotting.

### 3.5 Edge cases, quirks, suspected bugs
- **Quirk (SUSPECTED bug):** cubic `spline` for percentile extraction is unusual; with k points it can produce non-monotonic values, negative low-flow percentiles, and values outside the data range. Linear interpolation (`interp1`) is the conventional choice.
- **Edge:** for very small k the requested exceedance (e.g. 95%) can lie **outside** the plotting-position range → spline **extrapolates** (unbounded).
- **Edge:** `k==0` (all NaN) → `FDC` empty, `spline` errors.
- **Edge:** zero flows: `log10(0) = -Inf` is real, so `R2FDC` becomes `±Inf` rather than being caught by the `isreal` check.
- **Quirk:** `Ptile` naming inversion: `Ptile(1)` is documented as "Q95 = 05th Percentile", i.e. exceedance-95% flow = 5th percentile of magnitude. Keep the hydrological naming.
- **Quirk:** `IRH` denominator uses plain `sum` on already NaN-free data — fine.

### 3.6 Python notes
`numpy.sort` + Gringorten formula are trivial; use `scipy.interpolate.CubicSpline` (not-a-knot is its default `bc_type`) to reproduce MATLAB `spline` exactly, including extrapolation. Do not substitute `np.percentile` — results will differ.

---

## 4. iMHEA_IDC.m — Maximum Intensity–Duration Curve (precipitation)

### 4.1 Signature

```matlab
function [IDC,iM15m,iM1hr] = iMHEA_IDC(Date,P,varargin)
```

| Arg | Direction | Type / Units | Notes |
|---|---|---|---|
| `Date` | in | datetime | Ideally 5-min resolution |
| `P` | in | precipitation depth per interval [mm] | |
| `varargin` (flag) | in, optional | any | If present (`nargin>=3`) plot |
| `IDC` | out | 10×4 matrix: `[duration_min, max_intensity, mean_intensity, median_intensity]` all in mm/h | Declared 10×2 (line 44) but columns 3–4 appended at lines 55–56 |
| `iM15m` | out | max 15-min intensity [mm/h] | `IDC(D==3,2)` (line 62) |
| `iM1hr` | out | max 1-hour intensity [mm/h] | `IDC(D==12,2)` (line 63) |

### 4.2 Algorithm

**Step 1 — ensure 5-min basis (lines 25–40):**
```matlab
27  if round(datenum(median(diff(Date))),4) ~= round(5/1440,4)
```
If the median time step is not 5 min (compared after rounding datenum-days to 4 decimals): drop NaN samples, then **drop zero-precipitation samples** (lines 29–32), print a message, and aggregate to 5 min via `[~,VP] = iMHEA_Aggregation(VDate,VP,5);` (line 36). Otherwise (already 5-min): `VP(isnan(VP)) = 0;` (line 39) — gaps become zero rain.

**Step 2 — durations (lines 42–45).** Window lengths in 5-min steps:
```matlab
43  D = [1 2 3 6 12 24 48 144 288 576]; u =zeros(k1,1);
45  IDC(:,1) = D'*5;
```
i.e. durations 5, 10, 15, 30, 60, 120, 240, 720, 1440, 2880 minutes (the header comment says "2, 4, 12, 24 hours; 2 days").

**Step 3 — moving-window sums (lines 47–58).** For each duration `D(i)`, a running sum of `D(i)` consecutive 5-min values, computed by the O(n) recurrence:
```matlab
49  u(1) = sum(VP(1:D(i)));
51  for j = 2:k1-D(i)+1
52      u(j) = u(j-1) + VP(j+D(i)-1)-VP(j-1);
53  end
54  IDC(i,2) = nanmax(u)*12/D(i);
55  IDC(i,3) = nanmean(u(u>1E-12))*12/D(i);
56  IDC(i,4) = median(u(u>1E-12),'omitnan')*12/D(i);
```
Conversion factor `12/D(i)` turns a `D(i)`-step depth sum [mm] into intensity [mm/h] (12 five-min intervals per hour). Column 2 = max over all window positions; columns 3–4 = mean and median over windows with **non-zero** sums (`u > 1e-12`).

**Step 4 —** `iM15m` and `iM1hr` extracted (lines 62–63). Optional semilogx plot (lines 66–73).

### 4.3 NaN/gap handling
- Non-5-min branch: NaNs and zeros removed *before* aggregation (lines 29–32); the behaviour of missing intervals then depends entirely on `iMHEA_Aggregation` (whether it re-inserts a continuous grid with zeros/NaN).
- 5-min branch: NaN → 0 (line 39). Gaps are treated as **dry periods**, which is safe for maxima but depresses means/medians only through zero-window exclusion.
- `nanmax`/`nanmean`/`median(...,'omitnan')` guard residual NaNs.

### 4.4 Dependencies
- iMHEA: `iMHEA_Aggregation(Date,P,5)` (5-min accumulation) — only in the non-5-min branch.
- Built-ins: `median`, `diff`, `datenum`, `nanmax`, `nanmean`, `waitbar`, `semilogx`.

### 4.5 Edge cases, quirks, suspected bugs
- **SUSPECTED BUG (stale buffer):** `u = zeros(k1,1)` is allocated ONCE outside the duration loop (line 43). For each duration only entries `1..k1-D(i)+1` are overwritten, so entries `k1-D(i)+2 .. k1-D(i-1)+1` retain sums from the **previous, shorter duration**. `nanmax(u)` (line 54) is usually unaffected (shorter-window sums ≤ longer-window sums), but the **mean and median in columns 3–4 include stale values** and are contaminated for every duration after the first.
- **Edge:** if `k1 < D(i)` (series shorter than 2 days), `sum(VP(1:D(i)))` at line 49 indexes out of bounds → hard error.
- **Quirk:** removing zero-rain samples before aggregation (lines 31–32) is a performance trick; it changes nothing numerically only if `iMHEA_Aggregation` rebuilds a full time grid.
- **Quirk:** the 5-min check uses the **median** of `diff(Date)`, so a mostly-5-min series with gaps passes as 5-min even though gaps make windows span non-contiguous times (window sums then mix across gaps as if adjacent — acceptable for the NaN→0 branch, since the grid is continuous, but note the assumption).
- **Quirk:** output `IDC` documented as `[mm/h v time]` 2-column but is actually 4-column.

### 4.6 Python notes
Use `np.convolve(VP, np.ones(D), 'valid')` or `pandas.Series.rolling(D).sum()` per duration — this also fixes the stale-buffer bug automatically (decide whether bug-compatibility is required; recommend fixing and documenting). Guard `len(VP) >= max(D)`.

---

## 5. iMHEA_Pulse.m — High/low pulse counting against a threshold

### 5.1 Signature

```matlab
function [MH,VH,FH,DH,TH,ML,VL,FL,DL,TL] = iMHEA_Pulse(Date,Q,Lim,varargin)
```

| Arg | Direction | Type / Units | Notes |
|---|---|---|---|
| `Date` | in | datetime | |
| `Q` | in | discharge [l/s or l/s/km²] | |
| `Lim` | in | threshold, same units as Q | Single scalar; high pulse = `Q >= Lim` |
| `varargin` (flag) | in, optional | any | If present (`nargin>=4`) print a formatted report and plot |
| `MH/ML` | out | 1×5 magnitude stats of high/low pulse **peaks** `[Total Mean Min Max CV]` [l/s] | |
| `VH/VL` | out | 1×5 volume stats `[Total Mean Min Max CV]` (units: **l/s·day** above/below threshold; header says [l]) | VL values are **negative** (deficits) |
| `FH/FL` | out | 1×5 frequency stats per calendar year `[Total Mean Min Max CV]` | |
| `DH/DL` | out | 1×5 duration stats `[Total Mean Min Max CV]` [day] | |
| `TH/TL` | out | scalar "max period with no pulse occurrence" [day] (see bug) | |

### 5.2 Algorithm

**Step 1 — year bookkeeping (lines 31–34):** `Years = year(Date)` on the FULL input; `HFreq`/`LFreq` are `[yearList, 0]` tables covering `min(Years):max(Years)`.

**Step 2 — filter NaN (lines 36–38):**
```matlab
36  Date = datenum(Date(~isnan(Q)));
37  Q = Q(~isnan(Q));
```
(`Years` is NOT refiltered — see bug below.) `k = length(Q)`.

**Step 3 — setup (lines 40–47).** Counters `nH = nL = 1`; dummy first rows: `HPeriod=zeros(1,2)`-ish (grown dynamically), `HPeak=0`, `LPeak=Inf`, volumes 0. Then:
```matlab
45  ModQ = Q - Lim;
46  Date(end+1) = Date (end);
47  ModQ(end+1) = ModQ (end);
```
The last sample is duplicated so index `j+1` is always valid (the final interval has zero width).

**Step 4 — sample-by-sample classification (lines 50–88).** For `j = 1..k`:
- **High pulse sample** if `ModQ(j) >= 0` (threshold itself counts as high). Creates a provisional pulse: increment `nH`, increment that year's counter, record interval `[Date(j), Date(j+1)]`, peak `Q(j)`, and trapezoidal excess volume
```matlab
57  HVol(nH) = (Date(j+1)-Date(j))*(max(ModQ(j+1),0)+max(ModQ(j),0))/2;
```
(datenum days × l/s above threshold). Then **merge with the previous pulse** if contiguous (`HPeriod(nH,1) == HPeriod(nH-1,2)`, line 58): decrement `nH` and the year counter, extend the previous interval's end, keep `max` of peaks, add volumes (lines 58–68).
- **Low pulse sample** otherwise (`ModQ(j) < 0`): symmetric logic (lines 69–87) with `min` for peaks and volume
```matlab
75  LVol(nL) = (Date(j+1)-Date(j))*(min(ModQ(j+1),0)+min(ModQ(j),0))/2;
```
which is ≤ 0 (deficit volume).

**Step 5 — strip dummies (lines 90–91):** delete first rows/elements; `nH`, `nL` become true pulse counts; `HFreq`/`LFreq` reduced to their count columns.

**Step 6 — statistics (lines 94–129).** If no pulses of a class, the four stat vectors are `zeros(1,5)`. Otherwise for each property `x` in {Freq per year, Peak, Vol, Duration = `Period(:,2)-Period(:,1)` in days}:
`[sum(x) mean(x) min(x) max(x) std(x)/mean(x)]`.
Frequency stats are computed over the **year table** (one entry per calendar year in the span, including zero years); the others over pulses.

**Step 7 — no-pulse periods (lines 131–132):**
```matlab
131  TL = DH(3);
132  TH = DL(3);
```
"Max period with no LOW pulse" is taken from HIGH-pulse durations and vice versa — but using index 3 = **minimum** duration (see bug).

**Step 8 —** restore `Date` (lines 134–135); if flag, print the formatted table and plot Q vs threshold (lines 138–170).

### 5.3 NaN/gap handling
NaN samples are removed (lines 36–37) BEFORE the loop, so an interval spanning a removed NaN block is treated as directly contiguous in classification, but the merge test uses dates, so pulses separated by a NaN gap do NOT merge (interval end ≠ next interval start) — the gap silently splits/joins pulses depending on timestamps. Volumes across a gap use the (large) `Date(j+1)-Date(j)` spanning the gap for the last pre-gap sample, **inflating that pulse's volume and duration**.

### 5.4 Dependencies
- iMHEA: none.
- Built-ins: `year`, `datenum`, `datetime`, `max/min/sum/mean/std`, `fprintf`, plotting.

### 5.5 Edge cases, quirks, suspected bugs
- **BUG (indexing misalignment):** `Years` is computed on the full `Date` (line 31) but indexed with `j` that runs over the **NaN-filtered** series (lines 53, 61, 71, 79). With any NaN in `Q`, per-year frequency counts are attributed to wrong years, and `Years(j)` can even index past sensible range logic (no crash since `Years` is longer, but values are wrong).
- **BUG (copy-paste):** line 71 reads `LFreq(LFreq(:,1)==Years(j),2) = LFreq(HFreq(:,1)==Years(j),2) + 1;` and line 79 similarly — the read-side mask uses `HFreq(:,1)` instead of `LFreq(:,1)`. Harmless in practice only because both year columns are identical, but must not be replicated blindly.
- **SUSPECTED BUG:** `TL = DH(3)` / `TH = DL(3)` use element 3 = **min** duration; "max period with no low pulse occurrence" should logically be the **max** high-pulse duration `DH(4)`. As written, TL/TH report the *shortest* opposite-class pulse.
- **Quirk:** if a class has no pulses, its stats are zeros, so e.g. `TH = DL(3) = 0` even though "no low pulses" means the no-low-pulse period is the whole record.
- **Quirk:** volume units are `l/s × day` (needs ×86.4 for m³, ×86400 for litres); header claims [l]. Duration in datenum days (fractional).
- **Quirk:** frequency CV etc. include calendar years with zero pulses and also **years outside the data coverage** if the record has leading/trailing gaps — deflating means.
- **Quirk:** `sum(Peak)` as "Total magnitude" is physically meaningless but reported.
- **Quirk:** first real pulse can never merge with the dummy row (dummy end = 0), by construction.
- **Edge:** all-NaN `Q` → `k=0`, loop skipped, `nH=nL=0` path returns all zeros; `Date(end+1)=Date(end)` on empty errors first (SUSPECTED crash on empty/all-NaN input).

### 5.6 Python notes
Rewrite as run-length encoding on the boolean `Q >= Lim` (`itertools.groupby` / `np.diff` on indices) instead of the incremental merge loop — mathematically identical for contiguous data and far clearer. Fix the `Years` misalignment by computing years after NaN filtering; decide whether TL/TH keep the min-duration behaviour (bug-compatible) or the intended max.

---

## 6. iMHEA_MonthlyFlow.m — Monthly and annual discharge means

### 6.1 Signature

```matlab
function [Q_Month,Q_Year,Q_Avg_Month,Q_Avg_Year,Q_Matrix,Q_YMin,Q_YMax] = iMHEA_MonthlyFlow(Date,Q,varargin)
```

| Arg | Direction | Type / Units | Notes |
|---|---|---|---|
| `Date` | in | datetime | Any resolution |
| `Q` | in | discharge [l/s or l/s/km²] | |
| `varargin` (flag) | in, optional | any | If present (`nargin>=3`) plot 3 bar charts |
| `Q_Month` | out | (12·n)×1 vector of monthly mean flows, ordered Jan..Dec of year 1, then year 2, … | `matrixQM1(:)` column-major |
| `Q_Year` | out | n×2 `[year, annual mean flow]` | |
| `Q_Avg_Month` | out | 12×1 sample-weighted mean flow per calendar month | |
| `Q_Avg_Year` | out | scalar mean of annual means | |
| `Q_Matrix` | out | n×12 (years × months) monthly means | |
| `Q_YMin` | out | n×3 `[year, annual min, day-of-year of min]` | |
| `Q_YMax` | out | n×3 `[year, annual max, day-of-year of max]` | |

### 6.2 Algorithm

**Step 1 (lines 26–28):** `Years = year(Date)`, `Months = month(Date)`, `n = max(Years)-min(Years)+1` (**calendar span**, includes empty years).

**Step 2 — per year i = 1..n (lines 36–49):** with `yr = min(Years)+i-1`:
```matlab
38  Q_Year(i) = nanmean(Q(Years==min(Years)+i-1));
40  [Q_YMin(i,1),MinPos] = nanmin(Q(Years==min(Years)+i-1));
41  Q_YMin(i,2) = day(Date(MinPos),'dayofyear');
43  [Q_YMax(i,1),MaxPos] = nanmax(Q(Years==min(Years)+i-1));
44  Q_YMax(i,2) = day(Date(MaxPos),'dayofyear');
46      matrixQM1(j,i) = nanmean(Q(and(Years==min(Years)+i-1,Months==j)));
47      sizeQM1(j,i) = length(Q(and(Years==min(Years)+i-1,Months==j)));
```
Monthly value = `nanmean` of all samples in that (year, month); `sizeQM1` counts ALL samples (including NaN).

**Step 3 — aggregates (lines 52–60):**
```matlab
52  Q_Avg_Month = nansum(matrixQM1.*sizeQM1,2)./nansum(sizeQM1,2);
53  Q_Avg_Year = nanmean(Q_Year);
55  Q_Month = matrixQM1(:);
56  Q_Matrix = matrixQM1';
```
`Q_Avg_Month` is a **weighted** mean of the monthly means across years, weights = raw sample counts. Year/min/max tables get the year column prepended (lines 58–60).

**Step 4 —** plots if flag (lines 63–99): monthly series bar chart (with a 12-label tick set recycled over all bars), average-month bars overlaid with a `boxplot` of `Q_Matrix` padded with NaN rows, and annual bars. Uses `inputname(2)` for legend names (fails if Q is an expression, returning empty name).

### 6.3 NaN/gap handling
- `nanmean`/`nanmin`/`nanmax` skip NaN inside a month/year.
- A (year,month) with **no samples at all**: `nanmean(empty) = NaN` → monthly value NaN (good), `sizeQM1 = 0`. In `Q_Avg_Month`, `NaN*0` = NaN but `nansum` skips it → empty months are correctly excluded.
- A month with only NaN samples: monthly value NaN, but `sizeQM1 = count of NaN samples > 0` → `NaN*size = NaN`, still skipped by `nansum` in the numerator, **but the denominator `nansum(sizeQM1,2)` still adds those NaN-sample counts**, deflating `Q_Avg_Month` for that calendar month (SUSPECTED bug, see below).
- Years with no data: `Q_Year = NaN`, excluded from `Q_Avg_Year` by `nanmean`.
- **No completeness threshold:** a month with a single sample counts the same as a complete month.

### 6.4 Dependencies
- iMHEA: none.
- Built-ins: `year`, `month`, `day(...,'dayofyear')`, `nanmean`, `nansum`, `nanmin`, `nanmax`, `inputname`, `boxplot` (Statistics Toolbox), `bar`.

### 6.5 Edge cases, quirks, suspected bugs
- **BUG (definite):** lines 40–41 and 43–44 — `MinPos`/`MaxPos` are indices **within the year-subset** `Q(Years==yr)`, but they are used to index the FULL `Date` array: `day(Date(MinPos),'dayofyear')`. The reported day-of-year of the annual min/max is wrong for every year except (coincidentally) parts of the first. Correct code needs the subset of Date too.
- **SUSPECTED BUG:** `sizeQM1` uses `length(...)` = all samples including NaN (line 47), so months padded with NaN placeholders get inflated weights in `Q_Avg_Month` (and all-NaN months corrupt the denominator as described in 6.3).
- **Quirk:** `matrixQM1`/`sizeQM1` are preallocated 12×1 (lines 33–34) and grow column-by-column inside the loop — works, but relies on MATLAB auto-growth.
- **Quirk:** monthly means are means of raw samples, NOT volume-weighted; for irregular sampling this biases toward densely sampled periods.
- **Edge:** all-NaN year → `nanmin` returns NaN with `MinPos=1` → day-of-year of `Date(1)` reported.
- **Quirk:** header typos: outputs documented as `Q_Min_Year`/`Q_Max_Year` "precipitation" (lines 17–18) — they are discharge min/max.

### 6.6 Python notes
One-liner with pandas: `Q.groupby([Date.dt.year, Date.dt.month]).mean()` plus `idxmin`/`idxmax` for the extremes (which also fixes the MinPos bug — flag this as an intentional behaviour change). Replicate the sample-count weighting of `Q_Avg_Month` only if bug-compatibility is required; otherwise use `groupby(month).mean()` of raw data.

---

## 7. iMHEA_MonthlyRain.m — Monthly and annual precipitation totals

### 7.1 Signature

```matlab
function [P_Month,P_Year,P_Avg_Month,P_Avg_Year,P_Matrix,P_YMin,P_YMax] = iMHEA_MonthlyRain(Date,P,varargin)
```

Identical structure and outputs to `iMHEA_MonthlyFlow` but for precipitation [mm]: `P_Month` (12·n monthly totals), `P_Year` (n×2 annual totals), `P_Avg_Month` (12 weighted monthly averages), `P_Avg_Year` (mean annual total), `P_Matrix` (n×12), `P_YMin`/`P_YMax` (n×3 with day-of-year). Optional flag (`nargin>=3`) plots.

### 7.2 Algorithm — differences from iMHEA_MonthlyFlow ONLY

The code is a line-for-line clone with `nanmean` replaced by `nansum` for accumulation:
```matlab
38  P_Year(i) = nansum(P(Years==min(Years)+i-1));          % annual TOTAL
46  matrixPM1(j,i) = nansum(P(and(Years==min(Years)+i-1,Months==j)));  % monthly TOTAL
47  sizePM1(j,i) = length(P(and(Years==min(Years)+i-1,Months==j)));
52  P_Avg_Month = nansum(matrixPM1.*sizePM1,2)./nansum(sizePM1,2);
53  P_Avg_Year = nanmean(P_Year);
```
Min/max extremes (lines 40–44) still use `nanmin`/`nanmax` of the per-interval precipitation values (i.e. the largest/smallest single recorded interval depth in the year, NOT daily rain). Everything else (matrix stacking lines 55–60, plots lines 63–99) matches Section 6.

### 7.3 NaN/gap handling — CRITICAL DIFFERENCE
`nansum` of an **empty or all-NaN** slice returns **0**, not NaN. Therefore:
- A month with no data at all reports **0 mm** — indistinguishable from a genuinely dry month.
- A year with no data reports annual precipitation **0 mm**, and that 0 is INCLUDED in `P_Avg_Year = nanmean(P_Year)` (line 53), dragging the multi-annual average down. (In MonthlyFlow the equivalent slot is NaN and excluded.)
- In `P_Avg_Month` (line 52) an empty month contributes `0 * 0 = 0` to the numerator and 0 to the denominator — the empty month is effectively treated as a real 0-mm month whenever other samples exist in that calendar month across years? No: with `sizePM1=0` its weight is zero, so empty months are excluded from `P_Avg_Month`; but months containing only NaN samples get weight = NaN-count with value 0 → they pull `P_Avg_Month` **toward zero**. 
- No minimum-coverage threshold anywhere: partially recorded months report partial totals as if complete. This is the most important gap-handling caveat of the whole group for rainfall.

### 7.4 Dependencies
Same as MonthlyFlow: no iMHEA calls; `year`, `month`, `day(...,'dayofyear')`, `nansum`, `nanmean`, `nanmin`, `nanmax`, `inputname`, `boxplot`, `bar`.

### 7.5 Edge cases, quirks, suspected bugs
- **BUG (definite, inherited):** same `MinPos`/`MaxPos` subset-index-into-full-`Date` bug at lines 40–44 → wrong day-of-year for annual min/max.
- **SUSPECTED BUG:** missing months/years silently reported as 0 mm (see 7.3); `P_Avg_Year` biased low by empty calendar years inside the span.
- **SUSPECTED BUG (inherited):** `sizePM1` counts NaN samples as weight (line 47).
- **Quirk:** header typos (lines 17–18) describe P_Min/P_Max as "discharge".
- **Quirk:** annual min of interval precipitation is almost always 0 (any dry interval), making `P_YMin` nearly useless — likely intended for aggregated (e.g. daily/monthly) inputs.

### 7.6 Python notes
`groupby([year, month]).sum(min_count=1)` in pandas returns NaN for empty groups — use `min_count=1` to FIX the 0-vs-missing ambiguity, and document the deliberate deviation (or `.sum()` default for bug-compatibility). Add an optional coverage-fraction threshold parameter.

---

## Cross-cutting summary for the translator

1. **Toolbox dependency:** `regression` (BaseFlow, BaseFlowUK) is from the Deep Learning Toolbox → `scipy.stats.linregress`.
2. **Legacy NaN functions** (`nanmean`, `nansum`, `nanmin`, `nanmax`) everywhere → numpy `nan*` equivalents, BUT note `nansum([]) = 0` vs `nanmean([]) = NaN` semantics drive the MonthlyRain zero-gap issue.
3. **iMHEA dependencies:** `iMHEA_Average` (BaseFlowUK) and `iMHEA_Aggregation` (IDC) must be translated first.
4. Confirmed bugs to decide on: Monthly* day-of-year indexing; Pulse `Years` misalignment; IDC stale `u` buffer (mean/median columns); Pulse `TL/TH` min-vs-max; BaseFlowUK `k` output overload.
5. All plotting/waitbar/fprintf blocks are side effects gated on optional flags — recommend `plot=False` keyword args in Python.
