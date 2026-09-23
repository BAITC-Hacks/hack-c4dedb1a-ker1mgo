import numpy as np
import networkx as nx
import pandas as pd


def undirected_projection(G: nx.DiGraph) -> nx.Graph:
    # a->b and b->a collapse into one edge; KZT of both directions is summed before the log
    kzt = {}
    for u, v, d in G.edges(data=True):
        key = (u, v) if u <= v else (v, u)
        kzt[key] = kzt.get(key, 0.0) + d["sum_kzt"]
    U = nx.Graph()
    U.add_weighted_edges_from((u, v, np.log1p(s)) for (u, v), s in kzt.items())
    return U


def compute(ctx) -> pd.DataFrame:
    cfg = ctx.cfg["clusters"]
    U = undirected_projection(ctx.G)
    comms = nx.community.louvain_communities(U, weight="weight", resolution=cfg["resolution"], seed=cfg["seed"])
    # stable ids: biggest community first, ties broken by smallest gid
    comms = sorted(comms, key=lambda c: (-len(c), min(c)))
    comp = {g: i for i, c in enumerate(comms, start=1) for g in c}
    df = ctx.nodes[["gid"]].copy()
    df["cluster_id"] = df.gid.map(comp).fillna(0).astype(int)  # 0 = no edges at all
    return df


def _fmt_kzt(x):
    if x >= 1e6:
        return f"{x / 1e6:.1f}M KZT"
    if x >= 1e3:
        return f"{x / 1e3:.0f}k KZT"
    return f"{x:.0f} KZT"


def hypothesis(g: pd.DataFrame, internal_kzt: float, cfg: dict) -> str:
    n, n_seed = len(g), int(g.is_seed.sum())
    roles = g.role.value_counts()
    share = roles / n
    money = _fmt_kzt(internal_kzt)
    if roles.get("consolidator", 0) and n_seed >= cfg["collection_min_seeds"]:
        k = roles["consolidator"]
        return f"possible collection cell: {k} consolidator(s) take money from {n_seed} seeds; {money} inside"
    if roles.get("distributor", 0):
        top = g.loc[g.role == "distributor"].sort_values("out_deg", ascending=False).iloc[0]
        return f"possible payout network: distributor fans out to {int(top.out_deg)} recipients; {n} nodes, {money} inside"
    if share.get("transit", 0) >= cfg["layering_transit_share"]:
        return f"possible layering chain: {share['transit']:.0%} of {n} nodes pass money on; {money} inside"
    if share.get("terminal", 0) >= cfg["periphery_terminal_share"]:
        return f"likely end-recipient periphery: {share['terminal']:.0%} of {n} nodes only receive; {money} inside"
    return f"loosely linked group: {n} nodes, {n_seed} seed{"s" if n_seed != 1 else ""}, {money} inside"


def summarize(ctx) -> pd.DataFrame:
    f = ctx.features
    cfg = ctx.cfg["clusters"]
    e = ctx.edges.merge(f[["gid", "cluster_id"]].rename(columns={"gid": "src", "cluster_id": "cs"}), on="src") \
                 .merge(f[["gid", "cluster_id"]].rename(columns={"gid": "dst", "cluster_id": "cd"}), on="dst")
    internal = e[e.cs == e.cd].groupby("cs").sum_kzt.sum()
    rows = []
    for cid, g in f.groupby("cluster_id"):
        top = g.sort_values("priority_score", ascending=False).gid.head(5)
        kzt = float(internal.get(cid, 0.0))
        if cid == 0:
            hyp = f"{len(g)} nodes with no transfers >= 5,000 KZT observed: data gap"
        else:
            hyp = hypothesis(g, kzt, cfg)
        rc = g.loc[g.role != "peripheral", "role"].value_counts().head(3)
        rows.append({
            "cluster_id": int(cid),
            "n_nodes": len(g),
            "n_seed": int(g.is_seed.sum()),
            "sum_kzt_internal": kzt,
            "top_gids": ";".join(map(str, top)),
            "hypothesis": hyp,
            "dominant_roles": ";".join(f"{r}:{c}" for r, c in rc.items()),
            "seed_flow_in": float(g.seed_flow_in.sum()),
        })
    return pd.DataFrame(rows)
