import time
from pathlib import Path

import pandas as pd
import pytest

from moneygraph.run import run

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "project_docs" / "data"


@pytest.fixture(scope="session")
def pipeline(tmp_path_factory):
    out = tmp_path_factory.mktemp("out")
    t0 = time.perf_counter()
    ctx = run(DATA, out, verbose=False)
    elapsed = time.perf_counter() - t0
    return {
        "ctx": ctx,
        "out": out,
        "elapsed": elapsed,
        "nodes": pd.read_csv(out / "nodes_roles.csv"),
        "clusters": pd.read_csv(out / "clusters.csv"),
        "top": pd.read_csv(out / "top_nodes.csv"),
    }
