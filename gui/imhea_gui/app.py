"""iMHEA Data Processor — main application window."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog,
                               QHBoxLayout, QInputDialog, QLabel,
                               QMainWindow, QMessageBox, QPushButton,
                               QSplitter, QStackedWidget, QStatusBar,
                               QTabWidget, QToolBar, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

import imhea

from . import i18n
from .i18n import tr
from .project import CatchmentCfg, PairCfg, Project
from .runner import PipelineRunner
from .tabs import IndicesTab, LogTab, ResultsTab, SetupTab

ROLE_KEY = Qt.UserRole


class StartScreen(QWidget):
    def __init__(self, main):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addStretch(2)
        title = QLabel(tr("app_title"))
        title.setStyleSheet("font-size: 26px; font-weight: 500;")
        title.setAlignment(Qt.AlignCenter)
        sub = QLabel(tr("start_sub"))
        sub.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)
        lay.addWidget(sub)
        lay.addSpacing(24)
        for key, slot in (("start_process", main.new_project),
                          ("start_explore", main.explore_network),
                          ("start_open", main.open_project)):
            b = QPushButton(tr(key))
            b.setMinimumWidth(280)
            b.clicked.connect(slot)
            row = QHBoxLayout()
            row.addStretch(1)
            row.addWidget(b)
            row.addStretch(1)
            lay.addLayout(row)
        lay.addStretch(3)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr("app_title"))
        self.resize(1180, 720)
        self.project: Project | None = None
        self.runner: PipelineRunner | None = None
        self._node_tabs: dict[str, QTabWidget] = {}

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.start = StartScreen(self)
        self.stack.addWidget(self.start)

        self._build_toolbar()
        self.setStatusBar(QStatusBar())

    # -- chrome ------------------------------------------------------------
    def _build_toolbar(self):
        tb = QToolBar()
        tb.setMovable(False)
        self.addToolBar(tb)
        self.act_run = tb.addAction(tr("run"), self.run_selected)
        self.act_export = tb.addAction(tr("export"), self.export_selected)
        tb.addSeparator()
        tb.addAction(tr("save_project"), self.save_project)
        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy().horizontalPolicy(),
                             spacer.sizePolicy().verticalPolicy())
        self.cmb_lang = QComboBox()
        self.cmb_lang.addItems(["EN", "ES"])
        self.cmb_lang.setCurrentIndex(1 if i18n.LANG == "es" else 0)
        self.cmb_lang.activated.connect(self._switch_lang)
        tb.addWidget(self.cmb_lang)

    def _switch_lang(self, i):
        i18n.set_lang("es" if i == 1 else "en")
        QMessageBox.information(
            self, tr("app_title"),
            "Language will apply to new windows and tabs." if i == 0 else
            "El idioma se aplicará a nuevas ventanas y pestañas.")

    # -- project lifecycle ---------------------------------------------------
    def new_project(self):
        name, ok = QInputDialog.getText(self, tr("new_project"),
                                        tr("new_project"))
        if ok:
            self.project = Project(name or "untitled")
            self._show_workspace()

    def explore_network(self):
        root = QFileDialog.getExistingDirectory(self, tr("data_root"))
        if root and (Path(root) / "iMHEA_raw").is_dir():
            self.project = Project.from_registry(root)
            self._show_workspace()
        elif root:
            QMessageBox.warning(self, tr("app_title"),
                                f"iMHEA_raw not found in {root}")

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("start_open"),
                                              filter="iMHEA project (*.imhea)")
        if path:
            self.project = Project.load(path)
            self._show_workspace()

    def save_project(self):
        if not self.project:
            return
        path = self.project.path
        if path is None:
            p, _ = QFileDialog.getSaveFileName(
                self, tr("save_project"), f"{self.project.name}.imhea",
                "iMHEA project (*.imhea)")
            if not p:
                return
            path = p
        self.project.save(path)
        self.statusBar().showMessage(f"Saved {path}", 4000)

    # -- workspace -----------------------------------------------------------
    def _show_workspace(self):
        self.split = QSplitter()
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(210)
        self.tree.itemSelectionChanged.connect(self._select_node)
        self._rebuild_tree()

        side = QWidget()
        sl = QVBoxLayout(side)
        sl.setContentsMargins(4, 4, 4, 4)
        sl.addWidget(self.tree)
        for key, slot in (("add_catchment", self._add_catchment),
                          ("add_rain", self._add_rain),
                          ("add_pair", self._add_pair)):
            b = QPushButton("+ " + tr(key))
            b.clicked.connect(slot)
            sl.addWidget(b)

        self.center = QStackedWidget()
        self.center.addWidget(QLabel(tr("no_results")))
        self.split.addWidget(side)
        self.split.addWidget(self.center)
        self.split.setStretchFactor(1, 1)
        self.stack.addWidget(self.split)
        self.stack.setCurrentWidget(self.split)

    def _rebuild_tree(self):
        self.tree.clear()
        top_c = QTreeWidgetItem([tr("catchments")])
        top_r = QTreeWidgetItem([tr("rain_stations")])
        top_p = QTreeWidgetItem([tr("pairs")])
        for code, cfg in sorted(self.project.catchments.items()):
            item = QTreeWidgetItem([code])
            item.setData(0, ROLE_KEY, code)
            (top_r if cfg.rain_only else top_c).addChild(item)
        for i, pair in enumerate(self.project.pairs):
            item = QTreeWidgetItem([pair.label])
            item.setData(0, ROLE_KEY, f"pair:{i}")
            top_p.addChild(item)
        for t in (top_c, top_p, top_r):
            self.tree.addTopLevelItem(t)
            t.setExpanded(True)

    def _selected_key(self) -> str | None:
        items = self.tree.selectedItems()
        return items[0].data(0, ROLE_KEY) if items else None

    def _select_node(self):
        key = self._selected_key()
        if key is None:
            return
        self.center.setCurrentWidget(self._tabs_for(key))

    def _tabs_for(self, key: str) -> QTabWidget:
        if key not in self._node_tabs:
            tabs = QTabWidget()
            if not key.startswith("pair:"):
                tabs.addTab(SetupTab(self.project, key), tr("setup"))
            tabs.addTab(ResultsTab(), tr("results"))
            tabs.addTab(IndicesTab(), tr("indices"))
            tabs.addTab(LogTab(), tr("log"))
            self._node_tabs[key] = tabs
            self.center.addWidget(tabs)
            if key in self.project.results:
                self._push_result(key, self.project.results[key])
        return self._node_tabs[key]

    def _widget(self, key, cls):
        tabs = self._tabs_for(key)
        for i in range(tabs.count()):
            if isinstance(tabs.widget(i), cls):
                return tabs.widget(i)
        return None

    # -- node management -------------------------------------------------
    def _add_catchment(self, *, rain_only=False):
        code, ok = QInputDialog.getText(self, tr("add_catchment"), tr("code"))
        if ok and code and code not in self.project.catchments:
            self.project.catchments[code] = CatchmentCfg(
                code=code, flow_files=[] if rain_only else [])
            self._rebuild_tree()

    def _add_rain(self):
        self._add_catchment(rain_only=True)

    def _add_pair(self):
        codes = [c for c, cfg in self.project.catchments.items()
                 if not cfg.rain_only]
        if len(codes) < 2:
            return
        c1, ok = QInputDialog.getItem(self, tr("add_pair"), "1:", codes,
                                      editable=False)
        if not ok:
            return
        c2, ok = QInputDialog.getItem(self, tr("add_pair"), "2:",
                                      [c for c in codes if c != c1],
                                      editable=False)
        if ok:
            self.project.pairs.append(PairCfg(c1, c2))
            self._rebuild_tree()

    # -- run/export --------------------------------------------------------
    def run_selected(self):
        key = self._selected_key()
        if key is None or self.project is None:
            return
        if self.runner and self.runner.isRunning():
            return
        self.act_run.setEnabled(False)
        self.statusBar().showMessage(tr("running"))
        log = self._widget(key, LogTab)
        self.runner = PipelineRunner(self.project, key, self)
        if log is not None:
            self.runner.progress.connect(log.append_line)
        self.runner.finished_ok.connect(self._run_done)
        self.runner.failed.connect(self._run_failed)
        self.runner.start()

    def _run_done(self, key, result, secs):
        self.project.results[key] = result
        self._push_result(key, result)
        self.act_run.setEnabled(True)
        self.statusBar().showMessage(f"{tr('done_in')} {secs:.1f} s")

    def _push_result(self, key, result):
        is_pair = key.startswith("pair:")
        res_tab = self._widget(key, ResultsTab)
        idx_tab = self._widget(key, IndicesTab)
        if res_tab is not None:
            res_tab.set_result(result, is_pair)
        if idx_tab is not None:
            idx_tab.set_result(result, is_pair)

    def _run_failed(self, key, tb_text):
        log = self._widget(key, LogTab)
        if log is not None:
            log.append_line(tb_text)
        self.act_run.setEnabled(True)
        self.statusBar().showMessage(tr("failed"))
        QMessageBox.critical(self, tr("failed"), tb_text.splitlines()[-1])

    def export_selected(self):
        key = self._selected_key()
        result = self.project.results.get(key) if self.project else None
        if result is None:
            return
        out = QFileDialog.getExistingDirectory(self, tr("export"))
        if not out:
            return
        if key.startswith("pair:"):
            pair = self.project.pairs[int(key.split(":")[1])]
            imhea.export_pair(out, pair.code1[:3], result)
        else:
            from imhea.workflow import export_catchment
            export_catchment(out, key, result)
        self.statusBar().showMessage(f"{tr('export_done')} {out}", 6000)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("iMHEA Data Processor")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
