import html

import streamlit as st

from app import charts
from app.theme import fmt_kzt
from app.ui import get_store, open_dossier, page_header

store = get_store()
f = store.f
page_header(
    "From known couriers to a network worth investigating.",
    "Follow seed-originated money, inspect the evidence, and decide which client to review next.",
)
metrics = st.columns(4)
metrics[0].metric("Clients in this crawl", f"{len(f):,}")
metrics[1].metric("Known starting points", f"{int(f.is_seed.sum()):,}")
metrics[2].metric("Visible transfer volume", f"{fmt_kzt(store.edges.sum_kzt.sum())} KZT")
metrics[3].metric("Transfer links", f"{len(store.edges):,}")

left, right = st.columns([1.35, 1], gap="large")
with left:
    st.subheader("Start with a reason to look closer")
    top = store.top_nodes(1, include_seeds=False).iloc[0]
    node = store.get_node(top.gid)
    st.html(
        f'<div class="case-note"><strong>{html.escape(node["why"])}</strong><br>'
        f'<span class="dossier-id">{node["gid"]}</span><br>{html.escape(node["evidence"])}</div>'
    )
    if st.button("Investigate highest-priority client", type="primary"):
        open_dossier(top.gid)
    picks = store.demo_picks()
    demo_labels = {
        "biggest distributor": "Explore a distribution hub",
        "depth 4, inferred terminal": "Inspect an inferred end recipient",
    }
    for key, label in demo_labels.items():
        if key in picks and st.button(label, key=key):
            open_dossier(picks[key])
with right:
    st.subheader("Role hypotheses across the case")
    st.plotly_chart(charts.role_counts(store.role_counts()), config={"displayModeBar": False})

st.subheader("A missing edge is not evidence that money stopped")
depth4 = int(f.depth.eq(4).sum())
observed = int(f.role_detail.eq("terminal_observed").sum())
inferred = int(f.role_detail.eq("terminal_inferred").sum())
naive, ours = st.columns(2, gap="large")
with naive:
    st.html(
        f'<div class="finding-line"><h3>Naive: no outgoing edge means terminal</h3><p>This would label all {depth4:,} depth-4 clients as sinks, although their outgoing transfers were never crawled.</p></div>'
    )
with ours:
    st.html(
        f'<div class="finding-line"><h3>Our approach: observed and inferred stay separate</h3><p>{observed:,} observed terminals; {inferred:,} inferred terminals. A model learns forwarding patterns from shallower nodes; uncertain clients remain explicit data gaps.</p></div>'
    )

findings = [
    (
        "Follow money from the seeds",
        "Priority uses propagated KZT from the known starting points, with caps on visible outflow. Every dossier shows source routes and the contributions behind its score.",
    ),
    (
        "Test the choice against a baseline",
        "The resilience comparison includes degree, degree without seeds, and random removal. It shows where prioritizing money flow helps and where the simpler method wins.",
    ),
    (
        "Turn uncertainty into the next request",
        "Depth-4 forwarding candidates, missing seed inflows and small components become specific requests for the next crawl.",
    ),
    (
        "Ask questions with checked references",
        "The optional assistant reads graph tools and checks cited client IDs. Rule assignments and priority calculations stay in the reproducible pipeline.",
    ),
]
for pair in (findings[:2], findings[2:]):
    for column, (title, text) in zip(st.columns(2, gap="large"), pair):
        with column:
            st.html(f'<div class="finding-line"><h3>{title}</h3><p>{text}</p></div>')
