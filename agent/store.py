import json
from itertools import islice
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

OUT = Path("out")

CARD_COLS = [
    "gid", "depth", "is_seed", "role", "role_detail", "secondary_roles", "role_score", "evidence",
    "cluster_id", "priority_score", "why", "in_deg", "out_deg", "in_kzt", "out_kzt", "in_tx", "out_tx",
    "n_seed_payers", "pays_seed", "seed_flow_in", "n_seed_sources", "pass_through", "fast_pass_share",
    "p_has_out", "flags",
]


def to_gid(x):
    return int(str(x).strip())


def _clean(v):
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return None if np.isnan(v) else round(float(v), 4)
    if isinstance(v, np.bool_):
        return bool(v)
    return v


class GraphStore:
    def __init__(self, features, edges, tx, clusters=None, resilience=None, data_requests=None):
        self.f = features.set_index("gid", drop=False)
        self.edges = edges
        self.tx = tx.assign(date=pd.to_datetime(tx["date"]))
        self.clusters = clusters if clusters is not None else pd.DataFrame()
        self.resilience_df = resilience if resilience is not None else pd.DataFrame()
        self.data_requests = data_requests if data_requests is not None else pd.DataFrame()
        self.G = nx.DiGraph()
        self.G.add_nodes_from(self.f.index)
        for r in edges.itertuples(index=False):
            self.G.add_edge(r.src, r.dst, sum_kzt=float(r.sum_kzt), n_tx=int(r.n_tx))

    @classmethod
    def load(cls, out=OUT):
        out = Path(out)

        def opt(name):
            p = out / name
            return pd.read_csv(p) if p.exists() else None

        store = cls(
            pd.read_parquet(out / "features.parquet"),
            pd.read_parquet(out / "edges.parquet"),
            pd.read_parquet(out / "transactions.parquet"),
            opt("clusters.csv"),
            opt("resilience.csv"),
            opt("data_requests.csv"),
        )
        for name in ("rule_traces", "seed_paths", "truncation_model"):
            path = out / f"{name}.json"
            setattr(store, name, json.loads(path.read_text()) if path.exists() else {})
        return store

    def rule_trace(self, gid):
        return getattr(self, "rule_traces", {}).get("nodes", {}).get(str(to_gid(gid)), {})

    def money_paths(self, gid):
        return getattr(self, "seed_paths", {}).get("nodes", {}).get(str(to_gid(gid)), {})

    def has(self, gid):
        try:
            return to_gid(gid) in self.f.index
        except ValueError:
            return False

    def search(self, text, limit=20):
        text = str(text).strip()
        if not text:
            return []
        s = self.f.index.astype(str)
        return self.f.index[s.str.contains(text, regex=False)][:limit].tolist()

    def get_node(self, gid):
        gid = to_gid(gid)
        if gid not in self.f.index:
            return None
        row = self.f.loc[gid]
        return {c: _clean(row[c]) for c in CARD_COLS if c in row.index}

    def prio_components(self, gid):
        raw = self.f.loc[to_gid(gid)].get("prio_components", "{}")
        try:
            return json.loads(raw) if isinstance(raw, str) and raw else {}
        except json.JSONDecodeError:
            return {}

    def neighbors(self, gid, direction="both"):
        gid = to_gid(gid)
        rows = []
        if direction in ("in", "both"):
            for u, _, d in self.G.in_edges(gid, data=True):
                rows.append((u, "in", d["sum_kzt"], d["n_tx"]))
        if direction in ("out", "both"):
            for _, v, d in self.G.out_edges(gid, data=True):
                rows.append((v, "out", d["sum_kzt"], d["n_tx"]))
        df = pd.DataFrame(rows, columns=["gid", "direction", "sum_kzt", "n_tx"])
        df["role"] = self.f.loc[df.gid, "role"].to_numpy() if len(df) else []
        return df.sort_values("sum_kzt", ascending=False, ignore_index=True)

    def ego(self, gid, radius=1, max_nodes=300):
        gid = to_gid(gid)
        und = self.G.to_undirected(as_view=True)
        dist = nx.single_source_shortest_path_length(und, gid, cutoff=radius)
        nodes = list(dist)
        if len(nodes) > max_nodes:
            # keep the closest, then the ones moving the most money
            vol = self.f.loc[nodes, "in_kzt"] + self.f.loc[nodes, "out_kzt"]
            order = sorted(nodes, key=lambda n: (dist[n], -vol[n]))
            nodes = order[:max_nodes]
        return self.G.subgraph(nodes).copy()

    def cluster_graph(self, cluster_id, max_nodes=400):
        nodes = self.f.index[self.f.cluster_id == int(cluster_id)]
        if len(nodes) > max_nodes:
            nodes = self.f.loc[nodes].nlargest(max_nodes, "priority_score").index
        return self.G.subgraph(nodes).copy()

    def paths_between(self, a, b, max_len=4, limit=10):
        a, b = to_gid(a), to_gid(b)
        found = []
        for src, dst in ((a, b), (b, a)):
            found += islice(nx.all_simple_paths(self.G, src, dst, cutoff=max_len), limit)
        return sorted(found, key=len)[:limit]

    def common_collectors(self, gids, max_hops=2, min_sources=2):
        """Nodes that receive money (directly or within max_hops) from at least min_sources of gids."""
        gids = [to_gid(g) for g in gids if self.has(g)]
        reach = {}
        for g in gids:
            hops = nx.single_source_shortest_path_length(self.G, g, cutoff=max_hops)
            for n, h in hops.items():
                if n != g:
                    reach.setdefault(n, {})[g] = h
        rows = [
            (n, len(src), min(src.values()), sorted(src))
            for n, src in reach.items() if len(src) >= min(min_sources, len(gids))
        ]
        df = pd.DataFrame(rows, columns=["gid", "n_sources", "min_hops", "sources"])
        if df.empty:
            return df.assign(kzt_from_group=[], role=[], in_kzt=[])
        # money paid straight from the group; indirect hops aren't attributable
        df["kzt_from_group"] = [
            sum(self.G.edges[g, n]["sum_kzt"] for g in gids if self.G.has_edge(g, n)) for n in df.gid
        ]
        df["role"] = self.f.loc[df.gid, "role"].to_numpy()
        df["in_kzt"] = self.f.loc[df.gid, "in_kzt"].to_numpy()
        return df.sort_values(["n_sources", "min_hops", "kzt_from_group"], ascending=[False, True, False],
                              ignore_index=True)

    def top_nodes(self, n=10, role=None, include_seeds=True):
        df = self.f
        if role:
            df = df[df.role == role]
        if not include_seeds:
            df = df[~df.is_seed]
        cols = ["gid", "role", "priority_score", "why", "cluster_id", "is_seed"]
        return df.nlargest(n, "priority_score")[cols].reset_index(drop=True)

    def cluster_summary(self, cluster_id=None):
        if self.clusters.empty:
            return self.clusters
        if cluster_id is None:
            return self.clusters
        return self.clusters[self.clusters.cluster_id == int(cluster_id)]

    def resilience(self):
        return self.resilience_df

    def tx_timeline(self, gid):
        gid = to_gid(gid)
        t = self.tx
        inc = t[t.dst == gid].groupby("date").sum_kzt.sum().rename("in_kzt")
        out = t[t.src == gid].groupby("date").sum_kzt.sum().rename("out_kzt")
        return pd.concat([inc, out], axis=1, sort=False).fillna(0.0).sort_index().reset_index()

    def role_counts(self):
        return self.f.role.value_counts()

    def demo_picks(self):
        """Walk-through gids chosen from the current outputs, so they follow pipeline changes."""
        f = self.f
        picks = {}

        def best(label, mask, by):
            sub = f[mask]
            if len(sub):
                picks[label] = int(sub.nlargest(1, by).gid.iloc[0])

        best("top priority (non-seed)", ~f.is_seed, "priority_score")
        best("biggest distributor", f.role == "distributor", "out_deg")
        best("top consolidator", (f.role == "consolidator") & ~f.is_seed, "in_deg")
        best("top coordinator", f.role == "coordinator", "priority_score")
        best("depth 4, likely forwarding", (f.depth == 4) & f.p_has_out.notna(), "p_has_out")
        best("depth 4, inferred terminal", f.role_detail == "terminal_inferred", "in_kzt")
        return picks

    def demo_question(self):
        """The 'who collects from these five' question, built around the top consolidator."""
        c = self.demo_picks().get("top consolidator")
        if c is None:
            return None
        payers = self.neighbors(c, "in").gid.head(5).astype(str)
        return f"Кто собирает деньги с этих пятерых: {', '.join(payers)}?"
