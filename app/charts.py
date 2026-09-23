import plotly.graph_objects as go

from app.presentation import ROLE_NAMES
from app.theme import ACCENT, INK, ROLE_COLORS

# first three slots of a colour-blind-checked categorical palette
BLUE, ORANGE = "#176B80", "#D0632B"
GRID = "rgba(128,128,128,0.18)"


def _style(fig, height):
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        bargap=0.25,
        bargroupgap=0.08,
        legend=dict(orientation="h", y=1.08, x=0),
        hovermode="x unified",
        font=dict(family="Ubuntu, sans-serif", color=INK, size=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig


def timeline(tl):
    fig = go.Figure()
    fig.add_bar(
        x=tl.date, y=tl.in_kzt, name="Входящие", marker_color=BLUE, hovertemplate="%{y:,.0f} KZT"
    )
    fig.add_bar(
        x=tl.date,
        y=tl.out_kzt,
        name="Исходящие",
        marker_color=ORANGE,
        hovertemplate="%{y:,.0f} KZT",
    )
    fig.update_traces(marker_line_width=0, marker_cornerradius=3)
    fig.update_yaxes(title_text="KZT за день")
    return _style(fig, 280)


def role_counts(counts):
    counts = counts.reindex([r for r in ROLE_COLORS if r in counts.index]).iloc[::-1]
    fig = go.Figure(
        go.Bar(
            x=counts.values,
            y=[ROLE_NAMES[r] for r in counts.index],
            orientation="h",
            marker_color=[ROLE_COLORS[r] for r in counts.index],
            marker_cornerradius=3,
            text=counts.values,
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}: %{x} клиентов<extra></extra>",
        )
    )
    fig.update_xaxes(title_text="Клиенты", gridcolor=GRID, range=[0, max(counts.values) * 1.2])
    fig.update_yaxes(showgrid=False)
    fig = _style(fig, 60 + 34 * len(counts))
    fig.update_layout(hovermode="closest")
    return fig


def priority_waterfall(components, final_score, audit=None):
    audit = audit or {}
    components = audit.get("components", components)
    labels = {
        "seed_flow": "Поток от seeds",
        "role": "Признаки роли",
        "seed_sources": "Источники",
        "betweenness": "Посредничество",
        "removal_impact": "Влияние удаления",
    }
    values = list(components.values())
    names = [labels.get(k, k.replace("_", " ")) for k in components]
    subtotal = sum(values)
    seed_factor = audit.get("seed_factor", 1.0)
    names.extend(["Поправка seed", "Масштабирование", "Приоритет"])
    values.extend([subtotal * (seed_factor - 1), final_score - subtotal * seed_factor, final_score])
    fig = go.Figure(
        go.Waterfall(
            x=names,
            y=values,
            measure=["relative"] * (len(values) - 1) + ["total"],
            text=[f"{v:.3f}" for v in values],
            textposition="outside",
            increasing={"marker": {"color": ACCENT}},
            decreasing={"marker": {"color": ORANGE}},
            totals={"marker": {"color": INK}},
            connector={"line": {"color": "#CAD7DD"}},
        )
    )
    fig.update_yaxes(title_text="Вклад в итоговый балл", range=[0, max(1.1, final_score * 1.15)])
    fig.update_xaxes(tickangle=-25)
    return _style(fig, 350)
