"""Inspect exported method evidence without rerunning analytical calculations."""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from app.presentation import number, percent
from app.ui import OUT, get_store, page_header


@st.cache_data(show_spinner=False)
def read_json(path: str, modified: int) -> dict:
    return json.loads(Path(path).read_text())


@st.cache_data(show_spinner=False)
def read_csv(path: str, modified: int) -> pd.DataFrame:
    return pd.read_csv(path)


def exported_json(name: str) -> dict:
    path = OUT / name
    try:
        return read_json(str(path), path.stat().st_mtime_ns) if path.exists() else {}
    except (OSError, ValueError):
        command = "make bench" if name == "bench_metadata.json" else "make run"
        st.warning(f"Не удалось прочитать {name}. Дождитесь завершения выгрузки и обновите страницу. Повторный расчёт: `{command}`.")
        return {}


def exported_csv(name: str) -> pd.DataFrame:
    path = OUT / name
    try:
        return read_csv(str(path), path.stat().st_mtime_ns) if path.exists() else pd.DataFrame()
    except (OSError, ValueError):
        command = "make bench" if name == "bench.csv" else "make eval"
        st.warning(f"Не удалось прочитать {name}. Обновите страницу после выгрузки. Повторный расчёт: `{command}`.")
        return pd.DataFrame()


page_header("Метод и масштаб", "Как получены гипотезы, что измерено и где заканчиваются данные.")
store = get_store()
model = exported_json("truncation_model.json")
metadata = exported_json("pipeline_metadata.json")
bench = exported_csv("bench.csv")

columns = st.columns(3)
columns[0].metric("Клиенты в выборке", number(len(store.f)))
columns[1].metric("Исходящие неизвестны · шаг 4", number(store.f.depth.eq(4).sum()))
columns[2].metric("Модель перевода далее · CV AUC", number(model["auc_cv"], 3) if model.get("auc_cv") is not None else "Нет замера")
st.caption("CV AUC оценивает прогноз дальнейшего перевода. Это не оценка точности ролей или вероятности нарушения.")
scale_tab, evidence_tab, provenance_tab = st.tabs(["Производительность", "Доказательства и ограничения", "Методика и воспроизводимость"])

with scale_tab:
    st.subheader("Время расчёта при росте графа")
    st.write("Синтетические графы сохраняют распределения числа контрагентов и сумм переводов исходной выборки. Замеры показывают стоимость расчёта, но не точность анализа более крупного дела.")
    if bench.empty:
        st.info("Замеров пока нет. Выполните `make bench` и обновите страницу.")
    else:
        totals = bench[bench.step.eq("total")]
        mode_names = {"exact": "Точная центральность", "sampled": "Выборочная центральность"}
        if len(totals):
            st.line_chart(totals.pivot_table(index="nodes", columns="mode", values="seconds", aggfunc="median").rename(columns=mode_names), x_label="Клиенты", y_label="Время, с")
        st.caption("Сравнивайте режимы отдельно: выборочная центральность сокращает время за счёт точности. Один запуск — замер, а не доверительный интервал.")
        st.caption("Замер включает основные расчёты и выгрузку результатов. Подробные обоснования, копирование исходных parquet и отрисовка интерфейса исключены. Полное время этого дела — во вкладке «Методика и воспроизводимость».")
        with st.expander("Время по этапам и проверка нагрузки"):
            modes = [mode for mode in sorted(bench["mode"].dropna().unique()) if mode != "before"]
            mode = st.selectbox("Режим расчёта", modes, format_func=lambda value: mode_names.get(value, value), index=modes.index("sampled") if "sampled" in modes else 0, key="method_bench_mode")
            subset = bench[bench["mode"].eq(mode)]
            timing = subset.pivot_table(index="step", columns="nodes", values="seconds", aggfunc="median").round(3)
            timing.columns = [f"{number(nodes)} клиентов · с" for nodes in timing.columns]
            st.dataframe(timing, width="stretch")
            quality = [c for c in ["scale", "nodes", "edges", "transactions", "degree_distribution", "amount_distribution"] if c in bench]
            st.dataframe(subset[quality].drop_duplicates(), hide_index=True, width="stretch")
            st.caption("Названия этапов и полей оставлены на английском для сверки с кодом и экспортом.")
        download = st.columns(2)
        download[0].download_button("Скачать замеры · CSV", bench.to_csv(index=False), "bench.csv", "text/csv")
        chart = OUT / "bench.svg"
        if chart.exists():
            download[1].download_button("Скачать график · SVG (English)", chart.read_bytes(), "moneygraph-scale.svg", "image/svg+xml")
        reference = bench[bench.step.eq("temporal_reference")]
        optimized = bench[bench.step.eq("temporal") & bench["mode"].eq("exact") & bench.scale.eq(1)]
        if len(reference) and len(optimized):
            before, after = reference.seconds.median(), optimized.seconds.median()
            st.markdown("**Ускорение временных признаков**")
            st.write(f"На исходной выборке: {number(before, 3)} → {number(after, 3)} с, ускорение в {number(before / after, 1)} раза. Сравнение проверяет совпадение результатов до и после оптимизации.")
        environment = exported_json("bench_metadata.json")
        if environment:
            with st.expander("Среда замера и настройки режимов"):
                st.json(environment)
    st.caption("Следующие направления: Polars или DuckDB, компилируемые алгоритмы графа и инкрементальные обновления. Производительность на миллионе узлов здесь не измерялась.")

with evidence_tab:
    st.subheader("Неизвестный отток не означает остановку денег")
    details = store.f.role_detail.value_counts()
    comparison = pd.DataFrame([
        {"Подход": "Считать конечным любой узел без видимого оттока", "Результат": f"{number(store.f.depth.eq(4).sum())} непроверенных узлов на шаге 4 получили бы такую роль"},
        {"Подход": "Проверить исходящие на шагах 1–3", "Результат": f"{number(details.get('terminal_observed', 0))} гипотез по наблюдаемым данным"},
        {"Подход": "Модель только для неисследованных исходящих", "Результат": f"{number(details.get('terminal_inferred', 0))} гипотез по модели; остальные сохраняют неопределённость"},
    ])
    st.dataframe(comparison, hide_index=True, width="stretch")
    if model:
        st.write(f"Логистическая регрессия обучена на {number(model.get('n_train', 0))} клиентах шагов 1–3, кроме seeds. Используются только входящие признаки. Стратифицированная кросс-валидация на пяти частях проверяет ранжирование клиентов по наличию дальнейшего перевода. После обучения с балансировкой классов вероятности корректируются на базовую частоту.")
        rates = st.columns(2)
        rates[0].metric("Переводят далее · шаги 1–3", percent(model.get("observed_rate_depth1_3", 0), 1))
        rates[1].metric("Средний прогноз · шаг 4", percent(model.get("mean_p_depth4", 0), 1))
        with st.expander("Коэффициенты модели и запись обучения"):
            st.dataframe(pd.DataFrame(model.get("coefficients", {}).items(), columns=["Признак", "Стандартизированный коэффициент"]), hide_index=True, width="stretch")
            st.json({key: value for key, value in model.items() if key != "coefficients"})
        st.caption("Шаг 4 может отличаться от обучающей выборки. Запросите следующий шаг выгрузки, чтобы проверить гипотезы модели.")
    st.subheader("Как удаление клиентов влияет на поток от seeds")
    resilience = store.resilience()
    if len(resilience):
        labels = {"priority": "По приоритету", "degree": "По числу связей", "degree_nonseed": "По числу связей, без seeds", "random": "Случайно, среднее"}
        curve = resilience.pivot(index="n_removed", columns="strategy", values="seed_flow_reach").rename(columns=labels)
        st.line_chart(curve, x_label="Удалено клиентов", y_label="Оставшаяся доля потока")
        last = resilience[resilience.n_removed.eq(resilience.n_removed.max())].copy()
        last["strategy"] = last.strategy.replace(labels)
        last["seed_flow_reach"] = last.seed_flow_reach.map(lambda value: percent(value, 1))
        st.dataframe(last.rename(columns={"n_removed": "Удалено", "strategy": "Стратегия", "largest_wcc": "Крупнейшая компонента", "n_components": "Компоненты", "seed_flow_reach": "Осталось потока"}), hide_index=True, width="stretch")
        st.caption("Удаление seeds убирает сами источники денег. Для поиска новых объектов сравнивайте приоритет со связностью без seeds. Это симуляция, а не оценка эффекта реального вмешательства.")
    else:
        st.info("Выполните `make run`, чтобы выгрузить сравнение стратегий.")
    st.subheader("Что учитывать при проверке")
    st.dataframe(pd.DataFrame([
        ("Четыре шага, только исходящие связи", "Неизвестные исходящие и внешние поступления не позволяют делать вывод о балансе."),
        ("Входящие seeds неполны", "Входящий объём и доля пересылки не используются в правилах их ролей."),
        ("Нет переводов меньше 5 000 KZT", "Нельзя обнаружить дробление ниже этого порога."),
        ("Нет размеченных ролей и атрибутов клиентов", "Балл описывает силу правила, а не вероятность нарушения."),
        ("Приближённое распределение потока", "Нельзя установить, какое поступление оплатило конкретный перевод."),
        ("Кластеры по неориентированным связям", "Общая группа не доказывает наличие общего управления."),
    ], columns=["Ограничение", "Значение для аналитика"]), hide_index=True, width="stretch")

with provenance_tab:
    st.subheader("От переводов к проверяемому досье")
    st.code("Переводы → структурные и временные признаки → поток от seeds\n         → прогноз дальнейшего перевода → упорядоченные правила ролей\n         → кластеры и приоритет → материалы дела", language=None)
    st.write("Расчёт работает офлайн и сохраняет результаты. Интерфейс и ассистент читают готовые материалы. Досье показывает значения, пороги, ближайшее невыполненное правило, состав приоритета и расчётные пути денег. Обоснование использует те же условия, что и назначение роли.")
    if metadata:
        timings = metadata.get("step_timings", {})
        if timings:
            runtime = metadata.get("total_seconds")
            if runtime is not None:
                st.metric("Полное время расчёта дела", f"{number(runtime, 2)} с")
            st.dataframe(pd.DataFrame(timings.items(), columns=["Этап", "Время, с"]), hide_index=True, width="stretch")
            st.caption(f"Режим центральности: {metadata.get('centrality_mode', 'не записан')}. Время включает подготовку обоснований.")
        st.caption("Поток оценивается по агрегированным суммам переводов за период. Это модель распределения средств; хронологическая связь конкретных входящих и исходящих операций не установлена.")
        with st.expander("Пороги и веса этой выгрузки"):
            st.json(metadata.get("config", metadata.get("thresholds", {})) or metadata)
        with st.expander("Запись запуска (English)"):
            st.json({key: value for key, value in metadata.items() if key not in {"config", "thresholds"}})
    else:
        st.info("Запись запуска отсутствует. Выполните `make run`, чтобы обновить материалы.")
    st.subheader("Ассистент: ответы с проверкой ссылок")
    st.write("Ассистент запрашивает готовые материалы через ограниченные инструменты графа и не назначает роли или приоритет. ID сверяются с графом: неизвестные вызывают одну повторную попытку, затем маскируются. Проверка ID не подтверждает корректность каждого предложения.")
    evaluation = exported_csv("agent_eval.csv")
    if len(evaluation):
        st.dataframe(evaluation, hide_index=True, width="stretch")
    else:
        st.caption("Отчёта об оценке ассистента пока нет. Для его создания нужен подключённый модельный сервис и `make eval`.")
