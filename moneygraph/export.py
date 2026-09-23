from pathlib import Path

import pandas as pd

NODES_COLS = ["gid", "role", "role_score", "cluster_id", "priority_score", "evidence"]
NODES_EXTRA = ["role_detail", "secondary_roles", "depth", "is_seed"]
CLUSTER_COLS = ["cluster_id", "n_nodes", "n_seed", "sum_kzt_internal", "top_gids", "hypothesis"]
TOP_COLS = ["rank", "gid", "role", "priority_score", "why"]
EVIDENCE_MAX = 200


def _clip(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.slice(0, EVIDENCE_MAX)


def write(features: pd.DataFrame, clusters: pd.DataFrame, resilience: pd.DataFrame, out_dir: Path, top_n: int):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    f = features.copy()
    f["evidence"] = _clip(f.evidence)
    f["why"] = _clip(f.why)

    f.to_parquet(out_dir / "features.parquet", index=False)
    f[NODES_COLS + NODES_EXTRA].to_csv(out_dir / "nodes_roles.csv", index=False)
    clusters[CLUSTER_COLS + [c for c in clusters.columns if c not in CLUSTER_COLS]] \
        .sort_values("cluster_id").to_csv(out_dir / "clusters.csv", index=False)

    top = f.sort_values("priority_score", ascending=False).head(top_n).reset_index(drop=True)
    top.insert(0, "rank", top.index + 1)
    top[TOP_COLS + ["cluster_id", "evidence"]].to_csv(out_dir / "top_nodes.csv", index=False)

    resilience.to_csv(out_dir / "resilience.csv", index=False)
