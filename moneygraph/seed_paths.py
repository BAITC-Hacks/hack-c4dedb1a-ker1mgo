"""Top path attribution of the SAME capped, finite-round seed-flow model."""
from heapq import nlargest

import numpy as np

from .taint import FlowModel


def build(ctx):
    rounds = ctx.cfg["taint"]["rounds"]
    limit = ctx.cfg.get("explainability", {}).get("top_seed_paths", 5)
    model = FlowModel(ctx.G, ctx.seeds)
    nodes, idx = model.nodes, model.idx
    outgoing = [[] for _ in nodes]
    for source, target, weight in ctx.G.edges(data="sum_kzt"):
        i, j = idx[source], idx[target]
        if model.out_kzt[i] > 0:
            outgoing[i].append((j, weight / model.out_kzt[i]))
    incoming = [[] for _ in nodes]
    totals = np.zeros(len(nodes))
    for _ in range(rounds):
        next_paths = [[] for _ in nodes]
        for i, gid in enumerate(nodes):
            if model.is_seed[i]:
                emitted = [(float(model.out_kzt[i]), (gid,))]
            else:
                factor = min(1.0, model.out_kzt[i] / totals[i]) if totals[i] > 0 else 0.0
                emitted = [(amount * factor, path) for amount, path in incoming[i]]
            for j, share in outgoing[i]:
                next_paths[j].extend((amount * share, (*path, nodes[j])) for amount, path in emitted if amount * share > 0)
        # Pruning is exact for the top K: all prefixes at a node receive the same
        # proportional cap and outgoing share. K stronger prefixes dominate any
        # discarded prefix along every shared suffix, including cyclic walks.
        incoming = [nlargest(limit, paths, key=lambda p: (p[0], tuple(map(str, p[1])))) for paths in next_paths]
        emitted_totals = np.where(model.is_seed, model.out_kzt, np.minimum(totals, model.out_kzt))
        totals = model.matrix @ emitted_totals
    result = {}
    for i, gid in enumerate(nodes):
        shown = sum(amount for amount, _ in incoming[i])
        result[str(gid)] = {
            "seed_flow_in": float(totals[i]), "shown_kzt": float(shown),
            "omitted_kzt": float(max(0, totals[i] - shown)),
            "coverage": float(min(1, shown / totals[i])) if totals[i] > 0 else 0.0,
            "paths": [{"gids": list(map(str, path)), "kzt": float(amount), "hops": len(path) - 1,
                       "contains_cycle": len(path) != len(set(path))} for amount, path in incoming[i]],
        }
    return {
        "schema_version": 1, "rounds": rounds, "top_k": limit,
        "method": "Top modeled KZT path contributions to final-round seed_flow_in, with proportional splits and outflow caps.",
        "limitations": ["Attribution is modeled, not traced transactions or proof of ownership.",
                        "Paths are walks up to the round horizon; cycles may repeat nodes.",
                        "Every round replaces a seed's outgoing attribution with its own observed outflow.",
                        "KZT is final-round arrival, not cumulative flow; do not add arrivals across nodes.",
                        "Only top paths are shown; omitted modeled KZT and coverage are reported."],
        "nodes": result,
    }
