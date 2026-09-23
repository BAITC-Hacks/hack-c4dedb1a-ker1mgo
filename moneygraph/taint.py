from collections.abc import Iterable

import networkx as nx
import numpy as np
import pandas as pd
import scipy.sparse as sp

from .data import Context


def propagate(
    G: nx.DiGraph, seeds: set[int], rounds: int, removed: Iterable[int] = ()
) -> pd.Series:
    """KZT of seed-originated money flowing into each node (s_in), as a Series by gid.

    Each round, a node forwards what it received, capped at its own out_kzt, split over its
    edges by KZT share. Seeds always emit their full out_kzt. Nodes in `removed` pass nothing
    on and receive nothing, as if taken out of the graph (used by priority's removal impact).
    """
    nodes = list(G.nodes)
    idx = {g: i for i, g in enumerate(nodes)}
    src, dst, w = zip(*G.edges(data="sum_kzt")) if G.number_of_edges() else ((), (), ())
    out_kzt = np.bincount([idx[u] for u in src], weights=w, minlength=len(nodes))
    share = np.array(w) / out_kzt[[idx[u] for u in src]]
    # M[v, u] = share of u's outflow that goes to v, so s_in = M @ s_out
    M = sp.csr_matrix(
        (share, ([idx[v] for v in dst], [idx[u] for u in src])), shape=(len(nodes),) * 2
    )

    is_seed = np.array([g in seeds for g in nodes])
    removed = set(removed)
    keep = np.array([g not in removed for g in nodes])
    seed_out = np.where(is_seed & keep, out_kzt, 0.0)
    s_out = seed_out.copy()
    s_in = np.zeros(len(nodes))
    for _ in range(rounds):
        s_in = (M @ s_out) * keep
        s_out = np.where(is_seed, seed_out, np.minimum(s_in, out_kzt))
    return pd.Series(s_in, index=nodes)


def compute(ctx: Context) -> pd.DataFrame:
    G, seeds = ctx.G, ctx.seeds
    df = ctx.nodes[["gid"]].copy()
    df["seed_flow_in"] = df.gid.map(propagate(G, seeds, ctx.cfg["taint"]["rounds"])).astype(float)

    # seeds with a directed path to the node; a seed does not count as its own source
    n_src = dict.fromkeys(G.nodes, 0)
    for s in seeds:
        for v in nx.descendants(G, s) - {s}:
            n_src[v] += 1
    df["n_seed_sources"] = df.gid.map(n_src).astype(int)
    return df
