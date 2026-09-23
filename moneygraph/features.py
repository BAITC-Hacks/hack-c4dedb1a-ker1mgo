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
    hub, auth = nx.hits(G, max_iter=500)
    df["hub"] = df.gid.map(hub).astype(float)
    df["authority"] = df.gid.map(auth).astype(float)
    df["betweenness"] = df.gid.map(nx.betweenness_centrality(G)).astype(float)

    # seeds sharing a cycle with the node; the node itself is not counted
    on_cycle, cyc_seeds = set(), defaultdict(set)
    for cyc in nx.simple_cycles(G, length_bound=4):
        s = seeds.intersection(cyc)
        for v in cyc:
            on_cycle.add(v)
            cyc_seeds[v] |= s - {v}
    df["in_cycle"] = df.gid.isin(on_cycle).astype(int)
    df["cycle_with_seeds"] = df.gid.map(lambda v: len(cyc_seeds.get(v, ()))).astype(int)

    # printed on verbose runs so config thresholds can be checked against the data
    if getattr(ctx, "verbose", False):
        print("  percentiles (p50/p90/p95/p98):")
        for col in ["in_deg", "out_deg", "betweenness"]:
            q = df[col].quantile([0.5, 0.9, 0.95, 0.98]).tolist()
            print(f"    {col:<12}" + " ".join(f"{x:.4g}" for x in q))
    return df
