"""Agent eval: questions whose answers are computed from the graph, scored on gid recall and unknown gids.

python -m agent.eval  ->  out/agent_eval.csv
"""

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from agent.identifiers import cited_gids
from agent.store import GraphStore
from moneygraph.paths import OUTPUT_DIR

OUT = OUTPUT_DIR


def _pick(rng, items):
    items = sorted(items)
    return items[rng.integers(len(items))]


def make_questions(store, seed=7):
    """(id, question, expected gids). Everything is derived from the data, nothing is hand-picked."""
    rng = np.random.default_rng(seed)
    f = store.f
    qs = []

    # group -> shared collector, the demo question
    collectors = f.index[(f.in_deg >= 5) & ~f.is_seed]
    for lang, cid in (("ru", "collector_ru"), ("en", "collector_en")):
        c = _pick(rng, collectors)
        payers = store.neighbors(c, "in").gid.head(5).map(str).tolist()
        text = (
            f"Кто собирает деньги с этих пятерых: {', '.join(payers)}?"
            if lang == "ru"
            else f"Who collects money from these clients: {', '.join(payers)}?"
        )
        qs.append((cid, text, [str(c)]))

    # two payers -> recipient they share
    shared = [
        (v, sorted(store.G.predecessors(v))[:2]) for v in f.index if store.G.in_degree(v) >= 2
    ]
    _, (a, b) = shared[rng.integers(len(shared))]
    both = set(store.G.successors(a)) & set(store.G.successors(b))
    qs.append(
        (
            "shared_recipient",
            f"Which clients receive money from both {a} and {b}?",
            [str(x) for x in both],
        )
    )

    x = _pick(rng, f.index[f.in_deg.between(2, 4)])
    qs.append(
        (
            "payers",
            f"Кто переводит деньги клиенту {x}?",
            store.neighbors(x, "in").gid.map(str).tolist(),
        )
    )

    x = _pick(rng, f.index[f.out_deg.between(2, 5)])
    qs.append(
        (
            "recipients",
            f"To whom does {x} send money?",
            store.neighbors(x, "out").gid.map(str).tolist(),
        )
    )

    x = _pick(rng, f.index[f.out_deg >= 3])
    top = store.neighbors(x, "out").gid.iloc[0]
    qs.append(("biggest_recipient", f"Кто получил от {x} больше всего денег?", [str(top)]))

    qs.append(
        (
            "top5",
            "Which 5 clients should an analyst look at first?",
            store.top_nodes(5).gid.map(str).tolist(),
        )
    )
    qs.append(
        (
            "top3_nonseed",
            "Назови трёх самых приоритетных клиентов, которые не являются seed.",
            store.top_nodes(3, include_seeds=False).gid.map(str).tolist(),
        )
    )

    # a two-hop chain u -> m -> w
    edges = [
        (u, v)
        for u in sorted(store.G)
        for v in sorted(store.G.successors(u))
        if store.G.out_degree(v)
    ]
    u, m = edges[rng.integers(len(edges))]
    w = sorted(store.G.successors(m))[0]
    mids = {p[1] for p in store.paths_between(u, w, max_len=2) if len(p) == 3}
    qs.append(("path", f"Через кого проходят деньги от {u} к {w}?", [str(g) for g in mids]))

    cl = store.cluster_summary()
    if not cl.empty:
        row = cl[cl.cluster_id > 0].sort_values("n_seed", ascending=False).iloc[0]
        member = f.index[f.cluster_id == row.cluster_id][0]
        qs.append(
            (
                "cluster_top",
                f"Which cluster is {member} in, and who are its top clients?",
                [g for g in str(row.top_gids).replace(",", ";").split(";") if g.strip()],
            )
        )
    return qs


def score(question, expected, cited, store):
    exp, got = set(expected), set(cited)
    recall = len(exp & got) / len(exp) if exp else float(not got)
    # echoing the gids from the question isn't a wrong answer
    extra = got - exp - {str(g) for g in cited_gids(question)}
    precision = len(exp & got) / (len(exp & got) + len(extra)) if exp & got or extra else 1.0
    unknown = sorted(g for g in got if not store.has(g))
    return recall, precision, unknown


def run(model=None, out=OUT):
    from agent.graph import ask, build, enabled

    if not enabled():
        sys.exit("OPENAI_API_KEY is not set; the eval needs the assistant")
    store = GraphStore.load(out)
    app = build(store, model=model)
    rows = []
    for qid, q, expected in make_questions(store):
        t0 = time.perf_counter()
        try:
            r = ask(app, q)
            err = ""
        except Exception as e:
            r, err = {"answer": "", "gids": [], "tools": [], "steps": 0}, str(e)
        recall, precision, unknown = score(q, expected, r["gids"], store)
        rows.append(
            {
                "id": qid,
                "question": q,
                "expected": ";".join(expected),
                "cited": ";".join(r["gids"]),
                "recall": round(recall, 3),
                "precision": round(precision, 3),
                "n_unknown": len(unknown),
                "unknown": ";".join(unknown),
                "tools": ";".join(r["tools"]),
                "steps": r["steps"],
                "seconds": round(time.perf_counter() - t0, 1),
                "error": err,
                "answer": r["answer"],
            }
        )
        print(
            f"{qid:18s} recall {recall:.2f}  precision {precision:.2f}  unknown {len(unknown)}  tools {','.join(r['tools'])}"
        )
    df = pd.DataFrame(rows)
    df.to_csv(Path(out) / "agent_eval.csv", index=False)
    print(
        f"\n{len(df)} questions · gid recall {df.recall.mean():.2f} · precision {df.precision.mean():.2f} · "
        f"unknown gids {int(df.n_unknown.sum())} · -> {Path(out) / 'agent_eval.csv'}"
    )
    return df


if __name__ == "__main__":
    run(model=sys.argv[1] if len(sys.argv) > 1 else None)
