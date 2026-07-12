"""Central tab widgets: Setup, Results, Indices, Log."""

from __future__ import annotations

import numpy as np
import pandas as pd
from matplotlib.backends.backend_qtagg import (FigureCanvasQTAgg,
                                               NavigationToolbar2QT)
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox,
                               QFileDialog, QFormLayout, QGridLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QPlainTextEdit,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget, QApplication)

from imhea import monthly_flow, monthly_rain, no_voids, fdc as _fdc, idc as _idc
from imhea import plots

from .dialogs import FillReportDialog, RatingCurveDialog
from .i18n import tr


class SetupTab(QWidget):
    """Catchment metadata, discharge source, rain gauge file list."""

    def __init__(self, project, code: str, parent=None):
        super().__init__(parent)
        self.project = project
        self.code = code
        cfg = project.catchments[code]
        lay = QVBoxLayout(self)

        form = QFormLayout()
        self.ed_code = QLineEdit(cfg.code)
        self.sp_area = QDoubleSpinBox()
        self.sp_area.setDecimals(4)
        self.sp_area.setRange(0, 1e5)
        self.sp_area.setValue(cfg.area or 0.0)
        self.sp_bucket = QDoubleSpinBox()
        self.sp_bucket.setDecimals(3)
        self.sp_bucket.setRange(0.01, 5)
        self.sp_bucket.setSingleStep(0.1)
        self.sp_bucket.setValue(cfg.bucket)
        form.addRow(tr("code"), self.ed_code)
        form.addRow(tr("area"), self.sp_area)
        form.addRow(tr("bucket"), self.sp_bucket)
        lay.addLayout(form)

        # discharge group
        gq = QGroupBox(tr("discharge"))
        ql = QVBoxLayout(gq)
        self.lst_flow = QListWidget()
        self._fill_list(self.lst_flow, cfg.flow_files)
        ql.addWidget(self.lst_flow)
        row = QHBoxLayout()
        b_add_q = QPushButton(tr("select_flow"))
        b_add_q.clicked.connect(self._add_flow)
        self.cmb_src = QComboBox()
        self.cmb_src.addItems([tr("flow_col"), tr("level_rating")])
        self.cmb_src.setCurrentIndex(1 if cfg.flow_source == "level" else 0)
        self.cmb_src.activated.connect(self._src_changed)
        row.addWidget(b_add_q)
        row.addWidget(QLabel(tr("source")))
        row.addWidget(self.cmb_src)
        row.addStretch(1)
        ql.addLayout(row)
        lay.addWidget(gq)

        # rain gauges group
        gp = QGroupBox(tr("rain_gauges"))
        pl = QVBoxLayout(gp)
        self.lst_rain = QListWidget()
        self._fill_list(self.lst_rain, cfg.rain_files)
        pl.addWidget(self.lst_rain)
        row = QHBoxLayout()
        b_add = QPushButton("+ " + tr("add_files"))
        b_add.clicked.connect(self._add_rain)
        b_rm = QPushButton(tr("remove"))
        b_rm.clicked.connect(self._remove_selected)
        row.addWidget(b_add)
        row.addWidget(b_rm)
        row.addStretch(1)
        pl.addLayout(row)
        lay.addWidget(gp)

        bottom = QHBoxLayout()
        self.chk_compat = QCheckBox(tr("matlab_compat"))
        self.chk_compat.setChecked(project.matlab_compat)
        self.chk_compat.setToolTip(tr("compat_hint"))
        self.chk_compat.toggled.connect(self._compat)
        bottom.addWidget(self.chk_compat)
        bottom.addStretch(1)
        lay.addLayout(bottom)
        lay.addStretch(1)

        self.ed_code.editingFinished.connect(self._apply)
        self.sp_area.valueChanged.connect(self._apply)
        self.sp_bucket.valueChanged.connect(self._apply)

    # -- helpers -----------------------------------------------------------
    def _fill_list(self, widget, files):
        widget.clear()
        for f in files:
            item = QListWidgetItem(f"{f}\n    {self.project.file_summary(f)}")
            item.setData(Qt.UserRole, f)
            widget.addItem(item)

    def _cfg(self):
        return self.project.catchments[self.code]

    def _apply(self):
        cfg = self._cfg()
        cfg.area = self.sp_area.value() or None
        cfg.bucket = self.sp_bucket.value()

    def _compat(self, on):
        self.project.matlab_compat = bool(on)

    def _add_flow(self):
        files, _ = QFileDialog.getOpenFileNames(self, tr("select_flow"),
                                                filter="CSV (*.csv)")
        if files:
            cfg = self._cfg()
            cfg.flow_files.extend(files)
            cfg.flow_scales = [1.0] * len(cfg.flow_files)
            self._fill_list(self.lst_flow, cfg.flow_files)

    def _add_rain(self):
        files, _ = QFileDialog.getOpenFileNames(self, tr("add_files"),
                                                filter="CSV (*.csv)")
        if files:
            self._cfg().rain_files.extend(files)
            self._fill_list(self.lst_rain, self._cfg().rain_files)

    def _remove_selected(self):
        cfg = self._cfg()
        for item in self.lst_rain.selectedItems():
            cfg.rain_files.remove(item.data(Qt.UserRole))
        self._fill_list(self.lst_rain, cfg.rain_files)

    def _src_changed(self, i):
        cfg = self._cfg()
        if i == 1:
            dlg = RatingCurveDialog(cfg.weir, cfg.coeff, self)
            if dlg.exec():
                cfg.weir, cfg.coeff = dlg.values()
                cfg.flow_source = "level"
            else:
                self.cmb_src.setCurrentIndex(
                    1 if cfg.flow_source == "level" else 0)
        else:
            cfg.flow_source = "flow"


class ResultsTab(QWidget):
    """Metric cards + figure area with resolution/figure selectors."""

    FIGS = ["hydrograph", "fdc", "idc", "regime", "coverage", "double_mass"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.result = None
        self.is_pair = False
        lay = QVBoxLayout(self)

        self.cards = QLabel(tr("no_results"))
        lay.addWidget(self.cards)

        row = QHBoxLayout()
        self.cmb_res = QComboBox()
        self.cmb_res.addItems([tr("daily"), tr("hourly"), tr("highres")])
        self.cmb_fig = QComboBox()
        self.cmb_fig.addItems([tr(k) for k in self.FIGS])
        self.btn_fills = QPushButton(tr("fills_title"))
        self.btn_fills.clicked.connect(self._show_fills)
        row.addWidget(QLabel(tr("resolution")))
        row.addWidget(self.cmb_res)
        row.addWidget(QLabel(tr("figure")))
        row.addWidget(self.cmb_fig)
        row.addStretch(1)
        row.addWidget(self.btn_fills)
        lay.addLayout(row)

        self.canvas = FigureCanvasQTAgg(Figure(figsize=(8, 4.2)))
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        lay.addWidget(self.toolbar)
        lay.addWidget(self.canvas, stretch=1)
        self.cmb_res.activated.connect(self._redraw)
        self.cmb_fig.activated.connect(self._redraw)

    def set_result(self, result, is_pair: bool):
        self.result = result
        self.is_pair = is_pair
        self._update_cards()
        self._redraw()

    def _frame(self):
        r = self.result
        return [r.daily, r.hourly, r.hres][self.cmb_res.currentIndex()]

    def _update_cards(self):
        r = self.result
        d = r.daily
        parts = [f"{tr('period')}: {d.index[0]:%Y-%m} → {d.index[-1]:%Y-%m}"]
        qcol = "Q1" if self.is_pair else "Q"
        if qcol in d:
            gaps = 100 * d[qcol].isna().mean()
            parts.append(f"{tr('gaps')} Q: {gaps:.0f}%")
        if not self.is_pair and r.indices is not None:
            h = r.indices.hydro
            parts.append(f"RRl: {h['RRl']:.2f}")
            parts.append(f"BFI: {h['BFI1']:.2f}")
        self.cards.setText("   ·   ".join(parts))

    def _show_fills(self):
        FillReportDialog(getattr(self.result, "fills", None) or [],
                         self).exec()

    def _redraw(self):
        if self.result is None:
            return
        fig_kind = self.FIGS[self.cmb_fig.currentIndex()]
        df = self._frame()
        old = self.canvas.figure
        try:
            new_fig = self._build_figure(fig_kind, df)
        except Exception as e:
            new_fig = Figure()
            ax = new_fig.add_subplot(111)
            ax.text(0.5, 0.5, f"{type(e).__name__}: {e}", ha="center",
                    wrap=True, fontsize=9)
        self.canvas.figure = new_fig
        new_fig.set_canvas(self.canvas)
        old.clear()
        self.canvas.draw_idle()

    def _build_figure(self, kind, df):
        r = self.result
        if self.is_pair:
            if kind == "hydrograph":
                return plots.plot_pair(r.daily)
            if kind == "fdc":
                return plots.plot_fdc(
                    {c: _fdc(r.daily[c].dropna()).fdc
                     for c in ("Q1", "Q2") if c in r.daily})
            if kind == "idc":
                return plots.plot_idc(
                    {c: _idc(r.hres.index, r.hres[c].to_numpy())[0]
                     for c in ("P1", "P2")})
            if kind == "regime":
                out = {}
                for c in ("P1", "P2"):
                    p = r.daily[c].dropna()
                    out[c] = monthly_rain(p.index, p.to_numpy()).avg_month
                return plots.plot_monthly_regime(out, None)
            if kind == "coverage":
                return plots.plot_gaps(
                    {c: no_voids(df.index, df[c].to_numpy())
                     for c in df.columns})
            if kind == "double_mass":
                d = r.daily
                return plots.plot_double_mass(
                    d["P1"].fillna(0).cumsum(),
                    d["P2"].fillna(0).cumsum(),
                    title="P1 vs P2 double mass")
        else:
            has_q = "Q" in df.columns and df["Q"].notna().any()
            if kind == "hydrograph":
                if not has_q:
                    return plots.plot_series(df.index, {"P [mm]": df["P"]})
                return plots.plot_catchment(r.daily)
            if kind == "fdc" and has_q:
                return plots.plot_fdc({"Q": _fdc(r.daily["Q"].dropna()).fdc})
            if kind == "idc":
                return plots.plot_idc(
                    {"P": _idc(r.hres.index, r.hres["P"].to_numpy())[0]})
            if kind == "regime":
                p = r.daily["P"].dropna()
                pm = monthly_rain(p.index, p.to_numpy()).avg_month
                qm = None
                if has_q:
                    q = r.daily["Q"].dropna()
                    mdays = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30,
                                      31, 30, 31])
                    qm = (monthly_flow(q.index, q.to_numpy()).avg_month
                          * mdays * 86400 / 1e6)
                return plots.plot_monthly_regime(pm, qm)
            if kind == "coverage":
                return plots.plot_gaps(
                    {c: no_voids(df.index, df[c].to_numpy())
                     for c in df.columns})
            if kind == "double_mass" and has_q and r.indices is not None:
                return plots.plot_double_mass(r.indices.cum_p,
                                              r.indices.cum_q_mm)
        raise ValueError(tr("no_results"))


class IndicesTab(QWidget):
    """Table of the 59 + 13 indices, copy/export."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        b_copy = QPushButton(tr("copy_table"))
        b_copy.clicked.connect(self._copy)
        b_save = QPushButton(tr("save_csv"))
        b_save.clicked.connect(self._save)
        row.addStretch(1)
        row.addWidget(b_copy)
        row.addWidget(b_save)
        lay.addLayout(row)
        self.table = QTableWidget()
        lay.addWidget(self.table)
        self._df = None

    def set_result(self, result, is_pair: bool):
        if is_pair:
            df = pd.concat([result.hydro, result.climate])
        else:
            frames = {}
            if result.indices is not None:
                frames["value"] = pd.concat([result.indices.hydro,
                                             result.indices.climate])
            elif result.climate is not None:
                frames["value"] = result.climate
            df = pd.DataFrame(frames)
        self._df = df
        self.table.setRowCount(len(df))
        self.table.setColumnCount(len(df.columns) + 1)
        self.table.setHorizontalHeaderLabels([tr("index"), *df.columns])
        for i, (name, row) in enumerate(df.iterrows()):
            self.table.setItem(i, 0, QTableWidgetItem(str(name)))
            for j, v in enumerate(row):
                txt = f"{v:.4f}" if isinstance(v, float) and np.isfinite(v) \
                    else str(v)
                self.table.setItem(i, j + 1, QTableWidgetItem(txt))
        self.table.resizeColumnsToContents()

    def _copy(self):
        if self._df is not None:
            QApplication.clipboard().setText(self._df.to_csv(sep="\t"))

    def _save(self):
        if self._df is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, tr("save_csv"),
                                              "indices.csv", "CSV (*.csv)")
        if path:
            self._df.to_csv(path)


class LogTab(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(5000)

    def append_line(self, line: str):
        self.appendPlainText(line)
