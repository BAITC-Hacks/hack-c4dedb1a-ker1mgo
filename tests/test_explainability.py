"""Rule boundaries, exported evidence and faithful capped-flow path attribution."""

import copy
import math
from types import SimpleNamespace

import networkx as nx
import numpy as np
import pandas as pd
import pytest

from moneygraph import roles, seed_paths, taint
from moneygraph.data import load_config


def row(**changes):
    values = dict(
        gid=10,
        in_deg=1,
        out_deg=9,
        pays_seed=0,
        cycle_with_seeds=0,
        n_seed_sources=0,
        betweenness=0,
        is_seed=False,
        pass_through=10.0,
        fast_pass_share=0.0,
        depth=1,
        p_has_out=math.nan,
    )
    values.update(changes)
    return pd.Series(values)


def config():
    cfg = load_config()
    return dict(cfg["roles"], fast_pass_days=cfg["temporal"]["fast_pass_days"])


def test_trace_follows_order_and_same_rule_predicates():
    c = config()
    r = row(
        pays_seed=c["coordinator"]["min_pays_seed"],
        n_seed_sources=c["coordinator"]["min_seed_sources"],
        out_deg=c["distributor"]["min_out_deg"],
    )
    trace = roles.explain(r, c, 1)
    assignment = roles.assign(r, c, 1, trace)
    assert assignment[0] == trace["matched_rule"] == "coordinator"
    assert "distributor" in assignment[2]
    for rule in trace["rules"]:
        assert rule["matched"] == (roles.rule(rule["role"], r, c, 1) is not None)


def test_nearest_rule_reports_real_deficit_and_changes_with_config():
    c = config()
    threshold = c["distributor"]["min_out_deg"]
    r = row(out_deg=threshold - 1)
    nearest = roles.explain(r, c, 1)["nearest_rule"]
    assert nearest["role"] == "distributor"
    check = next(c for c in nearest["conditions"] if c["label"] == "Recipients")
    assert check["deficit"] == 1
    assert check["threshold"] == threshold
    assert not check["passed"]
    changed = copy.deepcopy(c)
    changed["distributor"]["min_out_deg"] = threshold - 1
    assert roles.rule("distributor", r, changed, 1) is not None
    assert roles.explain(r, changed, 1)["matched_rule"] == "distributor"


def test_terminal_strict_boundary_and_or_branch():
    c = config()
    threshold = c["terminal"]["max_p_has_out"]
    r = row(out_deg=0, depth=4, p_has_out=threshold)
    trace = roles.explain(r, c, 1)
    terminal = next(rule for rule in trace["rules"] if rule["role"] == "terminal")
    assert not terminal["matched"]
    assert terminal["distance"] > 0
    r["p_has_out"] = np.nextafter(threshold, 0)
    assert roles.explain(r, c, 1)["matched_rule"] == "terminal"
    # The alternative structural branch is enough, despite unavailable ratio data.
    r = row(in_deg=c["consolidator"]["min_in_deg"], out_deg=0, pass_through=math.nan)
    assert roles.explain(r, c, 1)["matched_rule"] == "consolidator"


def test_seed_trace_never_uses_pass_through_values():
    c = config()
    reference = None
    for pt in [math.nan, 0.1, 1.0, 1000.0]:
        r = row(is_seed=True, in_deg=6, out_deg=1, pass_through=pt)
        trace = roles.explain(r, c, 1)
        result = roles.assign(r, c, 1, trace)
        assert reference is None or result == reference
        reference = result
        for rule in trace["rules"]:
            for check in rule["conditions"]:
                if check["field"] == "pass_through":
                    assert check["value"] is None and not check["applicable"]


def test_real_data_traces_and_priority_reconcile(pipeline):
    ctx = pipeline["ctx"]
    for node in ctx.features.itertuples(index=False):
        trace = ctx.rule_traces[str(node.gid)]
        assert trace["role"] == node.role
        assert (trace["matched_rule"] or "peripheral") == node.role
        matching = [rule["role"] for rule in trace["rules"] if rule["matched"]]
        assert not matching or matching[0] == node.role
        audit = ctx.priority_audit[str(node.gid)]
        assert audit["weighted_sum"] == pytest.approx(sum(audit["components"].values()))
        assert audit["weighted_sum"] * audit["seed_factor"] / audit[
            "normalization_factor"
        ] == pytest.approx(node.priority_score)


def context(edges, seeds, rounds=6, top_k=3):
    graph = nx.DiGraph()
    graph.add_weighted_edges_from(edges, weight="sum_kzt")
    cfg = load_config()
    cfg["taint"]["rounds"] = rounds
    cfg["explainability"]["top_seed_paths"] = top_k
    return SimpleNamespace(G=graph, seeds=set(seeds), cfg=cfg)


def test_flow_paths_use_proportional_caps_not_edge_minimum():
    ctx = context([(1, 2, 100), (7, 2, 100), (2, 3, 40), (2, 4, 10)], {1, 7})
    output = seed_paths.build(ctx)
    paths = output["nodes"]["3"]
    # Two seed contributions compete for 50 outflow, and 80% then goes to 3.
    assert [p["kzt"] for p in paths["paths"]] == pytest.approx([20, 20])
    assert paths["seed_flow_in"] == pytest.approx(40)
    assert paths["coverage"] == pytest.approx(1)
    assert all(isinstance(gid, str) for p in paths["paths"] for gid in p["gids"])


def test_flow_paths_cycles_horizon_top_k_and_seed_reset():
    ctx = context([(1, 2, 100), (2, 3, 100), (3, 2, 50), (3, 4, 50)], {1}, rounds=6, top_k=1)
    output = seed_paths.build(ctx)
    expected = taint.propagate(ctx.G, ctx.seeds, 6)
    for gid, node in output["nodes"].items():
        assert node["seed_flow_in"] == pytest.approx(expected[int(gid)])
        assert node["shown_kzt"] + node["omitted_kzt"] == pytest.approx(node["seed_flow_in"])
        assert all(p["hops"] <= 6 for p in node["paths"])
    assert output["nodes"]["2"]["omitted_kzt"] > 0
    ctx.cfg["explainability"]["top_seed_paths"] = 20
    output = seed_paths.build(ctx)
    assert any(p["contains_cycle"] for node in output["nodes"].values() for p in node["paths"])
    reset = context([(1, 2, 100), (2, 3, 40)], {1, 2})
    assert seed_paths.build(reset)["nodes"]["3"]["paths"][0]["gids"] == ["2", "3"]


def test_seed_bitsets_equal_directed_reachability_with_cycles():
    graph = nx.gnp_random_graph(30, 0.08, seed=17, directed=True)
    seeds = {0, 3, 7}
    expected = {
        gid: sum(gid != seed and nx.has_path(graph, seed, gid) for seed in seeds) for gid in graph
    }
    assert taint.seed_source_counts(graph, seeds) == expected


def test_export_contract_is_complete_and_finite(pipeline):
    import json

    out, ctx = pipeline["out"], pipeline["ctx"]

    def reject_constant(value):
        raise AssertionError(f"Non-standard JSON constant: {value}")

    trace = json.loads((out / "rule_traces.json").read_text(), parse_constant=reject_constant)
    paths = json.loads((out / "seed_paths.json").read_text(), parse_constant=reject_constant)
    expected = set(ctx.features.gid.astype(str))
    assert set(trace["nodes"]) == set(paths["nodes"]) == expected
    pd.testing.assert_frame_equal(pd.read_parquet(out / "edges.parquet"), ctx.edges)
    pd.testing.assert_frame_equal(
        pd.read_parquet(out / "transactions.parquet"), ctx.tx, check_dtype=False
    )
    for gid, record in trace["nodes"].items():
        assert "hypothesis" in record["dossier"]
        if record["role"] == "peripheral":
            assert record["fallback"]["matched"]
        assert paths["nodes"][gid]["shown_kzt"] <= paths["nodes"][gid]["seed_flow_in"] + 1e-6
    assert list(pipeline["nodes"].columns) == [
        "gid",
        "role",
        "role_score",
        "cluster_id",
        "priority_score",
        "evidence",
        "role_detail",
        "secondary_roles",
        "depth",
        "is_seed",
    ]
    assert list(pipeline["top"].columns) == [
        "rank",
        "gid",
        "role",
        "priority_score",
        "why",
        "cluster_id",
        "evidence",
    ]
    assert list(pipeline["clusters"].columns) == [
        "cluster_id",
        "n_nodes",
        "n_seed",
        "sum_kzt_internal",
        "top_gids",
        "hypothesis",
        "dominant_roles",
        "seed_flow_in",
    ]
