import argparse
import time
from pathlib import Path

from . import clusters, data_requests, export, features, priority, roles, taint, temporal, truncation
from .data import load_context

# order matters: each step can read ctx.features produced by the ones before it
STEPS = [features, temporal, taint, truncation, roles, clusters, priority]


def run(data_dir, out_dir, verbose=True):
    t0 = time.perf_counter()
    ctx = load_context(data_dir)
    for step in STEPS:
        t = time.perf_counter()
        part = step.compute(ctx)
        assert len(part) == len(ctx.features), f"{step.__name__} returned {len(part)} rows"
        dup = [c for c in part.columns if c != "gid" and c in ctx.features.columns]
        assert not dup, f"{step.__name__} overwrites columns {dup}"
        ctx.features = ctx.features.merge(part, on="gid", how="left")
        if verbose:
            print(f"  {step.__name__.split('.')[-1]:<11} {time.perf_counter() - t:6.2f}s")

    cl = clusters.summarize(ctx)
    res = priority.resilience(ctx)
    export.write(ctx.features, cl, res, Path(out_dir), ctx.cfg["priority"]["top_n"])
    truncation.save(ctx, out_dir)
    data_requests.build(ctx).to_csv(Path(out_dir) / "data_requests.csv", index=False)

    if verbose:
        f = ctx.features
        print("\nroles:", f.role.value_counts().to_dict())
        print(f"clusters: {len(cl)}  multi-seed: {((cl.n_seed > 1) & (cl.cluster_id > 0)).sum()}")
        print(f"done in {time.perf_counter() - t0:.1f}s -> {out_dir}/")
    return ctx


def main():
    ap = argparse.ArgumentParser(description="money graph pipeline: parquet -> roles, clusters, priorities")
    ap.add_argument("--data", default="project_docs/data")
    ap.add_argument("--out", default="out")
    a = ap.parse_args()
    run(a.data, a.out)


if __name__ == "__main__":
    main()
