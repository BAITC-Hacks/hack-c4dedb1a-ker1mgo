import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.store import GraphStore  # noqa: E402
import charts  # noqa: E402
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


PAGES = ["Overview", "Network", "Node card", "Top list"]


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


def counterparties(nb, key, page):
    show = nb.assign(sum_kzt=nb.sum_kzt.map(fmt_kzt), gid=nb.gid.astype(str))
    ev = st.dataframe(show, hide_index=True, on_select="rerun", selection_mode="single-row", key=key)
    if ev.selection.rows:
        focus(nb.gid.iloc[ev.selection.rows[0]], page)
        st.rerun()


def overview_page():
    st.subheader("Overview")
    seeds = f[f.is_seed]
    k = st.columns(5)
    k[0].metric("clients", f"{len(f):,}")
    k[1].metric("transfer links", f"{store.G.number_of_edges():,}")
    k[2].metric("seeds", f"{len(seeds):,}")
    k[3].metric("KZT moved", fmt_kzt(store.edges.sum_kzt.sum()))
    k[4].metric("clusters", f"{(store.clusters.cluster_id > 0).sum() if len(store.clusters) else 0}")

    left, right = st.columns([2, 3])
    with left:
        st.markdown("**Roles**")
        st.plotly_chart(charts.role_counts(store.role_counts()), config={"displayModeBar": False})
        with st.expander("as table"):
            st.dataframe(store.role_counts().rename("nodes"))
    with right:
        st.markdown("**Clusters**")
        cl = store.cluster_summary()
        if cl.empty:
            st.caption("no clusters.csv yet")
        else:
            cl = cl.sort_values(["n_seed", "n_nodes"], ascending=False)
            st.dataframe(cl.assign(sum_kzt_internal=cl.sum_kzt_internal.map(fmt_kzt)), hide_index=True,
                         height=380)

    st.markdown("**Resilience**: what happens to the network if we remove the top-N nodes")
    res = store.resilience()
    if res.empty:
        st.caption("resilience.csv is empty until the priority step lands")
    else:
        st.plotly_chart(charts.resilience(res), config={"displayModeBar": False})
        with st.expander("as table"):
            st.dataframe(res, hide_index=True)


def gaps(node):
    out = []
    if node["is_seed"]:
        out.append("seed: incoming transfers were not crawled, so inflow is under-counted")
    if node["depth"] == 4:
        out.append("depth 4: outgoing transfers were not crawled")
        if node.get("p_has_out") is not None:
            out.append(f"truncation model: P(sends money on) = {node['p_has_out']:.2f}")
    return out


def card_page():
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
        f"{' · **seed**' if n['is_seed'] else ''} · cluster {n['cluster_id']}", unsafe_allow_html=True)
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
    k[5].metric("seed money in", fmt_kzt(n["seed_flow_in"] or 0), help=f"from {n['n_seed_sources']} seeds")

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

    st.button("show on network", on_click=focus, args=(gid, "Network"))
    nb = store.neighbors(gid)
    if len(nb):
        st.markdown("**Counterparties** (click to open)")
        counterparties(nb, key=f"nb_card_{gid}", page="Node card")


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
            st.caption(row.iloc[0].hypothesis)
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
    st.button("open node card", on_click=focus, args=(gid, "Node card"))
    if len(G) >= 300:
        st.caption("large neighbourhood: showing the 300 closest nodes, biggest flows first")
    st.iframe(render(G, f, focus=gid, color_by=color_by), height=670)

    nb = store.neighbors(gid)
    if len(nb):
        st.markdown("**Counterparties**")
        counterparties(nb, key=f"nb_{gid}", page="Network")


def top_page():
    st.subheader("Who to look at first")
    top = store.top_nodes(30)
    only_new = st.toggle("hide seeds", value=False)
    if only_new:
        top = store.top_nodes(30, include_seeds=False)
    show = top.assign(gid=top.gid.astype(str))
    st.caption("click a row to open its card")
    ev = st.dataframe(show, hide_index=True, on_select="rerun", selection_mode="single-row", key="top")
    if ev.selection.rows:
        focus(top.gid.iloc[ev.selection.rows[0]], "Node card")
        st.rerun()


{"Overview": overview_page, "Network": network_page, "Node card": card_page, "Top list": top_page}[page]()
