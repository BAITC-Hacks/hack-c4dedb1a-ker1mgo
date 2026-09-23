"""Rendering contracts that protect graph identity and analytical meaning."""

import json
from pathlib import Path

import networkx as nx
import pandas as pd

from app.graphview import CLUSTER_PALETTE, ROLE_COLORS, graph_data, node_color

# Adjacent 19-digit identifiers would collide if passed as JavaScript numbers.
A, B, C = 1000000031152841000, 1000000031152841001, 1000000031152841002


def sample():
    graph = nx.DiGraph()
    graph.add_edge(A, B, sum_kzt=1_000_000, n_tx=7)
    graph.add_edge(B, C, sum_kzt=100, n_tx=1)
    frame = pd.DataFrame(
        [
            {
                "gid": A,
                "role": "distributor",
                "cluster_id": 1,
                "is_seed": True,
                "depth": 0,
                "in_kzt": 0,
                "out_kzt": 1_000_000,
                "priority_score": 0.9,
            },
            {
                "gid": B,
                "role": "consolidator",
                "cluster_id": 2,
                "is_seed": False,
                "depth": 1,
                "in_kzt": 1_000_000,
                "out_kzt": 100,
                "priority_score": 0.5,
            },
            {
                "gid": C,
                "role": "terminal",
                "cluster_id": 0,
                "is_seed": False,
                "depth": 4,
                "in_kzt": 100,
                "out_kzt": 0,
                "priority_score": 0.1,
            },
        ]
    ).set_index("gid", drop=False)
    return graph, frame


def test_large_client_ids_survive_json_and_edge_direction():
    graph, frame = sample()
    result = json.loads(json.dumps(graph_data(graph, frame, focus=B)))
    assert {node["id"] for node in result["nodes"]} == {str(A), str(B), str(C)}
    assert [(edge["source"], edge["target"]) for edge in result["edges"]] == [
        (str(A), str(B)),
        (str(B), str(C)),
    ]
    assert result["focus"] == str(B)
    assert all(isinstance(node["id"], str) for node in result["nodes"])
    assert result["edges"][0]["width"] > result["edges"][1]["width"]
    assert result["edges"][0]["transactions"] == 7


def test_ego_lanes_and_visible_evidence_marks():
    graph, frame = sample()
    result = graph_data(graph, frame, focus=str(B))
    by_id = {node["id"]: node for node in result["nodes"]}
    assert by_id[str(A)]["x"] < by_id[str(B)]["x"] < by_id[str(C)]["x"]
    assert by_id[str(B)]["focus"]
    assert by_id[str(A)]["seed"]
    assert not by_id[str(B)]["seed"]
    assert by_id[str(C)]["boundary"]
    assert "не исследованы" in by_id[str(C)]["tooltip"]
    assert str(A) in by_id[str(A)]["tooltip"]
    assert by_id[str(A)]["color"] == ROLE_COLORS["distributor"]


def test_cluster_colors_and_no_cluster_neutral():
    graph, frame = sample()
    result = graph_data(graph, frame, color_by="cluster")
    by_id = {node["id"]: node for node in result["nodes"]}
    assert by_id[str(A)]["color"] == CLUSTER_PALETTE[1]
    assert by_id[str(C)]["color"] == "#A7B4B9"
    assert node_color({"role": "unknown"}, "role") == "#8F9996"


def test_network_layout_deterministic_with_reordered_input():
    graph, frame = sample()
    reversed_graph = nx.DiGraph()
    reversed_graph.add_nodes_from(reversed(list(graph.nodes)))
    reversed_graph.add_edges_from(reversed(list(graph.edges(data=True))))
    assert graph_data(graph, frame) == graph_data(reversed_graph, frame.iloc[::-1])
    assert all(
        0 <= node[axis] <= 1 for node in graph_data(graph, frame)["nodes"] for axis in ("x", "y")
    )


def test_empty_and_singleton_and_large_labels():
    graph, frame = sample()
    assert graph_data(nx.DiGraph(), frame)["nodes"] == []
    one = graph_data(graph.subgraph([A]), frame, focus=A)
    assert one["nodes"][0]["x"] == one["nodes"][0]["y"] == 0.5
    large = nx.DiGraph()
    large.add_edges_from((A + i, A + i + 1) for i in range(40))
    large_frame = pd.DataFrame([dict(frame.loc[A], gid=A + i) for i in range(41)])
    result = graph_data(large, large_frame, focus=A + 10)
    assert sum(node["label_visible"] for node in result["nodes"]) == 1
    assert all(0 <= node[axis] <= 1 for node in result["nodes"] for axis in ("x", "y"))


def test_frontend_is_offline_and_keeps_text_safe():
    source = (Path(__file__).parents[1] / "app" / "graph.js").read_text()
    assert "setTriggerValue('selected', node.id)" in source
    assert "textContent" in source
    assert "innerHTML" not in source
    assert "https://" not in source
    assert "fetch(" not in source
    assert "import " not in source
    assert "Number(node.id)" not in source
    assert "'stroke-dasharray': '4 3'" in source
