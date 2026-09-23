from collections import defaultdict

import numpy as np
import networkx as nx
import pandas as pd


def compute(ctx) -> pd.DataFrame:
    G = ctx.G
    df = ctx.nodes[["gid"]].copy()
    df["in_deg"] = df.gid.map(dict(G.in_degree())).astype(int)
    df["out_deg"] = df.gid.map(dict(G.out_degree())).astype(int)
    df["in_kzt"] = df.gid.map(dict(G.in_degree(weight="sum_kzt"))).astype(float)
    df["out_kzt"] = df.gid.map(dict(G.out_degree(weight="sum_kzt"))).astype(float)
    df["in_tx"] = df.gid.map(dict(G.in_degree(weight="n_tx"))).astype(int)
    df["out_tx"] = df.gid.map(dict(G.out_degree(weight="n_tx"))).astype(int)
    df["pagerank"] = df.gid.map(nx.pagerank(G, weight="sum_kzt"))

    # seeds' inflow is under-counted (graph is built from them), so the ratio means nothing there
    is_seed = df.gid.isin(ctx.seeds)
    df["pass_through"] = np.where((df.in_kzt > 0) & ~is_seed, df.out_kzt / df.in_kzt.where(df.in_kzt > 0), np.nan)

    seeds = ctx.seeds
    df["n_seed_payers"] = df.gid.map(lambda v: sum(u in seeds for u in G.predecessors(v))).astype(int)
    df["pays_seed"] = df.gid.map(lambda v: sum(w in seeds for w in G.successors(v))).astype(int)

    # no "weight" attribute on edges, so HITS runs on the unweighted structure
    hub, auth = nx.hits(G, max_iter=500, nstart=dict.fromkeys(G, 1.0))
    df["hub"] = df.gid.map(hub).astype(float)
    df["authority"] = df.gid.map(auth).astype(float)
    centrality = ctx.cfg.get("centrality", {})
    samples = centrality.get("betweenness_samples")
    df["betweenness"] = df.gid.map(nx.betweenness_centrality(
        G, k=min(samples, len(G)) if samples else None,
        seed=centrality.get("seed", ctx.cfg["clusters"]["seed"]))).astype(float)

    # Enumerate bounded local walks inside SCCs once. networkx.simple_cycles
    # repeatedly decomposes a giant SCC after removing vertices, which dominated
    # the 100× graph lift despite the short bound. Canonical start nodes dedupe.
    on_cycle, cyc_seeds = short_cycle_features(G, seeds)
    df["in_cycle"] = df.gid.isin(on_cycle).astype(int)
    df["cycle_with_seeds"] = df.gid.map(lambda v: len(cyc_seeds.get(v, ()))).astype(int)

    # printed on verbose runs so config thresholds can be checked against the data
    if getattr(ctx, "verbose", False):
        print("  percentiles (p50/p90/p95/p98):")
        for col in ["in_deg", "out_deg", "betweenness"]:
            q = df[col].quantile([0.5, 0.9, 0.95, 0.98]).tolist()
            print(f"    {col:<12}" + " ".join(f"{x:.4g}" for x in q))
    return df


def short_cycle_features(G, seeds, max_length=4):
    """Exact membership and other seed members of simple directed cycles ≤ 4."""
    on_cycle, cyc_seeds = set(), defaultdict(set)
    for component in nx.strongly_connected_components(G):
        adjacency = {gid: [v for v in G.successors(gid) if v in component] for gid in component}
        for start in component:
            stack = [(start, (start,))]
            while stack:
                current, path = stack.pop()
                for target in adjacency[current]:
                    if target == start:
                        seed_members = seeds.intersection(path)
                        on_cycle.update(path)
                        for gid in path:
                            cyc_seeds[gid].update(seed_members - {gid})
                    elif len(path) < max_length and target > start and target not in path:
                        stack.append((target, (*path, target)))
    return on_cycle, cyc_seeds
