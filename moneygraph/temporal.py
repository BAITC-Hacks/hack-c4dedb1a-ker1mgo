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
    cfg = ctx.cfg["temporal"]
    tx = ctx.tx
    by_dst = dict(tuple(tx.groupby("dst")))
    by_src = dict(tuple(tx.groupby("src")))
    empty = tx.iloc[:0]

    rows = []
    for g in ctx.nodes.gid:
        tin, tout = by_dst.get(g, empty), by_src.get(g, empty)
        both = pd.concat([tin, tout])
        rows.append({
            "gid": g,
            "fast_pass_share": fifo_fast_share(tin, tout, cfg["fast_pass_days"]),
            "out_before_in": bool(len(tin) and len(tout) and tout.date.min() < tin.date.min()),
            "max_same_day_payers": int(tin.groupby("date").src.nunique().max()) if len(tin) else 0,
            "active_days": int(both.date.nunique()),
            "flags": node_flags(tout, both, cfg["flags"]),
        })
    return pd.DataFrame(rows)
