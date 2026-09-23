import numpy as np
import pandas as pd


def compute(ctx) -> pd.DataFrame:
    # TODO(A6): logistic regression on depth 1-3, predict for depth-4 sinks, save truncation_model.json
    df = ctx.nodes[["gid"]].copy()
    df["p_has_out"] = np.nan
    return df
