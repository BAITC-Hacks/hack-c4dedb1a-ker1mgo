from moneygraph import ROLES
from moneygraph.export import CLUSTER_COLS, NODES_COLS, TOP_COLS


def test_runtime_under_limit(pipeline):
    assert pipeline["elapsed"] < 300


def test_nodes_roles_schema(pipeline):
    n = pipeline["nodes"]
    assert len(n) == 2248
    assert list(n.columns[: len(NODES_COLS)]) == NODES_COLS
    assert n[NODES_COLS].notna().all().all()
    assert n.gid.is_unique
    assert n.role.isin(ROLES).all()
    assert n.role_score.between(0, 1).all()
    assert n.priority_score.between(0, 1).all()


def test_evidence_has_numbers_and_fits(pipeline):
    ev = pipeline["nodes"].evidence.astype(str)
    assert ev.str.len().between(1, 200).all()
    assert ev.str.contains(r"\d").all()


def test_clusters_consistent(pipeline):
    c, n = pipeline["clusters"], pipeline["nodes"]
    assert list(c.columns[: len(CLUSTER_COLS)]) == CLUSTER_COLS
    assert c.hypothesis.notna().all()
    assert set(n.cluster_id) == set(c.cluster_id)
    assert c.n_nodes.sum() == len(n)


def test_top_nodes(pipeline):
    t = pipeline["top"]
    assert len(t) >= 20
    assert list(t.columns[: len(TOP_COLS)]) == TOP_COLS
    assert t.priority_score.is_monotonic_decreasing
    assert t["rank"].tolist() == list(range(1, len(t) + 1))
    assert t.why.notna().all()
