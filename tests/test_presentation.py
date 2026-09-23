"""Localization preserves exported facts, identity and uncertainty."""

import pandas as pd

from agent.store import GraphStore
from app.dossier import _condition_value
from app.presentation import CONDITIONS, DETAILS, REQUESTS, summary
from app.theme import fmt_kzt
from app.ui import display_table
from moneygraph.formatting import fmt_kzt as english_kzt


def test_localized_tables_keep_ids_and_exported_facts(pipeline):
    store = GraphStore.load(pipeline["out"])
    rows = store.top_nodes(30)
    before = rows.copy(deep=True)
    shown = display_table(rows, store)
    pd.testing.assert_frame_equal(rows, before)
    assert shown.gid.tolist() == [str(gid) for gid in rows.gid]
    pd.testing.assert_series_equal(shown.priority_score, rows.priority_score)
    assert shown.why.str.contains("исходных точек").all()
    assert set(store.data_requests.reason) <= REQUESTS.keys()


def test_localized_evidence_covers_rules_and_retains_boundary_uncertainty(pipeline):
    store = GraphStore.load(pipeline["out"])
    labels = {
        condition["label"]
        for trace in store.rule_traces["nodes"].values()
        for rule in trace["rules"]
        for condition in rule["conditions"]
    }
    assert labels and labels <= CONDITIONS.keys()
    special = store.f[store.f.role.ne(store.f.role_detail)]
    assert set(special.role_detail) <= DETAILS.keys()
    for gid in store.f[store.f.depth.eq(4)].gid:
        text = summary(store.get_node(gid))
        assert "не исследованы" in text or "Нужны данные" in text


def test_percent_gaps_and_currency_keep_their_units():
    condition = {"field": "pass_through", "value": 0.65, "threshold": 0.5, "deficit": 0.15}
    assert _condition_value(condition, "value") == "65,0%"
    assert _condition_value(condition, "threshold") == "50,0%"
    assert _condition_value(condition, "deficit") == "15,0 п.п."
    assert fmt_kzt(1_250_000) == "1,25 млн"
    assert english_kzt(1_250_000) == "1.25M"
