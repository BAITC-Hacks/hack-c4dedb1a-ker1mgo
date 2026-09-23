import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from graphview import ROLE_COLORS

# first three slots of a colour-blind-checked categorical palette
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
GRID = "rgba(128,128,128,0.18)"


def _style(fig, height):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=30, b=10), bargap=0.25, bargroupgap=0.08,
                      legend=dict(orientation="h", y=1.08, x=0), hovermode="x unified")
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig


def timeline(tl):
    fig = go.Figure()
    fig.add_bar(x=tl.date, y=tl.in_kzt, name="in", marker_color=BLUE,
                hovertemplate="%{y:,.0f} KZT")
    fig.add_bar(x=tl.date, y=tl.out_kzt, name="out", marker_color=ORANGE,
                hovertemplate="%{y:,.0f} KZT")
    fig.update_traces(marker_line_width=0, marker_cornerradius=3)
    fig.update_yaxes(title_text="KZT per day")
    return _style(fig, 280)


def prio_breakdown(comps):
    s = pd.Series(comps, dtype=float).sort_values()
    fig = go.Figure(go.Bar(x=s.values, y=s.index, orientation="h", marker_color=BLUE,
                           marker_cornerradius=3, text=[f"{v:.3f}" for v in s.values],
                           textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}: %{x:.3f}<extra></extra>"))
    fig.update_xaxes(title_text="contribution to priority score", gridcolor=GRID)
    fig.update_yaxes(showgrid=False)
    fig = _style(fig, 60 + 34 * len(s))
    fig.update_layout(hovermode="closest")
    return fig


def role_counts(counts):
    counts = counts.reindex([r for r in ROLE_COLORS if r in counts.index]).iloc[::-1]
    fig = go.Figure(go.Bar(x=counts.values, y=counts.index, orientation="h",
                           marker_color=[ROLE_COLORS[r] for r in counts.index], marker_cornerradius=3,
                           text=counts.values, textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}: %{x} nodes<extra></extra>"))
    fig.update_xaxes(title_text="nodes", gridcolor=GRID)
    fig.update_yaxes(showgrid=False)
    fig = _style(fig, 60 + 34 * len(counts))
    fig.update_layout(hovermode="closest")
    return fig


RES_METRICS = [("largest_wcc", "largest component"), ("n_components", "components"),
               ("seed_flow_reach", "seed flow reaching depth ≥ 2")]
RES_COLORS = {"priority": BLUE, "degree": ORANGE, "random": AQUA}


def resilience(res):
    fig = make_subplots(rows=1, cols=3, subplot_titles=[t for _, t in RES_METRICS], horizontal_spacing=0.07)
    for i, (col, _) in enumerate(RES_METRICS, start=1):
        for strat, g in res.groupby("strategy"):
            g = g.sort_values("n_removed")
            fig.add_scatter(x=g.n_removed, y=g[col], name=strat, legendgroup=strat, showlegend=i == 1,
                            mode="lines+markers", line=dict(width=2, color=RES_COLORS.get(strat, "#8F9996")),
                            marker=dict(size=8), row=1, col=i)
        fig.update_xaxes(title_text="nodes removed", row=1, col=i)
    return _style(fig, 320)
