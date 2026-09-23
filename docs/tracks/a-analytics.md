# Track A: analytics core

The critical path: every other track consumes these columns.
Owns: `moneygraph/features.py temporal.py taint.py truncation.py roles.py eda.py`, `tests/test_rules.py`.
Contract and rules: [../design.md](../design.md). Stubs already return the right columns; replace their `TODO(A…)` bodies.

Each milestone ends with a push (see "When to push" in [CONTRIBUTING.md](../../CONTRIBUTING.md)). Tick the box in the same push.

- [x] **A1 · features.py** (target 0:40)
  Add `n_seed_payers`, `pays_seed`, HITS (`nx.hits`, max_iter=500), exact directed betweenness,
  `in_cycle` / `cycle_with_seeds` via `nx.simple_cycles(G, length_bound=4)`. Keep `pass_through` NaN for seeds.
  *Done when:* `make run` prints p50/p90/p95/p98 of in_deg, out_deg and betweenness (used to confirm config thresholds).
  **Push.**

- [x] **A2 · temporal.py** (target 1:00)
  `fast_pass_share` (FIFO: each incoming transfer matched by outgoing within `fast_pass_days`), `out_before_in`,
  `active_days`, `max_same_day_payers`, `flags` (`repeat_amount` same amount ≥ 5×, `round_amounts` ≥ 80% multiples of 10k,
  `near_threshold` ≥ 3 tx in 5,000–6,000, `burst` ≥ 50% of tx on one day).
  *Done when:* about 429 nodes have `fast_pass_share > 0`.
  **Push.**

- [x] **A3 · taint.py** (target 1:15, checkpoint 1)
  Sparse row-normalized matrix, `rounds` from config, `s_out = min(s_in, out_kzt)` for non-seeds.
  `n_seed_sources` via BFS from each seed. Expose the propagation as a function B can call with a node removed.
  *Done when:* total seed flow reaching terminals and depth-4 nodes ≤ total seed out_kzt, and the top 10 by `seed_flow_in` make sense by eye.
  **Push. Checkpoint 1.**

- [x] **A4 · roles.py** (target 1:55)
  Ordered rules from `cfg["roles"]`, `role_detail`, `secondary_roles`, `role_score` margin formula, one evidence template per role/detail (≤ 200 chars, numbers).
  Seeds never use `in_kzt` / `pass_through`. Until A6 lands, depth-4 sinks are `peripheral / truncated_unknown`.
  *Done when:* role counts look sane (no single role except peripheral/terminal above ~60%) and you can explain 3 random gids aloud.
  **Push.**

- [x] **A5 · tests/test_rules.py** (target 2:15, checkpoint 2)
  One small toy DiGraph per role; depth-4 sink is never `terminal_observed`; seed role never depends on pass-through.
  **Push. Checkpoint 2.**

- [x] **A6 · truncation.py** (target 2:50)
  Logistic regression per design. Write `out/truncation_model.json` (AUC, coefficients, mean P at depth 4 vs observed rate at depth 1–3).
  Hook into roles: `terminal_inferred` / `truncated_unknown` / `truncated_likely_forwarding`. If AUC < `min_auc`, keep everything `truncated_unknown`.
  *Done when:* the AUC and coefficient table are sent to B for the README.
  **Push.**

- [ ] **A7 · freeze and demo prep** (3:00)
  Pick 3 walk-through gids (a consolidator, a distributor, an inferred terminal), write 30 seconds of explanation for each, and help B with the README role section.
  **Push** any fixes.

## Round 2 (from review)

- [x] **A8 · tighten coordinator** (next, 20 min)
  67 nodes are coordinators today, because `n_seed_sources ≥ 2` holds for 1,635 of 2,248 nodes (73%) and so doesn't discriminate.
  Measured options: `min_seed_sources: 9` (p90) → 20 nodes · `min_pays_seed: 2` → 22 · betweenness ≥ p98 required → 14.
  Pick one (or a combination) that gives roughly 15–25 nodes and write the reason next to it in `config.yaml`.
  *Done when:* 15–25 coordinators, and you can defend the top 3 aloud.
  **Push.**

- [x] **A9 · transit sanity + evidence wording** (20 min)
  88 of 189 transit nodes have `pass_through > 2` (e.g. "116k in, 507k out (439%)"): they get most of their money from outside the graph, so "passes money on" is a weak claim.
  Add `transit.max_pass_through_fast: 2.0` to config; the fast-pass branch only applies at or below it. Nodes above it fall to `weak_signal` with transit in `secondary_roles`.
  Evidence shows `betweenness 0.0000` for 18 coordinators: print the percentile instead ("betweenness top 2%").
  Only print the percentile table in `features.py` when running verbosely (it currently prints inside tests).
  *Done when:* no evidence line contains `0.0000`, and every transit node has pass_through ≤ 2 or is justified by the band rule.
  **Push.**

- [x] **A10 · README "Roles" and "Truncation" sections, as text for B** (by 3:15)
  Rule table with the final thresholds and reasons, plus role counts. Truncation: n_train 1,723, AUC, the coefficient table, and mean P at depth 4 vs the observed base rate (from `out/truncation_model.json`).
  Send it to B in chat (B owns README.md), or push it to your branch as `docs/roles_section.md` and B pastes it in.
