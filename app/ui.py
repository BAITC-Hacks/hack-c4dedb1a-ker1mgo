import html
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from agent.store import GraphStore
from app.theme import ROLE_COLORS, ROLE_LABELS

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("MONEYGRAPH_OUT", ROOT / "out"))


@st.cache_resource(show_spinner="Opening the case outputs…")
def _load_store(path, signature):
    return GraphStore.load(path)


def get_store():
    required = ["features.parquet", "edges.parquet", "transactions.parquet"]
    missing = [name for name in required if not (OUT / name).exists()]
    if missing:
        st.info("This case has not been prepared yet. Run `make run`, then refresh this page.")
        st.caption("Missing outputs: " + ", ".join(missing))
        st.stop()
    files = sorted(p for p in OUT.iterdir() if p.is_file())
    signature = tuple((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in files)
    try:
        return _load_store(str(OUT), signature)
    except (OSError, ValueError, KeyError) as error:
        st.error("The case outputs could not be opened. Run `make run` to rebuild them, then refresh.")
        with st.expander("Diagnostic details"):
            st.code(str(error))
        st.stop()


@st.cache_data
def read_table(path, modified):
    return pd.read_csv(path)


@st.cache_data
def read_json(path, modified):
    return json.loads(Path(path).read_text())


def page_header(title, description=""):
    store = get_store()
    dates = store.tx.date
    period = f"{dates.min():%d %b} – {dates.max():%d %b %Y}" if len(dates) else "No dated transfers"
    st.html(f'<div class="case-line"><span>Case workspace / KZT</span><span>{period}</span></div>')
    st.title(title)
    if description:
        st.html(f'<p class="page-description">{html.escape(description)}</p>')


def focus(gid):
    st.session_state.gid = str(gid)


def open_dossier(gid):
    focus(gid)
    st.switch_page("pages/investigate.py")


def focused_gid(store):
    selected = st.session_state.get("gid")
    if selected is None or not store.has(selected):
        selected = str(store.top_nodes(1, include_seeds=False).gid.iloc[0])
        focus(selected)
    return int(selected)


def badge(role, detail=""):
    label = ROLE_LABELS.get(role, role)
    st.html(f'<span class="role-badge"><i class="role-dot" style="background:{ROLE_COLORS.get(role, "#8F9996")}"></i>{html.escape(label)}</span>')
    if detail and detail != role:
        st.caption(detail.replace("_", " "))


def legend():
    items = ''.join(f'<span><i class="role-dot" style="background:{color}"></i>{role}</span>' for role, color in ROLE_COLORS.items())
    st.html(f'<div class="role-legend">{items}</div>')


def node_table(frame, key, columns=None):
    if frame.empty:
        st.info("No clients match these filters. Broaden the selection to continue.")
        return
    show = frame.copy()
    if "gid" in show:
        show["gid"] = show["gid"].map(str)
    if columns:
        show = show[[c for c in columns if c in show]]
    selected = st.dataframe(show, hide_index=True, width="stretch", key=key,
                            on_select="rerun", selection_mode="single-row",
                            column_config={"gid": st.column_config.TextColumn("Client ID"),
                                           "priority_score": st.column_config.NumberColumn("Priority", format="%.3f"),
                                           "sum_kzt": st.column_config.NumberColumn("KZT", format="localized"),
                                           "why": st.column_config.TextColumn("Reason for review", width="large")})
    if selected.selection.rows:
        gid = frame.iloc[selected.selection.rows[0]].gid
        if st.button("Open selected dossier", key=f"open_{key}", type="primary"):
            open_dossier(gid)
