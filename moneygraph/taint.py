"""Finite-round proportional seed-money propagation, with exact source reachability."""
import networkx as nx
import numpy as np
import pandas as pd
import scipy.sparse as sp


class FlowModel:
    """Prepare the sparse graph once for many removal scenarios."""

    def __init__(self, G, seeds):
        self.nodes = list(G.nodes)
        self.idx = {g: i for i, g in enumerate(self.nodes)}
        src, dst, weights = zip(*G.edges(data="sum_kzt")) if G.number_of_edges() else ((), (), ())
        src_idx = np.array([self.idx[u] for u in src], dtype=int)
        dst_idx = np.array([self.idx[v] for v in dst], dtype=int)
        self.out_kzt = np.bincount(src_idx, weights=weights, minlength=len(self.nodes))
        shares = np.divide(np.asarray(weights), self.out_kzt[src_idx],
                           out=np.zeros(len(weights), dtype=float), where=self.out_kzt[src_idx] > 0)
        self.matrix = sp.csr_matrix((shares, (dst_idx, src_idx)), shape=(len(self.nodes),) * 2)
        self.is_seed = np.array([g in seeds for g in self.nodes])

    def propagate(self, rounds, removed=()):
        keep = np.ones(len(self.nodes), dtype=bool)
        for g in removed:
            if g in self.idx:
                keep[self.idx[g]] = False
        seed_out = np.where(self.is_seed & keep, self.out_kzt, 0.0)
        s_out = seed_out.copy()
        s_in = np.zeros(len(self.nodes))
        for _ in range(rounds):
            s_in = (self.matrix @ s_out) * keep
            s_out = np.where(self.is_seed, seed_out, np.minimum(s_in, self.out_kzt))
        return pd.Series(s_in, index=self.nodes)


def propagate(G, seeds, rounds, removed=()):
    """Modeled KZT arriving in the final round, not cumulative transferred money.

    Seeds emit their observed outflow each round. Other nodes forward received
    flow, capped by observed outflow, split by edge KZT share. Re-entering a seed
    ends that attribution: its next emission is assigned to that seed itself.
    Removal preserves original edge shares, so blocked flow is not redistributed.
    """
    return FlowModel(G, seeds).propagate(rounds, removed)


def seed_source_counts(G, seeds):
    """Exact reachability using seed bitsets on the acyclic component graph.

    This replaces one whole-graph BFS per seed. Strongly connected nodes share
    the same reachable seed set; a seed never counts itself as its own source.
    """
    dag = nx.condensation(G)
    mapping = dag.graph["mapping"]
    masks = dict.fromkeys(dag, 0)
    for bit, seed in enumerate(sorted(seeds)):
        masks[mapping[seed]] |= 1 << bit
    for component in nx.topological_sort(dag):
        for target in dag.successors(component):
            masks[target] |= masks[component]
    return {gid: masks[mapping[gid]].bit_count() - int(gid in seeds) for gid in G}


def compute(ctx) -> pd.DataFrame:
    G, seeds = ctx.G, ctx.seeds
    df = ctx.nodes[["gid"]].copy()
    df["seed_flow_in"] = df.gid.map(propagate(G, seeds, ctx.cfg["taint"]["rounds"])).astype(float)
    df["n_seed_sources"] = df.gid.map(seed_source_counts(G, seeds)).astype(int)
    return df
