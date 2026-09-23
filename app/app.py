import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.store import GraphStore  # noqa: E402
from graphview import ROLE_COLORS, fmt_kzt, render  # noqa: E402

OUT = ROOT / "out"

st.set_page_config(page_title="Money graph", layout="wide")

if not (OUT / "features.parquet").exists():
    st.title("Money graph")
    st.warning("No outputs yet. Run `make run` first.")
    st.stop()


@st.cache_resource
def get_store(mtime):
    return GraphStore.load(OUT, ROOT / "project_docs" / "data")


store = get_store((OUT / "features.parquet").stat().st_mtime)
f = store.f


PAGES = ["Network", "Top list"]


def focus(gid, page="Network"):
    # applied on the next run, before the widgets are drawn
    st.session_state.goto = (int(gid), page)


if "goto" in st.session_state:
    gid, target = st.session_state.pop("goto")
    st.session_state.gid = gid
    st.session_state.page = target
    for k in [k for k in st.session_state if k == "top" or str(k).startswith("nb_")]:
        del st.session_state[k]


def on_search():
    hits = store.search(st.session_state.query)
    if len(hits) == 1:
        st.session_state.gid = hits[0]


def on_pick():
    if st.session_state.pick:
        st.session_state.gid = st.session_state.pick


# sidebar: gid search is always there
st.sidebar.title("Money graph")
page = st.sidebar.radio("Page", PAGES, key="page")
query = st.sidebar.text_input("Search gid", placeholder="full gid or any part of it", key="query",
                              on_change=on_search)
if query:
    hits = store.search(query)
    if not hits:
        st.sidebar.caption("no match")
    elif len(hits) > 1:
        st.sidebar.selectbox(f"{len(hits)} matches", hits, index=None, key="pick", on_change=on_pick)
if st.session_state.get("gid"):
    st.sidebar.caption(f"focus: `{st.session_state.gid}`")

st.sidebar.markdown("**Roles**")
st.sidebar.markdown(" ".join(
    f"<span style='color:{c}'>●</span> {r}" for r, c in ROLE_COLORS.items()), unsafe_allow_html=True)
st.sidebar.caption("thick dark border = seed · dashed = depth 4 (outgoing not crawled)")


def network_page():
    mode = st.radio("View", ["Ego graph", "Cluster"], horizontal=True, label_visibility="collapsed")
    c1, c2 = st.columns([1, 1])
    color_by = c2.radio("Colour by", ["role", "cluster"], horizontal=True)

    if mode == "Cluster":
        cids = sorted(f.cluster_id.unique())
        default = int(f.loc[st.session_state.gid, "cluster_id"]) if st.session_state.get("gid") else cids[-1]
        cid = c1.selectbox("Cluster", cids, index=cids.index(default) if default in cids else 0)
        G = store.cluster_graph(cid)
        row = store.cluster_summary(cid)
        if len(row):
            st.caption(f"{row.iloc[0].hypothesis} · {int(row.iloc[0].n_nodes)} nodes, "
                       f"{int(row.iloc[0].n_seed)} seeds")
        if len(G) < (f.cluster_id == cid).sum():
            st.caption(f"showing the top {len(G)} nodes by priority")
        st.iframe(render(G, f, focus=st.session_state.get("gid"), color_by=color_by), height=670)
        return

    gid = st.session_state.get("gid")
    if not gid:
        st.info("Search a gid in the sidebar, or pick one from the top list.")
        return
    radius = c1.radio("Radius", [1, 2], horizontal=True)
    G = store.ego(gid, radius)
    node = store.get_node(gid)
    st.markdown(f"**{gid}** · {node['role']} ({node['role_detail']}) · depth {node['depth']}"
                f"{' · seed' if node['is_seed'] else ''} · priority {node['priority_score']:.2f}")
    st.caption(node["evidence"])
    if len(G) >= 300:
        st.caption("large neighbourhood: showing the 300 closest nodes, biggest flows first")
    st.iframe(render(G, f, focus=gid, color_by=color_by), height=670)

    nb = store.neighbors(gid)
    if len(nb):
        st.markdown("**Counterparties**")
        nb = nb.assign(sum_kzt=nb.sum_kzt.map(fmt_kzt), gid=nb.gid.astype(str))
        ev = st.dataframe(nb, hide_index=True, on_select="rerun", selection_mode="single-row",
                          key=f"nb_{gid}")
        if ev.selection.rows:
            focus(nb.gid.iloc[ev.selection.rows[0]])
            st.rerun()


def top_page():
    st.subheader("Who to look at first")
    top = store.top_nodes(30)
    only_new = st.toggle("hide seeds", value=False)
    if only_new:
        top = store.top_nodes(30, include_seeds=False)
    show = top.assign(gid=top.gid.astype(str))
    st.caption("click a row to open it on the network")
    ev = st.dataframe(show, hide_index=True, on_select="rerun", selection_mode="single-row", key="top")
    if ev.selection.rows:
        focus(top.gid.iloc[ev.selection.rows[0]])
        st.rerun()


{"Network": network_page, "Top list": top_page}[page]()
