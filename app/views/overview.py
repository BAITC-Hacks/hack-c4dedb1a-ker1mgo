import streamlit as st

from app import charts
from app.navigation import node_table
from moneygraph.formatting import fmt_kzt


def render(store):
    f = store.f
    st.subheader("Overview")
    seeds = f[f.is_seed]
    role_counts = store.role_counts()
    k = st.columns(5)
    k[0].metric("clients", f"{len(f):,}")
    k[1].metric("transfer links", f"{store.G.number_of_edges():,}")
    k[2].metric("seeds", f"{len(seeds):,}")
    k[3].metric("KZT moved", fmt_kzt(store.edges.sum_kzt.sum()))
    k[4].metric(
        "clusters", f"{(store.clusters.cluster_id > 0).sum() if len(store.clusters) else 0}"
    )

    left, right = st.columns([2, 3])
    with left:
        st.markdown("**Roles**")
        st.plotly_chart(charts.role_counts(role_counts), config={"displayModeBar": False})
        with st.expander("as table"):
            st.dataframe(role_counts.rename("nodes"))
    with right:
        st.markdown("**Clusters**")
        cl = store.cluster_summary()
        if cl.empty:
            st.caption("no clusters.csv yet")
        else:
            cl = cl.sort_values(["n_seed", "n_nodes"], ascending=False)
            st.dataframe(
                cl.assign(sum_kzt_internal=cl.sum_kzt_internal.map(fmt_kzt)),
                hide_index=True,
                height=380,
            )

    with st.expander("Data gaps: what to request next"):
        dr = store.data_requests
        if dr.empty:
            st.caption("no data_requests.csv yet")
        else:
            counts = dr.groupby("reason").gid.nunique().sort_values(ascending=False)
            st.caption(" · ".join(f"{r}: {n}" for r, n in counts.items()))
            reason = st.selectbox("reason", ["all"] + counts.index.tolist(), key="dr_reason")
            show = dr if reason == "all" else dr[dr.reason == reason]
            node_table(show, key="dr", page="Node card")

    st.markdown("**Resilience**: what happens to the network if we remove the top-N nodes")
    res = store.resilience()
    if res.empty:
        st.caption("resilience.csv is empty until the priority step lands")
    else:
        st.plotly_chart(charts.resilience(res), config={"displayModeBar": False})
        with st.expander("as table"):
            st.dataframe(res, hide_index=True)
