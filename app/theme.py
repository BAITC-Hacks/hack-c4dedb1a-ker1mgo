from functools import partial

from moneygraph.formatting import fmt_kzt as format_kzt

ROLE_COLORS = {
    "coordinator": "#9B1C3A",
    "consolidator": "#D0632B",
    "distributor": "#7A4FB0",
    "transit": "#B8921A",
    "terminal": "#2E6E91",
    "peripheral": "#8F9996",
}
ROLE_LABELS = {
    "coordinator": "Признаки координации",
    "consolidator": "Признаки консолидации",
    "distributor": "Признаки распределения",
    "transit": "Признаки транзита",
    "terminal": "Возможный конечный получатель",
    "peripheral": "Недостаточно признаков роли",
}
CLUSTER_PALETTE = [
    "#176B80",
    "#D0632B",
    "#7A4FB0",
    "#677D30",
    "#9B1C3A",
    "#2E6E91",
    "#A2732B",
    "#517C73",
    "#976879",
    "#647583",
]
INK, ACCENT, MUTED, LINE, MIST = "#18333F", "#176B80", "#526A76", "#CAD7DD", "#EEF3F5"


fmt_kzt = partial(format_kzt, locale="ru")
