from moneygraph.formatting import fmt_kzt as fmt_kzt

ROLE_COLORS = {
    "coordinator": "#9B1C3A",
    "consolidator": "#D0632B",
    "distributor": "#7A4FB0",
    "transit": "#B8921A",
    "terminal": "#2E6E91",
    "peripheral": "#8F9996",
}
ROLE_LABELS = {
    "coordinator": "Signs of coordination",
    "consolidator": "Signs of consolidation",
    "distributor": "Signs of distribution",
    "transit": "Signs of transit",
    "terminal": "Possible end recipient",
    "peripheral": "Insufficient role evidence",
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
