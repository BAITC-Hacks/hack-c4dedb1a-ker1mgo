## Roles

Every client gets exactly one role from ordered, documented rules. The rules are checked top to bottom and the first match wins;
any other rules that also match are listed in `secondary_roles`. Thresholds live in `moneygraph/config.yaml`, each with its reason.

| # | Role | Rule (final thresholds) | Why |
|---|---|---|---|
| 1 | **coordinator** | (pays ≥ 2 distinct seeds, or on cycles of length ≤ 4 with ≥ 2 seeds) and (reachable from ≥ 2 seeds, or betweenness ≥ p98) | sends money back into several known couriers while sitting between seed flows. At "≥ 1 seed" the rule matched 67 nodes, because 73% of nodes are reachable from ≥ 2 seeds; at 2 it gives 22 |
| 2 | **distributor** | out_deg ≥ 10 and out_deg ≥ 3 × max(in_deg, 1) | fan-out: few sources, many recipients (hubs up to 116 recipients) |
| 3 | **consolidator** | in_deg ≥ 5 and (pass_through ≤ 0.5 or out_deg ≤ in_deg / 3) | many distinct payers, few exits. in_deg ≥ 5 is p98 |
| 4 | **transit** | non-seed, in ≥ 1, out ≥ 1, and (0.8 ≤ pass_through ≤ 1.2, or ≥ 50% of inflow forwarded within 2 days while pass_through ≤ 2) | passes money on without holding it. Above pass_through 2, most outflow comes from outside the graph, so fast forwarding alone is not enough |
| 5 | **terminal** | out = 0, in ≥ 1, and depth ≤ 3 (`terminal_observed`), or depth 4 with P(forwards) < 0.3 (`terminal_inferred`) | the crawl checked outgoing transfers of every depth 1–3 node, so a sink there is observed; at depth 4 it can only be inferred |
| 6 | **peripheral** | everything else: `truncated_unknown`, `truncated_likely_forwarding` (P > 0.6), `seed_no_outgoing`, `no_edges`, `weak_signal` | stays inside the role dictionary while being honest about gaps |

Seeds never use `in_kzt` or `pass_through`: their inflow is under-counted because the graph was crawled from them.
Fast pass-through is matched FIFO: each incoming transfer is matched by outgoing transfers within 2 days.

**role_score**: for each threshold condition, `m = clip((x - thr) / thr, 0, 1)` (the inverse for ≤ conditions), then `0.5 + 0.5 × mean(m)`.
`terminal_observed` = 0.9, `terminal_inferred` = 1 − P(forwards), `peripheral` = 1 − the node's best partial match to a structural role.

**evidence**: at most 200 characters, always with numbers, worded as a hypothesis, e.g.
`8 payers (2 seeds) → 2.16M in; sends on 24%; to 2 recipients; up to 7 payers same day; seed money in 875k; flags burst`.

### Role counts (2,248 clients)

| Role | Nodes | Share | By detail |
|---|---:|---:|---|
| terminal | 1,133 | 50.4% | 1,071 observed · 62 inferred |
| peripheral | 907 | 40.3% | 494 weak signal (94 of them fast forwarders above the pass-through cap) · 350 truncated unknown · 32 truncated likely forwarding · 31 seeds without outgoing |
| transit | 107 | 4.8% | |
| distributor | 50 | 2.2% | |
| consolidator | 29 | 1.3% | |
| coordinator | 22 | 1.0% | |

## Truncation

The crawl stopped at depth 4, so for the 444 depth-4 clients we can't see whether they send money on. Treating them all as end recipients
would be wrong: 35% / 42% / 36% of depth 1 / 2 / 3 clients do forward money.

We train a logistic regression (`StandardScaler` + `LogisticRegression(class_weight="balanced")`) on the **1,723 non-seed depth 1–3 clients with inflow**,
where outgoing transfers were crawled, with the label "has outgoing transfers". It uses **inbound-only** features, so the same inputs exist at depth 4,
and no depth feature. Payer role is not available at this step, so payer out-degree and pass-through stand in for it.

**5-fold stratified CV AUC: 0.733** (the trust threshold is 0.6; below it every depth-4 sink would stay `truncated_unknown`).

| Feature (standardized) | Coefficient |
|---|---:|
| mean incoming transfer (log) | −0.955 |
| distinct payers (in_deg) | +0.701 |
| largest incoming transfer (log) | +0.658 |
| payers' mean out-degree (log) | −0.371 |
| max payers on one day | −0.349 |
| days with incoming transfers | +0.326 |
| total inflow KZT (log) | +0.267 |
| payers' mean pass-through | +0.147 |
| share of round (10k) amounts | +0.071 |
| incoming transfer count | −0.019 |
| payers that are seeds | −0.015 |

Reading: clients who get many small-to-medium transfers from several payers over several days tend to send money on; a few large transfers
from a hub that pays many people look like an end recipient.

**Calibration.** Balanced class weights train as if forwarding were 50/50, so we shift the logit back by the observed base rate
(log-odds −0.516). Ranking and AUC are unchanged. **Mean P(forwards) at depth 4 = 0.41, vs an observed base rate of 0.37 at depths 1–3**,
so about 183 of 444 depth-4 clients likely forward money. With P < 0.3 → `terminal_inferred` (62), P > 0.6 → `truncated_likely_forwarding` (32),
and the rest (350) stay `truncated_unknown`. Likely forwarders are the candidates for a hop-5 data request (`data_requests.csv`).
Full model output: `out/truncation_model.json`.
