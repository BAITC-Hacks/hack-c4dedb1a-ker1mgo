import pandas as pd


def compute(ctx) -> pd.DataFrame:
    # TODO(A3): propagate seed outflow for cfg taint.rounds; BFS per seed for n_seed_sources
    df = ctx.nodes[["gid"]].copy()
    df["seed_flow_in"] = 0.0
    df["n_seed_sources"] = 0
    return df
