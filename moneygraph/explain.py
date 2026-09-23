"""Pipeline-only evidence exports consumed by the viewer and assistant."""

import json
import math
from pathlib import Path

from . import roles, seed_paths


def clean(value):
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path, value):
    Path(path).write_text(
        json.dumps(clean(value), ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
    )


def logic_text(tree):
    if "children" in tree:
        if not tree["children"]:
            return "No primary role rule matched"
        return (
            "("
            + (" AND " if tree["operator"] == "all" else " OR ").join(
                map(logic_text, tree["children"])
            )
            + ")"
        )
    return tree["label"]


def public_rule(item):
    return {
        "role": item["role"],
        "matched": item["matched"],
        "distance": item["distance"],
        "logic": logic_text(item["logic"]),
        "conditions": [
            {key: value for key, value in condition.items() if key not in {"margin", "scored"}}
            for condition in item["conditions"]
        ],
    }


def dossier(row, cfg):
    """Plain-language observations first; seed and crawl caveats remain explicit."""
    detail = row.role_detail
    payers, recipients = roles.n(row.in_deg, "payer"), roles.n(row.out_deg, "recipient")
    if detail == "terminal_observed":
        text = f"Receives from {payers} and has no outgoing transfers where outgoing activity was checked, a pattern consistent with an end recipient."
    elif detail == "terminal_inferred":
        text = (
            f"Receives from {payers}. The model estimates a {row.p_has_out:.0%} chance of forwarding, suggesting a possible end recipient. "
            "Outgoing activity at depth 4 was not collected, so this remains an inference."
        )
    elif detail.startswith("truncated_"):
        text = f"Receives from {payers}, but outgoing activity at depth 4 was not collected: this is an unverified sink."
        if math.isfinite(row.p_has_out):
            text += f" The model estimates a {row.p_has_out:.0%} chance of forwarding."
        if detail == "truncated_likely_forwarding":
            text += " Request the next hop to check where money goes."
    elif row.role == "coordinator":
        observations = []
        if row.pays_seed:
            observations.append(f"sends transfers to {roles.n(row.pays_seed, 'known seed')}")
        if row.cycle_with_seeds:
            observations.append(
                f"shares short transfer cycles with {roles.n(row.cycle_with_seeds, 'other seed')}"
            )
        text = "; ".join(observations).capitalize() + ", a pattern consistent with coordination."
    elif row.role == "distributor":
        text = f"Sends {roles.kzt(row.out_kzt)} KZT to {recipients}"
        if not row.is_seed:
            text += f" after receiving from {payers}"
        text += ", a pattern consistent with distribution."
    elif row.role == "consolidator":
        if row.is_seed:
            text = f"A known seed with {payers} and only {recipients}, a pattern consistent with consolidation."
        else:
            ratio = (
                f" and sends on {row.pass_through:.0%} of visible inflow"
                if math.isfinite(row.pass_through)
                else ""
            )
            text = f"Receives from {payers}{ratio} to {recipients}, a pattern consistent with consolidation."
    elif row.role == "transit":
        text = (
            f"Sends on {row.pass_through:.0%} of visible inflow to {recipients}; "
            f"{row.fast_pass_share:.0%} of inflow is matched to transfers sent within {cfg['temporal']['fast_pass_days']} days. "
            "This is consistent with transit activity."
        )
    elif detail == "seed_no_outgoing":
        text = "A known seed with no outgoing transfers in the supplied data. Request its transfer history to resolve the gap."
    elif detail == "no_edges":
        text = "No transfers involving this client appear in the supplied data. Request its transfer history before drawing conclusions."
    else:
        text = f"Receives from {payers} and sends to {recipients}; no structural role rule fully matches the observed pattern."
    text += f" About {roles.kzt(row.seed_flow_in)} KZT of modeled seed money reaches this client."
    if row.n_seed_sources:
        text += (
            f" Visible directed paths connect it to {roles.n(row.n_seed_sources, 'source seed')}."
        )
    if row.is_seed:
        text += " Its incomplete inflow is excluded from pass-through rules."
    return (
        text
        + " Treat this as an investigation hypothesis; modeled flow is not transaction-level attribution."
    )


def write(ctx, out_dir):
    out = Path(out_dir)
    nodes = {}
    for row in ctx.features.itertuples(index=False):
        trace = ctx.rule_traces[str(row.gid)]
        nodes[str(row.gid)] = {
            "role": row.role,
            "role_detail": row.role_detail,
            "matched_rule": trace["matched_rule"],
            "secondary_roles": trace["secondary_roles"],
            "rules": [public_rule(item) for item in trace["rules"]],
            "nearest_rule": public_rule(trace["nearest_rule"]) if trace["nearest_rule"] else None,
            "fallback": public_rule(trace["fallback"]) if "fallback" in trace else None,
            "priority": ctx.priority_audit[str(row.gid)],
            "dossier": dossier(row, ctx.cfg),
        }
    write_json(
        out / "rule_traces.json",
        {
            "schema_version": 1,
            "rule_order": roles.RULES,
            "semantics": "First matching rule wins; peripheral is the fallback. Secondary hints do not override the primary role.",
            "nearest_method": "Among failed rules with available evidence, sum normalized deficits for AND and take the minimum for OR; ties follow rule order. Distance is not a probability.",
            "seed_guard": "Seed pass-through observations are excluded, even if a value was supplied.",
            "nodes": nodes,
        },
    )
    write_json(out / "seed_paths.json", seed_paths.build(ctx))
    ctx.edges.to_parquet(out / "edges.parquet", index=False)
    ctx.tx.to_parquet(out / "transactions.parquet", index=False)
