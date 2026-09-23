import streamlit as st

from app.presentation import ROLE_NAMES
from app.theme import ROLE_COLORS
from app.ui import get_store, node_table, page_header

store = get_store()
page_header("Приоритеты проверки", "Очередь клиентов с объяснимыми основаниями. Нажмите строку, чтобы открыть досье.")
a, b, c = st.columns([2, 1.4, 1])
role = a.selectbox("Гипотеза роли", ["all"] + list(ROLE_COLORS), format_func=lambda v: "Все роли" if v == "all" else ROLE_NAMES[v])
hide = b.toggle("Скрыть исходные точки", value=True, help="Известные seeds уже входят в исходный список. Фильтр помогает найти других участников потока.")
limit = c.selectbox("Показать клиентов", [30, 50, 100], index=0)
rows = store.top_nodes(limit, role=None if role == "all" else role, include_seeds=not hide)
node_table(rows, "priority_queue", ["gid", "role", "priority_score", "why", "cluster_id"])
st.download_button("Скачать очередь · CSV", rows.to_csv(index=False), "review_queue.csv", "text/csv")
st.caption("Балл задаёт порядок проверки, а не вероятность нарушения. CSV сохраняет исходные английские названия полей для воспроизводимости.")
