"""Does a depth-4 sink forward money? The crawl stopped there, so we can't see its outgoing transfers.

Train on non-seed depth 1-3 nodes with inflow (their outgoing transfers were crawled), label
out_deg > 0, using inbound-only features so the same inputs exist at depth 4. No depth feature.
Payer role is not used: roles are assigned after this step, so payer out_deg and pass-through
stand in for it.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

FOLDS = 5


def inbound_features(ctx) -> pd.DataFrame:
    f = ctx.features.set_index("gid")
    tin = ctx.tx
    unit = ctx.cfg["temporal"]["flags"]["round_unit"]
    g = tin.groupby("dst")
    X = pd.DataFrame(index=f.index)
    X["in_deg"] = f.in_deg
    X["log_in_kzt"] = np.log1p(f.in_kzt)
    X["in_tx"] = f.in_tx
    X["mean_transfer"] = np.log1p(g.sum_kzt.mean())
    X["max_transfer"] = np.log1p(g.sum_kzt.max())
    X["round_share"] = g.sum_kzt.apply(lambda s: (s % unit == 0).mean())
    X["in_active_days"] = g.date.nunique()          # inbound days only; all active days would leak the label
    X["max_same_day_payers"] = f.max_same_day_payers
    X["n_seed_payers"] = f.n_seed_payers

    e = ctx.edges[["src", "dst"]].assign(p_out=ctx.edges.src.map(f.out_deg),
                                          p_pt=ctx.edges.src.map(f.pass_through))
    X["payer_out_deg"] = np.log1p(e.groupby("dst").p_out.mean())
    X["payer_pass_through"] = e.groupby("dst").p_pt.mean().clip(upper=5)  # seeds' NaN skipped by mean
    return X.fillna(0.0)


def fit(ctx):
    f = ctx.features.set_index("gid")
    X = inbound_features(ctx)
    train = (~f.is_seed) & f.depth.between(1, 3) & (f.in_deg >= 1)
    target = (f.depth == 4) & (f.out_deg == 0) & ~f.is_seed
    y = (f.out_deg[train] > 0).astype(int)

    info = {"n_train": int(train.sum()), "n_target": int(target.sum()), "features": list(X.columns),
            "observed_rate_depth": {int(d): round(float((f.out_deg[train & (f.depth == d)] > 0).mean()), 3)
                                    for d in (1, 2, 3) if (train & (f.depth == d)).any()}}
    if y.nunique() < 2 or y.value_counts().min() < FOLDS or not target.any():
        info["skipped"] = "too little data to train"
        return pd.Series(np.nan, index=f.index), info

    model = make_pipeline(StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=1000))
    cv = StratifiedKFold(FOLDS, shuffle=True, random_state=ctx.cfg["clusters"]["seed"])
    p_cv = cross_val_predict(model, X[train], y, cv=cv, method="predict_proba")[:, 1]
    model.fit(X[train], y)
    coef = model[-1].coef_[0]

    # balanced class weights train as if forwarding were 50/50; shift the logit back to the
    # observed base rate so P is a probability again (ranking and AUC are unchanged)
    prior = float(np.log(y.mean() / (1 - y.mean())))
    p = pd.Series(np.nan, index=f.index)
    p[target] = 1 / (1 + np.exp(-(model.decision_function(X[target]) + prior)))
    auc = float(roc_auc_score(y, p_cv))
    info.update({
        "auc_cv": round(auc, 3),
        "trusted": auc >= ctx.cfg["truncation"]["min_auc"],
        "observed_rate_depth1_3": round(float(y.mean()), 3),
        "mean_p_depth4": round(float(p[target].mean()), 3),
        "expected_forwarders_depth4": int(round(p[target].sum())),
        "coefficients": dict(sorted(((c, round(float(v), 3)) for c, v in zip(X.columns, coef)),
                                    key=lambda kv: -abs(kv[1]))),
        "intercept": round(float(model[-1].intercept_[0]), 3),
        "prior_shift": round(prior, 3),
    })
    return p, info


def compute(ctx) -> pd.DataFrame:
    p, info = fit(ctx)
    ctx.truncation_model = info
    if not info.get("trusted", False):
        p[:] = np.nan  # untrusted model: every depth-4 sink stays truncated_unknown
    df = ctx.nodes[["gid"]].copy()
    df["p_has_out"] = df.gid.map(p).astype(float)
    return df


def save(ctx, out_dir):
    """Writes out/truncation_model.json; called by run.py after export."""
    path = Path(out_dir) / "truncation_model.json"
    path.write_text(json.dumps(getattr(ctx, "truncation_model", {}), indent=2, ensure_ascii=False))
    return path
