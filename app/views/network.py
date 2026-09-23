import streamlit as st

from app.graphview import render as render_graph
from app.navigation import focus, node_table
from moneygraph.formatting import fmt_kzt


def render(store):
    f = store.f
    mode = st.radio("View", ["Ego graph", "Cluster"], horizontal=True, label_visibility="collapsed")
    c1, c2 = st.columns([1, 1])
    color_by = c2.radio("Colour by", ["role", "cluster"], horizontal=True)

    if mode == "Cluster":
        cids = sorted(f.cluster_id.unique())
        default = (
            int(f.loc[st.session_state.gid, "cluster_id"])
            if st.session_state.get("gid")
            else cids[-1]
        )
        cid = c1.selectbox("Cluster", cids, index=cids.index(default) if default in cids else 0)
        G = store.cluster_graph(cid)
        row = store.cluster_summary(cid)
        if len(row):
            st.caption(row.iloc[0].hypothesis)
        if len(G) < (f.cluster_id == cid).sum():
            st.caption(f"showing the top {len(G)} nodes by priority")
        st.iframe(
            render_graph(G, f, focus=st.session_state.get("gid"), color_by=color_by), height=670
        )
        return

    gid = st.session_state.get("gid")
    if not gid:
        st.info("Search a gid in the sidebar, or pick one from the top list.")
        return
    radius = c1.radio("Radius", [1, 2], horizontal=True)
    G = store.ego(gid, radius)
    node = store.get_node(gid)
    st.markdown(
        f"**{gid}** · {node['role']} ({node['role_detail']}) · depth {node['depth']}"
        f"{' · seed' if node['is_seed'] else ''} · priority {node['priority_score']:.2f}"
    )
    st.caption(node["evidence"])
    st.button("open node card", on_click=focus, args=(gid, "Node card"))
    if len(G) >= 300:
        st.caption("large neighbourhood: showing the 300 closest nodes, biggest flows first")
    st.iframe(render_graph(G, f, focus=gid, color_by=color_by), height=670)

    nb = store.neighbors(gid)
    if len(nb):
        st.markdown("**Counterparties**")
        node_table(nb.assign(sum_kzt=nb.sum_kzt.map(fmt_kzt)), key=f"nb_{gid}", page="Network")
