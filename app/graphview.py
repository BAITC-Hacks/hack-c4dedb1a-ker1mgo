"""Offline, selectable transfer graph with precision-safe client identifiers."""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import networkx as nx
import streamlit as st

from app.theme import CLUSTER_PALETTE, ROLE_COLORS, fmt_kzt


def node_color(row, color_by):
    if color_by == "cluster":
        cid = int(row.get("cluster_id", 0))
        return "#A7B4B9" if cid == 0 else CLUSTER_PALETTE[cid % len(CLUSTER_PALETTE)]
    return ROLE_COLORS.get(row.get("role", "peripheral"), "#8F9996")


def _layout(graph, focus):
    """Stable insertion order makes spring positions reproducible across reruns."""
    nodes = sorted(graph.nodes, key=str)
    if not nodes:
        return {}, "empty"
    if len(nodes) == 1:
        return {nodes[0]: (0.5, 0.5)}, "ego"
    direct_neighbors = (set(graph.predecessors(focus)) | set(graph.successors(focus))) if focus in graph else set()
    if focus in graph and len(nodes) <= 36 and set(nodes) <= direct_neighbors | {focus}:
        incoming = set(graph.predecessors(focus)) - {focus}
        outgoing = set(graph.successors(focus)) - {focus}
        groups = [
            (0.19, sorted(incoming - outgoing, key=str)),
            (0.81, sorted(outgoing, key=str)),
            (0.5, sorted(set(nodes) - incoming - outgoing - {focus}, key=str)),
        ]
        positions = {focus: (0.5, 0.5)}
        for x, group in groups:
            columns = max(1, math.ceil(len(group) / 9))
            rows_per_column = math.ceil(len(group) / columns) if group else 1
            for i, gid in enumerate(group):
                column, row = divmod(i, rows_per_column)
                count = min(rows_per_column, len(group) - column * rows_per_column)
                y = 0.14 + 0.72 * (row + 1) / (count + 1)
                lane_x = x + (column - (columns - 1) / 2) * 0.09
                positions[gid] = (lane_x, y)
        return positions, "ego"
    ordered = nx.Graph()
    ordered.add_nodes_from(nodes)
    ordered.add_edges_from(sorted(graph.edges(), key=lambda edge: (str(edge[0]), str(edge[1]))))
    raw = nx.spring_layout(ordered, seed=42, iterations=90, weight=None)
    axes = [(min(float(p[a]) for p in raw.values()), max(float(p[a]) for p in raw.values()))
            for a in (0, 1)]
    positions = {}
    for gid, pos in raw.items():
        positions[gid] = tuple(
            0.5 if hi == lo else 0.1 + 0.8 * (float(pos[axis]) - lo) / (hi - lo)
            for axis, (lo, hi) in enumerate(axes)
        )
    return positions, "network"


def graph_data(G, features, focus=None, color_by="role"):
    """Build JSON-safe render data; GIDs never cross JavaScript as numbers.

    Every visible edge preserves its payer/recipient direction. Layout is a
    presentation aid and does not change the analytical graph or its weights.
    """
    nodes_by_id = {str(gid): gid for gid in G.nodes}
    focus_id = str(focus) if focus is not None else None
    focus_node = nodes_by_id.get(focus_id)
    positions, layout = _layout(G, focus_node)
    # String indexes support stores that load identifiers as either int or str.
    frame = features.set_index("gid", drop=False) if "gid" in features.columns else features
    rows = {str(gid): row for gid, row in frame.iterrows()}
    nodes = []
    for gid in sorted(G.nodes, key=str):
        sid = str(gid)
        row = rows[sid]
        incoming = max(0.0, float(row.get("in_kzt", 0)))
        outgoing = max(0.0, float(row.get("out_kzt", 0)))
        seed = bool(row.get("is_seed", False))
        depth = int(row.get("depth", 0))
        role = str(row.get("role", "peripheral"))
        x, y = positions[gid]
        tooltip = (
            f"Client {sid}\n{role.replace('_', ' ').title()} · depth {depth}"
            f"{' · seed' if seed else ''}\n"
            f"Received {fmt_kzt(incoming)} · sent {fmt_kzt(outgoing)} KZT\n"
            f"Priority {float(row.get('priority_score', 0)):.3f}"
        )
        if depth == 4:
            tooltip += "\nDepth 4 boundary: outgoing activity is unobserved."
        nodes.append({
            "id": sid, "label": sid[-10:], "role": role,
            "color": node_color(row, color_by), "x": round(x, 7), "y": round(y, 7),
            "radius": round(min(19.0, 7.0 + 1.7 * math.log1p((incoming + outgoing) / 1e5)), 2),
            "seed": seed, "boundary": depth == 4, "focus": sid == focus_id,
            "label_visible": len(G) <= 36 or sid == focus_id, "tooltip": tooltip,
        })
    edges = []
    for payer, recipient, attrs in sorted(G.edges(data=True), key=lambda e: (str(e[0]), str(e[1]))):
        amount = max(0.0, float(attrs.get("sum_kzt", 0)))
        count = int(attrs.get("n_tx", 0))
        edges.append({
            "source": str(payer), "target": str(recipient),
            "width": round(min(5.0, max(0.8, math.log10(max(amount, 1)) - 3)), 2),
            "amount": amount, "transactions": count,
            "tooltip": f"{payer} → {recipient}\n{fmt_kzt(amount)} KZT · {count:,} transfers",
        })
    return {"nodes": nodes, "edges": edges, "focus": focus_id, "layout": layout,
            "color_by": color_by}


_CSS = """
:host {font-family: Ubuntu, sans-serif; color: #18333F;}
.mg-graph {position: relative; width: 100%; height: 100%; min-height: 240px;
  background: #F6F9FA; overflow: hidden; border-radius: 4px;}
.mg-canvas {width: 100%; height: 100%; display: block; touch-action: pan-y; cursor: grab;}
.mg-canvas.panning {cursor: grabbing;}
.mg-canvas:focus-visible {outline: 2px solid #176B80; outline-offset: -3px;}
.mg-toolbar {position: absolute; top: 12px; right: 12px; display: flex; gap: 5px; z-index: 2;}
.mg-toolbar button {border: 1px solid #C7D7DE; border-radius: 4px; background: white;
  min-width: 32px; height: 32px; font: inherit; color: #18333F; cursor: pointer;}
.mg-toolbar button:hover {background: #E7EFF2;}
.mg-toolbar button:focus-visible {outline: 2px solid #176B80; outline-offset: 2px;}
.mg-help {position: absolute; bottom: 10px; left: 12px; right: 12px; color: #58717E;
  pointer-events: none; font-size: 11px; line-height: 1.35;}
.mg-tooltip {position: absolute; z-index: 5; pointer-events: none; white-space: pre-line;
  background: #18333F; color: white; border-radius: 5px; padding: 9px 12px;
  font-size: 12px; line-height: 1.45; max-width: min(340px, calc(100% - 32px));
  overflow-wrap: anywhere; box-shadow: 0 4px 14px #18333F20;}
.mg-node {cursor: pointer; outline: none;}
.mg-node .node-label {fill: #294B5C; font-family: 'Ubuntu Mono', monospace;
  font-size: 17px; pointer-events: none; paint-order: stroke; stroke: #F6F9FA; stroke-width: 3px;}
.mg-node .focus-ring {fill: none; stroke: #176B80; stroke-width: 2.5; opacity: 0;}
.mg-node.is-focus .focus-ring {opacity: .8;}
.mg-node:hover .focus-ring, .mg-node:focus-visible .focus-ring {opacity: 1; stroke-width: 3;}
.mg-node:hover .node-label, .mg-node:focus-visible .node-label {opacity: 1;}
.mg-node .hidden-label {opacity: 0;}
.mg-edge {fill: none; stroke: #91A9B5; opacity: .68;}
.mg-edge:hover {stroke: #176B80; opacity: 1;}
.mg-lane {font-size: 17px; fill: #526A76;}
.mg-empty {fill: #58717E; font-size: 17px;}
"""


@lru_cache(maxsize=1)
def _component():
    return st.components.v2.component(
        "moneygraph_transfer_network",
        html='<div class="mg-graph"></div>',
        css=_CSS,
        js=Path(__file__).with_name("graph.js").read_text(),
    )


def render(G, features, focus=None, color_by="role", height=520, key="network"):
    """Mount the network and return ``result.selected`` on node activation."""
    data = graph_data(G, features, focus, color_by)
    data["height"] = height
    return _component()(data=data, height=height, key=key, on_selected_change=lambda: None)
