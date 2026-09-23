import networkx as nx
import pandas as pd


def compute(ctx) -> pd.DataFrame:
    # TODO(B3): Louvain on undirected log-weighted projection; stub uses weakly connected components
    comp = {}
    cid = 1
    for c in sorted(nx.weakly_connected_components(ctx.G), key=len, reverse=True):
        if len(c) == 1:
            (g,) = c
            comp[g] = 0  # no edges at all
            continue
        for g in c:
            comp[g] = cid
        cid += 1
    df = ctx.nodes[["gid"]].copy()
    df["cluster_id"] = df.gid.map(comp).astype(int)
    return df


def summarize(ctx) -> pd.DataFrame:
    f = ctx.features
    e = ctx.edges.merge(f[["gid", "cluster_id"]].rename(columns={"gid": "src", "cluster_id": "cs"}), on="src") \
                 .merge(f[["gid", "cluster_id"]].rename(columns={"gid": "dst", "cluster_id": "cd"}), on="dst")
    internal = e[e.cs == e.cd].groupby("cs").sum_kzt.sum()
    rows = []
    for cid, g in f.groupby("cluster_id"):
        top = g.sort_values("priority_score", ascending=False).gid.head(5)
        # TODO(B3): hypothesis templates from role mix
        hyp = "no transfers >= 5,000 KZT observed: data gap" if cid == 0 else f"stub: group of {len(g)} nodes"
        rows.append({
            "cluster_id": int(cid),
            "n_nodes": len(g),
            "n_seed": int(g.is_seed.sum()),
            "sum_kzt_internal": float(internal.get(cid, 0.0)),
            "top_gids": ";".join(map(str, top)),
            "hypothesis": hyp,
        })
    return pd.DataFrame(rows)
