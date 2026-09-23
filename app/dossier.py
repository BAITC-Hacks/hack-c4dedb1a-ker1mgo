import html

import pandas as pd
import streamlit as st

from app import charts
from app.theme import fmt_kzt
from app.ui import badge, focus


def _number(value):
    if value is None:
        return "not available"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (float, int)):
        return f"{value:,.4g}" if isinstance(value, float) else str(value)
    return str(value)


def _condition_value(condition, key):
    value = condition.get(key)
    field = condition.get("field", "")
    if value is not None and field in {"pass_through", "fast_pass_share", "p_has_out"}:
        if isinstance(value, (float, int)):
            return f"{value:.1%}"
        if isinstance(value, (list, tuple)):
            return " – ".join(f"{v:.1%}" for v in value)
    return _number(value)


def condition_table(rule):
    if not rule:
        return
    if rule.get("logic"):
        st.caption(rule["logic"])
    rows = []
    for c in rule.get("conditions", []):
        applicable = c.get("applicable", True)
        available = c.get("available", True)
        rows.append(
            {
                "Condition": c.get("label", c.get("field", "")),
                "Value": _condition_value(c, "value"),
                "Test": f"{c.get('operator', '')} {_condition_value(c, 'threshold')}",
                "Result": "not applicable"
                if not applicable
                else "unknown"
                if not available
                else "✓"
                if c.get("passed")
                else "✗",
                "Gap": _condition_value(c, "deficit")
                if applicable and not c.get("passed")
                else "—",
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def compact_conditions(rule):
    rows = []
    for condition in rule.get("conditions", []):
        if not condition.get("applicable", True):
            result = "not applicable"
        elif not condition.get("available", True):
            result = "not available"
        else:
            operator = (
                condition.get("operator", "")
                .replace(">=", "≥")
                .replace("<=", "≤")
                .replace("==", "=")
            )
            result = f"{_condition_value(condition, 'value')} {operator} {_condition_value(condition, 'threshold')} {'✓' if condition.get('passed') else '✗'}"
        rows.append(
            f'<div class="trace-condition"><span>{html.escape(condition.get("label", condition.get("field", "")))}</span><strong>{html.escape(result)}</strong></div>'
        )
    st.html("".join(rows))
    if rule.get("logic"):
        st.caption(rule["logic"])


def summary(store, gid):
    n = store.get_node(gid)
    trace = store.rule_trace(gid)
    st.subheader("Client dossier")
    st.html(f'<div class="dossier-id">{gid}</div>')
    badge(n["role"], n["role_detail"])
    st.write(trace.get("dossier") or n["evidence"])
    a, b = st.columns(2)
    a.metric("Priority", f"{n['priority_score']:.3f}")
    b.metric("Seed money reaching client", f"{fmt_kzt(n.get('seed_flow_in'))} KZT")
    st.caption(
        f"Depth {n['depth']} / Cluster {n['cluster_id']} / Role strength {n['role_score']:.2f}"
    )
    if n["is_seed"]:
        st.info(
            "This is a known starting point. Its incoming transfers were under-crawled, so its inflow cannot support a balance or pass-through finding."
        )
    if n["depth"] == 4:
        st.info(
            "Outgoing transfers were not crawled at depth 4. A terminal role here is inferred, not observed."
        )
        p = n.get("p_has_out")
        if p is not None:
            st.caption(f"Model estimate of forwarding: {p:.0%}. This is not a verified outcome.")
    rules = trace.get("rules", [])
    chosen = next((r for r in rules if r.get("role") == n["role"]), None)
    if n["role"] == "peripheral":
        chosen = trace.get("fallback_rule", trace.get("fallback", chosen))
    st.markdown("**Why this role?**")
    if chosen:
        compact_conditions(chosen)
    else:
        st.caption(n["evidence"])
    st.caption(
        "First matching rule wins. Role strength is a rule margin, not a probability of wrongdoing."
    )


def details(store, gid):
    n = store.get_node(gid)
    trace = store.rule_trace(gid)
    evidence, priority, routes, activity = st.tabs(
        ["Rule evidence", "Priority calculation", "Seed-money routes", "Transfer ledger"]
    )
    with evidence:
        nearest = trace.get("nearest_rule")
        if nearest:
            st.markdown(f"**Closest alternative: {nearest.get('role', 'another rule')}**")
            st.caption(
                "The smallest normalized rule gap identifies this alternative. Failed conditions show the change needed; an unavailable measurement cannot be treated as a match."
            )
            condition_table(nearest)
        for rule in trace.get("rules", []):
            with st.expander(
                f"{rule.get('role', 'Rule')} — {'matches' if rule.get('matched') else 'does not match'}"
            ):
                condition_table(rule)
        if not trace:
            st.info(
                "Rule trace is missing. Rebuild outputs with `make run` to inspect the configured conditions."
            )
        if n.get("secondary_roles"):
            st.caption("Additional signals: " + n["secondary_roles"].replace(";", ", "))
    with priority:
        st.write(n["why"])
        st.plotly_chart(
            charts.priority_waterfall(
                store.prio_components(gid), n["priority_score"], trace.get("priority")
            ),
            config={"displayModeBar": False},
        )
        st.caption(
            "Weighted percentile contributions are summed, adjusted for known seeds, then rescaled so the highest priority is 1. Priority orders review; it is not a risk probability."
        )
    with routes:
        paths = store.money_paths(gid)
        metadata = getattr(store, "seed_paths", {})
        st.write("Largest modeled routes from the known starting points")
        st.caption(
            metadata.get(
                "method",
                "Proportional attribution of seed-originated money through visible transfers.",
            )
        )
        if paths.get("paths"):
            coverage = paths.get("coverage", 0)
            st.caption(
                f"Shown routes account for {coverage:.1%} of modeled seed money reaching this client. Unlisted contribution: {fmt_kzt(paths.get('omitted_kzt', 0))} KZT."
            )
            for i, route in enumerate(paths["paths"], 1):
                st.markdown(
                    f"**{i}. {fmt_kzt(route['kzt'])} KZT**"
                    + (" — includes a return cycle" if route.get("contains_cycle") else "")
                )
                st.code(" → ".join(route["gids"]), language=None, wrap_lines=True)
        else:
            st.info(
                "No attributed seed-money route reaches this client within the model horizon. Check its visible counterparties in the transfer ledger."
            )
        limitations = metadata.get(
            "limitations",
            "Routes describe an aggregate flow model; they do not prove that particular transfers carried the same money.",
        )
        st.caption(" ".join(limitations) if isinstance(limitations, list) else limitations)
    with activity:
        a, b, c, d = st.columns(4)
        a.metric("Distinct payers", n["in_deg"])
        b.metric("Distinct recipients", n["out_deg"])
        c.metric("Visible inflow", f"{fmt_kzt(n['in_kzt'])} KZT")
        d.metric("Visible outflow", f"{fmt_kzt(n['out_kzt'])} KZT")
        timeline = store.tx_timeline(gid)
        if len(timeline):
            st.plotly_chart(charts.timeline(timeline), config={"displayModeBar": False})
        else:
            st.info(
                "No visible transfers for this client. Review Data gaps for a follow-up request."
            )
        nb = store.neighbors(gid)
        if len(nb):
            show = nb.assign(gid=nb.gid.map(str))
            st.dataframe(
                show,
                hide_index=True,
                width="stretch",
                column_config={
                    "gid": "Client ID",
                    "sum_kzt": st.column_config.NumberColumn("KZT", format="localized"),
                },
            )
            target = st.selectbox(
                "Open a counterparty", show.gid, index=None, key=f"counterparty_{gid}"
            )
            if target and st.button("Focus counterparty", key=f"focus_{gid}"):
                focus(target)
                st.rerun(scope="fragment")
        if n.get("flags"):
            st.caption("Patterns to inspect: " + n["flags"].replace(";", ", "))
