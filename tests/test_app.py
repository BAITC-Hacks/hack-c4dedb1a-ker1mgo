from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def app_test(pipeline, monkeypatch):
    from agent import config
    from app import graphview, ui

    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(config, "_env_loaded", True)
    monkeypatch.setattr(ui, "OUT", pipeline["out"])
    # AppTest creates a fresh component registry for each simulated runtime.
    graphview._component.cache_clear()
    return AppTest.from_file(ROOT / "app/app.py", default_timeout=30).run()


@pytest.mark.parametrize(
    "page,title,widget,label",
    [
        (
            "briefing",
            "From known couriers to a network worth investigating.",
            "button",
            "Investigate highest-priority client",
        ),
        ("investigate", "Follow the money.", "text_input", "Find a client"),
        ("clusters", "Find the groups within the graph.", "selectbox", "Choose a cluster"),
        ("priorities", "Who to review first, and why.", "selectbox", "Role hypothesis"),
        ("data_gaps", "Ask for the evidence that is missing.", "selectbox", "Request category"),
        ("assistant", "Ask a question. Inspect the references.", "info", None),
        ("method", "Method & scale", "tabs", None),
    ],
)
def test_every_page_without_key(app_test, page, title, widget, label):
    app_test.switch_page(f"pages/{page}.py").run()
    assert not app_test.exception
    assert app_test.title[0].value == title
    elements = getattr(app_test, widget)
    assert len(elements)
    if label:
        assert label in [item.label for item in elements]
    if page == "assistant":
        assert "not connected" in app_test.info[0].value


def test_search_and_evidence_tabs(app_test, pipeline):
    gid = str(pipeline["ctx"].features.query("role_detail == 'terminal_inferred'").gid.iloc[0])
    app_test.switch_page("pages/investigate.py").run()
    app_test.text_input(key="case_search").input(gid[-10:]).run()
    assert not app_test.exception
    assert app_test.session_state.gid == gid
    assert [tab.label for tab in app_test.tabs] == [
        "Rule evidence",
        "Priority calculation",
        "Seed-money routes",
        "Transfer ledger",
    ]
    assert any("inferred" in item.value for item in app_test.info)
    app_test.text_input(key="case_search").input("not-a-client").run()
    assert not app_test.exception
    assert any("No client ID" in item.value for item in app_test.info)


def test_missing_outputs_explain_next_action(monkeypatch, tmp_path):
    from app import ui

    monkeypatch.setattr(ui, "OUT", tmp_path)
    at = AppTest.from_file(ROOT / "app/app.py", default_timeout=10).run()
    assert not at.exception
    assert "make run" in at.info[0].value


def test_store_loads_only_exported_evidence(pipeline):
    from agent.store import GraphStore

    store = GraphStore.load(pipeline["out"])
    gid = str(store.top_nodes(1).gid.iloc[0])
    assert store.rule_trace(gid)["role"] == store.get_node(gid)["role"]
    assert "paths" in store.money_paths(gid)
    assert len(store.edges) == len(pipeline["ctx"].edges)


def test_waterfall_reconciles_seed_and_nonseed_scores(pipeline):
    from agent.store import GraphStore
    from app.charts import priority_waterfall

    store = GraphStore.load(pipeline["out"])
    for seeded in (True, False):
        gid = store.f[store.f.is_seed.eq(seeded)].nlargest(1, "priority_score").gid.iloc[0]
        score = store.get_node(gid)["priority_score"]
        trace = store.rule_trace(gid)["priority"]
        chart = priority_waterfall(store.prio_components(gid), score, trace)
        values = chart.data[0].y
        assert sum(values[:-1]) == pytest.approx(score)
        assert values[-1] == score


@pytest.mark.parametrize("missing_dependency", ["langgraph", "langchain_core", "langchain_openai"])
def test_missing_assistant_dependency_keeps_case_available_with_a_key(
    app_test, monkeypatch, missing_dependency
):
    from agent import config
    from app import ui

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(config, "enabled", lambda: True)
    monkeypatch.setattr(
        ui, "find_spec", lambda name: None if name == missing_dependency else object()
    )
    app_test.switch_page("pages/assistant.py").run()
    assert not app_test.exception
    assert not app_test.chat_input
    assert "optional assistant dependencies" in app_test.info[0].value

    app_test.switch_page("pages/investigate.py").run()
    assert not app_test.exception
    assert app_test.title[0].value == "Follow the money."


def test_assistant_citation_opens_dossier_without_a_model(app_test, pipeline, monkeypatch):
    from agent import config, graph
    from app import ui

    gid = str(pipeline["ctx"].features.gid.iloc[0])
    monkeypatch.setattr(config, "enabled", lambda: True)
    monkeypatch.setattr(ui, "get_agent", lambda *args: object())
    requests = []

    def answer(_agent, question, history):
        requests.append((question, history))
        return {
            "answer": f"Review {gid} as a hypothesis.",
            "gids": [gid],
            "tools": ["get_node"],
        }

    monkeypatch.setattr(graph, "ask", answer)
    app_test.switch_page("pages/assistant.py").run()
    assert not app_test.exception
    app_test.chat_input[0].set_value("Who should I review?").run()
    assert not app_test.exception
    assert requests == [("Who should I review?", [])]
    assert len(app_test.chat_message) == 2
    app_test.button(key=f"citation_1_{gid}").click().run()
    assert not app_test.exception
    assert app_test.title[0].value == "Follow the money."
    assert app_test.session_state.gid == gid
