from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd
import yaml

from .paths import CONFIG_PATH


@dataclass
class Context:
    """Input graph and explicit state shared by the ordered pipeline steps."""

    edges: pd.DataFrame
    nodes: pd.DataFrame
    tx: pd.DataFrame
    G: nx.DiGraph
    cfg: dict[str, Any]
    seeds: set[int]
    verbose: bool = False
    # grows as pipeline steps run; every step sees what earlier steps produced
    features: pd.DataFrame = field(init=False)
    truncation_model: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.features = self.nodes[["gid", "depth", "is_seed"]].copy()


def load_config(path: str | Path = CONFIG_PATH) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load(data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    edges = pd.read_parquet(data_dir / "edges.parquet")
    nodes = pd.read_parquet(data_dir / "nodes.parquet")
    tx = pd.read_parquet(data_dir / "transactions.parquet")
    tx["date"] = pd.to_datetime(tx["date"])
    return edges, nodes, tx


def sanity_check(edges: pd.DataFrame, nodes: pd.DataFrame, tx: pd.DataFrame) -> None:
    transaction_pairs = tx[["src", "dst"]].drop_duplicates()
    pairs = edges[["src", "dst"]].merge(
        transaction_pairs, on=["src", "dst"], how="outer", indicator=True
    )
    if not (pairs["_merge"] == "both").all():
        raise ValueError("edges and transactions disagree on pairs")
    if not nodes.gid.is_unique:
        raise ValueError("duplicate gid in nodes")
    missing = (set(edges.src) | set(edges.dst)) - set(nodes.gid)
    if missing:
        raise ValueError(f"{len(missing)} edge endpoints missing from nodes")


def build_graph(edges: pd.DataFrame, nodes: pd.DataFrame) -> nx.DiGraph:
    G = nx.DiGraph()
    G.add_nodes_from(nodes.gid)
    for r in edges.itertuples(index=False):
        G.add_edge(r.src, r.dst, sum_kzt=float(r.sum_kzt), n_tx=int(r.n_tx), depth=int(r.depth))
    return G


def load_context(
    data_dir: str | Path, cfg: dict[str, Any] | None = None, *, verbose: bool = False
) -> Context:
    data_dir = Path(data_dir)
    edges, nodes, tx = load(data_dir)
    sanity_check(edges, nodes, tx)
    G = build_graph(edges, nodes)
    return Context(
        edges=edges,
        nodes=nodes,
        tx=tx,
        G=G,
        cfg=cfg or load_config(),
        seeds=set(nodes.loc[nodes.is_seed, "gid"]),
        verbose=verbose,
    )
