import json

import networkx as nx
import numpy as np
import pandas as pd

from .data import Context
from .taint import FlowModel

COMPONENTS = ["seed_flow", "role", "seed_sources", "betweenness", "removal_impact"]


def pct(x: pd.Series) -> pd.Series:
    # percentile rank, but a zero stays zero: most nodes have no betweenness and shouldn't get 0.5 for it
    r = x.rank(pct=True, method="max")
    return r.where(x > 0, 0.0).fillna(0.0)


def removal_impact(G, seeds, rounds, gids) -> pd.Series:
    """Share of the seed flow reaching everyone else that disappears when the node is taken out."""
    model = FlowModel(G, seeds)
    base = model.propagate(rounds)
    out = {}
    for g in gids:
        rest = base.drop(g).sum()
        after = model.propagate(rounds, removed={g}).drop(g).sum()
        out[g] = (rest - after) / rest if rest > 0 else 0.0
    return pd.Series(out, dtype=float)


def _kzt(x):
    if x >= 1e6:
        return f"{x / 1e6:.2f}M KZT"
    if x >= 1e3:
        return f"{x / 1e3:.0f}k KZT"
    return f"{x:.0f} KZT"


def _phrase(comp, r):
    if comp == "seed_flow":
        return f"{_kzt(r.seed_flow_in)} of seed money flows in"
    if comp == "role":
        return f"{r.role} (role score {r.role_score:.2f})"
    if comp == "seed_sources":
        return f"reachable from {int(r.n_seed_sources)} seeds"
    if comp == "betweenness":
        return f"bridge: betweenness in top {max(1, round(100 * (1 - r.c_betweenness)))}%"
    return f"removing it cuts {r.removal_impact:.1%} of downstream seed flow"


def why(r, weights, n_parts=3) -> str:
    contrib = sorted(((weights[c] * getattr(r, f"c_{c}"), c) for c in COMPONENTS), reverse=True)
    parts = [_phrase(c, r) for v, c in contrib[:n_parts] if v > 0]
    text = "; ".join(parts) or "no seed flow, weak structural signals"
    if r.is_seed:
        text = "known seed; " + text
    return text


def compute(ctx: Context) -> pd.DataFrame:
    cfg = ctx.cfg["priority"]
    w = cfg["weights"]
    f = ctx.features.set_index("gid", drop=False)

    c = pd.DataFrame(index=f.index)
    c["seed_flow"] = pct(np.log1p(f.seed_flow_in.fillna(0)))
    c["role"] = pct(f.role.map(cfg["role_weight"]).fillna(0) * f.role_score)
    c["seed_sources"] = pct(f.n_seed_sources)
    c["betweenness"] = pct(f.betweenness)

    # removal impact is expensive, so only for the nodes that already rank high without it
    seed_factor = np.where(f.is_seed, cfg["seed_priority_factor"], 1.0)
    pre = sum(w[k] * c[k] for k in COMPONENTS[:-1]) * seed_factor
    cand = pre.sort_values(ascending=False).head(cfg["removal_candidates"]).index
    imp = (
        removal_impact(ctx.G, ctx.seeds, ctx.cfg["taint"]["rounds"], cand)
        .reindex(f.index)
        .fillna(0.0)
    )
    # ranked among the candidates only; everyone else gets 0
    c["removal_impact"] = pct(imp.loc[cand]).reindex(f.index).fillna(0.0)

    raw = sum(w[k] * c[k] for k in COMPONENTS) * seed_factor
    normalizer = float(raw.max()) if raw.max() > 0 else 1.0
    score = raw / normalizer
    ctx.priority_audit = {}
    if getattr(ctx, "capture_explanations", True):
        for i, gid in enumerate(f.index):
            components = {k: float(w[k] * c.at[gid, k]) for k in COMPONENTS}
            ctx.priority_audit[str(gid)] = {
                "components": components,
                "weighted_sum": sum(components.values()),
                "seed_factor": float(seed_factor[i]),
                "normalization_factor": normalizer,
                "priority_score": float(score.at[gid]),
            }

    r = f[["is_seed", "role", "role_score", "seed_flow_in", "n_seed_sources"]].copy()
    r["removal_impact"] = imp
    for k in COMPONENTS:
        r[f"c_{k}"] = c[k]

    df = f[["gid"]].reset_index(drop=True)
    df["priority_score"] = score.values
    df["prio_components"] = [
        json.dumps({k: round(w[k] * c.at[g, k], 4) for k in COMPONENTS}) for g in f.index
    ]
    df["why"] = [why(row, w) for row in r.itertuples(index=False)]
    return df


def _order(ctx, strategy, rng):
    f = ctx.features
    if strategy == "priority":
        return f.sort_values(["priority_score", "gid"], ascending=[False, True]).gid.tolist()
    if strategy.startswith("degree"):
        # degree_nonseed skips seeds, since priority discounts them and removing a seed removes the money's source
        g = f[~f.is_seed] if strategy == "degree_nonseed" else f
        return (
            g.assign(d=g.in_deg + g.out_deg)
            .sort_values(["d", "gid"], ascending=[False, True])
            .gid.tolist()
        )
    return rng.permutation(f.gid.to_numpy()).tolist()


def _measure(ctx, removed, deep, base_reach, model):
    H = ctx.G.subgraph(set(ctx.G.nodes) - removed)
    wcc = [len(c) for c in nx.weakly_connected_components(H)]
    s_in = model.propagate(ctx.cfg["taint"]["rounds"], removed=removed)
    reach = s_in[deep].sum() / base_reach if base_reach > 0 else 0.0
    return max(wcc, default=0), len(wcc), reach


def resilience(ctx: Context) -> pd.DataFrame:
    """Remove the top-N nodes by priority, by degree, and at random; see what's left of the network."""
    cfg = ctx.cfg["resilience"]
    f = ctx.features
    deep = f.loc[f.depth >= 2, "gid"].tolist()
    model = FlowModel(ctx.G, ctx.seeds)
    base_reach = model.propagate(ctx.cfg["taint"]["rounds"])[deep].sum()
    rng = np.random.default_rng(cfg["random_seed"])

    rows = []
    for strategy in ["priority", "degree", "degree_nonseed", "random"]:
        draws = cfg["random_draws"] if strategy == "random" else 1
        orders = [_order(ctx, strategy, rng) for _ in range(draws)]
        for n in cfg["n_removed"]:
            m = np.mean(
                [_measure(ctx, set(o[:n]), deep, base_reach, model) for o in orders], axis=0
            )
            rows.append(
                {
                    "n_removed": n,
                    "strategy": strategy,
                    "largest_wcc": round(m[0], 1),
                    "n_components": round(m[1], 1),
                    "seed_flow_reach": round(m[2], 4),
                }
            )
    return pd.DataFrame(rows)
