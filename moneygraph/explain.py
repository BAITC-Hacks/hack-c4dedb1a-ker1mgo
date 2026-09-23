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
    Path(path).write_text(json.dumps(clean(value), ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")


def logic_text(tree):
    if "children" in tree:
        return "(" + (" AND " if tree["operator"] == "all" else " OR ").join(map(logic_text, tree["children"])) + ")"
    return tree["label"]


def public_rule(item):
    return {"role": item["role"], "matched": item["matched"], "distance": item["distance"],
            "logic": logic_text(item["logic"]),
            "conditions": [{key: value for key, value in condition.items() if key not in {"margin", "scored"}}
                           for condition in item["conditions"]]}


def dossier(row):
    detail = row.role_detail
    if detail == "terminal_observed":
        role_text = "The observed transfers suggest an end recipient: outgoing activity was crawled and none was found."
    elif detail == "terminal_inferred":
        role_text = "The inbound pattern suggests a possible end recipient; this is a model inference because outgoing activity at depth 4 was not crawled."
    elif detail.startswith("truncated_"):
        role_text = "Outgoing activity was not crawled at depth 4, so this node is an unverified sink."
    elif row.role == "peripheral":
        role_text = "The observed pattern does not meet a primary structural role rule."
    else:
        role_text = f"The observed pattern shows signs of {row.role} activity under the ordered role rules."
    money = f" About {roles.kzt(row.seed_flow_in)} KZT of modeled seed-originated flow reaches it in the final propagation round."
    known = " It is already a known seed, and its incomplete inflow is excluded from pass-through rules." if row.is_seed else ""
    priority = f" Its review priority is {row.priority_score:.3f} on the current graph's relative scale."
    return role_text + money + priority + known + " This is an investigation hypothesis, not an allegation."


def write(ctx, out_dir):
    out = Path(out_dir)
    nodes = {}
    for row in ctx.features.itertuples(index=False):
        trace = ctx.rule_traces[str(row.gid)]
        nodes[str(row.gid)] = {"role": row.role, "role_detail": row.role_detail,
                              "matched_rule": trace["matched_rule"], "secondary_roles": trace["secondary_roles"],
                              "rules": [public_rule(item) for item in trace["rules"]],
                              "nearest_rule": public_rule(trace["nearest_rule"]) if trace["nearest_rule"] else None,
                              "fallback": public_rule(trace["fallback"]) if "fallback" in trace else None,
                              "priority": ctx.priority_audit[str(row.gid)], "dossier": dossier(row)}
    write_json(out / "rule_traces.json", {
        "schema_version": 1, "rule_order": roles.RULES,
        "semantics": "First matching rule wins; peripheral is the fallback. Secondary hints do not override the primary role.",
        "nearest_method": "Among failed rules with available evidence, sum normalized deficits for AND and take the minimum for OR; ties follow rule order. Distance is not a probability.",
        "seed_guard": "Seed pass-through observations are excluded, even if a value was supplied.",
        "nodes": nodes,
    })
    write_json(out / "seed_paths.json", seed_paths.build(ctx))
    ctx.edges.to_parquet(out / "edges.parquet", index=False)
    ctx.tx.to_parquet(out / "transactions.parquet", index=False)
