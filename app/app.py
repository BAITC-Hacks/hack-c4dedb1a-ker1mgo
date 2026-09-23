from pathlib import Path

import pandas as pd
import streamlit as st

OUT = Path("out")

st.set_page_config(page_title="Money graph", layout="wide")
st.title("Money graph")

if not (OUT / "nodes_roles.csv").exists():
    st.warning("No outputs yet. Run `make run` first.")
    st.stop()

nodes = pd.read_csv(OUT / "nodes_roles.csv")
top = pd.read_csv(OUT / "top_nodes.csv")

# TODO(C2): ego graph with pyvis, node card, overview, assistant tab
gid = st.sidebar.text_input("gid")
if gid:
    st.dataframe(nodes[nodes.gid.astype(str).str.contains(gid.strip())], use_container_width=True)
st.subheader("Top priorities")
st.dataframe(top, use_container_width=True)
