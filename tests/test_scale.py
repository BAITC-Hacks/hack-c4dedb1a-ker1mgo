"""Scaling workload integrity and exact optimization parity."""

import networkx as nx
import pandas as pd

from moneygraph import temporal
from moneygraph.bench import distribution_check, synthetic, temporal_reference
from moneygraph.data import Context, build_graph, load_config


def toy_context():
    tx = pd.DataFrame(
        [
            (1, 2, 100, "2026-01-01"),
            (1, 2, 100, "2026-01-01"),
            (2, 3, 160, "2026-01-01"),
            (3, 2, 50, "2026-01-04"),
            (2, 2, 5000, "2026-01-05"),
        ],
        columns=["src", "dst", "sum_kzt", "date"],
    )
    tx["date"] = pd.to_datetime(tx.date)
    edges = (
        tx.groupby(["src", "dst"])
        .agg(sum_kzt=("sum_kzt", "sum"), n_tx=("sum_kzt", "size"))
        .reset_index()
    )
    edges["depth"] = 1
    nodes = pd.DataFrame(
        {"gid": [1, 2, 3, 4], "depth": [0, 1, 2, 0], "is_seed": [True, False, False, True]}
    )
    ctx = Context(edges, nodes, tx, build_graph(edges, nodes), load_config(), {1, 4})
    return ctx


def test_temporal_vectorization_matches_fifo_reference_with_self_loop():
    ctx = toy_context()
    pd.testing.assert_frame_equal(temporal.compute(ctx), temporal_reference(ctx), check_dtype=False)


def test_synthetic_lift_exact_distributions_and_determinism():
    base = toy_context()
    first = synthetic(base, 10, 42)
    second = synthetic(base, 10, 42)
    assert distribution_check(base, first, 10) == (True, True)
    assert len(first.nodes) == len(base.nodes) * 10
    assert len(first.edges) == len(base.edges) * 10
    assert len(first.tx) == len(base.tx) * 10
    pd.testing.assert_frame_equal(first.tx, second.tx)
    # Edge permutations connect different copies; this is not disjoint repetition.
    n = len(base.nodes)
    assert ((first.edges.src - 1) // n != (first.edges.dst - 1) // n).any()


def test_bounded_cycle_features_equal_networkx_with_seed_membership():
    from moneygraph.features import short_cycle_features

    for seed in range(5):
        graph = nx.gnp_random_graph(20, 0.16, seed=seed, directed=True)
        graph.add_edge(0, 0)
        seeds = {0, 2, 4}
        found, sources = short_cycle_features(graph, seeds)
        expected_nodes, expected_seeds = set(), {gid: set() for gid in graph}
        for cycle in nx.simple_cycles(graph, length_bound=4):
            expected_nodes.update(cycle)
            for gid in cycle:
                expected_seeds[gid].update(seeds.intersection(cycle) - {gid})
        assert found == expected_nodes
        assert {gid: sources.get(gid, set()) for gid in graph} == expected_seeds
