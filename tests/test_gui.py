"""Phase-6 GUI smoke tests (headless; skipped when PySide6 is missing).

Run with QT_QPA_PLATFORM=minimal (or offscreen where EGL is available).
"""

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pyside = pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "minimal")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gui"))

from PySide6.QtWidgets import QApplication  # noqa: E402

import imhea  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def synthetic_result():
    rng = np.random.default_rng(0)
    dq = pd.date_range("2021-01-01", periods=200 * 288, freq="5min")
    q = 8 + rng.random(len(dq))
    tips = pd.date_range("2021-01-01", periods=900, freq="4h")
    return imhea.workflow(2.0, dq, q, 0.2,
                          [(tips, np.full(900, 0.2)),
                           (tips + pd.Timedelta("1min"),
                            np.full(900, 0.2))],
                          compute_indices=True)


def test_main_window_and_tabs(qapp, synthetic_result, tmp_path):
    from imhea_gui.app import MainWindow
    from imhea_gui.project import CatchmentCfg, Project
    from imhea_gui.tabs import IndicesTab, ResultsTab

    win = MainWindow()
    win.project = Project("test")
    win.project.catchments["SYN_01"] = CatchmentCfg("SYN_01", area=2.0)
    win._show_workspace()
    win.project.results["SYN_01"] = synthetic_result
    win._tabs_for("SYN_01")
    win._push_result("SYN_01", synthetic_result)

    res = win._widget("SYN_01", ResultsTab)
    for i in range(len(ResultsTab.FIGS)):
        res.cmb_fig.setCurrentIndex(i)
        res._redraw()                       # no figure may raise
    idx = win._widget("SYN_01", IndicesTab)
    assert idx.table.rowCount() == 72       # 59 + 13

    # project persistence
    f = tmp_path / "t.imhea"
    win.project.save(f)
    from imhea_gui.project import Project as P2
    assert "SYN_01" in P2.load(f).catchments


def test_rating_dialog(qapp):
    from imhea_gui.dialogs import RatingCurveDialog
    dlg = RatingCurveDialog((0.30, 1.00), (1.37, 2.5, 1.77, 1.5))
    weir, coeff = dlg.values()
    assert weir == (0.30, 1.00) and coeff[1] == 2.5


def test_fill_report(qapp, synthetic_result):
    from imhea_gui.dialogs import FillReportDialog
    FillReportDialog(synthetic_result.fills or [])
    assert len(synthetic_result.fills) == 1     # one gauge pair
