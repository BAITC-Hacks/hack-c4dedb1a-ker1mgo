import streamlit as st

from app.graphview import render
from app.theme import fmt_kzt
from app.ui import get_store, legend, node_table, open_dossier, page_header

store = get_store()
page_header(
    "Find the groups within the graph.",
    "Inspect connected communities, their role patterns, and the clients that deserve a closer look.",
)
clusters = store.cluster_summary()
if clusters.empty:
    st.info("No cluster summary is available. Run `make run` and refresh this page.")
    st.stop()
ordered = clusters.sort_values(["n_seed", "n_nodes"], ascending=False)
cid = st.selectbox(
    "Choose a cluster",
    ordered.cluster_id.tolist(),
    format_func=lambda x: f"Cluster {x}" + (" — isolated clients" if x == 0 else ""),
)
row = store.cluster_summary(cid).iloc[0]
st.write(row.hypothesis)
a, b, c = st.columns(3)
a.metric("Clients", int(row.n_nodes))
b.metric("Seeds", int(row.n_seed))
c.metric("Internal transfers", f"{fmt_kzt(row.sum_kzt_internal)} KZT")
view, members = st.tabs(["Community graph", "Cluster ledger"])
with view:
    G = store.cluster_graph(cid)
    result = render(G, store.f, height=510, key="cluster_graph")
    if result.selected and store.has(result.selected):
        open_dossier(result.selected)
    legend()
    if len(G) < row.n_nodes:
        st.caption(f"Showing the {len(G)} highest-priority clients of {int(row.n_nodes)}.")
    st.caption(
        "Communities use an undirected projection; arrows retain the original transfer direction. Membership is not evidence of a shared purpose."
    )
with members:
    subset = store.f[store.f.cluster_id.eq(cid)].sort_values("priority_score", ascending=False)
    node_table(subset, "cluster_members", ["gid", "role", "priority_score", "evidence"])
with st.expander("Compare all clusters"):
    st.dataframe(ordered, hide_index=True, width="stretch")
