"""Dialogs: rating-curve editor and gap-filling report."""

from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout,
                               QHBoxLayout, QLabel, QDoubleSpinBox,
                               QTableWidget, QTableWidgetItem, QVBoxLayout)

from imhea import level2flow

from .i18n import tr


class RatingCurveDialog(QDialog):
    """Edit weir dimensions/coefficients with a live level->flow preview."""

    def __init__(self, weir, coeff, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("rating_title"))
        self.resize(560, 420)
        lay = QVBoxLayout(self)

        form = QFormLayout()
        self._spins = {}
        fields = [("a", tr("vnotch_h"), weir[0], 0.01),
                  ("b", tr("rect_w"), weir[1], 0.01),
                  ("C1", "C1", coeff[0], 0.01), ("e1", "e1", coeff[1], 0.1),
                  ("C2", "C2", coeff[2], 0.01), ("e2", "e2", coeff[3], 0.1)]
        row = QHBoxLayout()
        for key, label, val, step in fields:
            sb = QDoubleSpinBox()
            sb.setDecimals(3)
            sb.setRange(0.0, 100.0)
            sb.setSingleStep(step)
            sb.setValue(float(val))
            sb.valueChanged.connect(self._redraw)
            self._spins[key] = sb
            form.addRow(label, sb)
        lay.addLayout(form)
        lay.addLayout(row)

        self._canvas = FigureCanvasQTAgg(Figure(figsize=(5, 2.6)))
        lay.addWidget(self._canvas)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok
                                   | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self._redraw()

    def values(self):
        s = {k: sb.value() for k, sb in self._spins.items()}
        return (s["a"], s["b"]), (s["C1"], s["e1"], s["C2"], s["e2"])

    def _redraw(self):
        weir, coeff = self.values()
        wl = np.linspace(0, max(2 * weir[0], 0.6) * 100, 200)  # cm
        q = level2flow(wl, weir, coeff)
        fig = self._canvas.figure
        fig.clear()
        ax = fig.add_subplot(111)
        ax.plot(wl, q, lw=1.4)
        ax.axvline(weir[0] * 100, ls=":", lw=0.8, color="grey")
        ax.set_xlabel("Level [cm]")
        ax.set_ylabel("Q [l/s]")
        ax.grid(alpha=0.3)
        fig.tight_layout()
        self._canvas.draw_idle()


class FillReportDialog(QDialog):
    """Table of double-mass gap-filling attempts of the last run."""

    def __init__(self, fills, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("fills_title"))
        self.resize(620, 300)
        lay = QVBoxLayout(self)
        if not fills:
            lay.addWidget(QLabel(tr("fills_none")))
        else:
            table = QTableWidget(len(fills), 6)
            table.setHorizontalHeaderLabels(
                ["Pair", "Filled", "R", "Slope M", "n filled 1", "n filled 2"])
            for i, f in enumerate(fills):
                vals = [f"{f.pair[0]} ↔ {f.pair[1]}",
                        "yes" if f.filled else "no (R < 0.99)"
                        if not np.isnan(f.r) else "no overlap",
                        f"{f.r:.4f}" if np.isfinite(f.r) else "—",
                        f"{f.slope:.4f}" if np.isfinite(f.slope) else "—",
                        str(f.n_filled[0]), str(f.n_filled[1])]
                for j, v in enumerate(vals):
                    table.setItem(i, j, QTableWidgetItem(v))
            table.resizeColumnsToContents()
            lay.addWidget(table)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.clicked.connect(self.accept)
        lay.addWidget(buttons)
