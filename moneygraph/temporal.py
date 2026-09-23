import pandas as pd


def compute(ctx) -> pd.DataFrame:
    # TODO(A2): FIFO in->out matching within cfg temporal.fast_pass_days, activity profile, flags
    df = ctx.nodes[["gid"]].copy()
    df["fast_pass_share"] = 0.0
    df["out_before_in"] = False
    df["max_same_day_payers"] = 0
    df["active_days"] = 0
    df["flags"] = ""
    return df
