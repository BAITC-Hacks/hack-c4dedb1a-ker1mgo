"""Sidebar controls and navigation shared by the viewer screens."""

import streamlit as st

from app.graphview import ROLE_COLORS


def focus(gid, page="Network"):
    # Apply on the next run, before the destination widgets are drawn.
    st.session_state.goto = (int(gid), page)


def apply_pending_navigation():
    if "goto" not in st.session_state:
        return
    gid, page = st.session_state.pop("goto")
    st.session_state.gid = gid
    st.session_state.page = page
    for key in list(st.session_state):
        if key in ("top", "dr") or str(key).startswith("nb_"):
            del st.session_state[key]


def _on_search(store):
    hits = store.search(st.session_state.query)
    if len(hits) == 1:
        st.session_state.gid = hits[0]


def _on_pick():
    if st.session_state.pick:
        st.session_state.gid = st.session_state.pick


def sidebar(store, pages):
    st.sidebar.title("Money graph")
    page = st.sidebar.radio("Page", pages, key="page")
    query = st.sidebar.text_input(
        "Search gid",
        placeholder="full gid or any part of it",
        key="query",
        on_change=_on_search,
        args=(store,),
    )
    if query:
        hits = store.search(query)
        if not hits:
            st.sidebar.caption("no match")
        elif len(hits) > 1:
            st.sidebar.selectbox(
                f"{len(hits)} matches", hits, index=None, key="pick", on_change=_on_pick
            )
    if st.session_state.get("gid"):
        st.sidebar.caption(f"focus: `{st.session_state.gid}`")

    with st.sidebar.expander("Demo walk-through"):
        for label, gid in store.demo_picks().items():
            st.button(
                label, key=f"demo_{label}", on_click=focus, args=(gid, "Node card"), width="stretch"
            )

    st.sidebar.markdown("**Roles**")
    st.sidebar.markdown(
        " ".join(
            f"<span style='color:{color}'>●</span> {role}" for role, color in ROLE_COLORS.items()
        ),
        unsafe_allow_html=True,
    )
    st.sidebar.caption("thick dark border = seed · dashed = depth 4 (outgoing not crawled)")
    return page


def node_table(rows, *, key, page):
    """Render a table whose selected row opens the corresponding node."""
    show = rows.assign(gid=rows.gid.astype(str))
    event = st.dataframe(
        show, hide_index=True, on_select="rerun", selection_mode="single-row", key=key
    )
    if event.selection.rows:
        focus(rows.gid.iloc[event.selection.rows[0]], page)
        st.rerun()
