from collections import deque

import pandas as pd


def fifo_fast_share(tx_in, tx_out, days):
    """Share of inflow KZT matched FIFO by outflow sent within `days` after it arrived.

    Dates have no time of day, so same-day in and out counts as matched.
    """
    total = tx_in.sum_kzt.sum()
    if total <= 0 or tx_out.empty:
        return 0.0
    window = pd.Timedelta(days=days)
    lots = deque()                      # [date, remaining amount], oldest first
    ins = iter(tx_in.sort_values("date")[["date", "sum_kzt"]].itertuples(index=False))
    nxt = next(ins, None)
    matched = 0.0
    for d, amt in tx_out.sort_values("date")[["date", "sum_kzt"]].itertuples(index=False):
        while nxt is not None and nxt.date <= d:
            lots.append([nxt.date, nxt.sum_kzt])
            nxt = next(ins, None)
        while lots and d - lots[0][0] > window:
            lots.popleft()              # too old to count as fast transit
        while amt > 0 and lots:
            take = min(amt, lots[0][1])
            matched += take
            amt -= take
            lots[0][1] -= take
            if lots[0][1] <= 0:
                lots.popleft()
    return matched / total


def node_flags(sent, all_tx, c):
    flags = []
    if not sent.empty and sent.sum_kzt.value_counts().max() >= c["repeat_amount_min"]:
        flags.append("repeat_amount")
    if len(all_tx) >= c["min_tx"]:
        if (all_tx.sum_kzt % c["round_unit"] == 0).mean() >= c["round_share"]:
            flags.append("round_amounts")
        if all_tx.date.value_counts().max() / len(all_tx) >= c["burst_share"]:
            flags.append("burst")
    lo, hi = c["near_threshold_range"]
    if all_tx.sum_kzt.between(lo, hi).sum() >= c["near_threshold_min"]:
        flags.append("near_threshold")
    return ";".join(flags)


def compute(ctx) -> pd.DataFrame:
    """Aggregate flags in columns; only the amount-matching FIFO needs a node loop."""
    cfg, tx = ctx.cfg["temporal"], ctx.tx
    c = cfg["flags"]
    ids = pd.Index(ctx.nodes.gid, name="gid")
    incoming = tx.rename(columns={"dst": "gid"})
    outgoing = tx.rename(columns={"src": "gid"})
    both = pd.concat([incoming[["gid", "date", "sum_kzt"]], outgoing[["gid", "date", "sum_kzt"]]], ignore_index=True)
    by_node = both.groupby("gid", sort=False)
    counts = by_node.size().reindex(ids, fill_value=0)
    round_share = both.assign(is_round=both.sum_kzt.mod(c["round_unit"]).eq(0)).groupby("gid").is_round.mean().reindex(ids, fill_value=0)
    lo, hi = c["near_threshold_range"]
    near = both.assign(near=both.sum_kzt.between(lo, hi)).groupby("gid").near.sum().reindex(ids, fill_value=0)
    burst = both.groupby(["gid", "date"]).size().groupby(level=0).max().reindex(ids, fill_value=0) / counts.where(counts > 0, 1)
    repeat = outgoing.groupby(["gid", "sum_kzt"]).size().groupby(level=0).max().reindex(ids, fill_value=0)
    flags = pd.Series("", index=ids)
    for name, mask in [("repeat_amount", repeat >= c["repeat_amount_min"]),
                       ("round_amounts", (counts >= c["min_tx"]) & (round_share >= c["round_share"])),
                       ("burst", (counts >= c["min_tx"]) & (burst >= c["burst_share"])),
                       ("near_threshold", near >= c["near_threshold_min"])]:
        flags.loc[mask] += name + ";"
    first_in = incoming.groupby("gid").date.min().reindex(ids)
    first_out = outgoing.groupby("gid").date.min().reindex(ids)
    max_payers = incoming.groupby(["gid", "date"]).src.nunique().groupby(level=0).max().reindex(ids, fill_value=0)

    # Sort once globally. Small numpy arrays avoid thousands of per-node DataFrame
    # sorts, concatenations and groupbys while preserving the original FIFO order.
    ordered = tx.sort_values("date", kind="stable")
    dates = ordered.date.to_numpy(dtype="datetime64[ns]").astype("int64")
    amounts = ordered.sum_kzt.to_numpy(dtype=float)
    by_dst = ordered.groupby("dst", sort=False).indices
    by_src = ordered.groupby("src", sort=False).indices
    window = pd.Timedelta(days=cfg["fast_pass_days"]).value
    shares = []
    for gid in ids:
        ins, outs = by_dst.get(gid, []), by_src.get(gid, [])
        total = amounts[ins].sum() if len(ins) else 0
        if total <= 0 or not len(outs):
            shares.append(0.0)
            continue
        lots, i, matched = deque(), 0, 0.0
        for j in outs:
            day, amount = dates[j], amounts[j]
            while i < len(ins) and dates[ins[i]] <= day:
                lots.append([dates[ins[i]], amounts[ins[i]]])
                i += 1
            while lots and day - lots[0][0] > window:
                lots.popleft()
            while amount > 0 and lots:
                take = min(amount, lots[0][1])
                matched += take
                amount -= take
                lots[0][1] -= take
                if lots[0][1] <= 0:
                    lots.popleft()
        shares.append(matched / total)
    return pd.DataFrame({"gid": ids, "fast_pass_share": shares,
                         "out_before_in": (first_out < first_in).to_numpy(),
                         "max_same_day_payers": max_payers.to_numpy(dtype=int),
                         "active_days": by_node.date.nunique().reindex(ids, fill_value=0).to_numpy(dtype=int),
                         "flags": flags.str.rstrip(";").to_numpy()})
