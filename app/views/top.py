import streamlit as st

from app.navigation import node_table


def render(store):
    st.subheader("Who to look at first")
    only_new = st.toggle("hide seeds", value=False)
    top = store.top_nodes(30, include_seeds=not only_new)
    st.caption("click a row to open its card")
    node_table(top, key="top", page="Node card")
