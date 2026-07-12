"""Background pipeline execution (QThread) with log capture."""

from __future__ import annotations

import logging
import time
import traceback

from PySide6.QtCore import QThread, Signal

import imhea


class _QtLogHandler(logging.Handler):
    def __init__(self, sig):
        super().__init__(level=logging.INFO)
        self._sig = sig

    def emit(self, record):
        try:
            self._sig.emit(self.format(record))
        except RuntimeError:
            pass


class PipelineRunner(QThread):
    """Runs workflow / workflow_rain / workflow_pair off the UI thread."""

    progress = Signal(str)                 #: log lines
    finished_ok = Signal(str, object, float)   #: node key, result, seconds
    failed = Signal(str, str)              #: node key, traceback

    def __init__(self, project, node_key: str, parent=None):
        super().__init__(parent)
        self.project = project
        self.node_key = node_key           #: catchment code or "pair:i"

    def run(self):
        handler = _QtLogHandler(self.progress)
        handler.setFormatter(logging.Formatter("%(message)s"))
        root = logging.getLogger("imhea")
        root.addHandler(handler)
        root.setLevel(logging.INFO)
        t0 = time.time()
        try:
            result = self._execute()
            self.finished_ok.emit(self.node_key, result, time.time() - t0)
        except Exception:
            self.failed.emit(self.node_key, traceback.format_exc())
        finally:
            root.removeHandler(handler)

    def _execute(self):
        p = self.project
        if self.node_key.startswith("pair:"):
            i = int(self.node_key.split(":")[1])
            pair = p.pairs[i]
            for code in (pair.code1, pair.code2):
                if code not in p.results:
                    self.progress.emit(f"processing {code} first…")
                    p.results[code] = self._run_catchment(code)
            r1 = p.results[pair.code1]
            r2 = p.results[pair.code2]
            self.progress.emit(f"pairing {pair.label}…")
            return imhea.workflow_pair(r1.hres, r2.hres,
                                       matlab_compat=p.matlab_compat)
        return self._run_catchment(self.node_key)

    def _run_catchment(self, code: str):
        p = self.project
        cfg = p.catchments[code]
        self.progress.emit(f"loading raw files for {code}…")
        dates_q, q, gauges = p.load_raw(code)
        if cfg.rain_only:
            return imhea.workflow_rain(cfg.bucket, gauges, name=code)
        return imhea.workflow(cfg.area, dates_q, q, cfg.bucket, gauges,
                              name=code, matlab_compat=p.matlab_compat)
