import math

from pyvis.network import Network

ROLE_COLORS = {
    "coordinator": "#9B1C3A",
    "consolidator": "#D0632B",
    "distributor": "#7A4FB0",
    "transit": "#B8921A",
    "terminal": "#2E6E91",
    "peripheral": "#8F9996",
}
CLUSTER_PALETTE = ["#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F", "#EDC948",
                   "#B07AA1", "#FF9DA7", "#9C755F", "#BAB0AC"]

OPTIONS = """
{
  "physics": {"solver": "barnesHut",
              "barnesHut": {"gravitationalConstant": -6000, "springLength": 120, "damping": 0.4},
              "stabilization": {"iterations": 250}},
  "edges": {"arrows": {"to": {"enabled": true, "scaleFactor": 0.5}},
            "smooth": {"type": "continuous"}, "color": {"inherit": false, "color": "#9aa5a8"}},
  "interaction": {"hover": true, "navigationButtons": true, "tooltipDelay": 100}
}
"""


def node_color(row, color_by):
    if color_by == "cluster":
        cid = int(row["cluster_id"])
        return "#cfd4d3" if cid == 0 else CLUSTER_PALETTE[cid % len(CLUSTER_PALETTE)]
    return ROLE_COLORS.get(row["role"], "#8F9996")


def fmt_kzt(x):
    x = float(x)
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if abs(x) >= div:
            return f"{x / div:.2f}{suf}"
    return f"{x:.0f}"


def render(G, features, focus=None, color_by="role", height=650):
    net = Network(height=f"{height}px", width="100%", directed=True, cdn_resources="in_line")
    net.set_options(OPTIONS)
    f = features.loc[list(G.nodes)]
    for gid, row in f.iterrows():
        vol = float(row["in_kzt"]) + float(row["out_kzt"])
        seed = bool(row["is_seed"])
        opts = dict(
            label=str(gid)[-6:],
            title=(f"{gid}\nrole: {row['role']} ({row.get('role_detail', '')})\ndepth {row['depth']}"
                   f"{' · seed' if seed else ''}\npriority {row['priority_score']:.2f}\n"
                   f"in {fmt_kzt(row['in_kzt'])} · out {fmt_kzt(row['out_kzt'])} KZT\n{row['evidence']}"),
            color={"background": node_color(row, color_by), "border": "#111111" if seed else "#ffffff",
                   "highlight": {"background": node_color(row, color_by), "border": "#000000"}},
            size=8 + 3 * math.log1p(vol / 1e5),
            borderWidth=4 if seed else 1,
            shape="star" if gid == focus else "dot",
        )
        if int(row["depth"]) == 4:
            opts["shapeProperties"] = {"borderDashes": [4, 3]}
            opts["borderWidth"] = max(opts["borderWidth"], 2)
            opts["color"]["border"] = "#333333"
        net.add_node(int(gid), **opts)
    for u, v, d in G.edges(data=True):
        net.add_edge(int(u), int(v), width=max(0.5, math.log10(max(d["sum_kzt"], 1)) - 3),
                     title=f"{fmt_kzt(d['sum_kzt'])} KZT in {d['n_tx']} tx")
    html = net.generate_html()
    # freeze the layout once it settles so big hubs don't keep jiggling
    return html.replace(
        "network = new vis.Network(container, data, options);",
        "network = new vis.Network(container, data, options);\n"
        "network.once('stabilizationIterationsDone', function() { network.setOptions({physics: false}); });",
    )
