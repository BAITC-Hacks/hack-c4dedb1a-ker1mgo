import pandas as pd


def compute(ctx) -> pd.DataFrame:
    # TODO(A4): ordered rules from cfg["roles"], role_score margins, evidence templates
    f = ctx.features
    df = f[["gid"]].copy()
    df["role"] = "peripheral"
    df["role_detail"] = "stub"
    df["secondary_roles"] = ""
    df["role_score"] = 0.1
    df["evidence"] = ("stub: in " + f.in_deg.astype(str) + " payers, out " + f.out_deg.astype(str) + " recipients").values
    return df
