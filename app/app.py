import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))

from app.presentation import number
from app.ui import get_store, legend

st.set_page_config(page_title="Граф денег | Money graph", page_icon="◈", layout="wide")
st.html(ROOT / "app/style.css")
pages = [
    st.Page("pages/briefing.py", title="Обзор дела", default=True, icon=":material/space_dashboard:"),
    st.Page("pages/investigate.py", title="Исследование", icon=":material/hub:"),
    st.Page("pages/clusters.py", title="Кластеры", icon=":material/workspaces:"),
    st.Page("pages/priorities.py", title="Приоритеты", icon=":material/format_list_numbered:"),
    st.Page("pages/data_gaps.py", title="Запросы данных", icon=":material/playlist_add_check:"),
    st.Page("pages/assistant.py", title="Ассистент", icon=":material/chat_bubble_outline:"),
    st.Page("pages/method.py", title="Метод и масштаб", icon=":material/query_stats:"),
]
page = st.navigation(pages, position="hidden")
store = get_store()
with st.sidebar:
    st.html('<div class="brand"><span class="brand-mark">◈</span>Граф денег</div>'
            '<div class="sidebar-caption">Money graph / AML workspace</div>')
    st.html('<div class="nav-section">Рабочее пространство</div>')
    for item in pages:
        st.page_link(item)
    st.html(f'<div class="sidebar-scope"><strong>{number(len(store.f))}</strong> клиентов в выборке<br><strong>{int(store.f.is_seed.sum())}</strong> исходная точка (seed)</div>')
    with st.expander("Как читать граф"):
        legend()
        st.caption("Стрелка указывает направление перевода. Толщина линии зависит от суммы. Тёмная обводка — исходная точка, пунктир — граница обхода на глубине 4.")
    st.html('<div class="sidebar-footnote">Роли и приоритеты — гипотезы для проверки, а не вывод о виновности.</div>')
page.run()
