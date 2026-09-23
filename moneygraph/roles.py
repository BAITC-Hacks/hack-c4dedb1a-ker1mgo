"""Role rules from config.yaml and docs/methodology.md; the first matching rule wins.

Each rule returns the margins of its threshold conditions (None if it does not match), so
role_score can say how far past the thresholds a node is. Seeds never use in_kzt or
pass_through: their inflow is under-counted because the graph was crawled from them.
"""

import math

import numpy as np
import pandas as pd

from .data import Context


class FeatureRow(dict):
    __getattr__ = dict.__getitem__


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


def condition(field, label, value, operator, threshold, source, *, applicable=True, scored=True):
    """One evaluated predicate shared by assignment and the exported explanation."""
    available = applicable and value is not None and np.isfinite(value)
    passed = False
    margin = None
    deficit = None
    if available:
        if operator == ">=":
            passed, margin = value >= threshold, ge(value, threshold)
            deficit = max(threshold - value, 0)
        elif operator == "<=":
            passed, margin = value <= threshold, le(value, threshold)
            deficit = max(value - threshold, 0)
        elif operator == "<":
            passed = value < threshold
            margin = 1.0 if passed else None
            deficit = max(value - threshold, 0)
        elif operator == "==":
            passed = value == threshold
            margin = 1.0 if passed else None
            deficit = abs(value - threshold)
        elif operator == "between":
            lo, hi = threshold
            passed = lo <= value <= hi
            margin = between(value, lo, hi)
            deficit = max(lo - value, value - hi, 0)
        elif operator == ">":
            passed = value > threshold
            margin = 1.0 if passed else None
            deficit = max(threshold - value, 0)
        else:
            raise ValueError(operator)
    scale = max(abs(v) for v in threshold) if isinstance(threshold, list) else abs(threshold)
    distance = (deficit / max(scale, 1.0)) if available else float("inf")
    if available and not passed and distance == 0:
        distance = np.finfo(float).eps  # a strict boundary still needs a change
    return {
        "field": field,
        "label": label,
        "value": float(value) if available else None,
        "operator": operator,
        "threshold": threshold,
        "threshold_source": source,
        "passed": bool(passed),
        "applicable": bool(applicable),
        "available": bool(available),
        "deficit": float(deficit) if deficit is not None else None,
        "distance": float(distance),
        "margin": margin,
        "scored": scored,
    }


def group(operator, *children, scored=True):
    matched = (
        all(c["passed"] for c in children)
        if operator == "all"
        else any(c["passed"] for c in children)
    )
    valid = [
        c["margin"] for c in children if c["passed"] and c["scored"] and c["margin"] is not None
    ]
    margin = (min(valid) if operator == "all" else max(valid)) if valid and matched else None
    distance = (
        sum(c["distance"] for c in children)
        if operator == "all"
        else min(c["distance"] for c in children)
    )
    return {
        "operator": operator,
        "children": list(children),
        "passed": matched,
        "margin": margin,
        "scored": scored,
        "distance": distance,
    }


def rule_definition(name, r, c, bt_thr):
    """The only role predicate definitions. Assignment and traces evaluate this same tree.

    A seed's pass-through values are suppressed before evaluation; the structural
    degree branch remains available to consolidators. Guard conditions do not
    contribute to the historical role-score margins.
    """

    def pred(field, label, op, threshold, key, **kw):
        return condition(field, label, r[field], op, threshold, key, **kw)

    def nonseed():
        check = pred("is_seed", "Known seed", "==", 0, "crawl.seed_guard", scored=False)
        if r.is_seed:
            check["distance"] = float("inf")  # known-seed status is not an adjustable observation
        return check

    if name == "coordinator":
        k = c[name]
        return group(
            "all",
            group(
                "any",
                pred(
                    "pays_seed",
                    "Seeds paid back",
                    ">=",
                    k["min_pays_seed"],
                    "roles.coordinator.min_pays_seed",
                ),
                pred(
                    "cycle_with_seeds",
                    "Other seeds on short cycles",
                    ">=",
                    k["min_cycle_seeds"],
                    "roles.coordinator.min_cycle_seeds",
                ),
            ),
            group(
                "any",
                pred(
                    "n_seed_sources",
                    "Reachable seed sources",
                    ">=",
                    k["min_seed_sources"],
                    "roles.coordinator.min_seed_sources",
                ),
                pred(
                    "betweenness", "Betweenness", ">=", bt_thr, "roles.coordinator.betweenness_pct"
                ),
            ),
        )
    if name == "distributor":
        k = c[name]
        return group(
            "all",
            pred("out_deg", "Recipients", ">=", k["min_out_deg"], "roles.distributor.min_out_deg"),
            pred(
                "out_deg",
                "Recipients versus payers",
                ">=",
                k["out_in_ratio"] * max(r.in_deg, 1),
                "roles.distributor.out_in_ratio × max(in_deg, 1)",
            ),
        )
    if name == "consolidator":
        k = c[name]
        return group(
            "all",
            pred("in_deg", "Payers", ">=", k["min_in_deg"], "roles.consolidator.min_in_deg"),
            group(
                "any",
                pred(
                    "pass_through",
                    "Outflow / observed inflow",
                    "<=",
                    k["max_pass_through"],
                    "roles.consolidator.max_pass_through",
                    applicable=not r.is_seed,
                ),
                pred(
                    "out_deg",
                    "Recipients versus payers",
                    "<=",
                    r.in_deg * k["out_in_ratio"],
                    "roles.consolidator.out_in_ratio × in_deg",
                ),
            ),
        )
    if name == "transit":
        k = c[name]
        return group(
            "all",
            nonseed(),
            pred("in_deg", "At least one payer", ">=", 1, "graph.has_incoming", scored=False),
            pred("out_deg", "At least one recipient", ">=", 1, "graph.has_outgoing", scored=False),
            group(
                "any",
                pred(
                    "pass_through",
                    "Outflow / observed inflow band",
                    "between",
                    [k["pass_through_low"], k["pass_through_high"]],
                    "roles.transit.pass_through_low/high",
                    applicable=not r.is_seed,
                ),
                group(
                    "all",
                    pred(
                        "fast_pass_share",
                        "Inflow forwarded within the configured time window",
                        ">=",
                        k["min_fast_pass_share"],
                        "roles.transit.min_fast_pass_share",
                        applicable=not r.is_seed,
                    ),
                    pred(
                        "pass_through",
                        "Fast-forwarding outflow cap",
                        "<=",
                        k["max_pass_through_fast"],
                        "roles.transit.max_pass_through_fast",
                        applicable=not r.is_seed,
                        scored=False,
                    ),
                ),
            ),
        )
    if name == "terminal":
        return group(
            "all",
            nonseed(),
            pred("out_deg", "No observed recipients", "==", 0, "graph.no_outgoing", scored=False),
            pred("in_deg", "At least one payer", ">=", 1, "graph.has_incoming", scored=False),
            group(
                "any",
                pred(
                    "depth",
                    "Outgoing transfers were crawled",
                    "<=",
                    3,
                    "crawl.observed_depth",
                    scored=False,
                ),
                pred(
                    "p_has_out",
                    "Estimated forwarding probability",
                    "<",
                    c[name]["max_p_has_out"],
                    "roles.terminal.max_p_has_out",
                    applicable=r.depth > 3 and not r.is_seed,
                    scored=False,
                ),
            ),
        )
    raise ValueError(name)


def rule(name, r, c, bt_thr):
    """Margins from the same predicate tree used in rule traces."""
    tree = rule_definition(name, r, c, bt_thr)
    return rule_margins(name, tree)


def rule_margins(name, tree):
    if not tree["passed"]:
        return None
    if name == "terminal":
        return [1.0]
    return [t["margin"] for t in tree["children"] if t["scored"]]


def flat_conditions(tree):
    if "children" not in tree:
        return [tree]
    return [leaf for child in tree["children"] for leaf in flat_conditions(child)]


def explain(r, c, bt_thr):
    """Ordered matches and the closest failed rule, by normalized predicate deficit.

    AND distances add; OR takes its closest branch. Missing / seed-excluded
    observations have infinite distance. A tie follows assignment order.
    This is a rule distance, never a likelihood or model confidence.
    """
    rules = []
    for name in RULES:
        tree = rule_definition(name, r, c, bt_thr)
        rules.append(
            {
                "role": name,
                "matched": tree["passed"],
                "distance": tree["distance"],
                "conditions": flat_conditions(tree),
                "logic": tree,
            }
        )
    failed = [item for item in rules if not item["matched"] and math.isfinite(item["distance"])]
    nearest = min(failed, key=lambda item: item["distance"]) if failed else None
    return {
        "matched_rule": next((item["role"] for item in rules if item["matched"]), None),
        "nearest_rule": nearest,
        "rules": rules,
    }


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


def fallback(r, c):
    """Ordered peripheral detail predicates, also exported in the dossier trace."""

    def p(field, label, op, threshold, source):
        return condition(field, label, r[field], op, threshold, source, scored=False)

    no_out = p("out_deg", "No observed recipients", "==", 0, "graph.no_outgoing")
    seed = p("is_seed", "Known seed", "==", 1, "crawl.seed_guard")
    no_in = p("in_deg", "No observed payers", "==", 0, "graph.no_incoming")
    depth4 = p("depth", "Outgoing activity not crawled", "==", 4, "crawl.last_depth")
    likely = condition(
        "p_has_out",
        "Estimated forwarding probability",
        r.p_has_out,
        ">",
        c["truncated_likely_forwarding_p"],
        "roles.truncated_likely_forwarding_p",
    )
    candidates = [
        ("seed_no_outgoing", group("all", seed, no_out)),
        ("no_edges", group("all", no_in, no_out)),
        ("truncated_likely_forwarding", group("all", depth4, no_out, likely)),
        ("truncated_unknown", group("all", depth4, no_out)),
    ]
    for detail, tree in candidates:
        if tree["passed"]:
            return detail, tree
    return "weak_signal", group("all")


def assign(r, c, bt_thr, trace=None):
    evaluated = trace["rules"] if trace else explain(r, c, bt_thr)["rules"]
    matched = {
        item["role"]: m
        for item in evaluated
        if (m := rule_margins(item["role"], item["logic"])) is not None
    }
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
        detail, _ = fallback(r, c)
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
    bt_top = f.betweenness.rank(method="max", ascending=False, pct=True)
    rows = []
    ctx.rule_traces = {}
    for values, top in zip(f.itertuples(index=False, name=None), bt_top):
        r = FeatureRow(zip(f.columns, values))
        r["bt_top"] = top
        trace = explain(r, c, bt_thr)
        role, detail, secondary, score = assign(r, c, bt_thr, trace=trace)
        trace.update(
            role=role, role_detail=detail, secondary_roles=secondary.split(";") if secondary else []
        )
        if role == "peripheral":
            _, tree = fallback(r, c)
            trace["fallback"] = {
                "role": detail,
                "matched": True,
                "distance": 0.0,
                "logic": tree,
                "conditions": flat_conditions(tree),
            }
        if getattr(ctx, "capture_explanations", True):
            ctx.rule_traces[str(r.gid)] = trace
        rows.append((r.gid, role, detail, secondary, score, evidence(r, role, detail, c)))
    return pd.DataFrame(
        rows, columns=["gid", "role", "role_detail", "secondary_roles", "role_score", "evidence"]
    )
