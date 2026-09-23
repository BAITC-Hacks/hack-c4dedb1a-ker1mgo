from dataclasses import dataclass, field
from pathlib import Path

import networkx as nx
import pandas as pd
import yaml

CONFIG_PATH = Path(__file__).with_name("config.yaml")


@dataclass
class Context:
    edges: pd.DataFrame
    nodes: pd.DataFrame
    tx: pd.DataFrame
    G: nx.DiGraph
    cfg: dict
    seeds: set
    # grows as pipeline steps run; every step sees what earlier steps produced
    features: pd.DataFrame = field(default=None)


def load_config(path=CONFIG_PATH) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load(data_dir: Path):
    edges = pd.read_parquet(data_dir / "edges.parquet")
    nodes = pd.read_parquet(data_dir / "nodes.parquet")
    tx = pd.read_parquet(data_dir / "transactions.parquet")
    tx["date"] = pd.to_datetime(tx["date"])
    return edges, nodes, tx


def sanity_check(edges, nodes, tx):
    agg = tx.groupby(["src", "dst"]).agg(s=("sum_kzt", "sum"), c=("sum_kzt", "size")).reset_index()
    m = edges.merge(agg, on=["src", "dst"], how="outer", indicator=True)
    assert (m["_merge"] == "both").all(), "edges and transactions disagree on pairs"
    assert nodes.gid.is_unique, "duplicate gid in nodes"
    missing = (set(edges.src) | set(edges.dst)) - set(nodes.gid)
    assert not missing, f"{len(missing)} edge endpoints missing from nodes"


def build_graph(edges, nodes) -> nx.DiGraph:
    G = nx.DiGraph()
    G.add_nodes_from(nodes.gid)
    for r in edges.itertuples(index=False):
        G.add_edge(r.src, r.dst, sum_kzt=float(r.sum_kzt), n_tx=int(r.n_tx), depth=int(r.depth))
    return G


def load_context(data_dir, cfg=None) -> Context:
    data_dir = Path(data_dir)
    edges, nodes, tx = load(data_dir)
    sanity_check(edges, nodes, tx)
    G = build_graph(edges, nodes)
    ctx = Context(edges=edges, nodes=nodes, tx=tx, G=G, cfg=cfg or load_config(),
                  seeds=set(nodes.loc[nodes.is_seed, "gid"]))
    ctx.features = nodes[["gid", "depth", "is_seed"]].copy()
    return ctx
