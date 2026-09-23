"""Offline smoke checks for the viewer's entry point and navigation."""

import json
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from agent import config
from agent.store import GraphStore
from app import resources

APP = Path(__file__).resolve().parents[1] / "app" / "app.py"


@pytest.fixture
def viewer(monkeypatch, tmp_path):
    features = pd.DataFrame(
        {
            "gid": [101, 102, 103],
            "depth": [0, 1, 4],
            "is_seed": [True, False, False],
            "role": ["peripheral", "consolidator", "terminal"],
            "role_detail": ["weak_signal", "fan_in", "terminal_inferred"],
            "secondary_roles": ["", "", ""],
            "role_score": [0.1, 0.8, 0.9],
            "evidence": ["1 recipient", "1 payer", "1 payer"],
            "priority_score": [0.2, 0.9, 0.5],
            "why": ["seed flow"] * 3,
            "cluster_id": [1] * 3,
            "in_deg": [0, 1, 1],
            "out_deg": [1, 1, 0],
            "in_kzt": [0, 1000, 800],
            "out_kzt": [1000, 800, 0],
            "in_tx": [0, 1, 1],
            "out_tx": [1, 1, 0],
            "seed_flow_in": [0, 1000, 800],
            "n_seed_sources": [0, 1, 1],
            "p_has_out": [None, None, 0.1],
            "flags": [""] * 3,
            "prio_components": ['{"seed_flow": 0.3}'] * 3,
        }
    )
    edges = pd.DataFrame(
        {"src": [101, 102], "dst": [102, 103], "sum_kzt": [1000, 800], "n_tx": [1, 1]}
    )
    transactions = edges.drop(columns="n_tx").assign(date="2026-07-01")
    clusters = pd.DataFrame(
        {
            "cluster_id": [1],
            "n_nodes": [3],
            "n_seed": [1],
            "sum_kzt_internal": [1800],
            "top_gids": ["102;103"],
            "hypothesis": ["3 linked clients"],
        }
    )
    resilience = pd.DataFrame(
        [
            {
                "strategy": strategy,
                "n_removed": removed,
                "largest_wcc": 3 - removed,
                "n_components": 1,
                "seed_flow_reach": 1 - removed * 0.5,
            }
            for strategy in ("priority", "degree", "random")
            for removed in (0, 1)
        ]
    )
    requests = pd.DataFrame(
        {"gid": [103], "reason": ["depth 4"], "suggested_request": ["outgoing transfers"]}
    )
    store = GraphStore(features, edges, transactions, clusters, resilience, requests)
    features_path = tmp_path / "features.parquet"
    features_path.touch()
    monkeypatch.setattr(resources, "FEATURES_PATH", features_path)
    monkeypatch.setattr(resources, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(resources, "get_store", lambda mtime: store)
    monkeypatch.setattr(config, "enabled", lambda: False)
    return AppTest.from_file(str(APP), default_timeout=15), tmp_path


def assert_ready(app):
    assert not app.exception, [error.message for error in app.exception]


def test_pages_and_node_navigation_work_offline(viewer):
    app, _ = viewer
    app.run()
    assert_ready(app)
    assert app.metric[0].value == "3"

    app.sidebar.radio(key="page").set_value("Top list").run()
    assert_ready(app)
    assert set(app.dataframe[0].value.gid) == {"101", "102", "103"}
    app.toggle[0].set_value(True).run()
    assert_ready(app)
    assert set(app.dataframe[0].value.gid) == {"102", "103"}

    app.sidebar.button(key="demo_top priority (non-seed)").click().run()
    assert_ready(app)
    assert app.sidebar.radio(key="page").value == "Node card"
    assert app.session_state["gid"] == 102
    assert any("### 102" in text.value for text in app.markdown)

    next(button for button in app.button if button.label == "show on network").click().run()
    assert_ready(app)
    assert app.sidebar.radio(key="page").value == "Network"
    next(radio for radio in app.radio if radio.label == "View").set_value("Cluster").run()
    assert_ready(app)
    assert any("3 linked clients" in caption.value for caption in app.caption)

    app.sidebar.radio(key="page").set_value("Assistant").run()
    assert_ready(app)
    assert "OPENAI_API_KEY" in app.info[0].value


def test_search_and_unfocused_pages(viewer):
    app, _ = viewer
    app.run()
    for page in ("Network", "Node card"):
        app.sidebar.radio(key="page").set_value(page).run()
        assert_ready(app)
        assert "Search a gid" in app.info[0].value
    app.sidebar.text_input(key="query").input("103").run()
    assert_ready(app)
    assert app.session_state["gid"] == 103
    assert any("depth 4: outgoing transfers were not crawled" in text.value for text in app.caption)


def test_method_reads_exported_evidence_and_handles_missing_extras(viewer):
    app, output_dir = viewer
    app.run()
    app.sidebar.radio(key="page").set_value("Method & scale").run()
    assert_ready(app)
    assert any("No benchmark export" in info.value for info in app.info)
    assert app.metric[2].value == "Not measured"

    (output_dir / "truncation_model.json").write_text(
        json.dumps(
            {
                "auc_cv": 0.72,
                "n_train": 2,
                "observed_rate_depth1_3": 0.5,
                "mean_p_depth4": 0.1,
                "coefficients": {"in_deg": 0.2},
            }
        )
    )
    (output_dir / "pipeline_metadata.json").write_text(
        json.dumps(
            {
                "total_seconds": 1.5,
                "step_timings": {"features": 0.5},
                "centrality_mode": "exact",
                "config": {"seed": 42},
            }
        )
    )
    pd.DataFrame(
        [
            {
                "mode": mode,
                "step": step,
                "nodes": 3,
                "edges": 2,
                "transactions": 2,
                "scale": 1,
                "seconds": seconds,
            }
            for mode, step, seconds in [
                ("exact", "temporal", 0.1),
                ("exact", "total", 1.0),
                ("sampled", "temporal", 0.08),
                ("sampled", "total", 0.8),
                ("before", "temporal_reference", 0.2),
            ]
        ]
    ).to_csv(output_dir / "bench.csv", index=False)
    app.run()
    assert_ready(app)
    assert app.metric[2].value == "0.720"
    assert app.selectbox(key="method_bench_mode").value == "sampled"
    assert any(metric.value == "1.50 s" for metric in app.metric)


def test_missing_pipeline_outputs_shows_startup_instruction(viewer):
    app, output_dir = viewer
    (output_dir / "features.parquet").unlink()
    app.run()
    assert_ready(app)
    assert "Run `make run` first" in app.warning[0].value


def test_assistant_reply_citations_open_node_cards_without_a_model(viewer, monkeypatch):
    from agent import graph
    from app.views import assistant

    app, output_dir = viewer
    monkeypatch.setattr(config, "enabled", lambda: True)
    monkeypatch.setattr(assistant, "FEATURES_PATH", output_dir / "features.parquet")
    monkeypatch.setattr(assistant, "get_agent", lambda *args: object())
    requests = []

    def answer(_agent, question, history):
        requests.append((question, history))
        return {
            "answer": "Review 102 as a hypothesis.",
            "gids": ["102"],
            "tools": ["get_node"],
            "steps": 2,
        }

    monkeypatch.setattr(graph, "ask", answer)
    app.run()
    app.sidebar.radio(key="page").set_value("Assistant").run()
    assert_ready(app)
    app.chat_input[0].set_value("Who should I review?").run()
    assert_ready(app)
    assert requests == [("Who should I review?", [])]
    assert len(app.chat_message) == 2
    app.button(key="cite_1_102").click().run()
    assert_ready(app)
    assert app.sidebar.radio(key="page").value == "Node card"
    assert app.session_state["gid"] == 102


@pytest.mark.parametrize("missing_dependency", ["langgraph", "langchain_core", "langchain_openai"])
def test_missing_assistant_dependency_keeps_viewer_available_with_a_key(
    viewer, monkeypatch, missing_dependency
):
    app, _ = viewer
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(config, "enabled", lambda: True)
    monkeypatch.setattr(
        resources, "find_spec", lambda name: None if name == missing_dependency else object()
    )
    app.run()
    app.sidebar.radio(key="page").set_value("Assistant").run()
    assert_ready(app)
    assert not app.chat_input
    assert "optional dependencies" in app.info[0].value

    app.sidebar.button(key="demo_top priority (non-seed)").click().run()
    assert_ready(app)
    assert app.sidebar.radio(key="page").value == "Node card"
    assert all(button.label != "write a summary" for button in app.button)
