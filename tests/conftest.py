import time

import pandas as pd
import pytest

from moneygraph.paths import DATA_DIR
from moneygraph.run import run


@pytest.fixture(scope="session")
def pipeline(tmp_path_factory):
    out = tmp_path_factory.mktemp("out")
    t0 = time.perf_counter()
    ctx = run(DATA_DIR, out, verbose=False)
    elapsed = time.perf_counter() - t0
    return {
        "ctx": ctx,
        "out": out,
        "elapsed": elapsed,
        "nodes": pd.read_csv(out / "nodes_roles.csv"),
        "clusters": pd.read_csv(out / "clusters.csv"),
        "top": pd.read_csv(out / "top_nodes.csv"),
    }
