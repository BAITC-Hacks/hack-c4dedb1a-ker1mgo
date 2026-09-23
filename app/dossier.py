import html

import pandas as pd
import streamlit as st

from app import charts
from app.presentation import (
    COLUMNS,
    FLAGS,
    ROLE_NAMES,
    condition_label,
    logic_text,
    number,
    percent,
    priority_reason,
)
from app.presentation import summary as node_summary
from app.theme import fmt_kzt
from app.ui import badge, display_table, focus


def _number(value):
    if value is None:
        return "нет данных"
    if isinstance(value, bool):
        return "да" if value else "нет"
    if isinstance(value, (float, int)):
        if float(value).is_integer():
            return number(value)
        return f"{value:.4g}".replace(".", ",")
    return str(value)


def _condition_value(condition, key):
    value = condition.get(key)
    if value is not None and condition.get("field") in {
        "pass_through",
        "fast_pass_share",
        "p_has_out",
    }:
        if isinstance(value, (float, int)):
            return number(value * 100, 1) + " п.п." if key == "deficit" else percent(value, 1)
        if isinstance(value, (list, tuple)):
            return "–".join(percent(v, 1) for v in value)
    if isinstance(value, (list, tuple)):
        return "–".join(_number(v) for v in value)
    return _number(value)


def _operator(value):
    return {">=": "≥", "<=": "≤", "==": "=", "between": "в диапазоне"}.get(value, value)


def condition_table(rule):
    if not rule:
        return
    rows = []
    for c in rule.get("conditions", []):
        applicable, available = c.get("applicable", True), c.get("available", True)
        rows.append(
            {
                "Условие": condition_label(c.get("label", c.get("field", ""))),
                "Значение": _condition_value(c, "value"),
                "Критерий": f"{_operator(c.get('operator', ''))} {_condition_value(c, 'threshold')}",
                "Результат": "не применяется"
                if not applicable
                else "нет данных"
                if not available
                else "✓ выполнено"
                if c.get("passed")
                else "✗ не выполнено",
                "Не хватает": _condition_value(c, "deficit")
                if applicable and not c.get("passed")
                else "—",
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    if rule.get("logic"):
        st.caption("Связь условий: " + logic_text(rule["logic"]))


def compact_conditions(rule):
    rows = []
    for c in rule.get("conditions", []):
        state = "unknown"
        if not c.get("applicable", True):
            result = "не применяется"
        elif not c.get("available", True):
            result = "нет данных"
        else:
            state = "pass" if c.get("passed") else "fail"
            result = f"{_condition_value(c, 'value')} {_operator(c.get('operator', ''))} {_condition_value(c, 'threshold')} {'✓' if c.get('passed') else '✗'}"
        rows.append(
            f'<div class="trace-condition"><span>{html.escape(condition_label(c.get("label", c.get("field", ""))))}</span><strong class="trace-{state}">{html.escape(result)}</strong></div>'
        )
    st.html("".join(rows))


def summary(store, gid):
    n = store.get_node(gid)
    trace = store.rule_trace(gid)
    st.html(
        f'<div class="panel-title">Досье клиента<span class="panel-meta">Кластер {n["cluster_id"]} / шаг {n["depth"]}</span></div>'
        f'<div class="dossier-id">{gid}</div>'
    )
    badge(n["role"], n["role_detail"])
    st.html(f'<p class="dossier-summary">{html.escape(node_summary(n))}</p>')
    a, b = st.columns(2)
    a.metric(
        "Приоритет проверки",
        number(n["priority_score"], 3),
        help="Относительный балл от 0 до 1. Это порядок проверки, а не вероятность нарушения.",
    )
    b.metric(
        "Поток от seeds, KZT",
        fmt_kzt(n.get("seed_flow_in")),
        help="Оценка потока от известных исходных точек. Она не идентифицирует происхождение каждого отдельного перевода.",
    )
    if n["is_seed"]:
        st.caption(
            "Исходная точка: входящие переводы видны не полностью. Доля отправленных средств для неё не используется."
        )
    if n["depth"] == 4 and n.get("p_has_out") is not None:
        st.caption(
            f"Вероятность дальнейшего перевода по модели: {percent(n['p_has_out'])}. Исходящие операции не исследованы."
        )
    rules = trace.get("rules", [])
    chosen = (
        trace.get("fallback")
        if n["role"] == "peripheral"
        else next((r for r in rules if r.get("role") == n["role"]), None)
    )
    st.markdown("**Основание гипотезы**")
    if chosen:
        compact_conditions(chosen)
        if " OR " in chosen.get("logic", ""):
            st.caption("Связь условий «И/ИЛИ» — во вкладке «Почему эта роль».")
    else:
        st.caption("Основные правила не выполнены. Подробнее — во вкладке «Почему эта роль».")


def details(store, gid):
    n = store.get_node(gid)
    trace = store.rule_trace(gid)
    evidence, priority, routes, activity = st.tabs(
        ["Почему эта роль", "Из чего приоритет", "Пути денег", "Переводы"]
    )
    with evidence:
        st.caption(
            "Проверка идёт по порядку: назначается первая подходящая роль. Значения и пороги взяты из того же расчёта, что и итоговая роль."
        )
        nearest = trace.get("nearest_rule")
        if nearest:
            st.markdown(
                f"**Ближайшая альтернатива: {ROLE_NAMES.get(nearest.get('role'), nearest.get('role'))}**"
            )
            st.caption(
                "В столбце «Не хватает» показан разрыв до условия. Процентные доли сравниваются в процентных пунктах; неизвестные значения не считаются выполненными."
            )
            condition_table(nearest)
        for rule in trace.get("rules", []):
            with st.expander(
                f"{ROLE_NAMES.get(rule['role'], rule['role'])} — {'условия выполнены' if rule.get('matched') else 'условия не выполнены'}"
            ):
                condition_table(rule)
        if not trace:
            st.info("Нет подробного обоснования. Выполните `make run`, чтобы обновить материалы.")
        if n.get("secondary_roles"):
            st.caption(
                "Дополнительные признаки: "
                + ", ".join(ROLE_NAMES.get(r, r) for r in n["secondary_roles"].split(";") if r)
            )
        with st.expander("Исходные поля и формулировки (English)"):
            st.code(str(gid), language=None)
            st.write(n["evidence"])
            st.json(trace)
    with priority:
        st.write(priority_reason(n))
        st.plotly_chart(
            charts.priority_waterfall(
                store.prio_components(gid), n["priority_score"], trace.get("priority")
            ),
            config={"displayModeBar": False},
        )
        st.caption(
            "Вклады суммируются, для известных исходных точек применяется поправка. Затем баллы масштабируются: максимальный приоритет равен 1."
        )
    with routes:
        paths = store.money_paths(gid)
        rounds = getattr(store, "seed_paths", {}).get("rounds")
        st.markdown("**Крупнейшие пути от исходных точек**")
        st.caption(
            f"Модель распределяет средства пропорционально суммам переводов и ограничивает поток видимым оттоком. Горизонт расчёта: {rounds if rounds is not None else 'не указан'} раундов."
        )
        if paths.get("paths"):
            st.caption(
                f"Показано {percent(paths.get('coverage', 0), 1)} расчётного потока. Вне списка: {fmt_kzt(paths.get('omitted_kzt', 0))} KZT."
            )
            for i, route in enumerate(paths["paths"], 1):
                st.markdown(
                    f"**{i}. {fmt_kzt(route['kzt'])} KZT**"
                    + (" — есть возвратный цикл" if route.get("contains_cycle") else "")
                )
                st.code(" → ".join(route["gids"]), language=None, wrap_lines=True)
        else:
            st.info(
                "За выбранный горизонт модель не обнаружила потока от исходных точек. Проверьте контрагентов во вкладке «Переводы»."
            )
        st.caption(
            "Это расчёт по совокупным переводам, а не доказательство происхождения конкретных средств. Потоки разных узлов нельзя складывать: одни средства могут проходить через несколько клиентов."
        )
    with activity:
        a, b, c, d = st.columns(4)
        a.metric("Плательщики", n["in_deg"])
        b.metric("Получатели", n["out_deg"])
        c.metric("Входящие, KZT", fmt_kzt(n["in_kzt"]))
        d.metric("Исходящие, KZT", fmt_kzt(n["out_kzt"]))
        timeline = store.tx_timeline(gid)
        if len(timeline):
            st.plotly_chart(charts.timeline(timeline), config={"displayModeBar": False})
        else:
            st.info(
                "Видимых переводов нет. Откройте «Запросы данных», чтобы выбрать следующий шаг."
            )
        nb = store.neighbors(gid)
        if len(nb):
            st.dataframe(display_table(nb), hide_index=True, width="stretch", column_config=COLUMNS)
            target = st.selectbox(
                "Открыть контрагента",
                nb.gid.map(str),
                index=None,
                placeholder="Выберите ID клиента",
                key=f"counterparty_{gid}",
            )
            if target and st.button("Перейти к контрагенту", key=f"focus_{gid}"):
                focus(target)
                st.rerun(scope="fragment")
        if n.get("flags"):
            st.caption(
                "Паттерны для проверки: "
                + "; ".join(FLAGS.get(v, v) for v in n["flags"].split(";") if v)
            )
