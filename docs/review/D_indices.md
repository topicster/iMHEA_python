# Group D — Index compilation functions (iMHEA)

Files covered (in `.../iMHEA/Protocolos/Scripts/iMHEA_scripts/`):
`iMHEA_Indices.m`, `iMHEA_IndicesPlus.m`, `iMHEA_IndicesTotal.m`, `iMHEA_ClimateP.m`, `iMHEA_ClimateTotal.m`, `iMHEA_Pair.m`

These six functions are the *orchestration/compilation* layer: most raw computation is delegated to
`iMHEA_ProcessP`, `iMHEA_ProcessQ`, `iMHEA_FDC`, `iMHEA_Pulse`, `iMHEA_MonthlyRain`, `iMHEA_MonthlyFlow`,
`iMHEA_IDC`, `iMHEA_Aggregation`, `iMHEA_Average` (documented in their own spec docs; their output
contracts are summarised here in §7 because index positions into their outputs are load-bearing).

Global conventions used by all functions in this group:

- **Time windows are CALENDAR years (Jan–Dec)**, obtained via `year(Date)`; there is no hydrological-year
  logic anywhere in this group. "Julian day" = `day(Date,'dayofyear')` (1–366).
- **Percentile convention** (via `iMHEA_FDC`): Gringorten plotting position on ascending-sorted flows,
  `FDC(:,1) = 100*(1-((1:k)-.44)/(k+.12))` (exceedance %, so `spline(...,95)` = flow exceeded 95 % of
  the time = "Q95" = 5th magnitude percentile), interpolated with **MATLAB cubic `spline`** — NOT linear
  interpolation and NOT `prctile`. `numpy.percentile` will NOT reproduce these values.
- **Naming convention**: `Qxx` = flow exceeded xx % of the time. So Q95 is a LOW flow, Q10 a HIGH flow;
  Q75 = 25th percentile, Q25 = 75th percentile.
- Flow indices are per unit area `[l/s/km2]` whenever the area `A` is passed (Q is divided by A first).
- Data resolution: precipitation is aggregated (summed) to daily/hourly/5-min grids with
  `iMHEA_Aggregation`; discharge is averaged to daily with `iMHEA_Average(...,1440)`. All flow indices
  in this group are computed from **daily mean flow**, all rain intensity indices from the **5-min grid**
  via `iMHEA_IDC`.
- **Gap handling pattern** (repeated everywhere): after gridding, rows with `NaN` are simply dropped
  (`NewQ = DQ(~isnan(DQ))`), and per-year rates are normalised by elapsed calendar span, not by valid
  days. There are **no minimum-record-length checks anywhere** — a 3-month record silently produces
  "annual" indices.

---

## 1. `iMHEA_Indices.m`

### 1.1 Signature

```matlab
function [IndicesP,PM,IDC,IndicesQ,QM,FDC,QYEAR,RRa,RRm,RRl,CumP,CumQ,DP,DQ] = iMHEA_Indices(Date,P,Q,A,varargin)
```

Inputs:

| Arg | Meaning | Units |
|---|---|---|
| `Date` | timestamp vector (MATLAB `datetime`), event/5-min resolution | – |
| `P` | precipitation depth per timestamp | mm |
| `Q` | discharge | l/s |
| `A` | catchment area | km2 |
| `varargin` (flag) | any 5th argument ⇒ produce 6 diagnostic figures AND pass plot flags down to `iMHEA_ProcessP` / `iMHEA_ProcessQ` | – |

Outputs:

| Output | Content | Units |
|---|---|---|
| `IndicesP` | 7×1 vector `[PYear; DayP0; PP0; PMDry; Sindx; iM15m; iM1hr]` (from `iMHEA_ProcessP`; note the header comment at lines 15–20 lists only 6 entries and **omits PP0** — the real vector has 7, see ProcessP header) | mixed |
| `PM` | 12×1 average monthly precipitation, Jan=1..Dec=12 | mm |
| `IDC` | max intensity–duration curve `[duration_min, max mm/h, mean mm/h, median mm/h]` | mm/h vs min |
| `IndicesQ` | 22×1 vector, order: `QDMin,Q95,DayQ0,PQ0,QMDry,QDMax,Q10,QDMY,QDML,Q50,BFI1,k1,BFI2,k2,Range,R2FDC,IRH,RBI1,RBI2,DRYQMEAN,DRYQWET,SINDQ` (from `iMHEA_ProcessQ`) | l/s/km2 or – |
| `QM` | 12×1 monthly flow, **converted to mm/month inside this function** (see step 4) | mm |
| `FDC` | flow duration curve `[exceedance %, Q l/s/km2]` | – |
| `QYEAR` | mean annual discharge | mm/yr |
| `RRa` | runoff ratio from annual averages | – |
| `RRm` | runoff ratio from monthly averages | – |
| `RRl` | runoff ratio from long-term daily means | – |
| `CumP` | `[datenum, cumulative P mm]` daily | mm |
| `CumQ` | `[datenum, cumulative Q]`, col 2 converted to mm (line 84) | mm |
| `DP` | `[datenum, daily P]` (NaN days removed) | mm |
| `DQ` | `[datenum, dailyQ, baseflow, stormflow]` | l/s/km2 |

### 1.2 Algorithm

1. **Delegate** (lines 73–79): if `nargin>=5` call `iMHEA_ProcessP(Date,P,1)` and
   `iMHEA_ProcessQ(Date,Q,A,1,1)` (plot flags on), else without flags. These produce ALL of
   `IndicesP, PM, IDC, CumP, DP` and `IndicesQ, QM, FDC, CumQ, DQ`. (All 22 flow indices and 7 rain
   indices are defined in the ProcessP/ProcessQ specs; `Q95/Q10/Q50/R2FDC/IRH` use the
   Gringorten+spline convention of `iMHEA_FDC`, §7.)
2. **QYEAR** (line 82): `QYEAR = IndicesQ(8)*365/1000000*86400;` i.e. QDMY (annual mean daily flow,
   l/s/km2) → mm/yr. Conversion: 1 l/s/km2 = 86400 l/day/km2 = 86400/10^6 mm/day; ×365 (never 366).
3. **RRa** (line 83): `RRa = QYEAR / IndicesP(1);` = QYEAR / PYear [–].
   Line 84 converts `CumQ(:,2) = CumQ(:,2)/1000000*86400;` (l/s/km2-days → mm) for plotting/output.
4. **QYEAR fallback & RRl** (lines 86–87):
   ```matlab
   if isnan(QYEAR); QYEAR = nanmean(DQ(:,2))/1000000*86400; end
   RRl = nanmean(DQ(:,2))/1000000*86400 / (nanmean(DP(:,2)));
   ```
   RRl = long-term mean daily Q [mm/day] / long-term mean daily P [mm/day]. Note the fallback QYEAR is
   in **mm/day**, not mm/yr (missing ×365) — see §1.5. Also the fallback happens AFTER RRa was computed,
   so RRa stays NaN even when QYEAR is patched.
5. **RRm** (lines 90–92):
   ```matlab
   MDays = [31 28 31 30 31 30 31 31 30 31 30 31]';
   QM = QM.*MDays/1000000*86400;
   RRm = nansum(QM)/nansum(PM);
   ```
   QM (l/s/km2 mean of each calendar month) → mm/month using fixed month lengths (**Feb always 28,
   no leap years**). RRm = Σ monthly Q mm / Σ monthly P mm.
6. **Plots** (lines 94–174, only if flag): input P (reversed y) & Q/A; cumulative P vs Q + double-mass
   plot; IDC (semilogx); FDC (semilogy); monthly PM vs QM; daily P bars and daily Q with
   baseflow/stormflow (`DQ` columns 2,3,4). No computation happens here.

### 1.3 NaN/gap handling
All inside ProcessP/ProcessQ (NaN days dropped after daily gridding). `nanmean`/`nansum` used at
lines 86–92 so months/years with no data drop out of RRm/RRl. No minimum-data requirement.

### 1.4 Dependencies
`iMHEA_ProcessP`, `iMHEA_ProcessQ` (which internally use `iMHEA_Aggregation`, `iMHEA_Average`,
`iMHEA_MonthlyRain`, `iMHEA_MonthlyFlow`, `iMHEA_IDC`, `iMHEA_FDC`, baseflow routines).
Built-ins: `nanmean`, `nansum`, `datetime(...,'ConvertFrom','datenum')`, plotting.

### 1.5 Edge cases / suspected bugs
- **SUSPECTED bug (units)**: line 86 fallback sets `QYEAR = nanmean(DQ(:,2))/1e6*86400` = mm/**day**,
  while QYEAR is documented and printed as annual mm. Missing `*365`. Only triggers when QDMY is NaN.
- **SUSPECTED (ordering)**: RRa (line 83) is computed before the QYEAR fallback → RRa = NaN whenever
  QDMY is NaN, even though QYEAR then gets a (wrong-unit) value.
- Fixed `MDays` with Feb=28 ignores leap years (≤0.1 % bias in RRm).
- Header typo line 27: "Q95 = 95 Percentile flow from IDC" — it is from the **FDC**.
- `QM` output is repurposed: ProcessQ returns l/s/km2, this function overwrites it in mm/month —
  callers (e.g. `iMHEA_Pair`) receive mm.
- 365 used everywhere (never 365.25).

### 1.6 Python notes
Pure orchestration: reimplement as a thin function calling process_p/process_q, returning a dataclass/dict.
Preserve the 22-element IndicesQ and 7-element IndicesP ordering exactly (downstream code indexes by
position). Decide explicitly whether to reproduce or fix the QYEAR-fallback unit bug (flag it).

---

## 2. `iMHEA_IndicesPlus.m`

### 2.1 Signature

```matlab
function [M,F,D,T,R] = iMHEA_IndicesPlus(Date,Q,A,varargin)
```

Inputs: `Date` (datetime), `Q` [l/s or l/s/km2], `A` [km2] optional — if `nargin>=3` then `Q = Q/A`
(line 81). 4th arg is documented as a plot flag but is **never used** (no plots in this function).

Outputs — five column vectors of Olden & Poff (2003) indices (`*` = modified from paper), assembled at
lines 249–283 in exactly this order:

- `M` (11×1): `MA5, MA41, MA3, MA11, ML17, ML21, ML18, MH16, MH14, MH22, MH27`
- `F` (8×1): `FL3, FL2, FL1, FH3, FH6, FH7, FH2, FH1`
- `D` (7×1): `DL17, DL16, DL13, DH13, DH16, DH20, DH15`
- `T` (3×1): `TH3, TL2, TL1`
- `R` (4×1): `RA8, RA5, RA6, RA7`

### 2.2 Algorithm (all from DAILY mean flow)

1. Normalise: `Q = Q/A` if `A` given (line 81).
2. Daily averaging (line 85): `[DDate,DQ,~,~,QDML] = iMHEA_Average(Date,Q,1440);` — `QDML` is the
   long-term mean of the daily series (mean over the full record as returned by iMHEA_Average).
3. Drop NaN days (lines 88–90): `NewDate = DDate(~isnan(DQ)); NewQ = DQ(~isnan(DQ)); k = length(NewQ);`
   (DL18/PQ0 intentionally commented out, lines 91–94 — they live in `iMHEA_ProcessQ`.)
4. **MA2** (median daily flow, internal only, lines 97–101):
   ```matlab
   MA2 = median(NewQ);
   if MA2==0
       MA2=QDML;
       disp('Warning: Median of flows is 0. Assigned mean.');
   end
   ```
5. **MA3** = `std(NewQ) / QDML` (line 103) — CV of daily flows [–]. (`std` = sample std, N−1.)
6. **MA5** = `QDML / MA2` (line 105) — skewness proxy, mean/median [–].
7. Percentiles (lines 108–112): `[~,~,~,Ptile] = iMHEA_FDC(NewQ);` then
   `Q75 = Ptile(2); Q25 = Ptile(6); Q10 = Ptile(7);` (Gringorten + cubic spline; Q75 = flow exceeded
   75 % of time = 25th pct, Q25 = 75th pct, Q10 = 90th pct).
8. **MH16** = `Q10 / MA2` (line 116) [–]. **MA11** = `(Q25 - Q75) / MA2` (line 119) — IQR/median [–].
9. Monthly/annual stats (line 122): `[~,Q_Year,QDMM,~,~,Q_YMin,~] = iMHEA_MonthlyFlow(NewDate,NewQ);`
   - `MonthMedian = median(QDMM)` (line 125) — median of the 12 long-term monthly means (weighted by
     day counts inside MonthlyFlow).
   - **MA41** = `mean(YearFlow)` where `YearFlow = Q_Year(:,2)` (lines 130–131) — mean of
     calendar-year mean daily flows [l/s/km2]; **partial first/last years get equal weight**.
10. **Rolling 30-day extrema** (lines 142–150): for every valid day `i`,
    `Y = NewQ(NewDate>=Today & NewDate<Today+30)`; `Max30(i)=max(Y); Min30(i)=min(Y)`.
    Forward-looking, date-based window (gaps shrink the sample; the last windows are truncated —
    the final day's window contains 1 value). Then:
    - **DH13** = `mean(Max30) / MA2` (line 151) [–]
    - **DL13** = `mean(Min30) / MA2` (line 152) [–]
    - **ML21** = `std(Min30) / mean(Min30)` (line 153) — CV of 30-day minima [–]
    - **MH14** = `median(Max30) / MA2` (line 154) [–]
11. **Rolling 7-day minima** (lines 157–163, same forward window with 7 days):
    - **ML17** = `min(Min7) / MA41` (line 164) — global 7-day minimum / mean annual flow [–]
      (*paper uses mean of annual ratios; this is modified*)
    - **ML18** = `std(Min7) / mean(Min7)` (line 165) — CV of the 7-day-minima series [–]
      (label "CV in ML17" is loose).
12. **Timing** (lines 169–171): `YearMinD = Q_YMin(:,3);` = Julian day of each calendar year's daily
    minimum; **TL1** = `median(YearMinD)`; **TL2** = `std(YearMinD)/mean(YearMinD)`.
    (No circular statistics — see §2.5 bug about Q_YMin.)
13. **Pulse-based indices** — every call is `iMHEA_Pulse(NewDate,NewQ,Lim)`; Pulse returns, for High
    and Low pulses, 5-element stats vectors ordered `(Total, Average, Min, Max, CVar)` for magnitude
    (peak), volume, frequency, duration, plus scalar `T` = longest spell without a pulse [day].
    `days_span = datenum(NewDate(end)-NewDate(1))` (duration→days).
    - Threshold **Q25** (line 177–182):
      `[MH27,~,FH12,DH1516] = iMHEA_Pulse(NewDate,NewQ,Q25);`
      **MH27** = `MH27(2)/MA2` (mean high-pulse peak / median) [–];
      **FH1** = `FH12(1)*365/datenum(NewDate(end)-NewDate(1)+1)` (total count → per year; span+1 day);
      **FH2** = `FH12(5)` (CV of annual high-pulse counts) [–];
      **DH15** = `DH1516(2)` (mean high-pulse duration) [day]; **DH16** = `DH1516(5)` (CV) [–].
    - Threshold **3·MA2** (lines 185–187):
      **FH3** = `FH3(1)*365/datenum(NewDate(end)-NewDate(1))` [1/yr] (**no `+1` here** — inconsistent);
      **MH22** = `MH22(2)/MA2` = mean high-pulse *volume* above threshold / median [day]
      (volume in l/s·day ÷ l/s = day).
    - Threshold **3·MonthMedian** (lines 196–197): **FH6** = `FH6(1)*365/(span+1)` [1/yr].
    - Threshold **7·MonthMedian** (lines 200–201):
      `FH7 = FH7(2)*365/datenum(NewDate(end)-NewDate(1)+1);` — uses element **(2) = average count per
      calendar year**, then divides by record length again → double normalisation (§2.5 bug).
    - Threshold **Q75**, LOW pulses (lines 204–208):
      **FL1** = `FL12(1)*365/datenum(NewDate(end)-NewDate(1))` [1/yr] (no `+1`);
      **FL2** = `FL12(5)` [–]; **DL16** = `DL1617(2)` [day]; **DL17** = `DL1617(5)` [–].
    - Threshold **0.05·QDML**, LOW pulses (lines 211–212): **FL3** = `FL3(1)*365/(span+1)` [1/yr].
    - Threshold **MA2/0.75** (lines 215–216): **DH20** = `DH20(2)` mean high-pulse duration [day].
    - Threshold **Q10** (lines 219–220): 5th output of Pulse = `TH` = longest period with no HIGH pulse
      above Q10; **TH3** = `TH3/365` — max proportion of the "year" (really record) without flood [–].
14. **Rate of change** (lines 224–246):
    ```matlab
    LogQ = log(NewQ);
    DiffLogQ = diff(LogQ);
    RA6 = median(DiffLogQ(DiffLogQ>0));
    RA7 = median(DiffLogQ(DiffLogQ<0));
    ```
    Natural log; **zeros are NOT handled** → `log(0) = -Inf`; a 0→positive step gives `+Inf`
    (excluded from neither median; ±Inf enters the >0/<0 subsets and can corrupt the median ordering
    endpoints — with ≥3 elements median is usually finite, but Inf can appear for short records).
    Also `diff` across data gaps treats non-consecutive days as consecutive.
    Reversals (lines 230–246): scan consecutive valid days; `RA8` counts sign reversals of the
    day-to-day change (state machine starting `reversal=1`; equal flows do not flip state);
    `RA5` counts days with `NewQ(i+1)>NewQ(i)`. Both divided by
    `datenum(NewDate(end)-NewDate(1)+1)` — i.e. per **day of calendar span** (not per valid pair, not
    per year despite the header saying `[year^-1]` for RA8).
15. Assemble M,F,D,T,R (lines 249–283) in the exact orders listed in §2.1.

### 2.3 NaN/gap handling
NaN days dropped once (line 88–89); afterwards the series is treated as contiguous: `diff`,
reversal counts, and rolling windows silently span gaps (rolling windows are at least date-bounded;
`diff`/reversals are not). Frequencies are normalised by calendar span, so gappy records
under-report pulse frequencies. No minimum record length.

### 2.4 Dependencies
`iMHEA_Average` (daily means), `iMHEA_FDC` (percentiles), `iMHEA_MonthlyFlow` (annual means, monthly
means, annual-minimum Julian days), `iMHEA_Pulse` (all F/D/T pulse stats).
Built-ins: `median, mean, std, min, max, log, diff, datenum, year`.

### 2.5 Edge cases / suspected bugs
- **SUSPECTED bug — FH7 (line 201)**: uses `FH7(2)` (average pulses per calendar year) then ALSO
  divides by record length ×365. Every sibling index (FH1, FH3, FH6, FL1, FL3) uses element `(1)`
  (total count). FH7 is therefore ≈ total/(n_years·span/365) — wrong by a factor ≈ n_years.
- **SUSPECTED bug — inherited from `iMHEA_MonthlyFlow`**: inside MonthlyFlow, the position of the annual
  minimum is found in the year-subset (`[..,MinPos]=nanmin(Q(Years==y))`) but the day-of-year is taken
  as `day(Date(MinPos),'dayofyear')` — `MinPos` indexes the subset while `Date` is the full vector, so
  **TL1/TL2 use wrong Julian days for every year after the first**.
- **SUSPECTED inconsistency**: record-length denominator is `span+1` days for FH1/FH6/FH7/FL3/RA5/RA8
  but `span` (no +1) for FH3/FL1 (lines 186, 205).
- **SUSPECTED**: RA6/RA7 with zero flows → ±Inf via `log(0)` (no zero-offset); units in the header say
  l/s/km2 but the quantities are dimensionless log-ratios.
- MA2==0 is silently replaced by the mean (line 98–101) — changes MA5, MA11, MH14/16/22/27, DH13, DL13,
  DH20 threshold, FH3 threshold for intermittent streams.
- TH3 is the longest floodless spell of the whole **record** divided by 365 — can exceed 1 for
  multi-year records with no Q10 exceedance.
- Rolling windows are forward-looking and right-truncated (last 30-day "window" has 1 sample) — biases
  Max30 down / Min30 up near the end of record.
- The `flag` argument (4th) is dead code; passing it only triggers the `Q/A` normalisation branch
  requirement (`nargin>=3` is what matters).
- `datenum(duration)+1`: `NewDate(end)-NewDate(1)` is a `duration`; `+1` adds one day; `datenum()` of a
  duration returns days as double. In Python: `(dates[-1]-dates[0]).days + 1`.

### 2.6 Python notes
Reimplement Ptile with the Gringorten+cubic-spline convention (scipy `CubicSpline` on the plotting
positions), not `np.percentile`. Rolling extrema: use date-indexed forward windows
(`pandas.rolling` on a reindexed daily series is backward-looking — reverse or shift carefully, and
reproduce the truncated tail if bit-compatibility is wanted). Decide policy for the FH7 and TL1 bugs:
recommend computing both "as-is" and "fixed" values during validation.

---

## 3. `iMHEA_IndicesTotal.m`

### 3.1 Signature

```matlab
function [Climate,Indices] = iMHEA_IndicesTotal(Date,P,Q,A,varargin)
```

Inputs as `iMHEA_Indices` (flag = 5th arg → plots in all sub-calls). Uses `inputname(4)` in the banner
printf (line 26) — requires `A` to be passed as a named workspace variable, else `inputname` returns ''.

Outputs:
- `Climate` = 13×1 vector (rows 1–13 of `iMHEA_Indices_Climate.csv`).
- `Indices` = 59×1 vector (rows 1–59 of `iMHEA_Indices_Hydro.csv`).

### 3.2 Algorithm

1. (lines 27–41) Call, with or without flag:
   `[IndicesP,~,~,IndicesQ,~,~,QYEAR,RRa,RRm,RRl] = iMHEA_Indices(Date,P,Q,A[,1]);`
   `[M,F,D,T,R] = iMHEA_IndicesPlus(Date,Q,A[,1]);`
   `[ClimateP] = iMHEA_ClimateP(Date,P[,1]);`
2. **Compile Climate** (lines 44–47):
   ```matlab
   [Climate] = [IndicesP(1:end-2);...
                ClimateP(end);...
                ClimateP(1:end-1);...
                IndicesP(end-1)];
   ```
   With IndicesP = `[PYear;DayP0;PP0;PMDry;Sindx;iM15m;iM1hr]` (7 el.) and
   ClimateP = `[RMED1D;RMED2D;RMED1H;iMAX1D;iMAX2D;iMAX1H;PVAR]` (7 el.), this yields the 13-vector:
   `PYEAR, DAYP0, PP0, PMDRY, SINDX, PVAR, RMED1D, RMED2D, RMED1H, iMAX1D, iMAX2D, iMAX1H, iMAX15M`.
   Note `IndicesP(end)` (= iM1hr from ProcessP) is **discarded**; the 1-hour intensity kept is
   ClimateP's iMAX1H (same formula, computed from a second IDC run). `iMAX15M = IndicesP(end-1)`.
3. **Compile Indices** (lines 48–57): `[IndicesQ; QYEAR; RRa; RRm; RRl; M; F; D; T; R]`
   = 22 + 4 + 11 + 8 + 7 + 3 + 4 = **59** elements.
4. Print everything (lines 60–155) with fixed labels. No further computation.

### 3.3 Mapping to published CSVs (verified against file headers)

`.../Scripts/iMHEA_indices/iMHEA_Indices_Hydro.csv` first column, rows 1–59, matches `Indices`
positions 1–59 exactly:

| Pos | CSV name | Source | Pos | CSV name | Source |
|---|---|---|---|---|---|
| 1 | QDMIN | IndicesQ(1) | 31 | ML17 | M(5) |
| 2 | Q95 | IndicesQ(2) | 32 | ML21 | M(6) |
| 3 | DAYQ0 | IndicesQ(3) | 33 | ML18 | M(7) |
| 4 | PQ0 | IndicesQ(4) | 34 | MH16 | M(8) |
| 5 | QMDRY | IndicesQ(5) | 35 | MH14 | M(9) |
| 6 | QDMAX | IndicesQ(6) | 36 | MH22 | M(10) |
| 7 | Q10 | IndicesQ(7) | 37 | MH27 | M(11) |
| 8 | QDMY | IndicesQ(8) | 38 | FL3 | F(1) |
| 9 | QDML | IndicesQ(9) | 39 | FL2 | F(2) |
| 10 | Q50 | IndicesQ(10) | 40 | FL1 | F(3) |
| 11 | BFI1 | IndicesQ(11) | 41 | FH3 | F(4) |
| 12 | K1 | IndicesQ(12) | 42 | FH6 | F(5) |
| 13 | BFI2 | IndicesQ(13) | 43 | FH7 | F(6) |
| 14 | K2 | IndicesQ(14) | 44 | FH2 | F(7) |
| 15 | RANGE | IndicesQ(15) | 45 | FH1 | F(8) |
| 16 | R2FDC | IndicesQ(16) | 46 | DL17 | D(1) |
| 17 | IRH | IndicesQ(17) | 47 | DL16 | D(2) |
| 18 | RBI1 | IndicesQ(18) | 48 | DL13 | D(3) |
| 19 | RBI2 | IndicesQ(19) | 49 | DH13 | D(4) |
| 20 | DRYQMEAN | IndicesQ(20) | 50 | DH16 | D(5) |
| 21 | DRYQWET | IndicesQ(21) | 51 | DH20 | D(6) |
| 22 | SINDQ | IndicesQ(22) | 52 | DH15 | D(7) |
| 23 | QYEAR | QYEAR | 53 | TH3 | T(1) |
| 24 | RRa | RRa | 54 | TL2 | T(2) |
| 25 | RRm | RRm | 55 | TL1 | T(3) |
| 26 | RRl | RRl | 56 | RA8 | R(1) |
| 27 | MA5 | M(1) | 57 | RA5 | R(2) |
| 28 | MA41 | M(2) | 58 | RA6 | R(3) |
| 29 | MA3 | M(3) | 59 | RA7 | R(4) |
| 30 | MA11 | M(4) | | | |

`iMHEA_Indices_Climate.csv` rows 1–13 = `Climate(1:13)`:
`PYEAR, DAYP0, PP0, PMDRY, SINDX, PVAR, RMED1D, RMED2D, RMED1H, iMAX1D, iMAX2D, iMAX1H, iMAX15M`.
The CSV contains **two extra rows — `ETYEAR` (annual reference evapotranspiration) and `RPPE`
(PYEAR/ETYEAR)** — which are NOT computed by any of these six functions (added elsewhere/manually).
CSV description quirks: Q50 says "from IDC" (should be FDC); DAYQ0/PQ0 descriptions say
"zero precipitation" (should be zero flow); TL1 says "Mean" (code uses `median`).

### 3.4 NaN/gap handling
None of its own; inherits everything from callees.

### 3.5 Edge cases / suspected bugs
- **SUSPECTED (cosmetic)**: unescaped `%` in fprintf format strings — line 98
  `'Slope of the FDC between 33%-66%: %8.4f [-]\n'` and line 126 `'...below 5% mean daily flow...'` —
  `%-6`, `% m` are parsed as conversion specs, so the printed labels/values are garbled. Values in the
  returned vectors are unaffected.
- `inputname(4)` (line 26) errors/blanks if called with literal arguments (e.g. `iMHEA_IndicesTotal(D,P,Q,1.5)`).
- Rain intensities (iMAX*) are computed **twice** (IDC inside ProcessP and again inside ClimateP) —
  pure inefficiency; `iMHEA_IDC` is O(record × durations) with a waitbar.

### 3.6 Python notes
This is the canonical column order for the published dataset — encode it as an ordered list of names
(match CSV names above) and build a pandas Series. Compute IDC once and share it between the P-index
and climate-index paths.

---

## 4. `iMHEA_ClimateP.m`

### 4.1 Signature

```matlab
function [ClimateP] = iMHEA_ClimateP(Date,P,varargin)
```

Inputs: `Date` (datetime), `P` [mm]. `varargin` is accepted but **completely unused** (no plots, no
branches) — callers pass 1 or 2 flags which are ignored.

Output `ClimateP` (7×1, lines 69–75), in order:

| # | Name | Definition | Units | Resolution |
|---|---|---|---|---|
| 1 | RMED1D | median over calendar years of the annual maximum daily precipitation | mm | daily |
| 2 | RMED2D | median of annual maximum 2-day (48 h rolling forward sum) precipitation | mm | daily→2-day |
| 3 | RMED1H | median of annual maximum hourly precipitation | mm | hourly |
| 4 | iMAX1D | maximum 24-h intensity over the whole record, from IDC | mm/h | 5-min |
| 5 | iMAX2D | maximum 48-h intensity over the whole record, from IDC | mm/h | 5-min |
| 6 | iMAX1H | maximum 1-h intensity over the whole record, from IDC | mm/h | 5-min |
| 7 | PVAR | CV of daily precipitation = std/mean of all valid days (zeros included) | – | daily |

### 4.2 Algorithm

1. Grid to daily and hourly (lines 27–28): `iMHEA_Aggregation(Date,P,1440)` and `(...,60)` (sums).
2. Drop NaN days/hours (lines 31–35).
3. **PVAR** (lines 38–40): `PBAR = mean(NewP); PSTD = std(NewP); PVAR = PSTD/PBAR;` — sample std (N−1),
   dry days included.
4. **2-day sums** (lines 43–49): for every valid day, forward date-bounded window
   `Sum2D(i) = sum(NewP(NewDate>=Today & NewDate<Today+2))` (last day's window has 1 day; gaps shrink
   windows).
5. **Annual maxima** (lines 52–57): 7th output of `iMHEA_MonthlyRain` = `P_YMax` =
   `[year, max value, dayofyear]` per calendar year;
   `RMED1D = median(PYMax1D(:,2)); RMED2D = median(PYMax2D(:,2)); RMED1H = median(PYMax1H(:,2));`
   Median over ALL calendar years present, including partial first/last years (their maxima are
   underestimates → biases the medians low).
6. **IDC intensities** (lines 60–66):
   ```matlab
   [IDC] = iMHEA_IDC(Date,P);
   D = [1 2 3 6 12 24 48 144 288 576];
   iMAX1D = IDC(D==288,2);
   iMAX2D = IDC(D==576,2);
   iMAX1H = IDC(D==12,2);
   ```
   `iMHEA_IDC` builds a 5-min grid and computes, for each duration D (in 5-min units: 288=24 h,
   576=48 h, 12=1 h), the maximum moving-window sum × 12/D → mm/h. Column 2 = maximum intensity.
   Note iMAX1D/iMAX2D are **intensities in mm/h**, not depths (a 100 mm day → iMAX1D ≈ 4.17 mm/h).
7. Assemble output (lines 69–75) in the order RMED1D, RMED2D, RMED1H, iMAX1D, iMAX2D, iMAX1H, PVAR.

### 4.3 NaN/gap handling
NaN grid cells dropped before every statistic; no completeness threshold on years (a year with one
valid day still contributes an "annual maximum"). Inside `iMHEA_IDC`, NaNs are zero-filled or removed
before the moving sums (so intensities can bridge gaps).

### 4.4 Dependencies
`iMHEA_Aggregation`, `iMHEA_MonthlyRain` (uses only `P_YMax(:,2)`, so the MinPos/MaxPos day-of-year
bug in MonthlyRain does NOT affect these outputs), `iMHEA_IDC`.
Built-ins: `mean, std, median, sum`.

### 4.5 Edge cases / suspected bugs
- **SUSPECTED inefficiency**: the same rolling-sum machinery exists in `iMHEA_IDC`; the explicit O(k·2)
  2-day loop and a full IDC recomputation duplicate work (IDC also computed in ProcessP when called
  from IndicesTotal → three IDC runs per catchment).
- The 2-day series Sum2D is an overlapping (per-day) rolling sum, so `RMED2D` is the median of annual
  maxima of **overlapping** 2-day totals — fine, but different from non-overlapping "2-day blocks".
- Partial calendar years contribute deflated annual maxima to RMED* medians (no exclusion rule).
- `varargin`/flag is dead (header even documents a flag in `iMHEA_ClimateTotal`'s call `(...,1,1)`).
- If the record spans < 1 year, medians reduce to that single annual max.

### 4.6 Python notes
Straightforward with pandas: daily/hourly resample sums, `rolling('2D').sum()` (note MATLAB's window is
forward-looking; only the annual max is used so direction is irrelevant except at record edges),
`groupby(year).max()`, `.median()`. Reuse a single IDC computation.

---

## 5. `iMHEA_ClimateTotal.m`

### 5.1 Signature

```matlab
function [Climate] = iMHEA_ClimateTotal(Date,P,varargin)
```

Inputs: `Date`, `P` [mm]; flag (3rd arg) → plots inside `iMHEA_ProcessP`. Uses `inputname(2)` in the
banner (line 22). Output: `Climate` 13×1 — identical content and order to the Climate vector of
`iMHEA_IndicesTotal` (§3.2–3.3), i.e. rows 1–13 of `iMHEA_Indices_Climate.csv`.

### 5.2 Algorithm

1. (lines 23–33) `[IndicesP] = iMHEA_ProcessP(Date,P[,1]);` and
   `[ClimateP] = iMHEA_ClimateP(Date,P[,1,1]);` (the ClimateP flags are ignored, §4).
2. Compile (lines 36–39) — **identical expression to IndicesTotal lines 44–47**:
   `Climate = [IndicesP(1:end-2); ClimateP(end); ClimateP(1:end-1); IndicesP(end-1)]`
   → `PYEAR, DAYP0, PP0, PMDRY, SINDX, PVAR, RMED1D, RMED2D, RMED1H, iMAX1D, iMAX2D, iMAX1H, iMAX15M`.
3. Print (lines 42–61). Same labels as IndicesTotal's climate block.

### 5.3 NaN/gap handling
None of its own (inherited).

### 5.4 Dependencies
`iMHEA_ProcessP`, `iMHEA_ClimateP`. Built-ins: `fprintf`, `inputname`.

### 5.5 Edge cases / suspected bugs
- `inputname(2)` fails to name the catchment if `P` is an expression.
- Duplicate IDC computation (once in ProcessP, once in ClimateP) as in §3.5.
- The rain-only twin of IndicesTotal; keep the two compile expressions in one shared helper when
  porting to avoid drift.

### 5.6 Python notes
One-liner wrapper: `climate_vector = compile_climate(process_p(...), climate_p(...))`; share the
compile function with indices_total.

---

## 6. `iMHEA_Pair.m`

### 6.1 Signature

```matlab
function [Indices,Climate,PM,QM,FDC1,FDC2,IDC1,IDC2] = iMHEA_Pair(Date1,P1,Q1,A1,Date2,P2,Q2,A2)
```

Inputs: two full catchment datasets (Date [datetime], P [mm], Q [l/s], A [km2]). No optional args.

Outputs:
- `Indices` 59×2 (column per catchment, row order = §3.3 Hydro table; matches
  `iMHEA_Indices_Hydro_Pair.csv`).
- `Climate` 13×2 (row order = §3.3 climate list; matches `iMHEA_Indices_Climate_Pair.csv`).
- `PM` 12×2 monthly precipitation [mm]; `QM` 12×2 monthly discharge **[mm]** (converted inside
  `iMHEA_Indices`, §1.2 step 5).
- `FDC1,FDC2` flow duration curves; `IDC1,IDC2` intensity–duration curves.
- Side effect: 5 comparative figure windows.

### 6.2 Algorithm

1. Preallocate (lines 28–31): `Climate = zeros(13,2); Indices = zeros(59,2); PM = zeros(12,2); QM = zeros(12,2);`
2. (lines 33–34) `[Climate(:,i),Indices(:,i)] = iMHEA_IndicesTotal(Date_i,P_i,Q_i,A_i);` for i = 1,2
   (no plot flag → sub-functions run silently apart from prints).
3. (lines 35–36) call `iMHEA_Indices` AGAIN per catchment just to harvest
   `PM, IDC, QM, FDC, CumP, CumQ, DP, DQ` for plotting — i.e. **every index is computed twice per
   catchment** (and IDC three times, via ProcessP/ClimateP/this call). Pure inefficiency, no numeric
   difference.
4. Plots (lines 40–192): input P/Q with unified `XLim`; cumulative curves + double-mass; IDC overlay
   (semilogx); FDC overlay (semilogy); monthly regimes (months 0–12, month 0 = December value
   prepended: `plot((0:12)',[PM(12,1);PM(:,1)],...)` line 127); daily P and daily Q with
   baseflow/stormflow per catchment.

### 6.3 NaN/gap handling
None of its own. Note the two catchments are processed **independently** — no common-period trimming,
so indices compare different time windows if records differ (by design of the paired-catchment setup,
but worth flagging).

### 6.4 Dependencies
`iMHEA_IndicesTotal`, `iMHEA_Indices`. Built-ins: plotting, `datetime(...,'ConvertFrom','datenum')`.

### 6.5 Edge cases / suspected bugs
- **SUSPECTED inefficiency**: full duplicate computation (step 3). In Python return everything from one
  call.
- **SUSPECTED plot bug (cosmetic)**: figure 2 (lines 85–86) plots `CumP1(:,1)` raw **datenums** on the
  x-axis while figure 1 used `datetime` axes, so `Xlim` (datetime-based) cannot be applied and dates
  show as serial numbers.
- `iMHEA_IndicesTotal`'s `inputname(4)` (§3.5) — `iMHEA_Pair` passes variables `A1`,`A2`, so the banner
  prints "CATCHMENT A1/A2".
- Hardcoded sizes 13 and 59 must track any change in the compile vectors.

### 6.6 Python notes
Wrapper: run the single-catchment pipeline once per catchment, assemble two-column DataFrames with the
CSV index names, and (optionally) reproduce the comparison plots with matplotlib. Consider adding an
optional common-period restriction as an improvement flag, not default.

---

## 7. Dependency output contracts relied upon by this group (reference)

Only what group-D functions index into; full specs live in the dependency documents.

- **`iMHEA_ProcessP` → `[IndicesP,PM,IDC,CumP,DP]`**; `IndicesP = [PYear;DayP0;PP0;PMDry;Sindx;iM15m;iM1hr]`
  (7 elements; PYear = Σ of the 12 weighted mean-monthly values, fallback `365*mean(NewP)` if NaN;
  DayP0 = `floor(365*nZeroDays/kValidDays)`; PP0 = DayP0/365; iM15m/iM1hr from IDC rows D=3 and D=12).
- **`iMHEA_ProcessQ` → `[IndicesQ,QM,FDC,CumQ,DQ]`**; `IndicesQ` 22×1 in the order of §3.3 rows 1–22;
  `DQ = [datenum, Q, baseflow, stormflow]`.
- **`iMHEA_FDC(Q)` → `[FDC,R2FDC,IRH,Ptile]`**; `Ptile = [Q95 Q75 Q66 Q50 Q33 Q25 Q10]` (exceedance
  95/75/66/50/33/25/10 %), Gringorten positions + cubic `spline`;
  `R2FDC = (log10(Ptile(3))-log10(Ptile(5)))/(.66-.33)` with complex→`-inf` guard;
  `IRH = sum(min(FDC flows, Q50 for the upper half)) / sum(FDC flows)`.
- **`iMHEA_Pulse(Date,Q,Lim)` → `[MH,VH,FH,DH,TH,ML,VL,FL,DL,TL]`**; each of M/V/F/D is a 5-vector
  `(Total, Average, Min, Max, CVar)`; `TH/TL` = longest spell without a high/low pulse [day]; annual
  counts use calendar years; contiguous threshold crossings are merged.
- **`iMHEA_MonthlyFlow` → `[Q_Month,Q_Year,Q_Avg_Month,Q_Avg_Year,Q_Matrix,Q_YMin,Q_YMax]`**;
  `Q_Year = [year, mean daily Q]`; `Q_Avg_Month` = 12 day-count-weighted means;
  `Q_YMin = [year, min, dayofyear]` — **dayofyear computation is buggy** (subset index used against the
  full Date vector), affecting TL1/TL2 (§2.5). `iMHEA_MonthlyRain` is the Σ-based twin (same bug; group
  D only uses its `P_YMax(:,2)` values, which are correct).
- **`iMHEA_IDC(Date,P)` → `[IDC,iM15m,iM1hr]`**; 5-min grid; `IDC = [D*5 min, max, mean, median]`
  intensities in mm/h with `D = [1 2 3 6 12 24 48 144 288 576]` (5 min … 2 days); moving-window sums
  ×`12/D`.
- **`iMHEA_Average` / `iMHEA_Aggregation`**: regular grid at `scale` minutes (daily = 1440), dates
  shifted −0.25 s before binning, empty bins = NaN (Average) / 0-or-NaN via void detection
  (Aggregation); 5th outputs give record-level mean/max stats (`QDML` etc.).

## 8. Consolidated list of SUSPECTED bugs found in this group

1. `iMHEA_IndicesPlus.m:201` — FH7 double normalisation (`FH7(2)` per-year value divided by record
   length again); should almost certainly be `FH7(1)`.
2. `iMHEA_IndicesPlus.m:169–171` (via `iMHEA_MonthlyFlow`) — TL1/TL2 built on wrong day-of-year values
   for all years after the first (subset-index bug in MonthlyFlow).
3. `iMHEA_IndicesPlus.m:186,205` vs `179,197,201,212,245` — inconsistent record-length denominators
   (`span` vs `span+1` days) across FH3/FL1 vs FH1/FH6/FH7/FL3/RA5/RA8.
4. `iMHEA_IndicesPlus.m:224–227` — `log(0) = -Inf` unguarded in RA6/RA7 for intermittent streams.
5. `iMHEA_Indices.m:86` — QYEAR NaN-fallback yields mm/day instead of mm/yr (missing ×365), and is
   applied after RRa is computed, leaving RRa = NaN.
6. `iMHEA_Indices.m:90` — fixed month lengths (Feb=28) in RRm; 365-day years everywhere.
7. `iMHEA_IndicesTotal.m:98,126` — unescaped `%` in fprintf garbles printed labels (cosmetic).
8. `iMHEA_Pair.m:33–36` — every index computed twice per catchment (3× for IDC); `iMHEA_Pair.m:85–86`
   datenum x-axis breaks shared XLim (cosmetic).
9. Systemic: no minimum-data requirements; partial calendar years included in annual statistics
   (MA41, RMED*, pulse annual counts); NaN-gap days treated as consecutive in diff/reversal indices.
