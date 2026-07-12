# Ochoa-Tocachi et al. (2018) — iMHEA High-resolution Hydrometeorological Data

**Citation:** Ochoa-Tocachi, B.F. et al. (2018). High-resolution hydrometeorological data from a network of headwater catchments in the tropical Andes. *Scientific Data* 5:180080. DOI: 10.1038/sdata.2018.80. Data DOI: 10.6084/m9.figshare.c.3943774. License CC BY 4.0.

**Purpose of this doc:** guide a MATLAB -> Python reimplementation of the iMHEA data processing. Original code is MATLAB R2017a; R/Python ports at https://github.com/topicster/iMHEA_scripts.

---

## 1. Network / Site Overview

- **iMHEA** = Regional Initiative for Hydrological Monitoring of Andean Ecosystems. Established 2009. Uses a **"trading-space-for-time"** paired-catchment design.
- Dataset presented: **28 catchments** (< 20 km2 each), **9 sites**, 3 countries. Comprising **67 rain gauges** and **25 streamflow stations**.
- **Design philosophy:** "control-intervention" pairwise comparison (usually without a pre-intervention baseline). Each catchment represents a single dominant land use/land cover (>= 75% homogeneous area). Catchments 0.5-20 km2, 2000-5000 m a.s.l. Zero-order catchments and very small (< 0.2 km2) catchments avoided.

### Site codes (Table 2)

| Code | Site, Country | Biome | Design (C/P/H) | Period |
|------|---------------|-------|----------------|--------|
| LLO | Lloa, Ecuador | Páramo | 2C / 4P / 2H | 01/2013–01/2017 |
| JTU | Jatunhuayco, Ecuador | Páramo | 4C / 8P / 4H | 11/2013–01/2017 |
| PAU | Paute, Ecuador | Páramo | 5C / 13P / 4H | 05/2001–07/2007 |
| PIU | Piura, Peru | Páramo; Forest | 7C / 20P / 5H | 04/2013–01/2017 |
| CHA | Chachapoyas, Peru | Jalca | 2C / 2P / 2H | 09/2010–12/2015 |
| HUA | Huaraz, Peru | Humid puna | 2C / 6P / 4H | 02/2011–09/2014 |
| HMT | Huamantanga, Peru | Dry puna | 2C / 4P / 2H | 06/2014–01/2017 |
| TAM | Tambobamba, Peru | Humid puna | 2C / 6P / 2H | 04/2012–04/2013 |
| TIQ | Tiquipaya, Bolivia | Humid puna | 2C / 4P / 2H | 02/2013–01/2016 |

C = number of catchments, P = rain gauges, H = streamflow stations. (Full iMHEA network has 16 sites incl. Venezuela; only these 9 are in the dataset.)

### Sensors and resolutions

- **Rain gauges (tipping bucket):** Onset HOBO, Davis Instruments Rain Collector II, Texas Electronics. Height 1.50 m. Resolution at least 0.254 mm (0.1 in), **typically 0.2 mm**, exceptionally 0.1 mm. Record tip time stamps (events); a few dataloggers store aggregated cumulative values at 5 or 30 min.
- **Water level (pressure transducers):** Onset HOBO U20, Schlumberger Diver/Baro-Diver, Solinst Levelogger 3001, Global Water WL16, Instrumentation Northwest AquiStar PT2X. Recorded every 15 min or (generally) 5 min; some limited to 30 min. Level resolution 0.1–0.5 mm.
- **Weirs:** compound sharp-crested — a 90° V-notch section (accurate low flows) combined with a triangular–rectangular section (contains peak flows). Dimensions per station in Table 6 (see section 3).

### Notable per-site caveats

- **CHA**: exception — both rainfall and streamflow monitored at 30 min interval only.
- **JTU and CHA**: some stations lack rain-gauge tip data because the logger was programmed to store cumulative values only.
- **JTU_04** is a large catchment (16.05 km2) containing the other three JTU catchments; its weir V-notch height is 0.0000 m (pure rectangular section, width 2.9 m).
- **PAU_05, PIU_05, PIU_06**: rainfall-only stations (no streamflow, no defined area).
- **HUA_02**: the discharge station was initially downstream of its current position (former area 2.71 km2); early-period data were **normalised during processing to the current area (2.38 km2)**.
- **HUA_01 and HUA_02** each have two weir sections (HD_01 = 1.0 m V-notch, width 0.0; HD_02 = 0.3 m V-notch with rectangular width) — compound handled as two entries.
- Tipping-bucket gauges may **underestimate total precipitation by ~15% for low-intensity events** in high Andean catchments.

---

## 2. Data Records / File Conventions

**Format:** CSV. Archived on Figshare.

**Naming conventions:**
- Raw sensor data: `iMHEA_<site code>_<catchment number>_<variable>_<sensor number>_raw.csv`
- Processed catchment data: `iMHEA_<site code>_<catchment number>_<temporal resolution>_processed.csv`
- Indices / properties: `iMHEA_Indices_<index type>.csv`
- Geographic data: `iMHEA_<site code>_<catchment number>_<geodata type>`

**Variable code = two letters.** First letter = station type: `P` = pluviometric, `H` = hydrological. Second letter = sensor make:
- Precipitation: `O` = Onset HOBO, `D` = Davis Instruments, `T` = Texas Electronics.
- Discharge: `O` = Onset HOBO, `S` = Solinst, `D` = Schlumberger Diver, `W` = Global Water, `I` = Instrumentation Northwest.

So e.g. `HMT_01_HI_01` = Huamantanga catchment 1, Hydrological station, Instrumentation Northwest sensor, sensor #1.

**Variable units and levels (Table 3):**

| Variable | Raw | Processed | Units |
|----------|-----|-----------|-------|
| Precipitation | one file/sensor; tips at 0.254/0.2/0.1 mm OR cumulative at 5/30 min | one file/catchment; series at max resolution matching discharge, plus 1 hr and 1 day | rainfall in **mm** |
| Streamflow | one file/sensor; water level instantaneous at 5/15/30 min | one file/catchment; series at max resolution, plus 1 hr and 1 day | water level in **cm**; streamflow in **l s⁻¹ km⁻²** (also expressible as mm) |
| Catchment characteristics | geographic info | matrix physical characteristics per catchment | categories: shape, drainage, elevation, topography, subsurface, climate, rainfall intensity, land cover/use |
| Hydrological indices | — | matrix of indices per catchment (averaged over monitoring period) | categories: water yield, hydrological regulation, water balance, magnitude, frequency, duration, timing, flashiness |

### Flags used in RAW data (critical for parsing)

- **`I`** = sensor is **launched/initialised** (software communication/functioning log, not a rainfall tip).
- **`D`** = data have been **downloaded** from the sensor (software log).
- **`X`** = software logs **removed from the rainfall count**, OR potentially erroneous tips (e.g. from manipulating the gauge) flagged for exclusion.
- **`P`** = other anomalies, e.g. **unrealistically high rainfall intensities**.
- **`V`** = **data gap** in the time series.

Software-log time stamps (`I`, `D`) are kept in raw files but must be separated from real rainfall tips. `X` and `P` mark records to exclude. Same flag convention (`I`,`D`,`X`,`P`,`V`) is applied to water level / discharge raw files.

---

## 3. METHODS (detail for reimplementation)

### 3.1 Quality control (QC)

- QC performed immediately after collection: reject data outside expected measurement range, negative water levels, extreme rainfall intensities (outliers).
- **Onset HOBO systematic anomaly:** some tip intervals are exactly **1 s** from the previous (logger max time resolution). Two 0.2 mm tips 1 s apart = 720 mm hr⁻¹, but the gauge manual caps at **127 mm hr⁻¹**; therefore **immediate consecutive events (1 s apart) were removed** during depuration.
- Rain-gauge cross-checks: correlation analysis + **double mass plots** between gauges to detect/correct errors and fill gaps. Automatic records validated against manual rain gauges.

### 3.2 Tipping-bucket events -> rainfall series (composite cubic spline)

Core algorithm (refs 49, 50, 51; Wang et al. 2008 method):

1. Convert tip time stamps to rainfall depth per rain-gauge resolution.
2. Aggregate to **1 min resolution using tip counting** first.
3. Apply a **composite cubic spline interpolation to the cumulative rainfall curve** to generate 1 min intensities (better than tip counting or linear interpolation).
4. **Four threshold intensities** are defined:
   - (i) **minimum intensity to separate rainfall events = 0.2 mm hr⁻¹** (depends on regional rainfall structure).
   - (ii) **maximum intensity to merge consecutive tips = 127 mm hr⁻¹** (avoids issues concatenating high/low-intensity intervals; = HOBO manual max).
   - (iii) **mean intensity to distribute single tips = 3 mm hr⁻¹** (used when insufficient info to interpolate a lone tip).
   - (iv) **low threshold intensity above which data are accepted = 0.1 mm hr⁻¹** (avoids extremely low rates).
5. **Event extremes:** assume the "real" initial and final points occur at **half the rainfall rate of the two extreme tips**, considering **half a partial tip remaining in the bucket from the previous event**. Set **first derivatives to zero at these new defined extremes** in the spline (improves extreme interpolation; otherwise equivalent to setting second derivatives to zero at extremes).
6. **Special case:** if an independent rainfall event has only **2 data points**, use **linear interpolation** instead of spline.
7. **Mass-conservation / discontinuity checks per independent event:**
   - (i) negative estimated rates (from rapid spline slope changes) -> **replaced by zero**.
   - (ii) rates between 0 and the low threshold -> **replaced by the low threshold (0.1 mm hr⁻¹)**.
   - (iii) bias between original and interpolated totals -> **corrected by re-scaling the remaining intensities**.
8. Reconstruct cumulative curve by consecutively adding corrected rates.
9. **If bias after interpolation is unacceptably large (> 25%; some studies allow up to 50%), discard the cubic spline and use linear interpolation instead.**
10. Aggregate rainfall to intervals matching the catchment's discharge, plus **1 hr and 1 day**.

### 3.3 Water level -> discharge (rating curve)

- Uses the **Kindsvater–Shen relation** (ref 56, USBR Water Measurement Manual) as a theoretical stage-discharge relation for the compound sharp-crested weir. Revised with manual flow-velocity observations where available.
- Weir geometry per station in **Table 6** (all V-notches are **90°**): parameters are `90° V-notch section height (m)` and `Rectangular section width (m)`.
- Water level validated/corrected using **manual water-depth-over-weir measurements (1 mm precision)** at each site visit, used to compensate offsets vs. automatic sensor.
- **Discharge normalised by catchment area** to units mm or **l s⁻¹ km⁻²** (enables inter-catchment comparison and water balance vs. rainfall).
- Kept at max temporal resolution; averaged at **1 hr and 1 day**.

**Table 6 weir dimensions (V-notch height m / rectangular width m; sensor range/accuracy/resolution):**

| Station | V-notch h (m) | Rect width (m) | Range (cm) | Accuracy (cm) | Resolution (cm) |
|---------|---------------|----------------|------------|---------------|-----------------|
| LLO_01_HI_01 | 0.3030 | 1.2520 | 200 | ±0.12 | 0.01 |
| LLO_02_HI_01 | 0.3000 | 1.4000 | 200 | ±0.12 | 0.01 |
| JTU_01_HI_01 | 0.2967 | 0.8500 | 200 | ±0.12 | 0.01 |
| JTU_02_HI_01 | 0.2961 | 0.7980 | 200 | ±0.12 | 0.01 |
| JTU_03_HI_01 | 0.2939 | 0.9000 | 200 | ±0.12 | 0.01 |
| JTU_04_HI_01 | 0.0000 | 2.9000 | 200 | ±0.12 | 0.01 |
| PIU_01_HI_01 | 0.6000 | 2.3000 | 200 | ±0.12 | 0.01 |
| PIU_02_HI_01 | 0.6000 | 2.3000 | 200 | ±0.12 | 0.01 |
| PIU_03_HI_01 | 0.3000 | 0.9000 | 200 | ±0.12 | 0.01 |
| PIU_04_HI_01 | 0.3000 | 0.9000 | 200 | ±0.12 | 0.01 |
| PIU_07_HI_01 | 0.3000 | 0.9000 | 200 | ±0.12 | 0.01 |
| CHA_01_HS_01 | 0.2975 | 1.2100 | 1000 | ±0.5 | n/s |
| CHA_02_HS_01 | 0.2975 | 1.2000 | 1000 | ±0.5 | n/s |
| HUA_01_HD_01 | 1.0000 | 0.0000 | 150–1000 | ±0.50 | 0.10–0.20 |
| HUA_01_HD_02 | 0.3000 | 1.6000 | 150–1000 | ±0.50 | 0.10–0.20 |
| HUA_02_HD_01 | 1.0000 | 0.0000 | 150–1000 | ±0.50 | 0.10–0.20 |
| HUA_02_HD_02 | 0.3000 | 2.2000 | 150–1000 | ±0.50 | 0.10–0.20 |
| HMT_01_HI_01 | 0.2981 | 0.8950 | 200 | ±0.12 | 0.01 |
| HMT_02_HI_01 | 0.3000 | 1.5000 | 200 | ±0.12 | 0.01 |
| TAM_01_HO_01 | 0.3065 | 1.1520 | 400–900 | ±0.30–0.50 | 0.14–0.21 |
| TAM_02_HO_01 | 0.3095 | 1.1510 | 400–900 | ±0.30–0.50 | 0.14–0.21 |
| TIQ_01_HD_01 | 0.3100 | 2.1100 | 150–1000 | ±0.50–1.00 | 0.10–0.20 |
| TIQ_02_HD_01 | 0.3000 | 1.2800 | 150–1000 | ±0.50–1.00 | 0.10–0.20 |

### 3.4 Aggregation

- Rainfall aggregated to the discharge interval AND to **1 hr and 1 day**.
- Streamflow kept at max resolution, averaged at **1 hr and 1 day**.
- Data are stored aggregated at **5, 15, 60 min, or 1 day** intervals. Imperative to keep the finest-resolution data.

### 3.5 Gap handling

- **Rainfall:** gaps flagged `V`. Filled using **double mass plots between gauges within a catchment only when regression R² > 0.99**. Remaining gaps filled from the **paired catchment's rainfall, again only when R² > 0.99**. Catchment average rainfall = **simple (unweighted) average of rain-gauge data within the catchment**.
- **Water level:** gaps filled **only for short periods when sensors were stopped for data retrieval** (generally < a few hours). **All other water level / discharge gaps were NOT filled** (to avoid distorting non-linear hydrological responses). This is a "restricted data gap filling."

### 3.6 Baseflow separation (TWO methods, both reported)

**Base Flow Index (BFI)** = ratio of baseflow to total flow (proportion of discharge from internal catchment stores).

**Method 1 — UK Flood Estimation Handbook / IH Report 108 (Gustard et al. 1992, ref 64):**
- Divide mean daily flow into **non-overlapping blocks of 5 days**.
- Compute the **minima of these consecutive periods**.
- Search for **turning points** in the sequence of minima.
- Daily baseflow = **linear interpolation between turning points**, **constrained by the original hydrograph** (baseflow set to observed flow wherever the separated line exceeds the observed hydrograph).
- Baseflow time series included in the daily flow dataset.

**Method 2 — Boughton two-parameter algorithm (Chapman 1999, ref 65):**
- **Filter parameter = 0.85** (fitted subjectively).
- Chosen because the two-parameter algorithm gives more consistent results than a one-parameter (recession-constant-based) algorithm or the IHACRES three-parameter algorithm.

**Recession constant:** baseflow recessions identified as hydrograph sections of at least **7 days duration** that are **approximately linear (R² > 0.8) on a logarithmic scale of flows**; the recession constant is derived from these. Reported indices include BFI and recession constants from **both** methods.

### 3.7 Precipitation-derived indices

Average annual precipitation, wetness index, days with zero rainfall, precipitation of the driest month, coefficient of variation in daily precipitation, seasonality index (Walsh & Lawler 1981, ref 52). Median/maximum rainfall intensities computed with a **5 min moving window for storm durations from 5 min to 2 days**.
- **Wetness index** = ratio between annual precipitation and evapotranspiration. Since most catchments lack a full met station, ET is computed from **WorldClim temperature** (ref 53) via the **Hargreaves formula** (Hargreaves & Samani 1985 / FAO-56).

### 3.8 Hydrological indices (streamflow signatures)

Selected to be independent, unambiguous, and responsive to interventions. Streamflow characterised by 5 response types: **Magnitude, Frequency, Duration, Timing/Predictability, Rate of change/Flashiness** (sub-divided into low, average, high flows). Derived from **normalised daily discharge**, averaged over monitoring periods. Categories and member indices:

- **Water yield (flow statistics):** minimum, maximum, median, annual mean, long-term mean, driest-month flow, flow percentiles.
- **Hydrological regulation:** baseflow index (BFI), recession constant, discharge range, slope of the flow duration curve, hydrological regulation index, **Richards-Baker flashiness index** (Baker et al. 2004, ref 63).
- **Water balance:** dry-month discharge ratio, dry-month discharge range, average annual discharge, runoff ratio.
- **Magnitude (extended):** skewness in daily flows, coefficients of variation, discharge ranges.
- **High & low flow pulse analysis:** magnitude, volume, frequency, duration.
- **Timing:** flood occurrence/absence, Julian day of extremes.
- **Flashiness:** flow reversals, logarithm of increasing and decreasing flow differences, ratio of days with increasing flow.

(Definitions per Ochoa-Tocachi et al. 2016 WRR ref 34, and Olden & Poff 2003 ref 59. Water balance: precipitation − discharge = combined losses ≈ evapotranspiration over the long term.)

---

## 4. Technical Validation (checks the authors did)

- **Regional representativeness:** catchments < 20 km2, single homogeneous land cover in >= 75% of area; zero-order and < 0.2 km2 catchments avoided; no upstream water abstractions.
- **Rain-gauge redundancy:** most sites have 3 gauges (low/mid/high elevation) or at least 2; exceeds WMO density (1 gauge / 250 km2 for mountains). Allows validation/correction if a sensor fails.
- **Uncertainty framework** (Table 5, following Westerberg & McMillan 2015):
  - *Precipitation:* equipment malfunction (compare data with/without QC); point measurement error (normal distribution, SD as function of rain rate); intensity interpolation (composite cubic spline + thresholds + bias correction); spatial interpolation (subsampling from network gauges).
  - *Streamflow:* water level measurement + barometric/temperature compensation (uniform/normal sampling, ±5 mm mid-range, or sensor nominal accuracy from Table 6); rating curve calibration/extrapolation (constrained by weir structure; voting-point likelihood; heteroscedastic max-likelihood model); time discretisation (compare indices at different time steps); seasonality (whole series vs. by season); index calculation method (compare algorithms, correlation, regionalisation).
- **Baseflow method comparison:** the two BFI methods give similar baseflow shapes and consistent inter-catchment trends, but different absolute values -> can lead to different interpretations of groundwater dominance.
- **Barometric compensation:** absolute pressure transducers had barometric + submerged sensors installed in similar/buffered temperature conditions to avoid diurnal artifacts; vented sensors kept dry and shaded.

---

## 5. Known data issues / caveats (for the port)

- Authors state the data are **not suitable for trend analysis** (short time series); value lies in paired/spatial comparison.
- Monitoring periods differ across sites/catchments — beware regional hydrometeorological drivers when pooling.
- Tipping buckets underestimate low-intensity precipitation by ~15% in high Andean sites.
- HOBO 1-second consecutive-tip artifact must be filtered.
- HUA_02 area re-normalisation (2.71 -> 2.38 km2) for the early period.
- CHA only at 30 min; JTU/CHA some cumulative-only rainfall loggers.
- Rating-curve high-flow extrapolation is the dominant discharge uncertainty; only a few catchments had the Kindsvater–Shen relation checked against direct flow observations.

---

## Key references for algorithms

- Rainfall spline: Wang, Fisher & Wolff (2008) ref 50; Sadler & Busscher (1989) ref 49; Ciach (2003) ref 51.
- Weir stage-discharge: USBR Water Measurement Manual (2001) ref 56 (Kindsvater–Shen).
- Baseflow M1: Gustard, Bullock & Dixon (1992), IH Report 108 ref 64.
- Baseflow M2 / recession: Chapman (1999) ref 65 (Boughton two-parameter, filter 0.85).
- Richards-Baker flashiness: Baker et al. (2004) ref 63.
- Seasonality index: Walsh & Lawler (1981) ref 52.
- Hargreaves ET: Hargreaves & Samani (1985) ref 54 / FAO-56 ref 55.
- Index definitions: Ochoa-Tocachi et al. (2016) WRR ref 34; Olden & Poff (2003) ref 59.
- Uncertainty framework: Westerberg & McMillan (2015) ref 67.
