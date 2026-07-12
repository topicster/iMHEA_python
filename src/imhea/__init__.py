"""imhea — processing of iMHEA hydrometeorological data.

Python translation of the iMHEA MATLAB scripts (Ochoa-Tocachi et al. 2018,
Scientific Data 5:180080). Phase 2 modules: I/O, cleaning, aggregation,
stage-discharge. Analysis (baseflow, indices) arrives in Phase 3.
"""

from .aggregate import AggResult, aggregate, aggregate_events, average
from .clean import (FillResult, depure, fill_gaps, monitoring_gaps, no_voids,
                    pair_overlap, voids)
from .flow import (BaseflowResult, baseflow_chapman, baseflow_ukih,
                   level2flow, recession_constant)
from .indices import (CLIMATE_NAMES, HYDRO_NAMES, CatchmentIndices,
                      climate_p, climate_total, indices_plus, indices_total,
                      pair, process_p, process_q)
from .io import (read_processed_csv, read_raw_csv, save_daily_csv,
                 save_double_csv, save_single_csv)
from .stats import (FDCResult, MonthlyResult, PulseResult, fdc, idc,
                    monthly_flow, monthly_rain, pulse)
from .workflow import (PairResult, WorkflowResult, export_pair,
                       export_single, workflow, workflow_pair, workflow_rain)
from . import registry

__version__ = "1.0.0"

__all__ = [
    "AggResult", "BaseflowResult", "CatchmentIndices", "FDCResult",
    "FillResult", "MonthlyResult", "PulseResult",
    "CLIMATE_NAMES", "HYDRO_NAMES",
    "aggregate", "aggregate_events", "average",
    "baseflow_chapman", "baseflow_ukih", "recession_constant",
    "climate_p", "climate_total", "depure", "fdc", "fill_gaps", "idc",
    "indices_plus", "indices_total", "level2flow", "monitoring_gaps",
    "monthly_flow", "monthly_rain", "no_voids", "pair", "pair_overlap",
    "process_p", "process_q", "pulse", "voids",
    "read_processed_csv", "read_raw_csv",
    "save_daily_csv", "save_double_csv", "save_single_csv",
    "PairResult", "WorkflowResult", "export_pair", "export_single",
    "workflow", "workflow_pair", "workflow_rain", "registry",
]
