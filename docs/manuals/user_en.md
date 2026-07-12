---
title: "iMHEA Data Processor — User Manual"
subtitle: "Version 1.0 · July 2026"
lang: en
---

# 1. Introduction

The iMHEA Data Processor converts raw sensor records from headwater
catchment monitoring — tipping-bucket rain gauge events and water-level or
discharge logger files — into quality-controlled rainfall and streamflow
series at high, hourly, and daily resolution, and computes 59 hydrological
and 13 climate indices describing water yield, regulation, flashiness,
frequency, duration, timing, and rainfall intensity.

The methods implement Ochoa-Tocachi et al. (2018), *High-resolution
hydrometeorological data from a network of headwater catchments in the
tropical Andes*, Scientific Data 5:180080. The software is a validated
Python translation of the original iMHEA MATLAB scripts: streamflow and
baseflow outputs reproduce the published dataset exactly, and every known
defect of the original code has been fixed (a compatibility mode can
reproduce the legacy behaviour; see section 11).

**Citing.** If you use results from this software in a publication, cite
the paper above.

# 2. Preparing your data

## 2.1 Raw file format

The software reads the standard iMHEA raw CSV layout. One file per sensor:

**Rain gauge files** (tipping-bucket events):

```
Date,Event mm,Flag
24/05/2001 00:00:01,0,I
24/05/2001 00:41:23,0.2,
03/04/2004 00:00:01,,V
```

**Water level / discharge files:**

```
Date,Level cm,Flow l/s,Flag
17/07/2012 14:00:00,8.1000,2.5582,"D,P"
```

Rules:

- Dates in `dd/mm/yyyy HH:MM:SS`, sorted ascending.
- Decimal point (`.`), comma-separated columns.
- Flags: `I` = logger launched, `D` = data downloaded, `X` = erroneous tip
  removed, `P` = anomalous intensity, `V` = data gap. A `V` row with an
  **empty value** marks the start of a gap — this is how the software
  knows data are missing rather than dry/zero.
- Encoding UTF-8 (a byte-order mark is tolerated); line endings may be
  Windows, Unix, or legacy Mac.
- Rainfall values are millimetres per tip; level in centimetres; flow in
  litres per second.

A machine-readable version of this specification is included as
`docs/DATA_FORMAT.md`.

## 2.2 What you need to know about each catchment

| Parameter | Meaning | Typical iMHEA values |
|---|---|---|
| Area | catchment area draining to the weir [km²] | 0.5 – 16 |
| Bucket | rain gauge resolution [mm per tip] | 0.1, 0.2, or 0.254 |
| Weir geometry | V-notch height *a* [m], rectangular width *b* [m] | 0.30 / site-specific |

# 3. Getting started

On launch, the start screen offers three paths:

- **Process my data** — creates an empty project to which you add your own
  catchments and files.
- **Explore the iMHEA network** — asks for the folder containing
  `iMHEA_raw/` and loads the complete 2018 network configuration
  (28 stations, 12 pairs) ready to run.
- **Open project…** — reopens a saved `.imhea` project file.

A **project** stores your catchment configurations, file locations, and
options. Save it from the toolbar (*Save project*); results are
recomputed on demand and are not stored in the project file.

The toolbar also holds **Run pipeline**, **Export**, and the **EN/ES**
language switch.

# 4. Configuring a catchment

Select a catchment in the sidebar and open its **Setup** tab.

1. Enter the code (e.g. `MYC_01`), area, and bucket size.
2. Under **Discharge**, add the level/flow file(s). If the file has a
   flow column it is used directly; choose *Level → rating curve…* to
   convert water level instead (section 4.1). Rain-only stations simply
   leave discharge empty.
3. Under **Rain gauges**, add one file per gauge. Multiple gauges are
   cross-checked and averaged automatically (section 5).
4. Each file shows a summary line — row count, time step, detected
   columns, period. Check these before running.

## 4.1 Rating curve editor

For stations recording water level only, the discharge is computed with
the compound sharp-crested weir equation (90° V-notch inside a
rectangular section):

- Within the notch (h ≤ a): Q = C1·h^e1
- Above it: Q = C1·(h^e1 − (h−a)^e1) + C2·b·(h−a)^e2

The editor lets you set *a*, *b* and the four coefficients (defaults:
C1 = 1.37, e1 = 2.5, C2 = 1.77, e2 = 1.5) and shows the resulting curve
live. Check *b* against your weir drawings — it is site-specific.

# 5. Running the pipeline

Press **Run pipeline** with a catchment selected. Processing runs in the
background; messages stream into the **Log** tab. What happens, in order:

1. **Depuration** — logger bounce tips arriving ≤ 1.1 s apart are removed.
2. **Grid selection** — the working resolution is the median time step of
   the discharge record (5 min typical; rain-only stations use 5 min).
3. **Rainfall disaggregation** — tip events become a continuous intensity
   series via cubic-spline interpolation of the cumulative curve (Sadler
   & Busscher 1989; Wang et al. 2008), preserving total volume; storms
   are separated at 0.2 mm/h, intensities capped at 127 mm/h, single tips
   spread at 3 mm/h.
4. **Gauge cross-filling** — every pair of gauges is compared by
   double-mass analysis; gaps are filled proportionally only when the
   correlation R ≥ 0.99. Catchment rainfall is the average of the filled
   series.
5. **Discharge averaging** to the grid; normalisation by area.
6. **Aggregation** to hourly and daily products; **baseflow separation**
   (UKIH smoothed-minima and Chapman two-parameter filter).
7. **Indices** — 59 hydrological + 13 climate indices (section 8).

The status bar reports the runtime (a few seconds per catchment
typically).

# 6. Results

The **Results** tab shows summary cards (period, runoff ratio, baseflow
index, gap percentage) and one of six figures, at daily, hourly or
high resolution:

| Figure | Shows |
|---|---|
| Hydrograph | inverted rainfall bars over the flow series with shaded baseflow |
| Flow duration curve | percentage of time each flow is exceeded (log scale) |
| Intensity-duration curve | maximum rainfall intensity vs duration, 5 min – 2 days |
| Monthly regime | precipitation and runoff climatology, mm/month |
| Data coverage | timeline of valid data and gaps per variable |
| Double-mass curve | cumulative rainfall vs cumulative runoff; breaks in slope reveal changes in behaviour or instrumentation |

Figures are interactive (zoom, pan) and can be saved as PNG/PDF/SVG from
the toolbar above the plot.

# 7. Gap-filling report

The **Gap-filling report** button (Results tab) lists every double-mass
comparison of the last run: gauge pair, whether filling was applied, the
correlation R, the slope M, and how many intervals were filled in each
series. Use it to document quality control and to detect gauges that
drift apart (R below 0.99 means no filling was applied — investigate
why).

# 8. The indices

The **Indices** tab lists all values; *Copy table* and *Save CSV…* export
them. Indices follow Olden & Poff (2003) nomenclature where applicable.
`Qxx` denotes the flow exceeded xx% of the time; percentiles use
Gringorten plotting positions. All flow indices are computed from daily
mean flow in l/s/km²; rainfall intensity indices from the 5-minute grid.

## 8.1 Hydrological indices (59)

| # | Code | Description | Units |
|---|---|---|---|
| 1 | QDMIN | Minimum daily flow | l/s/km² |
| 2 | Q95 | Flow exceeded 95% of the time (low flow) | l/s/km² |
| 3 | DAYQ0 | Days with zero flow per year | day |
| 4 | PQ0 | Proportion of days with zero flow | – |
| 5 | QMDRY | Mean daily flow of the driest month | l/s/km² |
| 6 | QDMAX | Maximum daily flow | l/s/km² |
| 7 | Q10 | Flow exceeded 10% of the time (high flow) | l/s/km² |
| 8 | QDMY | Annual mean daily flow | l/s/km² |
| 9 | QDML | Long-term mean daily flow | l/s/km² |
| 10 | Q50 | Median flow from the FDC | l/s/km² |
| 11 | BFI1 | Baseflow index, UKIH smoothed-minima method | – |
| 12 | K1 | Recession constant, UKIH method | – |
| 13 | BFI2 | Baseflow index, Chapman 2-parameter filter | – |
| 14 | K2 | Recession constant, Chapman filter | – |
| 15 | RANGE | Discharge range QDMAX/QDMIN | – |
| 16 | R2FDC | Slope of the FDC between 33% and 66% exceedance | – |
| 17 | IRH | Hydrological regulation index | – |
| 18 | RBI1 | Richards-Baker flashiness index (annual) | – |
| 19 | RBI2 | Richards-Baker flashiness index (seasonal) | – |
| 20 | DRYQMEAN | Driest-month flow / mean monthly flow | – |
| 21 | DRYQWET | Driest-month flow / wettest-month flow | – |
| 22 | SINDQ | Streamflow seasonality index | – |
| 23 | QYEAR | Average annual discharge | mm |
| 24 | RRa | Annual runoff ratio QYEAR/PYEAR | – |
| 25 | RRm | Monthly runoff ratio | – |
| 26 | RRl | Long-term runoff ratio | – |
| 27 | MA5 | Skewness of daily flows: mean/median | – |
| 28 | MA41 | Mean annual runoff | l/s/km² |
| 29 | MA3 | Coefficient of variation of daily flows | – |
| 30 | MA11 | (Q25 − Q75) / median | – |
| 31 | ML17 | 7-day minimum flow / mean annual flow | – |
| 32 | ML21 | CV of 30-day minimum flows | – |
| 33 | ML18 | CV of 7-day minimum flows | – |
| 34 | MH16 | High flow: Q10 / median | – |
| 35 | MH14 | Median 30-day maximum flow / median | – |
| 36 | MH22 | Mean high-flow volume above 3× median / median | day |
| 37 | MH27 | Mean peak above Q25 / median | – |
| 38 | FL3 | Low pulses below 5% of mean daily flow | 1/yr |
| 39 | FL2 | CV of annual low-pulse counts (FL1) | – |
| 40 | FL1 | Low pulses below Q75 | 1/yr |
| 41 | FH3 | High pulses above 3× median daily flow | 1/yr |
| 42 | FH6 | High-flow events above 3× median monthly flow | 1/yr |
| 43 | FH7 | High-flow events above 7× median monthly flow | 1/yr |
| 44 | FH2 | CV of annual high-pulse counts (FH1) | – |
| 45 | FH1 | High pulses above Q25 | 1/yr |
| 46 | DL17 | CV of low-pulse durations (DL16) | – |
| 47 | DL16 | Mean low-pulse duration below Q75 | day |
| 48 | DL13 | Mean 30-day minimum flow / median | – |
| 49 | DH13 | Mean 30-day maximum flow / median | – |
| 50 | DH16 | CV of high-pulse durations (DH15) | – |
| 51 | DH20 | Mean high-pulse duration above median/0.75 | day |
| 52 | DH15 | Mean high-pulse duration above Q25 | day |
| 53 | TH3 | Longest period with no flood (above Q10), fraction of year | – |
| 54 | TL2 | CV of TL1 | – |
| 55 | TL1 | Median Julian day of the annual 1-day minimum | – |
| 56 | RA8 | Rate of flow reversals between days | 1/day |
| 57 | RA5 | Fraction of days with rising flow | – |
| 58 | RA6 | Median rise rate, log space | – |
| 59 | RA7 | Median fall rate, log space | – |

## 8.2 Climate indices (13)

| # | Code | Description | Units |
|---|---|---|---|
| 1 | PYEAR | Average annual precipitation | mm |
| 2 | DAYP0 | Days with zero precipitation per year | day |
| 3 | PP0 | Proportion of days with zero precipitation | – |
| 4 | PMDRY | Precipitation of the driest month | mm |
| 5 | SINDX | Seasonality index (0 none – 1 extreme) | – |
| 6 | PVAR | Coefficient of variation of daily precipitation | – |
| 7 | RMED1D | Median annual maximum 1-day precipitation | mm |
| 8 | RMED2D | Median annual maximum 2-day precipitation | mm |
| 9 | RMED1H | Median annual maximum 1-hour precipitation | mm |
| 10 | iMAX1D | Maximum 1-day intensity | mm/h |
| 11 | iMAX2D | Maximum 2-day intensity | mm/h |
| 12 | iMAX1H | Maximum 1-hour intensity | mm/h |
| 13 | iMAX15M | Maximum 15-minute intensity | mm/h |

*(The published dataset lists two further rows, ETYEAR and RPPE, derived
from external evapotranspiration data; they are not computed by this
software.)*

# 9. Paired catchments

The iMHEA design compares paired catchments (e.g. conserved vs
intervened). Create a pair with **+ Add pair** after configuring both
catchments. Running a pair:

- resamples both to the coarser common resolution;
- cross-fills **rainfall** between the catchments by double-mass analysis
  (discharge is never filled);
- produces combined high-resolution/hourly/daily tables and side-by-side
  indices, with comparison figures (overlaid hydrographs, FDCs, IDCs).

# 10. Exporting

**Export** writes, to a folder you choose:

- `iMHEA_<CODE>_HRes_processed.csv` — high-resolution [Date, Rainfall,
  Flow]
- `iMHEA_<CODE>_1hr_processed.csv` — hourly
- `iMHEA_<CODE>_1day_processed.csv` — daily, including baseflow
- for pairs, the corresponding `_01`/`_02` files in the published iMHEA
  format (dates `dd/mm/yyyy HH:MM:SS`, fixed-width values, `NaN` for
  gaps).

Indices export from the Indices tab (CSV or clipboard).

# 11. MATLAB compatibility mode

During translation, nine defects were found in the original MATLAB code
(documented in `docs/CODE_REVIEW.md` and quantified in
`docs/VALIDATION.md`). By default this software computes the **corrected**
values. Ticking *MATLAB-compatible mode* (Setup tab) reproduces the
legacy behaviour where feasible — useful when comparing against the 2018
published dataset. The differences that matter most:

- **BFI1/K1**: published values are inflated for records with data gaps
  (gap blocks entered the baseflow line as turning points).
- **TL1/TL2**: published timing values are unreliable after the first
  year of each record (day-of-year indexing defect).
- **FH7**: published values are double-normalised (too small by roughly
  the number of years).

# 12. Command-line reference

For batch work, the `imhea` command (requires the Python package):

```
imhea process --code MYC_01 --area 2.63 --bucket 0.2 \
    --flow flow.csv --gauge rg1.csv --gauge rg2.csv --out ./processed
imhea process --code RAIN_01 --bucket 0.1 --gauge rg.csv --out ./out
imhea pair --hres1 A_HRes.csv --hres2 B_HRes.csv --site XYZ --out ./out
imhea network --data-root ./Scripts --out ./valout
imhea --version
```

`--level-to-flow` (with `--weir A B` and `--coeff C1 E1 C2 E2`) converts a
level column through the rating curve; `--matlab-compat` enables the
compatibility mode.

# 13. Frequently asked questions

**How much data is needed for meaningful indices?** At least one full
year; the software computes indices for any record length without
warning, so interpret short-record results cautiously (annual statistics
treat partial years as full ones, as in the original methodology).

**Why does my rainfall total change slightly after processing?**
Depuration removes physically impossible double tips (≤ 1.1 s apart);
the log reports the removed volume. Disaggregation itself conserves
volume.

**Gaps appear where I expect data.** Gaps propagate from `V`-flag marker
rows in the raw files. Check the Data coverage figure and the raw files'
flag column.

**Can I process data from non-iMHEA loggers?** Yes — convert to the raw
CSV layout of section 2.1. Only the date format, column layout, and the
`V` gap convention are mandatory.

**Where are my project's results stored?** Results live in memory and are
recomputed on demand; exported CSVs and the `.imhea` project file are the
persistent artefacts.

# 14. References

- Ochoa-Tocachi, B.F., et al. (2018). High-resolution hydrometeorological
  data from a network of headwater catchments in the tropical Andes.
  *Scientific Data* 5, 180080.
- Gustard, A., Bullock, A., Dixon, J.M. (1992). *Low flow estimation in
  the United Kingdom.* Institute of Hydrology Report 108.
- Chapman, T. (1999). A comparison of algorithms for stream flow
  recession and baseflow separation. *Hydrological Processes* 13.
- Olden, J.D., Poff, N.L. (2003). Redundancy and the choice of hydrologic
  indices for characterizing streamflow regimes. *River Research and
  Applications* 19.
- Sadler, E.J., Busscher, W.J. (1989). High-intensity rainfall rate
  determination from tipping-bucket rain gauge data. *Agronomy Journal* 81.
- Wang, J., et al. (2008). A new treatment of depth-dependent errors in
  tipping-bucket rain gauge measurements. *J. Atmos. Oceanic Technol.* 25.
