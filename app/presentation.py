"""Russian display copy over exported facts; no analytical rules live here."""
import math
import re

from app.theme import fmt_kzt

ROLE_NAMES = {"coordinator": "Координация", "consolidator": "Консолидация", "distributor": "Распределение",
              "transit": "Транзит", "terminal": "Конечный получатель", "peripheral": "Периферия"}
DETAILS = {"terminal_observed": "Исходящие переводы проверены", "terminal_inferred": "Вывод модели · требует проверки",
           "truncated_unknown": "Исходящие переводы неизвестны", "truncated_likely_forwarding": "Возможное продолжение потока",
           "seed_no_outgoing": "Исходная точка без исходящих переводов", "no_edges": "Нет видимых переводов",
           "weak_signal": "Недостаточно структурных признаков"}
CONDITIONS = {
    "Seeds paid back": "Переводы исходным точкам", "Other seeds on short cycles": "Исходные точки в коротких циклах",
    "Reachable seed sources": "Доступные исходные точки", "Betweenness": "Посредничество в сети",
    "Recipients": "Получатели", "Recipients versus payers": "Получатели относительно плательщиков",
    "Payers": "Плательщики", "Outflow / observed inflow": "Доля отправленных средств",
    "Known seed": "Исходная точка (seed)", "At least one payer": "Есть входящие связи",
    "At least one recipient": "Есть исходящие связи", "Outflow / observed inflow band": "Доля отправленных средств",
    "Inflow forwarded within the configured time window": "Быстрый перевод поступлений",
    "Fast-forwarding outflow cap": "Ограничение доли исходящих",
    "No observed recipients": "Число видимых получателей", "Outgoing transfers were crawled": "Глубина проверенного обхода",
    "Estimated forwarding probability": "Вероятность дальнейшего перевода",
    "Outgoing activity not crawled": "Глубина обрыва наблюдения",
}
REQUESTS = {
    "truncated_likely_forwarding": ("Продолжить обход", "Запросить исходящие переводы на следующем, пятом шаге обхода."),
    "seed_inflow_undercounted": ("Уточнить источники средств", "Запросить полную историю входящих переводов исходной точки."),
    "seed_no_outgoing": ("Проверить исходную точку", "Запросить историю переводов и проверить другие каналы: исходящих связей в выборке нет."),
    "small_component": ("Проверить отдельную группу", "Расширить историю переводов небольшой компоненты и проверить связи за пределами выборки."),
}
FLAGS = {"burst": "Всплеск операций за один день", "repeat_amount": "Повторяющиеся суммы",
         "round_amounts": "Округлённые суммы", "near_threshold": "Переводы около порога выгрузки"}
COLUMNS = {"gid": "ID клиента", "role": "Гипотеза роли", "priority_score": "Приоритет", "why": "Основание для проверки",
           "cluster_id": "Кластер", "evidence": "Наблюдаемые признаки", "reason": "Причина запроса",
           "suggested_request": "Что запросить", "sum_kzt": "Сумма, KZT", "n_tx": "Переводы",
           "direction": "Направление", "is_seed": "Исходная точка", "n_nodes": "Клиенты", "n_seed": "Исходные точки",
           "sum_kzt_internal": "Оборот внутри, KZT", "hypothesis": "Гипотеза", "seed_flow_in": "Поток от seeds, KZT"}


def number(value, digits=0):
    return f"{value:,.{digits}f}".replace(",", " ").replace(".", ",")


def percent(value, digits=0):
    return number(float(value) * 100, digits) + "%"


def condition_label(label):
    return CONDITIONS.get(label, label)


def logic_text(text):
    for source in sorted(CONDITIONS, key=len, reverse=True):
        text = text.replace(source, CONDITIONS[source])
    return text.replace(" AND ", " И ").replace(" OR ", " ИЛИ ").replace("No primary role rule matched", "Ни одно основное правило не выполнено")


def summary(node):
    role, detail = node["role"], node.get("role_detail", "")
    inc, out = int(node.get("in_deg", 0)), int(node.get("out_deg", 0))
    if detail == "terminal_inferred":
        return "Исходящие переводы не исследованы. Модель указывает на возможного конечного получателя; подтвердить вывод можно только новым запросом данных."
    if detail.startswith("truncated_"):
        return "Обход остановился на этом клиенте. Отсутствие исходящих связей не означает, что деньги остались на счёте. Нужны данные следующего шага."
    if detail == "seed_no_outgoing":
        return "Исходная точка без исходящих переводов в выборке. Запросите историю операций и сведения о других каналах."
    if detail == "no_edges":
        return "Переводов в выборке нет. Для выводов о роли нужна дополнительная история операций."
    if role == "terminal":
        return f"Входящих связей: {inc}. Исходящие переводы проверены и не найдены — это согласуется с ролью конечного получателя в пределах выборки."
    if role == "coordinator":
        return f"Переводы направлены к {int(node.get('pays_seed', 0))} исходным точкам; короткие циклы связывают клиента с {int(node.get('cycle_with_seeds', 0))} исходными точками. Это признаки возможной координации."
    if role == "distributor":
        return f"Отправлено {fmt_kzt(node.get('out_kzt'))} KZT; получателей: {out}. Веерное распределение средств — основание проверить назначение переводов."
    if role in {"consolidator", "transit"}:
        ratio = node.get("pass_through")
        text = f"Плательщиков: {inc}, получателей: {out}."
        if not node.get("is_seed") and ratio is not None and math.isfinite(ratio):
            text += f" Отправлено дальше {percent(ratio)} видимых поступлений."
        return text + (" Картина согласуется с консолидацией средств." if role == "consolidator" else " Картина согласуется с транзитом средств.")
    return f"Плательщиков: {inc}, получателей: {out}. Наблюдаемые связи не удовлетворяют правилам основных ролей."


def priority_reason(node):
    return f"{fmt_kzt(node.get('seed_flow_in'))} KZT от исходных точек; доступных источников: {int(node.get('n_seed_sources', 0))}. {ROLE_NAMES.get(node['role'], node['role'])}."


def cluster_hypothesis(text):
    translations = [(r"possible collection cell", "Возможная группа сбора средств"),
                    (r"possible payout network", "Возможная сеть распределения"),
                    (r"possible layering chain", "Возможная цепочка транзита"),
                    (r"likely end-recipient periphery", "Возможная группа конечных получателей"),
                    (r"loosely linked group", "Слабо связанная группа")]
    for pattern, label in translations:
        if re.search(pattern, str(text)):
            return label
    if "no transfers" in str(text):
        return "Изолированные клиенты: переводы не наблюдались"
    return "Группа для дополнительного анализа"
