# iMHEA MATLAB → Python Migration Plan

**Project:** Translate the iMHEA hydrological data processing scripts (Ochoa-Tocachi et al. 2018,
*Scientific Data* 5:180080) from MATLAB to Python, and build a standalone cross-platform desktop
application for non-programmers.

**Owner:** Boris Ochoa Tocachi · **Assistant:** Claude (Fable)
**Started:** 2026-07-11

## Agreed decisions

- **Architecture:** Python package (`imhea`, pip-installable) + CLI + desktop GUI built on top.
- **GUI:** PySide6/Qt, bundled with PyInstaller into double-clickable apps (Windows/macOS/Linux).
- **Validation:** Match MATLAB outputs to numerical tolerance where possible, but optimisations
  and mathematically/statistically equivalent methods are welcome; all deviations documented.
- **Plots:** Reimagined in modern matplotlib (same information content), shared by CLI and GUI.

## Source material (in parent folder)

- `iMHEA_scripts/` — 35 MATLAB scripts (~4,700 lines) + flow diagram + .mat files.
- `iMHEA_raw/` — raw sensor CSVs per site (PD = tipping-bucket rain events, HW = level/flow).
  Format quirks: UTF-8 BOM, CR-only line endings, `dd/mm/yyyy hh:mm:ss` timestamps, Flag column.
- `iMHEA_processed/` — MATLAB-produced HighRes/Hourly/Daily outputs → validation reference.
- `iMHEA_indices/` — published hydrological/climate indices → validation reference.
- `Ochoa-Tocachi-etal-2018-...pdf` — methods paper.

## Phases

| Phase | Deliverable | Status |
|---|---|---|
| 0. Scaffolding | Project structure, this plan | ✅ Done |
| 1. Deep review | `docs/CODE_REVIEW.md` + 6 detailed specs in `docs/review/` | ✅ Done |
| 2. Core translation | `src/imhea/`: io, mtime, clean, aggregate (incl. CS/LI splines), flow + 22 tests | ✅ Done |
| 3. Analysis translation | `stats.py`, baseflow in `flow.py`, `indices.py` (59+13 indices) + 13 tests | ✅ Done |
| 4. Workflows + validation | `workflow.py`, `registry.py`, `validation/` harness + `docs/VALIDATION.md` | ✅ Done |
| 5. Plotting | `imhea.plots` (9 figure functions) + example PNGs in `examples/` | ✅ Done |
| 6. GUI mini-project | PySide6 app in `gui/` (project files, EN/ES, rating editor, fill report, pair view) | ✅ Done |
| 7. Packaging | CLI + PyInstaller spec + GitHub Actions (Win/macOS x2/Linux) + build guide | ✅ Done |

## Working agreements

- Every phase ends with files saved here (`imhea-python/`), so progress survives sessions.
- Understand before changing: no translation until Phase 1 review is complete.
- Any suspected bug or inefficiency in the MATLAB code is flagged to Boris before deciding
  whether to reproduce or fix it (fixes get documented in the validation report).
- Numerical validation on at least 3 catchments spanning different sites/resolutions.

## Session log

- **2026-07-11:** Explored materials, agreed decisions and plan, scaffolded project.
- **2026-07-11 (cont.):** Phase 1 complete. 6 parallel review agents produced ~195 KB of
  line-referenced specs (docs/review/A–F). Key claims spot-checked against source. 9 confirmed
  bugs + 7 design quirks consolidated in CODE_REVIEW.md §4 — awaiting Boris's reproduce-vs-fix
  decisions before Phase 2.
- **2026-07-11 (cont.):** Phase 2 complete. Package `imhea` v0.2.0: mtime (exact integer
  binning replacing datenum float hacks), io (flag/BOM/CR-aware readers — note HS/HI/HW files
  have 4 columns Level+Flow; MATLAB-compatible writers), clean (depure/voids/fill_gaps),
  aggregate (Aggregation/Average + CS/LI event disaggregation unified under method=),
  flow (level2flow). 22 tests pass, incl. regression vs published CHA_01: rainfall corr
  >0.9999 with exact mass conservation; rating-curve flow corr >0.999, median ratio 1.000.
  Deviations from MATLAB (fixed by default): sentinel float hazard (2·MaxT), single-tip
  mass conservation for 0.254mm buckets, FillGaps cutend restore, Level2Flow NaN handling.
  ProcessP/ProcessQ deferred to Phase 3 (they orchestrate indices functions).
- **2026-07-11 (cont.):** Phase 3 complete (v0.3.0). New: stats.py (FDC Gringorten+spline,
  IDC fixed stale-buffer, Pulse RLE with fixed year alignment, monthly stats with fixed
  day-of-year), baseflow_chapman + baseflow_ukih + recession_constant in flow.py,
  indices.py (process_p/q, indices_plus, indices_total 59+13, climate_p/total, pair).
  35 tests pass. CHA_01 end-to-end vs published CSVs: 57/72 indices within 0.1%, all
  deviations >1% explained: intentional fixes (FH7, TH3, TL1/TL2), MATLAB Inf-turning-point
  artifact inflating published BFI1/K1 near gaps (IMPORTANT: flag to Boris — published BFI1
  for gappy records is inflated), upstream P-grid sensitivity (intensity indices; IDC verified
  EXACT on MATLAB's own series), MH22 pulse-volume sensitivity. Chapman BFI2/K2 match exactly.
  Runtime: 0.3 s per catchment (MATLAB: minutes). Phase 4 next: workflows + full validation.
- **2026-07-11 (cont.):** Phase 4 complete (v0.4.0). workflow.py (Workflow/WorkflowRain/
  WorkflowPair with fixed alignment + correctly-labelled duration curves), registry.py
  (data-driven replacement for Raw2Processed incl. JTU cascade, HUA merge/rescale, PIU
  crossfill), validation/run_network.py (full 28-station rerun, ~3 min, checkpointed).
  RESULTS (docs/VALIDATION.md): Q and BQ reproduce published data BIT-LEVEL at all
  resolutions for all 24 flow catchments; daily P matches everywhere (mass exact); 89.9%
  of 1,640 index comparisons within 0.1%. All residuals explained: TL1/TL2 (MATLAB doy bug
  — published values unreliable), MH22/TH3 (published values predate current MATLAB source),
  CHA sub-daily P (sentinel float hazard, bias-free). 38 tests pass. Next: Phase 5 plots,
  then GUI.
- **2026-07-11 (cont.):** Phase 5 complete (v0.5.0). imhea.plots: plot_series (Plot2/3),
  plot_catchment (inverted hyetograph + hydrograph + baseflow shading), plot_pair
  (PlotPair redesign), plot_fdc/plot_idc overlays, plot_monthly_regime, plot_network
  (Plot4 redesign), plot_double_mass, plot_gaps (coverage timeline — new). Example
  figures on real CHA/network data in examples/. 44 tests pass. Next: Phase 6 GUI
  (design mockup first), then Phase 7 packaging.
- **2026-07-11 (cont.):** Phase 6 complete (v0.6.0). Design mockup approved by Boris
  (start screen with dual entry, sidebar tree, Setup/Results/Indices/Log tabs, EN/ES,
  extras: rating-curve editor, gap-filling report, pair view). Implemented in gui/:
  app.py, project.py (.imhea JSON files + built-in network registry), runner.py
  (QThread + log capture), tabs.py, dialogs.py, i18n.py. Library: FillInfo diagnostics
  added to WorkflowResult/PairResult; export_catchment(). Headless smoke test on real
  CHA data passes (all 6 figure kinds, single + pair runs, exports, project roundtrip).
  47 tests total. Next: Phase 7 — PyInstaller specs + GitHub Actions builds.
- **2026-07-11 (cont.):** Phase 7 complete (v0.7.0). Added imhea.cli (process/pair/network
  commands; console scripts `imhea` and `imhea-gui`), packaging/imhea_gui.spec (one-dir
  PyInstaller bundle, macOS .app, Qt bloat excluded), .github/workflows/build.yml (test job
  + Windows/macOS-arm64/macOS-intel/Linux builds + release-on-tag), packaging/README.md.
  CLI verified on real CHA data; spec/workflow syntax verified; binaries build via CI or
  one local command (sandbox cannot run multi-minute builds). 50 tests pass.

## PROJECT COMPLETE — all 7 phases delivered
To publish: create a GitHub repository from imhea-python/, push, and tag v1.0.0 —
the workflow will attach Windows/macOS/Linux app bundles to the release automatically.
- **2026-07-11 (cont.):** Documentation for distribution. docs/manuals/: Installation
  Manual + User Manual, each in EN and ES, as .docx + .pdf (+ markdown sources for
  maintenance). User manual includes data-format spec, full 59+13 index reference,
  methods summary, compat-mode guidance, CLI reference, FAQ. Release extras: LICENSE
  (MIT), CITATION.cff, CHANGELOG.md (v1.0.0), docs/DATA_FORMAT.md (bilingual).
