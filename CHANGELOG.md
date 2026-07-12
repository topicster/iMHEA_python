# Changelog

## 1.0.0 — 2026-07-11

First public release: complete Python translation of the iMHEA MATLAB
scripts (Ochoa-Tocachi et al. 2018, Scientific Data 5:180080).

- Library (`imhea`): raw I/O, tip depuration, cubic-spline rainfall
  disaggregation, gauge cross-filling, stage-discharge rating, baseflow
  separation (UKIH, Chapman), FDC/IDC/pulse/monthly statistics, 59+13
  indices, catchment/rain-only/paired workflows, plotting module.
- Validation: streamflow and baseflow reproduce the published dataset
  bit-level for all 24 flow catchments; 89.9% of 1,640 index comparisons
  within 0.1% (docs/VALIDATION.md).
- Fixes over the MATLAB original (matlab_compat=True restores legacy
  behaviour): UKIH gap artifact, day-of-year timing indices, FH7
  normalisation, IDC buffer, pulse year alignment, FillGaps cutend,
  Level2Flow NaN handling, and others (docs/CODE_REVIEW.md §4).
- Desktop app (PySide6): projects, guided setup, rating-curve editor,
  background processing, interactive figures, indices table, gap-filling
  report, pair comparison, EN/ES.
- CLI: `imhea process | pair | network`.
- Packaging: PyInstaller spec, double-click build scripts (macOS/Windows),
  GitHub Actions multi-platform builds.
- Documentation: installation and user manuals (EN/ES, docx+PDF), data
  format specification, code review, validation report.
