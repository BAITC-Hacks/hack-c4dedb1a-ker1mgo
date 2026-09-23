"""Role rules from config.yaml and docs/methodology.md; the first matching rule wins.

Each rule returns the margins of its threshold conditions (None if it does not match), so
role_score can say how far past the thresholds a node is. Seeds never use in_kzt or
pass_through: their inflow is under-counted because the graph was crawled from them.
"""

import math

import numpy as np
import pandas as pd

from .data import Context

RULES = ["coordinator", "distributor", "consolidator", "transit", "terminal"]
EVIDENCE_MAX = 200


def ge(x, thr):
    """Margin of x >= thr: 0 at the threshold, 1 at twice the threshold. None if not met."""
    if x < thr:
        return None
    return 1.0 if thr <= 0 else min((x - thr) / thr, 1.0)


def le(x, thr):
    if x > thr:
        return None
    return 1.0 if thr <= 0 else min((thr - x) / thr, 1.0)


def between(x, lo, hi):
    if not lo <= x <= hi:
        return None
    half = (hi - lo) / 2
    return 1.0 - abs(x - (lo + hi) / 2) / half


def any_of(*ms):
    ms = [m for m in ms if m is not None]
    return max(ms) if ms else None


def all_of(*ms):
    return None if any(m is None for m in ms) else list(ms)


def nan_to(x, v):
    return v if x is None or (isinstance(x, float) and math.isnan(x)) else x


def rule(name, r, c, bt_thr):
    """Margins list if node r matches role `name`, else None."""
    pt = nan_to(
        r.pass_through, math.inf
    )  # NaN (seeds, no inflow) never satisfies a pass-through bound
    if name == "coordinator":
        k = c["coordinator"]
        return all_of(
            any_of(
                ge(r.pays_seed, k["min_pays_seed"]), ge(r.cycle_with_seeds, k["min_cycle_seeds"])
            ),
            any_of(ge(r.n_seed_sources, k["min_seed_sources"]), ge(r.betweenness, bt_thr)),
        )
    if name == "distributor":
        k = c["distributor"]
        return all_of(
            ge(r.out_deg, k["min_out_deg"]), ge(r.out_deg, k["out_in_ratio"] * max(r.in_deg, 1))
        )
    if name == "consolidator":
        k = c["consolidator"]
        few_exits = le(r.out_deg, r.in_deg * k["out_in_ratio"])
        holds = None if r.is_seed else le(pt, k["max_pass_through"])
        return all_of(ge(r.in_deg, k["min_in_deg"]), any_of(holds, few_exits))
    if name == "transit":
        k = c["transit"]
        if r.is_seed or r.in_deg < 1 or r.out_deg < 1:
            return None
        fast = (
            ge(r.fast_pass_share, k["min_fast_pass_share"])
            if pt <= k["max_pass_through_fast"]
            else None
        )
        return all_of(any_of(between(pt, k["pass_through_low"], k["pass_through_high"]), fast))
    if name == "terminal":
        if r.is_seed or r.out_deg > 0 or r.in_deg < 1:
            return None
        if r.depth <= 3:
            return [1.0]
        p = r.p_has_out
        return None if math.isnan(p) or p >= c["terminal"]["max_p_has_out"] else [1.0]
    raise ValueError(name)


def fast_pass_only(r, c):
    """Fast pass-through but pass_through above the cap: kept as a secondary hint, not a role."""
    k = c["transit"]
    return (
        not r.is_seed
        and r.in_deg >= 1
        and r.out_deg >= 1
        and r.fast_pass_share >= k["min_fast_pass_share"]
        and nan_to(r.pass_through, 0) > k["max_pass_through_fast"]
    )


def partial_match(r, c):
    """How close a non-matching node gets to the structural roles, 0-1 (for peripheral scores)."""
    k = c
    pt = nan_to(r.pass_through, math.inf)

    def close(x: float, threshold: float) -> float:
        return min(x / threshold, 1.0) if threshold > 0 else 1.0

    cands = [
        np.mean(
            [
                close(r.out_deg, k["distributor"]["min_out_deg"]),
                close(r.out_deg, k["distributor"]["out_in_ratio"] * max(r.in_deg, 1)),
            ]
        ),
        np.mean(
            [
                close(r.in_deg, k["consolidator"]["min_in_deg"]),
                1.0 if r.out_deg <= r.in_deg * k["consolidator"]["out_in_ratio"] else 0.0,
            ]
        ),
        close(r.fast_pass_share, k["transit"]["min_fast_pass_share"]) if not r.is_seed else 0.0,
    ]
    if not r.is_seed and r.in_deg and r.out_deg and math.isfinite(pt):
        lo, hi = k["transit"]["pass_through_low"], k["transit"]["pass_through_high"]
        cands.append(max(0.0, 1 - max(lo - pt, pt - hi, 0) / lo))
    return float(max(cands))


def kzt(x):
    x = float(x)
    if x >= 1e6:
        return f"{x / 1e6:.2f}M"
    if x >= 1e3:
        return f"{x / 1e3:.0f}k"
    return f"{x:.0f}"


def n(k, word):
    return f"{k} {word}" if k == 1 else f"{k} {word}s"


def pct(x):
    return f"{100 * x:.0f}%"


def betweenness_text(top):
    """top = share of nodes with betweenness >= this node's; NaN/None when not computed."""
    if top is None or math.isnan(top):
        return ""
    return "betweenness 0" if top >= 0.5 else f"betweenness top {max(1, math.ceil(100 * top))}%"


def evidence(r, role, detail, c):
    days = c["fast_pass_days"]
    seeds = f" ({n(r.n_seed_payers, 'seed')})" if r.n_seed_payers else ""
    inflow = "" if r.is_seed else f" → {kzt(r.in_kzt)} in"  # seeds: in_kzt is under-counted
    if role == "coordinator":
        parts = [
            f"pays {n(r.pays_seed, 'seed')} back" if r.pays_seed else "",
            f"on cycles with {n(r.cycle_with_seeds, 'seed')}" if r.cycle_with_seeds else "",
            f"downstream of {n(r.n_seed_sources, 'seed')}",
            betweenness_text(r.get("bt_top")),
        ]
        s = "; ".join(p for p in parts if p)
    elif role == "distributor":
        s = f"pays {n(r.out_deg, 'recipient')} {kzt(r.out_kzt)}; from {n(r.in_deg, 'payer')}{seeds}"
        if not r.is_seed:
            s += f"; {pct(r.fast_pass_share)} passed on within {days} days"
    elif role == "consolidator":
        s = f"{n(r.in_deg, 'payer')}{seeds}{inflow}"
        if not r.is_seed:
            s += f"; sends on {pct(nan_to(r.pass_through, 0))}"
        s += f"; to {n(r.out_deg, 'recipient')}; up to {n(r.max_same_day_payers, 'payer')} same day"
    elif role == "transit":
        s = (
            f"{kzt(r.in_kzt)} in from {r.in_deg}, {kzt(r.out_kzt)} out to {r.out_deg} "
            f"({pct(nan_to(r.pass_through, 0))}); {pct(r.fast_pass_share)} forwarded within {days} days"
        )
    elif detail == "terminal_observed":
        s = f"{n(r.in_deg, 'payer')}{seeds}{inflow}; no outgoing transfers although depth {r.depth} was crawled"
    elif detail == "terminal_inferred":
        s = f"depth-4 sink: {n(r.in_deg, 'payer')}{seeds}{inflow}; P(forwards) = {r.p_has_out:.2f}, likely end recipient"
    elif detail == "truncated_likely_forwarding":
        s = f"depth-4 sink: {n(r.in_deg, 'payer')}{seeds}{inflow}; P(forwards) = {r.p_has_out:.2f}, request hop 5"
    elif detail == "truncated_unknown":
        p = "" if math.isnan(r.p_has_out) else f"; P(forwards) = {r.p_has_out:.2f}"
        s = f"depth-4 sink: {n(r.in_deg, 'payer')}{seeds}{inflow}; outgoing transfers not in data{p}"
    elif detail == "no_edges":
        s = "0 payers, 0 recipients: no transfers in the graph"
    elif detail == "seed_no_outgoing":
        s = f"seed with 0 outgoing transfers in data; {n(r.in_deg, 'payer')}"
    elif fast_pass_only(r, c):
        s = (
            f"{kzt(r.in_kzt)} in, {kzt(r.out_kzt)} out ({pct(r.pass_through)}); {pct(r.fast_pass_share)} forwarded "
            f"within {days} days, but most outflow comes from outside the graph"
        )
    else:
        s = f"{n(r.in_deg, 'payer')} / {n(r.out_deg, 'recipient')}; {kzt(r.out_kzt)} out; no role rule met"
    if r.seed_flow_in > 0:
        s += f"; seed money in {kzt(r.seed_flow_in)}"
    flags = r["flags"]
    if flags:
        s += f"; flags {flags.replace(';', ',')}"
    return s[:EVIDENCE_MAX]


def assign(r, c, bt_thr):
    matched = {name: m for name in RULES if (m := rule(name, r, c, bt_thr)) is not None}
    if matched:
        role = next(iter(matched))
        m = matched[role]
        if role == "terminal":
            detail = "terminal_observed" if r.depth <= 3 else "terminal_inferred"
            score = 0.9 if detail == "terminal_observed" else 1 - r.p_has_out
        else:
            detail, score = role, 0.5 + 0.5 * float(np.mean(m))
    else:
        role = "peripheral"
        if r.is_seed and r.out_deg == 0:
            detail = "seed_no_outgoing"
        elif r.in_deg == 0 and r.out_deg == 0:
            detail = "no_edges"
        elif r.depth == 4 and r.out_deg == 0:
            likely = nan_to(r.p_has_out, 0) > c["truncated_likely_forwarding_p"]
            detail = "truncated_likely_forwarding" if likely else "truncated_unknown"
        else:
            detail = "weak_signal"
        score = 1 - partial_match(r, c)
    others = [name for name in matched if name != role]
    if "transit" not in matched and fast_pass_only(r, c):
        others.append("transit")
    secondary = ";".join(others)
    return role, detail, secondary, float(np.clip(score, 0, 1))


def compute(ctx: Context) -> pd.DataFrame:
    f = ctx.features
    c = dict(ctx.cfg["roles"], fast_pass_days=ctx.cfg["temporal"]["fast_pass_days"])
    bt_thr = float(f.betweenness.quantile(c["coordinator"]["betweenness_pct"]))
    # share of nodes at or above each betweenness value, for "betweenness top 2%" in evidence
    # max rank includes ties without materializing a nodes-by-nodes comparison matrix
    bt_top = f.betweenness.rank(method="max", ascending=False).fillna(0) / len(f)
    rows = []
    for i, r in f.iterrows():
        r["bt_top"] = bt_top[i]
        role, detail, secondary, score = assign(r, c, bt_thr)
        rows.append((r.gid, role, detail, secondary, score, evidence(r, role, detail, c)))
    return pd.DataFrame(
        rows, columns=["gid", "role", "role_detail", "secondary_roles", "role_score", "evidence"]
    )
