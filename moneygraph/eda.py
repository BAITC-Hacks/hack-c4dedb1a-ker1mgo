"""Print descriptive graph statistics used to inspect the methodology's assumptions."""

import argparse
from pathlib import Path

import networkx as nx
import pandas as pd

from .data import load_context
from .paths import DATA_DIR


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=DATA_DIR)
    ctx = load_context(ap.parse_args().data)
    G, N, E, T = ctx.G, ctx.nodes, ctx.edges, ctx.tx
    out_deg = pd.Series(dict(G.out_degree()))
    in_deg = pd.Series(dict(G.in_degree()))

    print("share of nodes that send money on, by depth:")
    for k in [1, 2, 3]:
        gids = N[N.depth == k].gid
        print(f"  depth {k}: {(out_deg[gids] > 0).mean():.3f}")
    d = N.set_index("gid").depth
    print("depth-4 sinks:", int(((d == 4) & (out_deg[d.index] == 0)).sum()))
    print(
        "depth 1-3 sinks with inflow:",
        int(((d < 4) & (out_deg[d.index] == 0) & (in_deg[d.index] > 0)).sum()),
    )

    fi, fo = T.groupby("dst").date.min(), T.groupby("src").date.min()
    both = fi.index.intersection(fo.index)
    print(
        f"intermediaries: {len(both)}, first out before first in: {int((fo[both] < fi[both]).sum())}"
    )

    dd = E[["src", "dst"]].assign(depth_src=E.src.map(d), depth_dst=E.dst.map(d))
    print(
        "back/lateral edges:",
        int((dd.depth_dst <= dd.depth_src).sum()),
        " into seeds:",
        int(E.dst.isin(ctx.seeds).sum()),
    )
    print(
        "max in/out degree:",
        int(in_deg.max()),
        int(out_deg.max()),
        " in_deg>=5:",
        int((in_deg >= 5).sum()),
    )
    print(
        "weak components:",
        [len(c) for c in sorted(nx.weakly_connected_components(G), key=len, reverse=True)][:5],
    )
    print("amounts multiple of 10k:", round(float((T.sum_kzt % 10000 == 0).mean()), 3))


if __name__ == "__main__":
    main()
