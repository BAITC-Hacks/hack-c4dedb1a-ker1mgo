"""One small toy graph per role, run through the real pipeline steps up to roles."""

import math
from types import SimpleNamespace

import networkx as nx
import pandas as pd

from moneygraph import features, roles, taint, temporal, truncation
from moneygraph.data import Context, build_graph, load_config

DAY = "2026-07-0{}"


def toy(transfers, depth, seeds):
    """transfers: (src, dst, kzt, day); depth: {gid: depth}; seeds: set of gids."""
    tx = pd.DataFrame(transfers, columns=["src", "dst", "sum_kzt", "day"])
    tx["date"] = pd.to_datetime(tx.day.map(DAY.format))
    tx = tx.drop(columns="day")
    edges = (
        tx.groupby(["src", "dst"])
        .agg(sum_kzt=("sum_kzt", "sum"), n_tx=("sum_kzt", "size"))
        .reset_index()
    )
    edges["depth"] = edges.dst.map(depth)
    nodes = pd.DataFrame({"gid": list(depth), "depth": list(depth.values())})
    nodes["is_seed"] = nodes.gid.isin(seeds)
    ctx = Context(
        edges=edges,
        nodes=nodes,
        tx=tx,
        G=build_graph(edges, nodes),
        cfg=load_config(),
        seeds=set(seeds),
    )
    for step in [features, temporal, taint, truncation, roles]:
        ctx.features = ctx.features.merge(step.compute(ctx), on="gid", how="left")
    return ctx.features.set_index("gid")


def role_of(f, gid):
    return f.loc[gid, "role"], f.loc[gid, "role_detail"]


def test_coordinator_pays_back_into_seeds():
    # two seeds pay 10, and 10 sends money back into both of them
    both = [(1, 10, 100_000, 1), (2, 10, 80_000, 1), (10, 1, 50_000, 2), (10, 2, 40_000, 2)]
    f = toy(both, {1: 0, 2: 0, 10: 1}, {1, 2})
    assert role_of(f, 10)[0] == "coordinator"

    # paying back into a single seed is not enough (min_pays_seed = 2)
    f = toy(both[:3], {1: 0, 2: 0, 10: 1}, {1, 2})
    assert role_of(f, 10)[0] != "coordinator"


def test_distributor_fans_out():
    fan = [(10, 100 + i, 9_000, 2) for i in range(12)]
    f = toy([(1, 10, 120_000, 1)] + fan, {1: 0, 10: 1, **{100 + i: 2 for i in range(12)}}, {1})
    assert role_of(f, 10)[0] == "distributor"


def test_consolidator_collects_and_holds():
    payers = [(i, 10, 100_000, 1) for i in range(1, 7)]
    f = toy(
        payers + [(10, 20, 50_000, 3)],
        {**{i: 0 for i in range(1, 7)}, 10: 1, 20: 2},
        set(range(1, 7)),
    )
    assert role_of(f, 10)[0] == "consolidator"


def test_transit_passes_money_on():
    f = toy([(1, 10, 100_000, 1), (10, 20, 95_000, 2)], {1: 0, 10: 1, 20: 2}, {1})
    assert role_of(f, 10)[0] == "transit"


def test_fast_pass_above_cap_is_not_transit():
    # 10 forwards its inflow the next day but sends 5x what it received: money from outside the graph
    f = toy([(1, 10, 100_000, 1), (10, 20, 500_000, 2)], {1: 0, 10: 1, 20: 2}, {1})
    assert role_of(f, 10) == ("peripheral", "weak_signal")
    assert "transit" in f.loc[10, "secondary_roles"]


def test_observed_sink_is_terminal_observed():
    f = toy([(1, 10, 100_000, 1)], {1: 0, 10: 1}, {1})
    assert role_of(f, 10) == ("terminal", "terminal_observed")


def test_depth4_sink_is_never_terminal_observed():
    chain = [(1, 11, 100_000, 1), (11, 12, 90_000, 2), (12, 13, 80_000, 3), (13, 14, 70_000, 4)]
    f = toy(chain, {1: 0, 11: 1, 12: 2, 13: 3, 14: 4}, {1})
    assert role_of(f, 14)[1] != "terminal_observed"

    c = dict(load_config()["roles"], fast_pass_days=2)
    row = f.loc[14].copy()
    row["gid"] = 14
    for p, expect in [
        (math.nan, "truncated_unknown"),
        (0.1, "terminal_inferred"),
        (0.45, "truncated_unknown"),
        (0.9, "truncated_likely_forwarding"),
    ]:
        row["p_has_out"] = p
        assert roles.assign(row, c, bt_thr=1.0)[1] == expect, p


def test_seed_role_ignores_inflow_and_pass_through():
    payers = [(i, 1, 100_000, 1) for i in range(20, 26)]
    f = toy(payers + [(1, 10, 10_000, 2)], {1: 0, 10: 1, **{i: 1 for i in range(20, 26)}}, {1})
    c = dict(load_config()["roles"], fast_pass_days=2)
    row = f.loc[1].copy()
    row["gid"] = 1
    assert math.isnan(row.pass_through)
    results = set()
    for in_kzt, pt in [(0.0, math.nan), (1e9, 0.01), (1.0, 1.0), (5e5, 50.0)]:
        row["in_kzt"], row["pass_through"] = in_kzt, pt
        role, detail, _, score = roles.assign(row, c, bt_thr=1.0)
        ev = roles.evidence(row, role, detail, c)
        assert roles.kzt(in_kzt) + " in" not in ev
        results.add((role, detail, score))
    assert len(results) == 1


def test_coordinator_evidence_counts_tied_betweenness():
    transfers = [(1, 10, 100_000, 1), (2, 10, 80_000, 1), (10, 1, 50_000, 2), (10, 2, 40_000, 2)]
    coordinator = toy(transfers, {1: 0, 2: 0, 10: 1}, {1, 2}).loc[10]
    features = pd.DataFrame([coordinator.to_dict()] * 100)
    features["gid"] = range(100)
    features["betweenness"] = [0.9] * 2 + [0.5] * 3 + [0.0] * 95

    result = roles.compute(SimpleNamespace(features=features, cfg=load_config()))

    assert result.evidence.iloc[:2].str.contains("betweenness top 2%", regex=False).all()
    assert result.evidence.iloc[2:5].str.contains("betweenness top 5%", regex=False).all()
    assert result.evidence.iloc[5:].str.contains("betweenness 0", regex=False).all()


def test_removed_node_stops_seed_flow_for_any_iterable():
    graph = nx.DiGraph()
    graph.add_weighted_edges_from([(1, 2, 100.0), (2, 3, 80.0)], weight="sum_kzt")

    assert taint.propagate(graph, {1}, rounds=2).to_dict() == {1: 0.0, 2: 100.0, 3: 80.0}
    assert taint.propagate(graph, {1}, rounds=2, removed=iter([2])).eq(0).all()
