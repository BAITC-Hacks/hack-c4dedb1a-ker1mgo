# Track C: viewer and assistant

Owns: `app/`, `agent/`, `tests/test_store.py`. Reads only `out/` and `project_docs/data/`, and never imports `moneygraph` internals except for loading.
Design: [../design.md](../design.md) (sections Assistant and Viewer). Build against the stub outputs first; they have the final column names.

Each milestone ends with a push (see "When to push" in [CONTRIBUTING.md](../../CONTRIBUTING.md)). Tick the box in the same push.

- [x] **C1 · environment** (target 0:20)
  `.env` from `.env.example` (never commit it). Confirm that a pyvis graph renders inside `st.components.v1.html` and that `make run && make app` shows the placeholder.

- [x] **C2 · agent/store.py + network view** (target 1:15, checkpoint 1)
  `GraphStore` loads `out/features.parquet`, `out/clusters.csv`, edges and transactions; pure query functions (`get_node`, `neighbors`, `paths_between`,
  `common_collectors`, `top_nodes`, `cluster_summary`, `resilience`, `tx_timeline`) shared by the app and the agent.
  App: sidebar gid search, ego graph radius 1–2 (arrows, width ∝ log KZT, role colours from design, seeds outlined, depth-4 dashed), top-list page.
  *Done when:* any gid shows its directed neighbours in under 2 s.
  **Push. Checkpoint 1.**

- [x] **C3 · node card + overview** (target 1:45)
  Card: role, score, evidence, secondary roles, priority breakdown bar (`prio_components`), daily in vs out timeline (plotly), counterparties, flags.
  Overview: KPIs, role counts, clusters table with hypotheses, resilience chart.
  **Push.**

- [x] **C4 · tools + LangGraph agent** (target 2:15, checkpoint 2)
  `agent/tools.py` wraps store functions as tools. `agent/graph.py`: explicit `StateGraph` (agent → ToolNode loop → guardrail node that verifies every cited gid exists → answer), max 8 steps,
  `ChatOpenAI(model=OPENAI_MODEL, base_url=OPENAI_BASE_URL or None)`, Langfuse `CallbackHandler` when keys are set. `tests/test_store.py` on a toy graph without an LLM.
  *Done when:* "кто собирает деньги с этих пятерых: …" returns cited gids that all exist.
  **Push. Checkpoint 2.**

- [x] **C5 · assistant tab + cards** (target 2:40)
  Chat with history in `session_state`; cited gids as buttons that open the card. `agent/cards.py`: deterministic fact card, optional LLM prose cached in `out/cards/`.
  Without `OPENAI_API_KEY` the tab shows a short notice and the rest of the app works.
  **Push.**

- [x] **C6 · agent/eval.py** (target 3:00)
  About 10 questions whose answers are computed from the graph; score gid recall and zero unknown gids; write `out/agent_eval.csv`.
  Send the score and a Langfuse trace screenshot to B for the README.
  **Push. Freeze.**

- [x] **C7 · demo driver** (3:40)
  Pre-select the demo gids, test the app without a key, and record a backup screen capture of the assistant answering.
  **Push** any fixes.

## Round 2 (from review)

C is ahead of schedule, so it picks up data requests (was B5) and proof for the assistant.

- [x] **C8 · moneygraph/data_requests.py** (next, 30 min)
  The stub is already wired into `run.py` → `out/data_requests.csv` with `gid, reason, suggested_request`. Rows:
  `truncated_likely_forwarding` depth-4 nodes (request hop 5 outgoing) · seeds with `seed_no_outgoing` (request other channels) ·
  seeds with outgoing but under-counted inflow (request their incoming transfers) · nodes in small weak components (< 20 nodes) not linked to the main network.
  Add a "Data gaps" expander on the Overview page reading this file.
  *Done when:* the file has rows for every category with counts printed by `make run`, and `make test` is green.
  **Push.**

- [ ] **C9 · tracing and eval with real keys** (30 min)
  `pip install -r requirements.txt` (adds `langchain`, which `langfuse.langchain` needs; without it tracing silently turned off).
  Run the demo question from the app and confirm the trace appears in Langfuse. Then run `make eval` after B4 lands (the top-N questions depend on real priority).
  *Done when:* `out/agent_eval.csv` exists, you have a trace screenshot, and the recall/precision numbers are posted in chat.
  **Push** any fixes.

- [ ] **C10 · README "Assistant" section** (by 3:15)
  How to enable it (`.env`), the graph diagram (agent → tools → guardrail), the tool list, the guardrail behaviour, the eval method and score, and Langfuse. Keep it short.
  **Push.**
