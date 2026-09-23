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

- [ ] **A3 · taint.py** (target 1:15, checkpoint 1)
  Sparse row-normalized matrix, `rounds` from config, `s_out = min(s_in, out_kzt)` for non-seeds.
  `n_seed_sources` via BFS from each seed. Expose the propagation as a function B can call with a node removed.
  *Done when:* total seed flow reaching terminals and depth-4 nodes ≤ total seed out_kzt, and the top 10 by `seed_flow_in` make sense by eye.
  **Push. Checkpoint 1.**

- [ ] **A4 · roles.py** (target 1:55)
  Ordered rules from `cfg["roles"]`, `role_detail`, `secondary_roles`, `role_score` margin formula, one evidence template per role/detail (≤ 200 chars, numbers).
  Seeds never use `in_kzt` / `pass_through`. Until A6 lands, depth-4 sinks are `peripheral / truncated_unknown`.
  *Done when:* role counts look sane (no single role except peripheral/terminal above ~60%) and you can explain 3 random gids aloud.
  **Push.**

- [ ] **A5 · tests/test_rules.py** (target 2:15, checkpoint 2)
  One small toy DiGraph per role; depth-4 sink is never `terminal_observed`; seed role never depends on pass-through.
  **Push. Checkpoint 2.**

- [ ] **A6 · truncation.py** (target 2:50)
  Logistic regression per design. Write `out/truncation_model.json` (AUC, coefficients, mean P at depth 4 vs observed rate at depth 1–3).
  Hook into roles: `terminal_inferred` / `truncated_unknown` / `truncated_likely_forwarding`. If AUC < `min_auc`, keep everything `truncated_unknown`.
  *Done when:* the AUC and coefficient table are sent to B for the README.
  **Push.**

- [ ] **A7 · freeze and demo prep** (3:00)
  Pick 3 walk-through gids (a consolidator, a distributor, an inferred terminal), write 30 seconds of explanation for each, and help B with the README role section.
  **Push** any fixes.
