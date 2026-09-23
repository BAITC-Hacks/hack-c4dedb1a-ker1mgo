import streamlit as st

from agent import cards
from app import charts
from app.graphview import ROLE_COLORS
from app.navigation import focus, node_table
from app.resources import assistant_enabled
from moneygraph.formatting import fmt_kzt


def gaps(node):
    out = []
    if node["is_seed"]:
        out.append("seed: incoming transfers were not crawled, so inflow is under-counted")
    if node["depth"] == 4:
        out.append("depth 4: outgoing transfers were not crawled")
        if node.get("p_has_out") is not None:
            out.append(f"truncation model: P(sends money on) = {node['p_has_out']:.2f}")
    return out


def render(store):
    gid = st.session_state.get("gid")
    if not gid:
        st.info("Search a gid in the sidebar, or pick one from the top list.")
        return
    n = store.get_node(gid)
    color = ROLE_COLORS.get(n["role"], "#8F9996")
    st.markdown(f"### {gid}")
    st.markdown(
        f"<span style='background:{color};color:white;padding:2px 10px;border-radius:10px'>{n['role']}</span>"
        f" &nbsp;{n['role_detail']} · role score {n['role_score']:.2f} · depth {n['depth']}"
        f"{' · **seed**' if n['is_seed'] else ''} · cluster {n['cluster_id']}",
        unsafe_allow_html=True,
    )
    st.markdown(f"> {n['evidence']}")
    if n.get("secondary_roles"):
        st.caption(f"also matches: {n['secondary_roles']}")
    if n.get("flags"):
        st.markdown(" ".join(f"`{x}`" for x in str(n["flags"]).split(";") if x))
    for g in gaps(n):
        st.caption(f"gap: {g}")

    k = st.columns(6)
    k[0].metric("priority", f"{n['priority_score']:.2f}")
    k[1].metric("payers", n["in_deg"])
    k[2].metric("recipients", n["out_deg"])
    k[3].metric("in, KZT", fmt_kzt(n["in_kzt"]))
    k[4].metric("out, KZT", fmt_kzt(n["out_kzt"]))
    k[5].metric(
        "seed money in", fmt_kzt(n["seed_flow_in"] or 0), help=f"from {n['n_seed_sources']} seeds"
    )

    left, right = st.columns([2, 3])
    with left:
        st.markdown("**Why this priority**")
        st.caption(n["why"])
        comps = store.prio_components(gid)
        if comps:
            st.plotly_chart(charts.prio_breakdown(comps), config={"displayModeBar": False})
        else:
            st.caption("no component breakdown yet")
    with right:
        st.markdown("**Daily in vs out**")
        tl = store.tx_timeline(gid)
        if tl.empty:
            st.caption("no transfers")
        else:
            st.plotly_chart(charts.timeline(tl), config={"displayModeBar": False})

    with st.expander("fact card"):
        st.markdown(cards.fact_card(store, gid))
        if assistant_enabled():
            if st.button("write a summary", key=f"prose_{gid}"):
                with st.spinner("writing"):
                    st.session_state[f"prose_text_{gid}"] = cards.prose(store, gid)
            if st.session_state.get(f"prose_text_{gid}"):
                st.info(st.session_state[f"prose_text_{gid}"])

    st.button("show on network", on_click=focus, args=(gid, "Network"))
    nb = store.neighbors(gid)
    if len(nb):
        st.markdown("**Counterparties** (click to open)")
        node_table(
            nb.assign(sum_kzt=nb.sum_kzt.map(fmt_kzt)), key=f"nb_card_{gid}", page="Node card"
        )
