import pandas as pd

COLS = ["gid", "reason", "suggested_request"]


def build(ctx) -> pd.DataFrame:
    # TODO(C8): likely-forwarding depth-4 nodes, seeds without outgoing, seeds' missing inflow, small components
    return pd.DataFrame(columns=COLS)
