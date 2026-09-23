import streamlit as st

from app.graphview import render
from app.presentation import COLUMNS, cluster_hypothesis, number
from app.theme import fmt_kzt
from app.ui import get_store, legend, node_table, open_dossier, page_header

store = get_store()
page_header("Кластеры сети", "Исследуйте связанные группы и откройте досье клиента прямо на карте или в списке.")
clusters = store.cluster_summary()
if clusters.empty:
    st.info("Сводка по кластерам отсутствует. Выполните `make run` и обновите страницу.")
    st.stop()
ordered = clusters.sort_values(["n_seed", "n_nodes"], ascending=False)
cid = st.selectbox("Кластер", ordered.cluster_id.tolist(),
                   format_func=lambda x: f"Кластер {x}" + (" — изолированные клиенты" if x == 0 else ""))
row = store.cluster_summary(cid).iloc[0]
st.write(cluster_hypothesis(row.hypothesis))
a, b, c = st.columns(3)
a.metric("Клиенты", int(row.n_nodes))
b.metric("Исходные точки", int(row.n_seed))
c.metric("Оборот внутри, KZT", fmt_kzt(row.sum_kzt_internal))
view, members = st.tabs(["Карта группы", "Клиенты группы"])
with view:
    G = store.cluster_graph(cid)
    result = render(G, store.f, height=430, key="cluster_graph")
    if result.selected and store.has(result.selected):
        open_dossier(result.selected)
    legend()
    if len(G) < row.n_nodes:
        st.caption(f"Показаны {len(G)} клиентов с наибольшим приоритетом из {int(row.n_nodes)}.")
    st.caption("Кластеры учитывают наличие связей, а стрелки — направление переводов. Членство в группе не доказывает общую цель.")
with members:
    st.caption("Нажмите строку, чтобы открыть досье.")
    subset = store.f[store.f.cluster_id.eq(cid)].sort_values("priority_score", ascending=False)
    node_table(subset, "cluster_members", ["gid", "role", "priority_score", "evidence"])
with st.expander("Сравнить все кластеры"):
    show = ordered[["cluster_id", "n_nodes", "n_seed", "sum_kzt_internal", "hypothesis"]].copy()
    show["hypothesis"] = show.hypothesis.map(cluster_hypothesis)
    st.dataframe(show, hide_index=True, width="stretch", column_config=COLUMNS)
