# iMHEA Pre-processing Functions — Translation Specification (Group A)

Source directory: `/Users/boris/Library/CloudStorage/OneDrive-FundaciónBINARA/Projects/iMHEA/Protocolos/Scripts/iMHEA_scripts/`

Functions covered (all read line-by-line; line numbers refer to the source files):

1. `iMHEA_Depure.m` (40 lines)
2. `iMHEA_Voids.m` (105 lines)
3. `iMHEA_MonitoringGaps.m` (60 lines)
4. `iMHEA_FillGaps.m` (200 lines)
5. `iMHEA_Aggregation.m` (102 lines)
6. `iMHEA_AggregationCS.m` (509 lines, 4 subfunctions)
7. `iMHEA_AggregationLI.m` (479 lines, 4 subfunctions)
8. `iMHEA_Average.m` (114 lines)

**Global conventions used throughout this group**

- Time is handled as MATLAB **datenum**: a float whose unit is **days** since 0-Jan-0000. Therefore:
  - `1/1440` = 1 minute, `1/86400` = 1 second, `x*1440` converts days → minutes, `x*86400` days → seconds.
  - `nd = 1440/scale` is the number of aggregation intervals per day; `datenum*nd` converts a date to "interval index" units.
- Data gaps in input series are represented as **NaN rows in the value column with a valid timestamp** — a gap is *not* a missing timestamp. `iMHEA_Voids` is the single source of truth for gap intervals and is called by almost everything else.
- Aggregated timestamps are **right-labelled**: interval index `i` (a value of `NewDate` before rescaling) covers the half-open window `(i-1, i]` in units of `1/nd` days; the tip/sample at exactly the boundary belongs to the interval that *ends* there.
- Several functions shift input dates by `-0.25/86400` (0.25 s earlier) before processing, to keep boundary timestamps (e.g. exactly hh:mm:00) from falling on the wrong side of a bin edge due to datenum floating-point error.
- All functions assume **timestamps sorted ascending** and (except where noted) **no duplicate timestamps**. Nothing sorts or dedupes.
- `nansum/nanmean/nanmax/nanmin/nanmedian` (Statistics Toolbox legacy) = NaN-ignoring reductions.

---

## 1. `iMHEA_Depure.m`

### 1.1 Signature

```matlab
function [NewEvent_mm] = iMHEA_Depure(Event_Date,Event_mm)
```

| Arg | Direction | Meaning | Units |
|---|---|---|---|
| `Event_Date` | in | Tip timestamps, sorted ascending; treated as **datenum numeric** (see quirks) | days |
| `Event_mm` | in | Precipitation per tip | mm |
| `NewEvent_mm` | out | Same length as `Event_mm`; repetitive tips **replaced by 0** (not deleted) | mm |

No optional args. NOTE: the help text (lines 3–4) claims the function returns `[NewEvent_Date,NewEvent_mm]`, but the actual signature returns only `NewEvent_mm` — the dates are unchanged and not returned.

### 1.2 Algorithm

1. Constant: `nd = 86400` (s/day); minimum inter-tip interval `MinT = 1.1/nd` (line 24) — i.e. **1.1 seconds** expressed in days. Tips arriving faster than 1.1 s apart are physically impossible for a tipping bucket and treated as logger repetitions.
2. Line 28–29:
   ```matlab
   Diff_Event_Date = diff(Event_Date);
   Diff_Event_Date = [MinT*100;Diff_Event_Date];
   ```
   Compute time between consecutive tips and prepend `MinT*100` so the **first tip can never be flagged**.
3. Line 31–33:
   ```matlab
   EventDiff = Diff_Event_Date <= MinT;
   NewEvent_mm = Event_mm;
   NewEvent_mm(EventDiff) = 0;
   ```
   Any tip whose gap to the *previous* tip is ≤ 1.1 s is zeroed. In a burst of k tips each ≤1.1 s apart, tips 2..k are zeroed and **only the first survives** (each tip is compared to its immediate predecessor, using ORIGINAL time differences, so the whole chain is flagged).
4. Prints MinT in seconds (`MinT*86400` = 1.10), count of flagged tips, and rainfall volume before/after using `nansum`.

### 1.3 NaN/gap handling

None explicitly. NaN values in `Event_mm` pass through unchanged unless their timestamp gap flags them (then they become 0, silently destroying the gap marker). NaN in `Event_Date` would poison `diff` comparisons (`NaN <= MinT` is false → never flagged).

### 1.4 Dependencies

None (no iMHEA calls). MATLAB: `diff`, `nansum`, `fprintf`.

### 1.5 Edge cases & quirks

- If `Event_Date` is a `datetime` array, `diff` returns `duration` and `duration <= MinT` (numeric) **errors** in modern MATLAB. The function effectively requires numeric datenum input.
- Empty input: `diff([])=[]`, prepending gives a 1-element vector vs 0-element `Event_mm` — `NewEvent_mm(EventDiff)` with logical index longer than the array errors. Empty input is not supported.
- Volume is **not conserved**: flagged tips are zeroed, not merged into a neighbour (contrast with `MergeEvents` inside AggregationCS/LI, which conserves volume). This is intentional — these are considered spurious repetitions.

### 1.6 Suspected bugs / inefficiencies

- SUSPECTED (doc bug): help text output list doesn't match the real signature (see 1.1).
- None functional; fully vectorised.

### 1.7 Python notes

```python
dt = np.diff(dates_seconds, prepend=np.inf)   # seconds
p_out = np.where(dt <= 1.1, 0.0, p)
```
One-liner with `pandas.Series.diff().dt.total_seconds()` if timestamps are `DatetimeIndex`.

---

## 2. `iMHEA_Voids.m`

### 2.1 Signature

```matlab
function [Voids,NoVoids] = iMHEA_Voids(Date,Data,varargin)
```

| Arg | Direction | Meaning |
|---|---|---|
| `Date` | in | Timestamps (datenum numeric or datetime; converted by `datenum()` at line 22), sorted ascending |
| `Data` | in | Values (P in mm or Q in l/s etc.); **NaN marks a gap sample** |
| `varargin{1}` (flag1) | in, optional | If present (`nargin >= 3`) print the interval inventory to console |
| `varargin{2}` (flag2) | in, optional | If present (`nargin >= 4`) plot the data/voids inventory figure |
| `Voids` | out | v×2 **datetime** matrix `[start, end]` of gap intervals; `[]` if none |
| `NoVoids` | out | nv×2 **datetime** matrix `[start, end]` of valid-data intervals |

### 2.2 Algorithm

1. `k = length(Data)`; `Date = datenum(Date)` (line 22) — accepts datetime or numeric.
2. Counters `v = 1; nv = 1`; `Voids = zeros(1,1); NoVoids = zeros(1,1)` — a **sentinel row of zeros** occupies row 1 of each accumulator (a 1×1 zero that grows to n×2 on first assignment).
3. Line 27: `Date(end+1) = Date(end);` — the date vector is extended by duplicating the last timestamp so that `Date(jv+1)` is always valid.
4. Main loop (lines 32–53), for each sample `jv = 1:k`:
   - If `Data(jv)` is NaN: increment `v`, set `Voids(v,1) = Date(jv)` (void starts at the NaN sample's own timestamp) and `Voids(v,2) = Date(jv+1)` (void ends at the **next** sample's timestamp).
     Then merge with the previous void if contiguous (lines 37–41):
     ```matlab
     if Voids(v,1) == Voids(v-1,2)
         v = v - 1;
         Voids(v,2) = Voids(v+1,2);
         Voids(v+1,:) = [];
     end
     ```
     Because a void's end is defined as the next timestamp, consecutive NaNs always satisfy this equality (exact float equality of datenums — safe because both come from the same array element).
   - Else (valid sample): symmetric logic appends/merges into `NoVoids` with counter `nv`.
5. Lines 58–62: delete the sentinel first row of each matrix; decrement counters; if `v==0` set `Voids = []`.
6. Lines 63–64: convert both to `datetime(...,'ConvertFrom','datenum')`.
7. If `nargin >= 3`: print each NoVoid and Void interval with `datestr`. If `nargin >= 4`: plot horizontal bars, data at y=-0.5 (blue), voids at y=-1 (red).

### 2.3 NaN/gap handling

- A gap is **only** a NaN in `Data`. A jump in timestamps with no rows in between is *not* detected as a void — upstream code must have inserted NaN placeholder rows (the aggregation functions do this on regular grids).
- A NaN as the **last** sample yields a zero-length void `[Date(end), Date(end)]` (because of the duplicated final date).
- Consecutive NaNs are coalesced into one interval spanning first-NaN timestamp → first-valid timestamp after the run.

### 2.4 Dependencies

None (no iMHEA calls). MATLAB: `datenum`, `datetime(...,'ConvertFrom','datenum')`, `datestr`, `isnan`, plotting (`plot`, `datetick`, `legend`).

### 2.5 Edge cases & quirks

- Returns **datetime** even when input was datenum; every caller in this group relies on that (they compare `NewDate` datetime vectors against `Voids` datetimes).
- All-NaN input: `nv` stays 0 after sentinel removal; `NoVoids` becomes empty but is **not** reset to `[]` the way `Voids` is (asymmetric guard at line 60–62). `datetime` of the empty numeric is empty, so it usually works out.
- Empty `Data`: loop is skipped, sentinel deletion leaves empties; `Date(end)` at line 27 **errors on empty Date**.
- Assumes strictly increasing dates. Duplicate timestamps make merging behave oddly (equality test may merge non-adjacent intervals) but do not crash.
- The zero sentinel means the first real interval's merge test compares against `0` (year 0000) — never equal to a real datenum, so safe.

### 2.6 Suspected bugs / inefficiencies

- SUSPECTED inefficiency: growing `Voids`/`NoVoids` element-by-element AND deleting rows (`Voids(v+1,:) = []`) inside a per-sample loop is **O(n²)** on long NaN-y series (every merge reallocates the matrix). At 5-min resolution over years this is millions of iterations. Vectorisable with a NaN-run-length encoding.
- SUSPECTED (minor asymmetry): missing `if nv==0, NoVoids = []` guard (line 60 only guards `Voids`).

### 2.7 Python notes

Vectorise with a boolean mask: `isna = data.isna()`; find run starts/ends via `np.diff(isna.astype(int))`; void start = timestamp of first NaN in run, void end = timestamp of the sample after the run (or the last timestamp if the run reaches the end). Return a DataFrame with `start`,`end` columns.

---

## 3. `iMHEA_MonitoringGaps.m`

### 3.1 Signature

```matlab
function [dates,c] = iMHEA_MonitoringGaps(Data,varargin)
```

| Arg | Direction | Meaning |
|---|---|---|
| `Data` | in | Table or matrix `[Date, P1, Q1, P2, Q2]`; column 1 = datenum date |
| `varargin{1}` = `i` | in, optional | Column index whose gaps are measured. **Default 2** (lines 24–28) |
| `varargin{2}` = `'Pair'` | in, optional | If the string `'Pair'`, also compute flow/rain overlap of a catchment pair |
| `dates` | out | char string `'dd/mm/yyyy - dd/mm/yyyy'` monitoring period (help text calls it `Cdates`) |
| `c` | out | Percentage of data gaps in column `i`; in `'Pair'` mode instead a 1×2 vector `[flow-overlap %, flow&rain-overlap %]` |

### 3.2 Algorithm

1. `i = varargin{1}` if `nargin > 1` else `i = 2`.
2. Lines 31–39: whether table or matrix, compute `a = min(datetime(dates,'ConvertFrom','datenum'))`, `b = max(...)`, and call `[Voids,~] = iMHEA_Voids(dates, Data(:,i))`. Table access uses `Data{:,1}` / `Data{:,i}` brace indexing.
3. Line 41:
   ```matlab
   c = 100*sum(diff(Voids'))/(b-a);
   ```
   `Voids` is v×2 datetime; transposing and diffing gives one `duration` per void (`end-start`); sum = total void time; dividing duration/duration yields a plain double: **percentage of the monitoring span that is gap**.
4. `'Pair'` mode (lines 44–58), matrix indexing only:
   - `a1/a2` = index of first non-NaN in columns 3 and 5 (Q1, Q2); `b1/b2` = last non-NaN.
   - Overlap window: `a = max(Data(a1,1),Data(a2,1))`, `b = min(Data(b1,1),Data(b2,1))` (datenum doubles now, not datetimes — used only for the string).
   - `total = length(Data)` (row count, assuming rows > 5 columns).
   - Delete all rows where Q1 or Q2 is NaN; `c(1) = 100*length(Data)/total` = % of *all* rows where **both flows** exist.
   - Then also delete rows where P1 (col 2) or P2 (col 4) is NaN; `c(2) = 100*length(Data)/total` = % of rows where **both flows and both rains** exist.
5. Line 60: `dates = [datestr(a,'dd/mm/yyyy'),' - ',datestr(b,'dd/mm/yyyy')];`

### 3.3 NaN/gap handling

Delegated to `iMHEA_Voids` for the single-column percentage; in Pair mode NaN rows are deleted directly.

### 3.4 Dependencies

- iMHEA: `iMHEA_Voids`.
- MATLAB: `istable`, table brace indexing, `datetime`, `datestr`, `find(...,1,'first'/'last')`, `length`.

### 3.5 Edge cases & quirks

- If `Voids` is empty, `sum(diff([]))` is 0 → `c = 0`. Fine.
- `a`,`b` in the default path are datetimes; in the Pair path they are datenum doubles — `datestr` accepts both, so line 60 works either way.
- In Pair mode the scalar gap percentage from step 3 is **overwritten** by `c(1)`; both semantics share one output name.

### 3.6 Suspected bugs / inefficiencies

- SUSPECTED BUG: the `'Pair'` branch always uses **matrix** indexing (`Data(:,3)`, `Data(a1,1)`, `Data(isnan(Data(:,3)),:) = []`). If `Data` is a table (explicitly supported at lines 31–34), this branch errors or misbehaves (`isnan` on a table is invalid). Pair mode is matrix-only despite the help text.
- SUSPECTED fragility: `total = length(Data)` returns `max(size(Data))`; for a matrix with < 6 rows this would be the column count. Should be `size(Data,1)`.
- SUSPECTED (minor): Pair-mode overlap percentages are computed over the whole record (`total` rows) rather than over the overlap window `[a,b]` that the function itself computes — the printed period and the percentage denominators are inconsistent.

### 3.7 Python notes

`gap_pct = voids['dur'].sum() / (t.max() - t.min()) * 100`; pair overlap: `df[['Q1','Q2']].notna().all(axis=1).mean()*100` and `df[['P1','Q1','P2','Q2']].notna().all(axis=1).mean()*100`.

---

## 4. `iMHEA_FillGaps.m`

### 4.1 Signature

```matlab
function [NewDate1,NewP1,NewDate2,NewP2] = iMHEA_FillGaps(Date1,P1,Date2,P2,cutend,varargin)
```

| Arg | Direction | Meaning |
|---|---|---|
| `Date1`,`Date2` | in | Timestamps of two rain gauges, ideally at the same regular resolution |
| `P1`,`P2` | in | Precipitation series [mm], NaN = gap |
| `cutend` | in, optional | If true, do not fill beyond the earlier of the two series' last valid data. **Default `false`** (`nargin < 5 || isempty(cutend)`, lines 25–28) |
| `varargin{1}` (flag) | in, optional | If present (`nargin >= 6`), plot regression + before/after time series |
| `NewDate1`,`NewDate2` | out | Identical datetime vectors on the unified grid |
| `NewP1`,`NewP2` | out | Gap-filled precipitation [mm] |

**Single-output mode**: if `nargout == 1`, `NewDate1 = [NewDate/nd, NewP1, NewP2]` — a matrix `[datenum, P1, P2]` (lines 100–101, 132–134, 198–200).

### 4.2 Algorithm

1. **Resolution harmonisation** (lines 31–45):
   ```matlab
   scale1 = diff(datenum(Date1))*1440;   % minutes
   scale2 = diff(datenum(Date2))*1440;
   ```
   Compare `nanmedian(scale1)` vs `nanmedian(scale2)`. If either median is strictly larger, set `scale = round(nanmedian(coarser))` and re-aggregate **both** series with `iMHEA_Aggregation(Date,P,scale)`. If equal, `scale = round(nanmedian(scale1))` and no aggregation.
2. **Void inventories** printed for both series: `iMHEA_Voids(Date1,P1,1)` (lines 50, 52).
3. **Unified integer grid** (lines 56–68):
   ```matlab
   nd = 1440/scale;                      % intervals per day
   Date1 = round(nd*datenum(Date1));     % integer interval indices
   Date2 = round(nd*datenum(Date2));
   DI = min(Date1(1),Date2(1)); DF = max(Date1(end),Date2(end));
   NewDate = (DI:DF)';
   NewP1 = nan(size(NewDate)); NewP1(ismember(NewDate,Date1)) = P1;
   NewP2 = nan(size(NewDate)); NewP2(ismember(NewDate,Date2)) = P2;
   ```
   Dates are converted to **integers** (interval counts since epoch) to avoid float-equality failures; both series are scattered onto the union grid, unmatched slots stay NaN.
4. **Optional end-cut** (lines 70–79): find last non-NaN index in each of `P1`,`P2`; `indexndate = min(Date1(indexnP1),Date2(indexnP2))`; delete all grid entries with `NewDate > indexndate` from `NewP1`, `NewP2`, `NewDate`.
5. **Overlap test** (lines 83–109): build `auxP1`,`auxP2` by deleting every position where *either* is NaN. If empty or length 1: print "no date coincidence", restore the uncut grid if `cutend`, emit outputs unfilled (dates via `datetime(NewDate/nd,'ConvertFrom','datenum')`), call `iMHEA_Plot3(...)`, and **return**.
6. **Regression on cumulative curves** (lines 113–115):
   ```matlab
   auxCumP1 = cumsum(auxP1);
   auxCumP2 = cumsum(auxP2);
   [R,M,~] = regression(auxCumP1',auxCumP2');
   ```
   `regression` is the **Deep Learning (Neural Network) Toolbox** function: linear regression of targets `auxCumP1` on outputs `auxCumP2`, returning correlation coefficient `R`, slope `M`, intercept (discarded). Note the cumulative sums are taken over the *overlap-only, concatenated* samples (double-NaN sections removed), so the curves are double-mass curves.
7. **Acceptance threshold** (line 117): fill only if `R >= 0.99`. Otherwise print "correlation is not significant ... R2 = ...", plot `plotregression`, restore uncut grid if needed, return unfilled outputs (same output logic as step 5).
8. **Gap filling** (lines 147–148):
   ```matlab
   NewP1(isnan(NewP1)) = NewP2(isnan(NewP1))/M;
   NewP2(isnan(NewP2)) = NewP1(isnan(NewP2))*M;
   ```
   Missing P1 values ← P2/M; missing P2 ← P1·M. Note: **slope only, no intercept**, applied to *interval rainfall values* (not cumulative), i.e. a proportional double-mass scaling. Line 148 runs on the already-updated `NewP1`, so positions where both were NaN stay NaN (NaN/M = NaN); a P2 gap coinciding with a *filled* P1 value would be filled from the derived value — but such positions were both-NaN, hence remain NaN. Net effect: only single-sided gaps are filled.
9. **"Restore" step when cutend** (lines 151–155):
   ```matlab
   if cutend
       NewP1(ismember(NewDate,Date1)) = P1;
       NewP2(ismember(NewDate,Date2)) = P2;
   end
   ```
   Intended to restore the trimmed tails; see bugs below.
10. **Outputs** (lines 159–162): all dates back to datetime via `/nd` + `ConvertFrom','datenum'`. Prints `nansum` volumes before/after. With flag: plot regression of the filled overlap and before/after subplots. With `nargout==1`: matrix output as above.

### 4.3 NaN/gap handling

- NaN = gap on the unified grid; grid slots not covered by either input become NaN.
- Fill is proportional (slope of double-mass regression). Both-sided gaps remain NaN.
- `nanmedian` for resolutions and `nansum` for reporting.

### 4.4 Dependencies

- iMHEA: `iMHEA_Aggregation`, `iMHEA_Voids`, `iMHEA_Plot3` (plot only).
- MATLAB toolboxes: `regression` and `plotregression` (**Deep Learning Toolbox**), `nanmedian`, `nansum`; core `ismember`, `cumsum`, `datenum`, `datetime`, `round`, `find(...,1,'last')`.

### 4.5 Edge cases & quirks

- `ismember(NewDate,Date1)` requires `Date1` (rounded integer) to have **no duplicates** and be a subset of `DI:DF`; a duplicate rounded timestamp makes the mask have fewer `true`s than `numel(P1)` → assignment dimension error.
- If both series are irregular but with equal medians, no aggregation happens and the integer rounding may collapse/misalign samples silently.
- The message at line 118 prints `R` labelled as "R2" — it is the correlation coefficient, not R².
- In the aggregated branch, `iMHEA_Aggregation` returns datetime dates; subsequent `datenum()` handles both types.

### 4.6 Suspected bugs / inefficiencies

- SUSPECTED BUG (serious, `cutend=true` path): step 9 re-assigns the ORIGINAL `P1` (which contains NaNs) back onto the grid, **undoing the gap filling at every original timestamp** — the NaNs just filled at line 147 are overwritten with NaN again. The section title says "RESTORE THE DATA AND THE END OF THE VECTORS", suggesting the intent was to restore only trimmed tail values, but it restores everything including gaps.
- SUSPECTED BUG (crash, `cutend=true`): after the cut (lines 76–78) `NewDate` no longer contains the tail of the longer series, so at line 153 `ismember(NewDate,Date1)` can have fewer matches than `numel(P1)` → "Unable to perform assignment" runtime error whenever one gauge extends beyond the common last-valid date. The restore lines also don't re-extend `NewDate` to `(DI:DF)` the way the early-return branches (lines 92, 124) do.
- SUSPECTED design wart: filling values with `P2/M` uses the slope of a regression **with an intercept** fitted on cumulative curves; ignoring the intercept is fine for slopes of double-mass curves through the origin, but nothing forces the fit through the origin.
- Inefficiency: `ismember` over long integer vectors is O(n log n) — fine.

### 4.7 Python notes

Reindex both series onto `pd.date_range(union_start, union_end, freq=f'{scale}min')`; overlap mask `m = s1.notna() & s2.notna()`; fit `M = np.polyfit(s1[m].cumsum(), s2[m].cumsum(), 1)[0]` and `R = np.corrcoef(...)`; then `s1.fillna(s2/M)`, `s2.fillna(s1*M)`. Reproduce (or deliberately fix) the cutend restore bug.

---

## 5. `iMHEA_Aggregation.m`

### 5.1 Signature

```matlab
function [NewDate,NewP,CumP,VoidP,MaxP] = iMHEA_Aggregation(Date,P,scale,varargin)
```

| Arg | Direction | Meaning |
|---|---|---|
| `Date` | in | Tip timestamps (datenum or datetime), sorted ascending | 
| `P` | in | Precipitation per tip [mm], NaN = gap sample |
| `scale` | in | Aggregation interval [minutes] |
| `varargin{1}` (flag) | in, optional | If present (`nargin > 3`): print void inventory and plot via iMHEA_Plot2/3 |
| `NewDate` | out | datetime vector, regular grid at `scale` min, right-labelled |
| `NewP` | out | Aggregated precipitation per interval [mm]; NaN inside voids |
| `CumP` | out | `cumsum(NewP)` (computed before voids re-inserted); NaN inside voids |
| `VoidP` | out | Complement series: the aggregated values **only at void positions** (0s there), NaN elsewhere — used for plotting gaps |
| `MaxP` | out | scalar `nanmax(NewP)` = max intensity per interval [mm per `scale` min] |

**Single-output mode** (lines 100–102): `NewDate = [datenum(NewDate), NewP, CumP, VoidP]`.

### 5.2 Algorithm

1. Line 26: `Date = Date - 0.25/86400;` — shift all timestamps **0.25 s earlier** to keep on-the-minute stamps inside the interval that ends at that minute despite datenum rounding.
2. Gap inventory: `[Voids] = iMHEA_Voids(Date,P,...)` (with print flag if `nargin>3`), lines 27–33. `Voids` is datetime.
3. Line 35: `P(isnan(P)) = 0;` — gaps temporarily zeroed. Line 37: `Date = datenum(Date)`.
4. **Grid construction** (lines 41–46):
   ```matlab
   nd = 1440/scale;
   DI = ceil(min(Date)*nd);  DF = ceil(max(Date)*nd);
   NewDate = (DI:DF)';       n = length(NewDate);
   NewP = zeros(size(NewDate));
   ```
   Integer interval indices; interval `i` covers `((i-1)/nd, i/nd]` days.
5. Lines 48–50: delete all zero tips (`Date(P==0)=[]; P(P==0)=[];`) so only volume-bearing tips are scanned; `k = length(P)`.
6. **Two-pointer aggregation** (lines 52–64):
   ```matlab
   if nd*(Date(1)) == NewDate(1)
       j = 2; NewP(1) = P(1);
   else
       j = 1;
   end
   for i = j:n
       while j<=k && nd*Date(j)<=NewDate(i)
           NewP(i) = NewP(i) + P(j);
           j = j+1;
       end
   end
   ```
   `j` walks the tips once (overall O(n+k)); every tip with `date*nd <= i` not yet consumed is added to interval `i`. The commented-out lower-bound test (`&& nd*Date(j)>NewDate(i-1)`) is unnecessary because `j` is monotone. The special case assigns a tip landing exactly on the first boundary `DI` to interval 1 and starts the sweep at `i = 2` (note the loop start `for i = j:n` — see quirks).
7. Lines 66–70 — **dead code** (see bugs):
   ```matlab
   for i = 2:(n-1)
       if isnan(NewP(i))
           NewP(i) = 0;
       end
   end
   ```
8. **Post-processing** (lines 73–88):
   - `CumP = cumsum(NewP)` (over zero-filled gaps — cumulative continues flat through voids).
   - `NewDate = datetime(NewDate/nd,'ConvertFrom','datenum')`.
   - Re-insert gaps: for each void row `i`,
     ```matlab
     CumP(NewDate>Voids(i,1) & NewDate<Voids(i,2)) = NaN;
     NewP(NewDate>Voids(i,1) & NewDate<Voids(i,2)) = NaN;
     ```
     **strict** inequalities — grid points exactly on a void boundary stay numeric.
   - `VoidP = NewP` (captured *before* NaN-insertion at line 77); then `VoidP(~isnan(NewP)) = NaN;` so VoidP holds values (zeros) only where NewP is NaN.
   - Last-row correction (lines 84–88): if `NewP(end)==0 && isnan(NewP(end-1))`, the final point is also declared void (`VoidP(end)=NewP(end); NewP(end)=NaN; CumP(end)=NaN;`) — the trailing grid point created by `ceil` shouldn't pretend to be a valid 0 after a gap.
   - `MaxP = nanmax(NewP)`.
9. Optional plots via `iMHEA_Plot2(Date,P,NewDate,NewP,NewDate,VoidP)` and `iMHEA_Plot3(NewDate,NewP,VoidP,CumP)`.

### 5.3 NaN/gap handling

- Input NaNs → temporarily 0 for binning, then every grid point **strictly inside** a `iMHEA_Voids` interval is set back to NaN in `NewP` and `CumP`.
- Because void ends coincide with the first valid timestamp, the interval containing the first valid sample stays numeric; boundary bins of a gap are counted as data (they may contain partial-interval zeros).

### 5.4 Dependencies

- iMHEA: `iMHEA_Voids`, `iMHEA_Plot2` and `iMHEA_Plot3` (plot only).
- MATLAB: `datenum`, `datetime`, `cumsum`, `nanmax`, `ceil`.

### 5.5 Edge cases & quirks

- Right-labelling: output timestamp `t` holds rain from `(t-scale, t]` minutes.
- Line 52 uses post-deletion `Date(1)`/`P(1)` (first nonzero tip). If **all** tips are zero/NaN, `Date` becomes empty and `Date(1)` **errors**.
- Float comparison `nd*Date(j) <= NewDate(i)` is the reason for the 0.25 s pre-shift; exact equality at line 52 similarly relies on it. When translating, bin with integer arithmetic (e.g. `ceil(round(t_sec/60/scale - eps))`) or replicate the shift.
- `for i = j:n` with `j=2` skips `i=1`, but interval 1 was already given `P(1)`; any *further* tips that also belong in interval 1 would then be swept into interval 2 by the while condition (`<= NewDate(2)`), because the lower bound is commented out. Only matters with duplicate timestamps at the exact grid boundary.
- `CumP` treats voids as zero rain before NaN-masking, so cumulative totals after a gap are lower bounds.

### 5.6 Suspected bugs / inefficiencies

- SUSPECTED dead code (lines 66–70): `NewP` is initialised with `zeros` and only ever added to — it can never be NaN at this point, so the "fill single missing value" loop does nothing. (The analogous loop in `iMHEA_Average` *is* live because of 0/0.)
- SUSPECTED misbinning with duplicate boundary tips (see quirk above) — benign in practice.
- Void re-insertion loop over voids × full-vector logical comparisons is O(v·n); acceptable, vectorisable with interval joins.

### 5.7 Python notes

`s = pd.Series(p, index=t - pd.Timedelta('0.25s')); out = s.fillna(0).resample(f'{scale}min', label='right', closed='right').sum()`, then mask with the voids table (`start < idx < end`). `CumP = out.fillna(0).cumsum().mask(out.isna())`.

---

## 6. `iMHEA_AggregationCS.m`

### 6.1 Signature

```matlab
function [NewDate,NewP,CumP,Single] = iMHEA_AggregationCS(Event_Date,Event_mm,scale,bucket,mintip,halves,varargin)
```

| Arg | Direction | Meaning | Default (via `nargin < k || isempty(...)`) |
|---|---|---|---|
| `Event_Date` | in | Tip timestamps (date format; later `datenum`ed) | required |
| `Event_mm` | in | mm per tip; NaN = gap marker | `0.2*ones(size(Event_Date))` (lines 49–52) |
| `scale` | in | Output aggregation interval [min] | `1` (lines 53–56) |
| `bucket` | in | Bucket volume [mm/tip] | `0.2` (lines 57–60) |
| `mintip` | in | If true: pre-aggregate tips to 1-min before interpolation; else merge fast tips | `true` (lines 61–64) |
| `halves` | in | If truthy: add estimated zero-rate event endpoints (Sadler & Busscher 1989 half-tip method) | `true` (lines 65–68) |
| `varargin{1}` (flag1) | in, optional | If present (`nargin > 6`): plot inventory + per-event diagnostic plots |
| `NewDate` | out | datetime grid at `scale` min |
| `NewP` | out | Interpolated aggregated precipitation [mm]; NaN in voids |
| `CumP` | out | cumsum of NewP; NaN in voids |
| `Single` | out | Portion of NewP that came from single-tip events distributed at 3 mm/h; NaN in voids |

**Single-output mode** (lines 363–365): `NewDate = [datenum(NewDate), NewP, CumP, Single]`.

### 6.2 Constants (lines 28–39)

```matlab
Minint = 0.2/1;                 % 0.2 mm/h  minimum intensity separating events [Padron et al 2015]
Maxint = 127;                   % 127 mm/h  maximum plausible intensity [Onset 2013]
Meanint = 3;                    % 3 mm/h    rate to spread single tips [Wang et al 2008]
Lowint = min(0.1/60,Minint/120);% mm/min threshold; both terms = 1/600 ≈ 0.0016667 mm/min
Event_Date = Event_Date - 0.25/86400;   % 0.25 s shift, as in iMHEA_Aggregation
```
Derived (lines 99–103), in **days**:
```matlab
nd = 1440;
MaxT = 60*(1/nd)*bucket/Minint;   % = bucket/Minint hours; bucket=0.2 → 1 h = 1/24 day
MinT = 60*(1/nd)*bucket/Maxint;   % bucket=0.2 → 0.2/127 h ≈ 5.67 s
```
`MaxT` = inter-tip time above which tips belong to different events; `MinT` = inter-tip time below which tips are merged.

### 6.3 Algorithm

1. **Defaults & gap inventory.** `Voids = iMHEA_Voids(Event_Date,Event_mm,1)` (print; plus plot with the flag, lines 74–85).
2. **Numeric conversion & cleaning** (lines 89–96): `Event_Date = datenum(Event_Date)`; working copies `NewEvent_Date/NewEvent_mm`; NaN→0; delete all zero tips.
3. **Pre-conditioning** (lines 105–121):
   - If `mintip`: `AggregateEvents` — bin tips onto a 1-min grid by tip counting (same right-labelled two-pointer sweep as `iMHEA_Aggregation`, subfunction lines 372–403; grid `DI = floor(min(Date))*1440 : DF = ceil(max(Date))*1440`, zero bins then removed). This caps intensities at 1-min resolution.
   - Else: `MergeEvents(...,MinT)` (subfunction lines 405–439) — repeatedly merges any tip whose gap to the previous tip ≤ `MinT` into the **following** timestamp (`NewEvent_mm(j) = NewEvent_mm(j)+NewEvent_mm(j-1)` then delete `j-1`), looping `while any(EventDiff)` with the *stale* flag vector re-evaluated after each full pass. Volume-conserving (contrast `iMHEA_Depure`).
   - Line 113–114: prepend a **sentinel tip** `(Event_Date(1)-MaxT, 0 mm)` so `DivideEvents` can index `i-2` safely near the start.
   - `DivideEvents(...,MaxT)` (subfunction lines 441–472): for tips whose preceding gap `d` satisfies `MaxT/2 < d <= MaxT` (i.e. `HalfEventDiff(i-1) && ~EventDiff(i-1)`) **and** an adjacent gap is also short (`~EventDiff(i) || ~EventDiff(i-2)`), split tip `i` into two half-tips: one at `t0 = Event_Date(i) - d/2` (gap midpoint) and one at the original time (lines 459–465). This spreads borderline-slow tips so they stay inside one event.
   - Lines 120–121: remove the sentinel.
4. **Event segmentation** (lines 135–148):
   ```matlab
   NewEventDiff = diff(NewEvent_Date) > MaxT;  NewEventDiff = cat(1,true,NewEventDiff);
   indx = find(NewEventDiff);            % event start pointers
   n = diff(indx)-1;  n(end+1) = length(NewEvent_Date) - indx(end);
   ```
   `n(i)` = number of tips in event i **minus 1** (0 ⇒ single-tip event). Durations `D` computed for reporting (`*1440` → minutes; note `D(end+1)` at line 144 is **not** multiplied by 1440 — reporting-only bug, see 6.6).
5. **1-min master grid** (lines 153–159): `DI = floor(min(Event_Date))*nd; DF = ceil(max(Event_Date))*nd; NewDate_1min = (DI:DF)';` with accumulators `CumP_1min`, `Single_1min` (zeros) and per-event `biased`, `bEvent`.
6. **Per-event loop** (`for i = 1:length(n)`, lines 162–314), inside a `waitbar`:
   - **Multi-tip events (`n(i) >= 1`)**:
     a. `x` = tip times in **seconds** relative to the event's first tip (`*86400`, line 168); `y = cumsum(tips)` (line 170).
     b. If `halves` (always true — see 6.6), estimate event start/end paddings (lines 172–185):
        ```matlab
        x0 = bucket*(x(2)-x(1))/(y(2)-y(1))-0.5;   % s before 1st tip (time to fill one bucket at initial rate, −0.5 s)
        xf = bucket*(x(end)-x(end-1))/(y(end)-y(end-1));  % s after last tip
        x = x + x0;  y = y - bucket/2;
        y = cat(1,0,y,y(end)+bucket/2);  x = cat(1,0,x,x(end)+xf);
        x = round(x);
        ```
        Each tip contributes half a bucket before/after its stamp; endpoints get cumulative 0 and total. Window in 1-min units: `DI = max(DI_global, floor((t_start - x0/86400)*1440))`, `DF = ceil((t_lasttip + xf/86400)*1440)`; `x1m = round(60*((DI:DF)' - t_start*1440 + x0/60))` = grid seconds relative to event start (lines 182–185).
        Without halves: `DI = max(DI, floor((t_start+0.5/86400)*1440))`, `DF = ceil(t_last*1440)`, no padding (lines 187–192).
     c. **Spline fit** (lines 194–204): with halves, `pp = spline(x,[0;y;0])` — a **clamped cubic spline with zero first derivatives at both ends** (Sadler & Busscher 1989); without halves, `pp = csape(x,y,'second')` — zero second derivatives (natural spline, Wang et al 2008; requires Curve Fitting Toolbox). Evaluate `y1m = fnval(pp,x1m)`; with halves force `y1m(1)=0; y1m(end)=y1m(end-1);`. 1-min rates `r1m = [y1m(1);diff(y1m)]` [mm/min].
     d. **Bias/negativity correction** — nested `intCorrection(r1m,y,Lowint,halves,x,x1m)` (lines 474–509):
        - `biased = abs(y(end)-sum(r1m(r1m>0)))/y(end)` — relative volume error counting only positive rates.
        - If `biased > 0.25`: **abandon the spline**, use `y2m = interp1(x,y,x1m,'linear',0)` (linear interp, 0 outside domain), re-apply border zeros, recompute rate and bias; flag `bEvent = 1`.
        - Iterative fix, at most **11 passes** (`while iter<=10 && (abs(y(end)-sum(r2m))>Lowint || any(round(r2m(r2m~=0),8) < Lowint))`, lines 492–499):
          ```matlab
          r2m(r2m < 0) = 0;
          r2m(r2m > 0 & r2m < Lowint) = Lowint;
          r2m(r2m >= Lowint) = r2m(r2m >= Lowint)*(y(end)-sum(r2m(r2m < Lowint)))/(sum(r2m)-sum(r2m(r2m < Lowint)));
          ```
          i.e. clamp negatives to 0, raise tiny positives to `Lowint`, rescale the rest so the event total is conserved.
        - Rebuild `y2m = cumsum(r2m)`; pin `y2m(end) = y(end)` (and `y2m(end-1) = y(end)` if halves); recompute `r2m = [y2m(1);diff(y2m)]`.
     e. **Assembly** (lines 214–216): add `y2m` onto `CumP_1min` over `[DI,DF]` and hold the value at `DF` constant for all later grid points:
        ```matlab
        CumP_1min(NewDate_1min>=DI & NewDate_1min<=DF) = CumP_1min(...) + y2m;
        CumP_1min(NewDate_1min>DF) = CumP_1min(NewDate_1min==DF);
        ```
        Events are chronological, so the running tail always carries the cumulative total.
     f. Diagnostic plotting block (lines 218–278) also runs when `any(isnan(r2m))` — it recomputes linear (`y3m/r4m`) and tip-counting (`r5m/y5m`) references purely for the figure; no effect on outputs.
   - **Single-tip events (`n(i) < 1`)** (lines 279–312): spread the tip backwards at `Meanint = 3 mm/h`:
     ```matlab
     x0 = NewEvent_mm(indx(i))/Meanint*60-1;    % duration in minutes (0.2 mm → 3 min)
     xf = NewEvent_Date(indx(i))*nd;            % tip time in minutes
     x  = (xf-x0*nd/1440:xf)';                  % nd/1440 = 1 → xf-x0 : xf, one point per minute
     y  = NewEvent_mm(indx(i))*ones(size(x))/(x0+1);   % equal mm per minute
     ```
     Then tip-count `y` onto the 1-min grid `x1m = (floor(xf-x0):ceil(xf))'` with the standard two-pointer sweep, cumulative `y1m = cumsum(r1m)`, and add to **both** `CumP_1min` and `Single_1min` with the same window+tail-hold assembly (lines 304–311).
   - Report max bias and number of `bEvent`s (lines 316–317).
7. **Rescale to `scale` minutes** (lines 324–348):
   ```matlab
   NewDate = (NewDate_1min(1):scale:NewDate_1min(end))';
   NewP   = [bucket/2; CumP_1min(scale+1:scale:end) - CumP_1min(1:scale:end-scale)];   % (halves branch)
   Single = [bucket/2; Single_1min(scale+1:scale:end) - Single_1min(1:scale:end-scale)];
   ```
   (non-halves branch uses `0` instead of `bucket/2` as the first element). `CumP = cumsum(NewP)`. Kill float dust: `NewP(round(NewP,8)==0) = 0` (same for `Single`).
   Cut to the actual record: `DI = ceil(min(Event_Date)*ndv)*scale; DF = ceil(max(Event_Date)*ndv)*scale;` with `ndv = 1440/scale` (lines 342–344; note **ceil** here vs **floor** in the LI version) and drop grid points outside `[DI,DF]`. `NewDate = NewDate/1440` → datenum → `datetime`.
8. **Re-insert voids** (lines 358–362): strict-inequality NaN masking of `CumP`, `NewP`, `Single` inside each `Voids` interval, exactly as `iMHEA_Aggregation`.
9. Print total volume before/after (`nansum`).

### 6.4 NaN/gap handling

Input NaNs define voids (step 1), are zeroed and dropped for interpolation, and the void windows are re-NaNed on the output grid (strict inequalities). Everything between events is genuine 0 rain unless inside a void.

### 6.5 Dependencies

- iMHEA: `iMHEA_Voids`, `iMHEA_Depure` (recommended in comments only, line 71 — not called).
- MATLAB: `spline` (clamped-end syntax), `csape`/`fnval` (**Curve Fitting Toolbox**), `interp1('linear',0)`, `cumsum`, `datenum/datetime`, `waitbar`, `nansum/nanmax`, `round(x,8)`.

### 6.6 Edge cases & quirks / suspected bugs

- QUIRK: every halves test is written `if halves ~= false || halves ~= 0` (lines 171, 196, 205, 230, 326, 483, 504). For scalar logical/0/1 this reduces to "halves is truthy" (both operands false only when halves is false/0), so it works — but it reads like a De Morgan mistake; translate as `if halves:`.
- SUSPECTED BUG (acknowledged in-source, line 457 comment): `DivideEvents` can index `EventDiff(0)` when `i==2` and the short-circuit doesn't save it (`HalfEventDiff(1) && ~EventDiff(1) && EventDiff(2)` true ⇒ evaluates `EventDiff(0)` → crash). The caller mitigates by prepending the sentinel tip at `t1−MaxT` (line 113), which makes `EventDiff(1)` true and the whole condition false at i=2 — but `MergeEvents`-path inputs and the LI variant (sentinel at `t1`, no −MaxT) are less protected.
- SUSPECTED BUG (cosmetic): `D(end+1) = NewEvent_Date(end) - NewEvent_Date(indx(end));` (line 144) — the last event's duration is left in **days** while all others were `*1440` minutes; only affects the printed mean duration.
- SUSPECTED BUG: `MergeEvents` inner `for i = 2:n` keeps using the **stale** `EventDiff` while deleting elements, so indices drift within a pass; the outer `while any(EventDiff)` re-pass makes it converge, but merge pairing within a pass can differ from a strict left-to-right merge. Also its "Number of tips removed: i-j" print (line 436) uses loop leftovers and is meaningless if the while body never runs (`i-j = 0` from the pre-initialised `i=0;j=0`).
- SUSPECTED design oddity: first output element hardcoded `NewP(1) = bucket/2` (line 328) regardless of whether any event touches the first interval — injects a spurious half-tip at the very first timestamp of the record when `halves` is true. Same for `Single(1)`.
- SUSPECTED: `x = round(x)` (line 180) rounds tip times to whole seconds after shifting; with sub-second tip spacing two x's can collide → `spline` errors on duplicate abscissae. `MinT`/1-min pre-aggregation makes this unlikely but not impossible.
- SUSPECTED: the per-event plotting condition `if nargin > 6 || any(isnan(r2m))` (line 218) opens figures inside a batch loop when NaNs slip through — side effect in a computation function.
- `x0` can be negative if the first inter-tip interval is shorter than the time to fill a bucket... actually `x0 = bucket*(x(2)-x(1))/(y(2)-y(1)) - 0.5` ≥ −0.5 only if the first gap ≥ 0; with 1-min pre-aggregation `x(2)-x(1) ≥ 60 s` and `y(2)-y(1)` can exceed bucket, so `x0` can be small; `x+x0` then `cat(1,0,x,…)` still needs `x(1)=x0 ≥ 0`... if `x0 < 0` the prepended 0 breaks monotonicity → `spline` error. With bucket-sized increments this requires `(y(2)-y(1))/bucket > (x(2)-x(1))/0.5s`, i.e. >1 bucket per half-second — prevented by depuration/merging, but worth an assertion in Python.
- Waitbar/figure side effects (`waitbar`, `close(h)`, `figure(199)`) should be dropped or made optional in translation.
- Events are assumed non-overlapping after padding; if an event's `x0` padding reaches back past the previous event's `DF`, the `+ y2m` add is still correct (additive) but the tail-hold line then overwrites part of the previous event's window with a constant — SUSPECTED subtle mis-assembly in pathological cases.

### 6.7 Python notes

Per-event: `scipy.interpolate.CubicSpline(x, y_ext, bc_type='clamped')` for the halves case (zero end-slopes) and `bc_type='natural'` for the `csape(...,'second')` case; `np.interp` for the linear fallback; then the same clamp-and-rescale loop. Assemble on an `np.arange` 1-min grid and downsample by slicing `cum[::scale]` differences.

---

## 7. `iMHEA_AggregationLI.m`

Structurally a **clone of `iMHEA_AggregationCS`** with linear interpolation instead of splines. Same signature (returns `[NewDate,NewP,CumP,Single]`), same defaults (`Event_mm→0.2*ones`, `scale→1`, `bucket→0.2`, `mintip→true`, `halves→true`), same constants (`Minint=0.2`, `Maxint=127`, `Meanint=3`, `Lowint=min(0.1/60,0.2/120)`), same −0.25 s shift, same subfunctions `AggregateEvents` / `MergeEvents` / `DivideEvents` (byte-for-byte equivalent logic), same event segmentation, same single-tip handling, same rescaling and void re-insertion. **Document only the differences:**

1. **Interpolator** (lines 194–200): instead of a spline,
   ```matlab
   y1m = interp1(x,y,x1m,'linear',0);        % linear, extrapolation value 0
   if halves ... y1m(1) = 0; y1m(end) = y1m(end-1); end
   r1m = [y1m(1);diff(y1m)];
   ```
   No Curve Fitting Toolbox dependency; no `spline`/`csape`/`fnval`.
2. **`intCorrection` signature differs** (line 453): `intCorrection(r1m,Total,Lowint,halves)` takes the scalar event total (`y(end)`) rather than `(y,x,x1m)`, because there is **no linear-fallback branch** — if `biased > 0.25` it merely flags `bEvent = 1` (lines 458–460) and proceeds with the same clamp/rescale loop (lines 461–469, identical formulas with `Total` in place of `y(end)`), then pins `y2m(end) = Total` (+`y2m(end-1)` if halves) and recomputes rates. Call site line 202: `[r2m,y2m,biased(i),bEvent(i)] = intCorrection(r1m,y(end),Lowint,halves);`
3. **Sentinel tip** (line 114): prepended at `Event_Date(1)` (NOT `Event_Date(1)-MaxT` as in CS line 113). Consequence: the sentinel is only ~0 s before the first real tip, so `EventDiff(1)` in `DivideEvents` is typically **false**, and the `i==2` zero-index hazard (see 6.6) is *less* shielded here — SUSPECTED the CS version's `-MaxT` is the corrected one and LI was not updated.
4. **Final cut uses `floor`** (lines 322–323):
   ```matlab
   DI = floor(min(Event_Date)*nd)*scale;  DF = ceil(max(Event_Date)*nd)*scale;
   ```
   versus CS lines 343–344 which use `ceil` for `DI`. LI keeps one extra leading interval relative to CS — SUSPECTED unintended inconsistency; the two functions' outputs are offset by one bin at the start for identical inputs.
5. Cosmetics: figure number 197 vs 199; `AggregateEvents` prints "before/after merging" (lines 380–381) instead of "aggregation"; event-count message wording differs (line 148).
6. Diagnostic plot block (lines 209–258) computes only tip-counting reference `r5m/y5m` (no `y3m/r4m` linear duplicate, since the main path is already linear).

All quirks/bugs listed in 6.6 apply except the spline-specific ones; add items 3 and 4 above as LI-specific SUSPECTED bugs.

**Python note:** identical skeleton to CS with `np.interp` only; keep the `DI` floor/ceil discrepancy configurable or normalise it deliberately (document the choice).

---

## 8. `iMHEA_Average.m`

### 8.1 Signature

```matlab
function [NewDate,NewQ,CumQ,VoidQ,MeanQ,MaxQ,MinQ] = iMHEA_Average(Date,Q,scale,varargin)
```

| Arg | Direction | Meaning |
|---|---|---|
| `Date` | in | Timestamps (date format), sorted ascending |
| `Q` | in | Stage/discharge [l/s, m³/s or mm]; NaN = gap |
| `scale` | in | Averaging interval [min] |
| `varargin{1}` (flag) | in, optional | If present (`nargin > 3`): print void inventory and plot |
| `NewDate` | out | datetime grid at `scale` min, right-labelled |
| `NewQ` | out | **Mean** of samples per interval; NaN in voids |
| `CumQ` | out | cumsum of NewQ (gaps as 0 before masking); NaN in voids |
| `VoidQ` | out | Complement series (values only at void positions) |
| `MeanQ`,`MaxQ`,`MinQ` | out | scalars: `nanmean/nanmax/nanmin(NewQ)` |

**Single-output mode** (lines 112–114): `NewDate = [datenum(NewDate), NewQ, CumQ, VoidQ]`.

### 8.2 Algorithm

Identical skeleton to `iMHEA_Aggregation` with these differences:

1. Line 28: same `-0.25/86400` shift; voids via `iMHEA_Voids(Date,Q[,1])` (note: never passes the plot flag, unlike Aggregation).
2. NaN samples are **deleted** (lines 48–49: `Date(isnan(Q))=[]; Q(isnan(Q))=[];`) rather than zeroed — zero flows are legitimate data here, so zero-deletion is not used either.
3. Grid: `nd = 1440/scale; DI = ceil(min(Date)*nd); DF = ceil(max(Date)*nd); NewDate = (DI:DF)';` — note `min(Date)` is evaluated **before** the NaN deletion... actually line 42–43 run before lines 48–49, so DI/DF cover the full record including NaN-stamped rows.
4. **Averaging sweep** (lines 52–67): same two-pointer scan as Aggregation, but with a per-interval counter:
   ```matlab
   for i = j:n
       l = 0;
       while j<=k && nd*Date(j)<=NewDate(i)
           NewQ(i) = NewQ(i) + Q(j); j = j+1; l = l+1;
       end
       NewQ(i) = NewQ(i)/l;
   end
   ```
   An interval with no samples gives `0/0 = NaN` — this is the **intended** empty-bin marker (relies on IEEE NaN, no error in MATLAB).
   Boundary special case (lines 52–57) as in Aggregation: if the first sample lands exactly on `DI`, `NewQ(1) = Q(1)` (a plain value, not an average) and the sweep starts at `i = 2`.
5. **Single-bin interpolation** (lines 69–73):
   ```matlab
   for i = 2:(n-1)
       if isnan(NewQ(i))
           NewQ(i) = mean([NewQ(i-1),NewQ(i+1)]);
       end
   end
   ```
   Isolated empty bins get the arithmetic mean of neighbours. Because `mean` (without `'omitnan'`) of anything containing NaN is NaN, a run of ≥2 empty bins is *not* filled... except the left-to-right order means bin `i` may use an already-filled `NewQ(i-1)`: for a run of 2, the first uses (valid, NaN) → NaN, stays empty; so effectively **only runs of exactly 1** are filled. (First and last bins never filled.)
6. Line 75: `NewQ(isnan(NewQ)) = 0;` — remaining empty bins zeroed so `CumQ = cumsum(NewQ)` is computable.
7. Post-processing mirrors Aggregation (lines 78–98): datetime conversion; strict-inequality NaN re-insertion from `Voids` into `CumQ` and `NewQ`; `VoidQ` = complement; **two** boundary corrections instead of one:
   ```matlab
   if NewQ(1) == 0 && NewQ(2)~=0     % lines 89–93
       VoidQ(1)=NewQ(1); NewQ(1)=NaN; CumQ(1)=NaN;
   end
   if NewQ(end) == 0 && NewQ(end-1)~=0   % lines 94–98
       VoidQ(end)=NewQ(end); NewQ(end)=NaN; CumQ(end)=NaN;
   end
   ```
   (Heuristic: a solitary zero at either edge next to nonzero flow is assumed to be a partial/empty bin, not a real zero-flow reading.)
8. Scalars `MeanQ/MaxQ/MinQ` via `nanmean/nanmax/nanmin`; optional plots via `iMHEA_Plot2`/`iMHEA_Plot3`.

### 8.3 NaN/gap handling

Three layers: (a) input NaNs deleted before binning; (b) empty bins → NaN via 0/0, isolated ones linearly patched with the neighbour mean, remaining → 0; (c) `iMHEA_Voids` intervals re-imposed as NaN (strict inequalities), plus the two edge heuristics.

### 8.4 Dependencies

iMHEA: `iMHEA_Voids`, `iMHEA_Plot2`, `iMHEA_Plot3` (plots only). MATLAB: `datenum/datetime`, `cumsum`, `mean`, `nanmean/nanmax/nanmin`, `isnan`.

### 8.5 Edge cases & quirks

- 0/0 → NaN is load-bearing; in Python use `np.errstate` or pandas `.mean()` which naturally yields NaN for empty groups.
- If all `Q` are NaN, `Date` becomes empty and `Date(1)` at line 52 **errors** (same as Aggregation).
- The exact-boundary special case means a first sample on the grid edge is not averaged with any co-interval samples (they'd spill into bin 2 — same duplicate-boundary caveat as Aggregation §5.5).
- Edge-zero heuristic (step 7) can destroy a *real* zero-flow reading at the record edges (e.g. ephemeral streams) — behavioural, keep or document in translation.
- `CumQ` sums *averages* per interval, not volumes — it is a cumulative of mean rates, meaningful only up to a `scale` factor.

### 8.6 Suspected bugs / inefficiencies

- SUSPECTED: the neighbour-mean fill (step 5) is order-dependent (left-to-right, uses already-filled values) — harmless for single gaps but ill-defined as documented; in Python prefer an explicit "isolated NaN" mask.
- SUSPECTED inefficiency: per-sample while loop is O(n+k) (fine), but the void re-insertion loop is O(v·n) as in Aggregation.
- SUSPECTED inconsistency: unlike `iMHEA_Aggregation`, empty bins between data become 0 (then NaN only if inside a declared void). A time span with no samples **and no NaN marker rows** silently becomes zero flow, not a gap — dangerous for irregular loggers; only NaN-marked gaps survive.

### 8.7 Python notes

`s.resample(f'{scale}min', label='right', closed='right').mean()` reproduces the core (empty bins → NaN automatically); then patch isolated NaNs with `(prev+next)/2`, zero the rest for the cumulative, and re-mask voids. Skip the exact-boundary special case by binning with `closed='right'` consistently.

---

## Cross-cutting translation checklist

1. **Bin convention everywhere**: right-closed, right-labelled bins of width `scale` minutes, grid from `ceil(t_min*nd)` to `ceil(t_max*nd)` (LI uses `floor` for the lower cut — decide and document). Apply the −0.25 s shift or, better, replace with exact integer binning.
2. **Voids are NaN-marker driven**, never inferred from timestamp jumps. Preserve this or you will "discover" gaps MATLAB never saw (and vice versa: Average's silent zeros).
3. **Strict inequalities** when re-masking voids (`> start & < end`): boundary bins stay numeric.
4. `iMHEA_Voids` returns datetimes; every consumer compares datetimes. In Python, keep voids as a two-column DatetimeIndex frame.
5. Reproduce constants exactly: 1.1 s (Depure), 0.2/127/3 mm/h, `Lowint = 1/600` mm/min, 0.99 R threshold, 25% bias threshold, 11-iteration cap, `round(x,8)` dust threshold, `bucket/2` half-tips.
6. Known cross-function inconsistencies to resolve deliberately: CS vs LI lower-cut (ceil vs floor), CS vs LI sentinel (`t1−MaxT` vs `t1`), FillGaps cutend restore bug, Aggregation dead-code loop.
