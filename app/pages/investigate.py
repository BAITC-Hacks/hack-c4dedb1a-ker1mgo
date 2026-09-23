import streamlit as st

from app import dossier
from app.graphview import render
from app.presentation import number
from app.ui import focus, focused_gid, get_store, legend, page_header

store = get_store()
page_header("Исследование связей", "Найдите клиента и выберите узел на графе, чтобы проверить его роль, переводы и источники средств.")


@st.fragment
def investigation():
    search, radius_col, colour_col = st.columns([2.6, 1.1, 1.2], gap="medium")
    query = search.text_input("ID клиента", placeholder="Полный ID или последние цифры", key="case_search")
    radius = radius_col.segmented_control("Глубина связей", [1, 2], default=1,
                                          format_func=lambda r: "1 шаг" if r == 1 else "2 шага", key="graph_radius") or 1
    color_by = colour_col.segmented_control("Цвет узлов", ["role", "cluster"], default="role",
                                            format_func=lambda v: "Роли" if v == "role" else "Кластеры", key="graph_color") or "role"
    query = query.strip()
    if query:
        hits = store.search(query, limit=100)
        if not hits:
            st.info("Клиент не найден. Проверьте цифры или сократите запрос.")
        elif len(hits) == 1:
            if st.session_state.get("last_search") != query:
                focus(str(hits[0]))
                st.session_state.last_search = query
        else:
            st.caption(f"Найдено совпадений: {len(hits)}" + (" или больше. Уточните ID." if len(hits) == 100 else ". Выберите клиента."))
            selected = st.selectbox("Совпадения", [str(g) for g in hits], index=None,
                                    placeholder="Выберите ID клиента", key=f"search_matches_{query}")
            if selected and st.session_state.get("last_match") != selected:
                focus(selected)
                st.session_state.last_match = selected
    else:
        st.session_state.last_search = ""
        st.session_state.last_match = ""
    gid = focused_gid(store)
    graph, card = st.columns([1.65, 1], gap="large")
    G = store.ego(gid, radius)
    with graph:
        st.html(f'<div class="panel-title">Карта переводов<span class="panel-meta">{number(len(G))} узлов / {number(G.number_of_edges())} связей</span></div>')
        result = render(G, store.f, focus=gid, color_by=color_by, height=430, key="case_graph")
        if result.selected and store.has(result.selected) and str(result.selected) != str(gid):
            focus(result.selected)
            st.rerun(scope="fragment")
        legend()
        if len(G) >= 300:
            st.caption("Показаны 300 ближайших узлов; при одинаковой глубине выбраны крупнейшие потоки.")
    with card:
        dossier.summary(store, gid)
    st.write("")
    dossier.details(store, gid)


investigation()
