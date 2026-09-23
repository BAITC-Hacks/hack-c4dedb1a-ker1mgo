import pandas as pd
import pytest

from agent.store import GraphStore

# five payers -> collector C -> sink S, plus a seed that pays C and one isolated node
P = [11, 12, 13, 14, 15]
C, S, SEED, ISO = 20, 30, 1, 99


@pytest.fixture
def store():
    edges = [(p, C, 1000.0 * (i + 1), 1) for i, p in enumerate(P)] + [(C, S, 9000.0, 3), (SEED, C, 500.0, 1)]
    edges = pd.DataFrame(edges, columns=["src", "dst", "sum_kzt", "n_tx"])
    gids = P + [C, S, SEED, ISO]
    feats = pd.DataFrame({
        "gid": gids,
        "depth": [2] * 5 + [1, 2, 0, 1],
        "is_seed": [g == SEED for g in gids],
        "role": ["peripheral"] * 5 + ["consolidator", "terminal", "peripheral", "peripheral"],
        "priority_score": [0.1, 0.2, 0.3, 0.4, 0.5, 0.9, 0.6, 0.7, 0.0],
        "why": ["x"] * 9,
        "cluster_id": [1] * 8 + [0],
        "in_kzt": [0, 0, 0, 0, 0, 15500, 9000, 0, 0],
        "out_kzt": [1000, 2000, 3000, 4000, 5000, 9000, 0, 500, 0],
        "prio_components": ['{"seed_flow": 0.3}'] + ["{}"] * 8,
    })
    tx = pd.DataFrame({
        "src": [11, 20, 20], "dst": [20, 30, 30],
        "date": ["2026-07-01", "2026-07-02", "2026-07-02"], "sum_kzt": [1000.0, 4000.0, 5000.0],
    })
    return GraphStore(feats, edges, tx)


def test_get_node(store):
    n = store.get_node(str(C))
    assert n["role"] == "consolidator" and n["gid"] == C
    assert store.get_node(12345) is None
    assert store.has(" 20 ") and not store.has("abc")


def test_neighbors(store):
    nb = store.neighbors(C)
    assert set(nb[nb.direction == "in"].gid) == set(P) | {SEED}
    assert nb[nb.direction == "out"].gid.tolist() == [S]
    assert nb.sum_kzt.is_monotonic_decreasing


def test_ego_and_isolated(store):
    assert set(store.ego(C, 1)) == set(P) | {C, S, SEED}
    assert set(store.ego(ISO, 2)) == {ISO}
    assert len(store.ego(C, 2, max_nodes=3)) == 3


def test_paths_between(store):
    paths = store.paths_between(11, S)
    assert paths == [[11, C, S]]
    assert store.paths_between(S, 11) == [[11, C, S]]
    assert store.paths_between(11, ISO) == []


def test_common_collectors(store):
    cc = store.common_collectors(P)
    assert cc.gid.tolist()[:2] == [C, S]
    assert cc.iloc[0].n_sources == 5 and cc.iloc[0].min_hops == 1
    assert store.common_collectors([11, 12], max_hops=1).gid.tolist() == [C]


def test_top_and_timeline(store):
    assert store.top_nodes(2).gid.tolist() == [C, SEED]
    assert store.top_nodes(1, include_seeds=False).gid.tolist() == [C]
    tl = store.tx_timeline(C)
    assert tl.in_kzt.sum() == 1000 and tl.out_kzt.sum() == 9000 and len(tl) == 2
    assert store.prio_components(11) == {"seed_flow": 0.3}
