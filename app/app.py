"""Entry point for `streamlit run app/app.py`."""

import sys
from pathlib import Path

import streamlit as st

# Streamlit runs this file directly, so make project packages importable.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if sys.path[0] != str(PROJECT_ROOT):
    sys.path.insert(0, str(PROJECT_ROOT))

from app.navigation import apply_pending_navigation, sidebar  # noqa: E402
from app.resources import FEATURES_PATH, get_store  # noqa: E402
from app.views import assistant, method, network, node, overview, top  # noqa: E402

PAGES = {
    "Overview": overview.render,
    "Network": network.render,
    "Node card": node.render,
    "Top list": top.render,
    "Assistant": assistant.render,
    "Method & scale": method.render,
}


def main():
    st.set_page_config(page_title="Money graph", layout="wide")
    if not FEATURES_PATH.exists():
        st.title("Money graph")
        st.warning("No outputs yet. Run `make run` first.")
        st.stop()

    store = get_store(FEATURES_PATH.stat().st_mtime)
    apply_pending_navigation()
    page = sidebar(store, list(PAGES))
    PAGES[page](store)


if __name__ == "__main__":
    main()
