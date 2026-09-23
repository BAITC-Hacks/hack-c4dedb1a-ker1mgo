import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))

from app.ui import get_store, legend

st.set_page_config(page_title="Money graph | Case workspace", page_icon="◈", layout="wide")
st.html(ROOT / "app/style.css")
pages = [
    st.Page("pages/briefing.py", title="Briefing", default=True),
    st.Page("pages/investigate.py", title="Investigate"),
    st.Page("pages/clusters.py", title="Clusters"),
    st.Page("pages/priorities.py", title="Priorities"),
    st.Page("pages/data_gaps.py", title="Data gaps"),
    st.Page("pages/assistant.py", title="Assistant"),
    st.Page("pages/method.py", title="Method & scale"),
]
page = st.navigation(pages, position="hidden")
store = get_store()
with st.sidebar:
    st.html('<div class="brand"><span class="brand-mark">◈</span>Money graph</div>'
            '<div class="sidebar-caption">Financial intelligence workspace</div>')
    for item in pages:
        st.page_link(item)
    st.divider()
    st.caption(f"{len(store.f):,} clients / {int(store.f.is_seed.sum()):,} starting points")
    legend()
    st.caption("Outlined nodes are seeds. Dashed outlines mark depth 4, where outgoing transfers were not crawled.")
    st.divider()
    st.caption("Findings are hypotheses for review. The graph shows visible transfers, not complete account balances.")
page.run()
