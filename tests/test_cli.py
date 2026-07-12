"""Phase-7 CLI tests."""

import numpy as np
import pandas as pd
import pytest

from imhea.cli import main


def _write_raw(path, dates, values, header="Date,Event mm,Flag"):
    lines = [header]
    for d, v in zip(dates, values):
        lines.append(f"{d:%d/%m/%Y %H:%M:%S},{v},")
    path.write_text("\r".join(lines))          # CR-only, like real files


def test_cli_process_rain_only(tmp_path):
    d = pd.date_range("2021-01-01", periods=800, freq="4h")
    _write_raw(tmp_path / "rg.csv", d, np.full(800, 0.2))
    rc = main(["process", "--code", "TST_01", "--bucket", "0.2",
               "--gauge", str(tmp_path / "rg.csv"),
               "--out", str(tmp_path / "out")])
    assert rc == 0
    out = {p.name for p in (tmp_path / "out").iterdir()}
    assert "iMHEA_TST_01_1day_processed.csv" in out
    assert "iMHEA_TST_01_indices.csv" in out


def test_cli_process_with_flow(tmp_path):
    d = pd.date_range("2021-01-01", periods=800, freq="4h")
    _write_raw(tmp_path / "rg.csv", d, np.full(800, 0.2))
    dq = pd.date_range("2021-01-01", periods=200 * 288, freq="5min")
    rng = np.random.default_rng(1)
    _write_raw(tmp_path / "q.csv", dq,
               np.round(8 + rng.random(len(dq)), 3),
               header="Date,Flow l/s,Flag")
    rc = main(["process", "--code", "TST_02", "--area", "2.0",
               "--flow", str(tmp_path / "q.csv"),
               "--gauge", str(tmp_path / "rg.csv"),
               "--out", str(tmp_path / "out")])
    assert rc == 0
    idx = pd.read_csv(tmp_path / "out" / "iMHEA_TST_02_indices.csv",
                      index_col=0)
    assert len(idx) == 72


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
