import html

import streamlit as st

from app import charts
from app.presentation import number, priority_reason, summary
from app.theme import fmt_kzt
from app.ui import badge, get_store, page_header, open_dossier

store = get_store()
f = store.f
page_header("Картина движения денег", "От известных исходных точек — к клиентам, связям и запросам, которые стоит проверить следующими.")
metrics = st.columns(4)
metrics[0].metric("Клиенты в выборке", number(len(f)))
metrics[1].metric("Исходные точки (seeds)", int(f.is_seed.sum()))
metrics[2].metric("Видимый оборот, KZT", fmt_kzt(store.edges.sum_kzt.sum()))
metrics[3].metric("Связи между клиентами", number(len(store.edges)))

left, right = st.columns([1.2, 1], gap="large")
with left:
    st.subheader("С чего начать проверку")
    top = store.top_nodes(1, include_seeds=False).iloc[0]
    node = store.get_node(top.gid)
    badge(node["role"])
    st.html(f'<div class="case-note"><div class="dossier-id">{node["gid"]}</div>{html.escape(summary(node))}</div>')
    st.caption(priority_reason(node))
    if st.button("Открыть досье первого кандидата", type="primary"):
        open_dossier(top.gid)
    picks = store.demo_picks()
    labels = {"biggest distributor": "Крупный распределитель", "depth 4, inferred terminal": "Получатель на границе обхода", "top coordinator": "Признаки координации"}
    with st.expander("Другие примеры для исследования"):
        for key, label in labels.items():
            if key in picks and st.button(label, key=key, width="stretch"):
                open_dossier(picks[key])
with right:
    st.subheader("Какие роли наблюдаются")
    st.plotly_chart(charts.role_counts(store.role_counts()), config={"displayModeBar": False})

st.subheader("Граница данных — не конец денежного потока")
depth4 = int(f.depth.eq(4).sum())
observed = int(f.role_detail.eq("terminal_observed").sum())
inferred = int(f.role_detail.eq("terminal_inferred").sum())
for column, title, text in zip(st.columns(2, gap="large"),
    [f"{number(depth4)} клиента без исследованных исходящих", "Наблюдение отдельно от предположения"],
    ["На четвёртом шаге обход остановился. Нулевая исходящая степень не доказывает, что средства остались на счёте.",
     f"{number(observed)} конечный получатель по наблюдаемым данным; {number(inferred)} — по оценке модели. Неопределённость видна в досье и запросах данных."]):
    with column:
        st.html(f'<div class="finding-line"><h3>{title}</h3><p>{text}</p></div>')

findings = [
    ("Следуем за средствами", "Приоритет учитывает расчётный поток от seeds. В досье видно, из чего складывается балл и какие пути ведут к клиенту."),
    ("Проверяем полезность приоритета", "Сравниваем удаление узлов по приоритету, числу связей и случайному выбору. Результаты доступны в разделе «Метод и масштаб»."),
    ("Формируем следующий запрос", "Неизвестные исходящие переводы, неполные поступления и отдельные компоненты превращаются в конкретные запросы данных."),
    ("Задаём вопросы по графу", "Опциональный ассистент обращается к готовым данным и проверяет ID в ответах. Для основного исследования подключение не требуется."),
]
for pair in (findings[:2], findings[2:]):
    for column, (title, text) in zip(st.columns(2, gap="large"), pair):
        with column:
            st.html(f'<div class="finding-line"><h3>{title}</h3><p>{text}</p></div>')
