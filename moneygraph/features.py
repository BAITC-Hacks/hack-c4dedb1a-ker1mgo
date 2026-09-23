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

    # TODO(A1): n_seed_payers, pays_seed, hub, authority, betweenness, in_cycle, cycle_with_seeds
    for col in ["n_seed_payers", "pays_seed", "in_cycle", "cycle_with_seeds"]:
        df[col] = 0
    for col in ["hub", "authority", "betweenness"]:
        df[col] = 0.0
    return df
