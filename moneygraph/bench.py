"""Reproducible core-pipeline scaling using random lifts of the observed graph.

Each node is copied k times; each original edge connects copies through a seeded
permutation. This preserves every node's in/out degree, each edge amount/count,
and the empirical transaction-amount distribution exactly. Copies are mixed,
not isolated replicas. It is a controlled workload, not a realistic new AML case.
"""
import argparse
import copy
import platform
import os
import sys
import tempfile
import time
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from . import clusters, data_requests, export, temporal
from .data import Context, build_graph, load_context
from .explain import write_json
from .run import STEPS
from . import priority


def synthetic(base, scale, seed):
    if scale < 1:
        raise ValueError("scale must be a positive integer")
    rng = np.random.default_rng(seed)
    gids = list(base.nodes.gid)
    node_index = {gid: i for i, gid in enumerate(gids)}
    n = len(gids)
    nodes = pd.concat([base.nodes.assign(gid=np.arange(n) + replica * n + 1) for replica in range(scale)], ignore_index=True)
    pairs = base.edges[["src", "dst"]].copy()
    pairs["edge_index"] = np.arange(len(pairs))
    indexed_tx = base.tx.merge(pairs, on=["src", "dst"], how="left", validate="many_to_one")
    edge_src = base.edges.src.map(node_index).to_numpy()
    edge_dst = base.edges.dst.map(node_index).to_numpy()
    tx_src = indexed_tx.src.map(node_index).to_numpy()
    tx_dst = indexed_tx.dst.map(node_index).to_numpy()
    tx_edge = indexed_tx.edge_index.to_numpy(dtype=int)
    permutations = np.stack([rng.permutation(scale) for _ in range(len(pairs))])
    edges, transactions = [], []
    for replica in range(scale):
        edges.append(base.edges.assign(src=edge_src + replica * n + 1,
                                       dst=edge_dst + permutations[:, replica] * n + 1))
        transactions.append(indexed_tx.drop(columns="edge_index").assign(
            src=tx_src + replica * n + 1, dst=tx_dst + permutations[tx_edge, replica] * n + 1))
    edges, tx = pd.concat(edges, ignore_index=True), pd.concat(transactions, ignore_index=True)
    ctx = Context(edges, nodes, tx, build_graph(edges, nodes), copy.deepcopy(base.cfg), set(nodes.loc[nodes.is_seed, "gid"]))
    ctx.features = nodes[["gid", "depth", "is_seed"]].copy()
    ctx.verbose = False
    ctx.capture_explanations = False
    return ctx


def distribution_check(base, ctx, scale):
    # Joint directed degrees are a stronger check than a total-degree histogram.
    expected = sorted([(base.G.in_degree(g), base.G.out_degree(g)) for g in base.G] * scale)
    actual = sorted((ctx.G.in_degree(g), ctx.G.out_degree(g)) for g in ctx.G)
    original_amounts = base.tx.sum_kzt.value_counts().sort_index()
    lifted_amounts = ctx.tx.sum_kzt.value_counts().sort_index()
    degree_ok = expected == actual
    amount_ok = lifted_amounts.equals(original_amounts * scale)
    assert degree_ok and amount_ok, "synthetic workload changed a required empirical distribution"
    return degree_ok, amount_ok


def temporal_reference(ctx):
    """Pre-optimization implementation, retained only for a measured 1× comparison."""
    tx, cfg = ctx.tx, ctx.cfg["temporal"]
    by_dst, by_src = dict(tuple(tx.groupby("dst"))), dict(tuple(tx.groupby("src")))
    empty, rows = tx.iloc[:0], []
    for gid in ctx.nodes.gid:
        tin, tout = by_dst.get(gid, empty), by_src.get(gid, empty)
        both = pd.concat([tin, tout])
        rows.append({"gid": gid, "fast_pass_share": temporal.fifo_fast_share(tin, tout, cfg["fast_pass_days"]),
                     "out_before_in": bool(len(tin) and len(tout) and tout.date.min() < tin.date.min()),
                     "max_same_day_payers": int(tin.groupby("date").src.nunique().max()) if len(tin) else 0,
                     "active_days": int(both.date.nunique()), "flags": temporal.node_flags(tout, both, cfg["flags"])})
    return pd.DataFrame(rows)


def chart(frame, path):
    """Standalone measured figure; deterministic SVG metadata and no runtime CDN."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    selected = frame[(frame["mode"] == "sampled") & (frame.step == "total")]
    measured = selected.groupby(["scale", "nodes"], as_index=False).seconds.mean().sort_values("scale")
    with plt.rc_context({"svg.hashsalt": "moneygraph-benchmark", "font.family": "DejaVu Sans"}):
        figure, axes = plt.subplots(figsize=(8.6, 4.2), layout="constrained")
        axes.plot(measured.nodes, measured.seconds, color="#2E6E91", marker="o", linewidth=2.5)
        axes.set_xscale("log")
        axes.set_yscale("log")
        axes.set_xticks(measured.nodes, [f"{row.scale}×\n{row.nodes:,} nodes" for row in measured.itertuples()])
        axes.set_ylabel("Core pipeline wall time (seconds)")
        axes.grid(axis="y", alpha=0.2, which="both")
        axes.spines[["top", "right"]].set_visible(False)
        for row in measured.itertuples():
            axes.annotate(f"{row.seconds:.2f} s", (row.nodes, row.seconds), xytext=(0, 10),
                          textcoords="offset points", ha="center", color="#253B49")
        axes.margins(x=0.14, y=0.3)
        figure.suptitle("Measured scaling · sampled betweenness", fontsize=15, color="#253B49")
        axes.set_title("Synthetic graph lifts preserve degree and amount distributions", fontsize=10, pad=15)
        figure.savefig(path, format="svg", metadata={"Date": None})
        plt.close(figure)
    path = Path(path)
    path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")


def run(data_dir, out_dir, scales=None, samples=None, repeat=1):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    base = load_context(data_dir)
    cfg = base.cfg["benchmark"]
    scales = list(scales or cfg["scales"])
    samples = samples or cfg["betweenness_samples"]
    rows = []
    def record(ctx, scale, mode, trial, step, elapsed):
        rows.append({"scale": scale, "nodes": len(ctx.nodes), "edges": len(ctx.edges),
                     "transactions": len(ctx.tx), "step": step, "seconds": elapsed,
                     "mode": mode, "repeat": trial, "betweenness_samples": samples if mode == "sampled" else 0,
                     "degree_distribution": "exact", "amount_distribution": "exact"})
        print(f"{mode:7} {scale:3}× {step:18} {elapsed:9.3f}s", flush=True)
        pd.DataFrame(rows).to_csv(out / "bench.csv", index=False)

    # Limit BLAS parallelism for repeatable comparisons on shared hosts.
    with threadpool_limits(limits=1):
        for mode, scale in [("exact", 1)] + [("sampled", scale) for scale in scales]:
            for trial in range(1, repeat + 1):
                start = time.perf_counter()
                ctx = synthetic(base, scale, cfg["seed"])
                distribution_check(base, ctx, scale)
                ctx.cfg["centrality"]["betweenness_samples"] = samples if mode == "sampled" else None
                record(ctx, scale, mode, trial, "synthetic_load", time.perf_counter() - start)
                for module in STEPS:
                    t = time.perf_counter()
                    part = module.compute(ctx)
                    ctx.features = ctx.features.merge(part, on="gid", how="left", validate="one_to_one")
                    record(ctx, scale, mode, trial, module.__name__.split(".")[-1], time.perf_counter() - t)
                t = time.perf_counter()
                summary = clusters.summarize(ctx)
                record(ctx, scale, mode, trial, "cluster_summary", time.perf_counter() - t)
                t = time.perf_counter()
                resilience = priority.resilience(ctx)
                record(ctx, scale, mode, trial, "resilience", time.perf_counter() - t)
                t = time.perf_counter()
                with tempfile.TemporaryDirectory(prefix="moneygraph-bench-") as tmp:
                    export.write(ctx.features, summary, resilience, Path(tmp), ctx.cfg["priority"]["top_n"])
                    data_requests.build(ctx).to_csv(Path(tmp) / "data_requests.csv", index=False)
                record(ctx, scale, mode, trial, "core_export", time.perf_counter() - t)
                record(ctx, scale, mode, trial, "total", time.perf_counter() - start)
                if mode == "exact" and trial == 1:
                    t = time.perf_counter()
                    reference = temporal_reference(ctx)
                    elapsed = time.perf_counter() - t
                    optimized = ctx.features[reference.columns]
                    pd.testing.assert_frame_equal(reference, optimized, check_dtype=False, rtol=1e-12)
                    record(ctx, scale, "before", trial, "temporal_reference", elapsed)
    frame = pd.DataFrame(rows)
    chart(frame, out / "bench.svg")
    write_json(out / "bench_metadata.json", {
        "schema_version": 1, "python": sys.version.split()[0], "platform": platform.platform(),
        "processor": next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                           if line.startswith("model name")), platform.processor()) if Path("/proc/cpuinfo").exists() else platform.processor(),
        "logical_cpus": os.cpu_count(),
        "ram_gib": round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024 ** 3, 2) if hasattr(os, "sysconf") else None,
        "networkx": nx.__version__, "numpy": np.__version__,
        "pandas": pd.__version__, "repeat": repeat, "seed": cfg["seed"], "blas_threads": 1,
        "scales": scales, "betweenness_samples": samples,
        "workload": "Seeded random lifts of the observed directed graph; joint in/out degrees, edge KZT and transaction amount empirical distributions preserved exactly. Copies are mixed by edge permutations.",
        "scope": "All seven analytical steps, cluster summaries, resilience and core file export. Timings include graph construction and integrity checks. Interactive explanation JSON, input parquet copies and UI rendering excluded.",
        "caution": "Synthetic topology differs from the original; sampled betweenness changes features and rankings. Exact 1× is a separate baseline. Timings are measurements on this host, not a million-node performance promise.",
        "optimization": "Column aggregation and array FIFO replace per-node pandas operations; 1× reference verifies identical temporal outputs. Rank replaces quadratic percentile storage, component bitsets replace per-seed BFS, bounded cycle enumeration avoids repeated component decompositions, and removal scenarios reuse a sparse matrix.",
    })
    return frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="project_docs/data")
    parser.add_argument("--out", default="out")
    parser.add_argument("--scales", nargs="+", type=int)
    parser.add_argument("--samples", type=int)
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()
    if args.repeat < 1 or args.samples is not None and args.samples < 1 or args.scales and min(args.scales) < 1:
        parser.error("repeat, samples and scales must be positive")
    run(args.data, args.out, args.scales, args.samples, args.repeat)


if __name__ == "__main__":
    main()
