import pandas as pd


def compute(ctx) -> pd.DataFrame:
    # TODO(B4): weighted components from cfg["priority"], removal impact, why text
    f = ctx.features
    df = f[["gid"]].copy()
    df["priority_score"] = f.pagerank.rank(pct=True).values
    df["prio_components"] = "{}"
    df["why"] = ("stub: pagerank percentile " + (df.priority_score * 100).round().astype(int).astype(str)).values
    return df


def resilience(ctx) -> pd.DataFrame:
    # TODO(B4): remove top-N by priority vs degree vs random
    return pd.DataFrame(columns=["n_removed", "strategy", "largest_wcc", "n_components", "seed_flow_reach"])
