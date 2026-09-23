import streamlit as st

from app.presentation import REQUESTS, number
from app.ui import get_store, node_table, page_header

store = get_store()
page_header(
    "Запросы недостающих данных",
    "Выберите пробел в наблюдениях, проверьте досье и сформируйте запрос следующей выгрузки.",
)
requests = store.data_requests
if requests.empty:
    st.info("Список запросов отсутствует. Выполните `make run`, чтобы подготовить материалы.")
    st.stop()
a, b, c = st.columns(3)
a.metric("Клиенты с запросами", number(requests.gid.nunique()))
b.metric("Категории запросов", requests.reason.nunique())
c.metric("Граница обхода · шаг 4", int(store.f.depth.eq(4).sum()))
reason = st.selectbox(
    "Тип запроса",
    ["all"] + sorted(requests.reason.unique()),
    format_func=lambda v: "Все запросы" if v == "all" else REQUESTS.get(v, (v, ""))[0],
)
rows = requests if reason == "all" else requests[requests.reason.eq(reason)]
st.caption("Нажмите строку, чтобы проверить основания в досье клиента.")
node_table(rows, "request_queue", ["gid", "reason", "suggested_request"])
st.download_button(
    "Скачать запросы · CSV", rows.to_csv(index=False), "data_requests.csv", "text/csv"
)
st.caption(
    "Переводы менее 5 000 KZT и операции за пределами банка не входят в выборку. Их нельзя восстановить по видимым связям."
)
