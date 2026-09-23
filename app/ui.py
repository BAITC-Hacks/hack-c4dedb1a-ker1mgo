import html
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from agent.store import GraphStore
from app.presentation import COLUMNS, DETAILS, REQUESTS, ROLE_NAMES, number, priority_reason, summary
from app.theme import ROLE_COLORS, ROLE_LABELS

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("MONEYGRAPH_OUT", ROOT / "out"))


@st.cache_resource(show_spinner="Открываем материалы…")
def _load_store(path, signature):
    return GraphStore.load(path)


def get_store():
    required = ["features.parquet", "edges.parquet", "transactions.parquet"]
    missing = [name for name in required if not (OUT / name).exists()]
    if missing:
        st.info("Материалы ещё не подготовлены. Выполните `make run` и обновите страницу.")
        st.caption("Отсутствуют файлы: " + ", ".join(missing))
        st.stop()
    files = sorted(p for p in OUT.iterdir() if p.is_file())
    signature = tuple((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in files)
    try:
        return _load_store(str(OUT), signature)
    except (OSError, ValueError, KeyError) as error:
        st.error("Не удалось открыть материалы. Выполните `make run`, затем обновите страницу.")
        with st.expander("Технические подробности"):
            st.code(str(error))
        st.stop()


@st.cache_data
def read_table(path, modified):
    return pd.read_csv(path)


@st.cache_data
def read_json(path, modified):
    return json.loads(Path(path).read_text())


def page_header(title, description=""):
    dates = get_store().tx.date
    period = f"{dates.min():%d.%m}–{dates.max():%d.%m.%Y}" if len(dates) else "Период не указан"
    st.html(f'<div class="case-line"><span>Финансовое расследование <span class="case-product">Money graph</span></span><span>{period} <span class="case-currency">KZT</span></span></div>')
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
        st.caption(DETAILS.get(detail, detail))


def legend():
    items = ''.join(f'<span title="{role}"><i class="role-dot" style="background:{color}"></i>{ROLE_NAMES[role]}</span>' for role, color in ROLE_COLORS.items())
    st.html(f'<div class="role-legend">{items}</div>')


def display_table(frame, store=None):
    show = frame.copy()
    if "gid" in show:
        show["gid"] = show["gid"].map(str)
    if "role" in show:
        show["role"] = show.role.map(lambda r: ROLE_NAMES.get(r, r))
    if store is not None:
        for column, formatter in (("why", priority_reason), ("evidence", summary)):
            if column in show:
                show[column] = [formatter(store.get_node(gid)) for gid in frame.gid]
    if "reason" in show:
        show["reason"] = frame.reason.map(lambda r: REQUESTS.get(r, (r, ""))[0])
    if "suggested_request" in show:
        show["suggested_request"] = frame.reason.map(lambda r: REQUESTS.get(r, (r, r))[1])
    if "direction" in show:
        show["direction"] = show.direction.map({"in": "Входящий", "out": "Исходящий"})
    return show


def node_table(frame, key, columns=None):
    if frame.empty:
        st.info("Нет клиентов с такими условиями. Измените фильтры, чтобы продолжить.")
        return
    show = display_table(frame, get_store())
    if columns:
        show = show[[c for c in columns if c in show]]
    selected = st.dataframe(show, hide_index=True, width="stretch", key=key,
                            on_select="rerun", selection_mode="single-row",
                            column_config={**COLUMNS,
                                           "priority_score": st.column_config.ProgressColumn("Приоритет", min_value=0, max_value=1, format="%.3f"),
                                           "sum_kzt": st.column_config.NumberColumn("Сумма, KZT", format="localized"),
                                           "why": st.column_config.TextColumn("Основание для проверки", width="large"),
                                           "suggested_request": st.column_config.TextColumn("Что запросить", width="large")})
    if selected.selection.rows:
        gid = frame.iloc[selected.selection.rows[0]].gid
        # A consumed selection must not reopen the dossier when returning here.
        del st.session_state[key]
        open_dossier(gid)
