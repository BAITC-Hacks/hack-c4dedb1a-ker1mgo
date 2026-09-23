import networkx as nx
import pandas as pd

from .data import Context

COLS = ["gid", "reason", "suggested_request"]


def _kzt(x):
    x = float(x)
    for div, suf in ((1e6, "M"), (1e3, "k")):
        if abs(x) >= div:
            return f"{x / div:.2f}{suf}"
    return f"{x:.0f}"


def build(ctx: Context) -> pd.DataFrame:
    f = ctx.features
    rows = []

    fwd = f[f.role_detail == "truncated_likely_forwarding"].sort_values(
        "p_has_out", ascending=False
    )
    for r in fwd.itertuples():
        rows.append(
            (
                r.gid,
                "truncated_likely_forwarding",
                f"hop 5: outgoing transfers of this depth-4 node (P(forwards) = {r.p_has_out:.2f}, "
                f"{_kzt(r.in_kzt)} KZT in)",
            )
        )

    seeds = f[f.is_seed]
    for r in seeds[seeds.out_deg == 0].itertuples():
        rows.append(
            (
                r.gid,
                "seed_no_outgoing",
                "no outgoing transfers >= 5,000 KZT in data: check other channels (cash, cards, other banks)",
            )
        )
    for r in seeds[seeds.out_deg > 0].sort_values("out_kzt", ascending=False).itertuples():
        rows.append(
            (
                r.gid,
                "seed_inflow_undercounted",
                f"incoming transfers of this seed: only {r.in_deg} payers seen, "
                f"{_kzt(r.out_kzt)} KZT out",
            )
        )

    # weak components cut off from the main network
    max_size = ctx.cfg["data_requests"]["small_component_max"]
    comps = sorted(nx.weakly_connected_components(ctx.G), key=len, reverse=True)
    listed = {r[0] for r in rows}
    for comp in comps[1:]:
        # isolated seeds already have their own row
        if len(comp) >= max_size or comp <= listed:
            continue
        n_seed = len(comp & ctx.seeds)
        for g in sorted(comp):
            rows.append(
                (
                    g,
                    "small_component",
                    f"transfers linking this {len(comp)}-node group ({n_seed} seed{'s' * (n_seed != 1)}) "
                    "to the main network",
                )
            )

    df = pd.DataFrame(rows, columns=COLS)
    if ctx.verbose:
        print("data requests:", df.reason.value_counts().to_dict())
    return df
