import streamlit as st

from app.theme import ROLE_COLORS
from app.ui import get_store, node_table, page_header

store = get_store()
page_header(
    "Who to review first, and why.",
    "A ranked review queue based on seed money, role evidence, connected sources and removal impact.",
)
a, b, c = st.columns([2, 1, 1])
role = a.selectbox("Role hypothesis", ["All roles"] + list(ROLE_COLORS))
hide = b.toggle("Hide known seeds", value=True)
limit = c.selectbox("Clients to show", [30, 50, 100], index=0)
rows = store.top_nodes(limit, role=None if role == "All roles" else role, include_seeds=not hide)
st.caption(
    "Select a row to open its dossier. Scores order analyst review and are not probabilities of wrongdoing."
)
node_table(rows, "priority_queue", ["gid", "role", "priority_score", "why", "cluster_id"])
st.download_button(
    "Download this review queue", rows.to_csv(index=False), "review_queue.csv", "text/csv"
)
