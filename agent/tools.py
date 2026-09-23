import json

from langchain_core.tools import tool

from agent.identifiers import cited_gids as cited_gids

MAX_ROWS = 25


def _rows(df, cols=None):
    if cols:
        df = df[cols]
    df = df.head(MAX_ROWS).copy()
    for c in df.columns:
        if c == "gid" or c.endswith("gid"):
            df[c] = df[c].astype(str)
    return json.loads(df.to_json(orient="records", double_precision=2))


def _dump(x):
    return json.dumps(x, ensure_ascii=False, default=str)


def make_tools(store):
    """Tools over GraphStore. gids go in and out as strings: 18 digits don't survive as JSON floats."""

    def check(gid):
        if not store.has(gid):
            return _dump({"error": f"gid {gid} not in the graph"})
        return None

    @tool
    def get_node(gid: str) -> str:
        """Full profile of one client: role, role evidence, priority and why, degrees, KZT in/out, seed flow, flags."""
        if err := check(gid):
            return err
        n = store.get_node(gid)
        n["gid"] = str(n["gid"])
        n["prio_components"] = store.prio_components(gid)
        return _dump(n)

    @tool
    def neighbors(gid: str, direction: str = "both") -> str:
        """Direct counterparties of a client. direction: 'in' (who pays it), 'out' (whom it pays) or 'both'.
        Sorted by KZT, at most 25 rows, plus totals."""
        if err := check(gid):
            return err
        nb = store.neighbors(gid, direction)
        totals = nb.groupby("direction").agg(n=("gid", "size"), sum_kzt=("sum_kzt", "sum")).round(0)
        return _dump({"totals": totals.to_dict("index"), "rows": _rows(nb)})

    @tool
    def paths_between(gid_a: str, gid_b: str, max_len: int = 4) -> str:
        """Directed transfer paths between two clients (either direction), up to max_len hops, shortest first."""
        for g in (gid_a, gid_b):
            if err := check(g):
                return err
        paths = store.paths_between(gid_a, gid_b, max_len=min(int(max_len), 6))
        return _dump({"n_paths": len(paths), "paths": [[str(g) for g in p] for p in paths]})

    @tool
    def common_collectors(gids: list[str], max_hops: int = 1) -> str:
        """Who collects money from a group of clients: nodes that receive transfers from at least 2 of the
        given gids. max_hops=1 means direct payments (kzt_from_group = KZT paid straight from the group);
        use 2 only if nothing direct is found. Sorted by how many of the group feed it."""
        known = [g for g in gids if store.has(g)]
        unknown = [g for g in gids if not store.has(g)]
        cc = store.common_collectors(known, max_hops=min(int(max_hops), 4))
        if not cc.empty:
            cc = cc.assign(sources=cc.sources.map(lambda s: [str(x) for x in s]))
        return _dump({"unknown_gids": unknown, "rows": _rows(cc)})

    @tool
    def top_nodes(n: int = 10, role: str = "", include_seeds: bool = True) -> str:
        """Highest-priority clients (who an analyst should look at first), optionally for one role:
        coordinator, consolidator, distributor, transit, terminal, peripheral."""
        return _dump(_rows(store.top_nodes(min(int(n), MAX_ROWS), role or None, include_seeds)))

    @tool
    def cluster_summary(cluster_id: int = -1) -> str:
        """Community summary: size, seeds, internal KZT, top gids and a hypothesis. -1 lists all clusters."""
        cl = store.cluster_summary(None if int(cluster_id) < 0 else cluster_id)
        if cl.empty:
            return _dump({"error": "no such cluster"})
        return _dump(_rows(cl.sort_values("n_seed", ascending=False)))

    @tool
    def resilience() -> str:
        """How the network breaks when the top-N nodes are removed by priority vs degree vs random."""
        res = store.resilience()
        return _dump(_rows(res) if not res.empty else {"error": "resilience not computed yet"})

    @tool
    def tx_timeline(gid: str) -> str:
        """Daily incoming vs outgoing KZT of a client, to judge timing (e.g. money passed on within days)."""
        if err := check(gid):
            return err
        tl = store.tx_timeline(gid)
        tl["date"] = tl.date.dt.strftime("%Y-%m-%d")
        return _dump(json.loads(tl.head(60).to_json(orient="records", double_precision=0)))

    return [
        get_node,
        neighbors,
        paths_between,
        common_collectors,
        top_nodes,
        cluster_summary,
        resilience,
        tx_timeline,
    ]
