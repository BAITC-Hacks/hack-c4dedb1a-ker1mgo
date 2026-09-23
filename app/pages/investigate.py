import streamlit as st

from app import dossier
from app.graphview import render
from app.ui import focus, focused_gid, get_store, legend, page_header

store = get_store()
page_header(
    "Follow the money.",
    "Trace a client’s connections and inspect the evidence behind each finding.",
)


@st.fragment
def investigation():
    search, radius_col = st.columns([3, 1])
    query = search.text_input(
        "Find a client", placeholder="Search any part of a client ID", key="case_search"
    )
    radius = radius_col.radio(
        "Neighbourhood",
        [1, 2],
        horizontal=True,
        format_func=lambda r: f"{r} hop" + ("s" if r == 2 else ""),
    )
    if query.strip():
        hits = store.search(query, limit=100)
        if not hits:
            st.info(
                "No client ID contains this text. Try fewer digits, or select a client from Priorities."
            )
        elif len(hits) == 1:
            candidate = str(hits[0])
            if st.session_state.get("last_search") != query:
                focus(candidate)
                st.session_state.last_search = query
        else:
            selected = st.selectbox(
                f"Matching clients (up to {len(hits)})",
                [str(g) for g in hits],
                index=None,
                key="search_matches",
            )
            if selected and st.button("Open matching dossier", type="primary"):
                focus(selected)
    else:
        st.session_state.last_search = ""
    gid = focused_gid(store)
    graph, card = st.columns([1.65, 1], gap="large")
    with graph:
        st.subheader("Money flow")
        G = store.ego(gid, radius)
        color_by = (
            st.segmented_control(
                "Colour nodes by", ["role", "cluster"], default="role", key="graph_color"
            )
            or "role"
        )
        result = render(G, store.f, focus=gid, color_by=color_by, height=510, key="case_graph")
        if result.selected and store.has(result.selected) and str(result.selected) != str(gid):
            focus(result.selected)
            st.rerun(scope="fragment")
        legend()
        st.caption(
            f"{len(G):,} nodes / {G.number_of_edges():,} directed links. Edge width follows log KZT. Select a node to open its dossier."
        )
        if len(G) >= 300:
            st.caption(
                "This neighbourhood is capped at 300 nodes, keeping closest nodes and the largest flows first."
            )
    with card:
        dossier.summary(store, gid)
    st.divider()
    dossier.details(store, gid)


investigation()
