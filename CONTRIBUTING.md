# Working on this repo

Three people, three tracks, one `main`. Each track owns its own files, so we can work
in parallel and merge often without conflicts.

- What we're building and why: [docs/design.md](docs/design.md)
- Track A, analytics (features, roles, truncation): [docs/tracks/a-analytics.md](docs/tracks/a-analytics.md)
- Track B, pipeline (skeleton, clusters, priority, tests, README): [docs/tracks/b-pipeline.md](docs/tracks/b-pipeline.md)
- Track C, viewer + assistant (Streamlit, LangGraph agent): [docs/tracks/c-viewer-agent.md](docs/tracks/c-viewer-agent.md)

## Getting started

```bash
git clone git@github.com:BAITC-Hacks/hack-c4dedb1a-ker1mgo.git
cd hack-c4dedb1a-ker1mgo
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # once B1 has landed; before that: pip install -r project_docs/starter/requirements.txt
cp .env.example .env                   # only track C needs keys
```

Then pick your track, open its file, and start at the first unchecked milestone.

## Who owns what

| Track | Owns | Doesn't touch without asking |
|---|---|---|
| A | `moneygraph/features.py temporal.py taint.py truncation.py roles.py eda.py`, `tests/test_rules.py` | everything else |
| B | `moneygraph/data.py clusters.py priority.py export.py run.py config.yaml`, `tests/` (except rules/store), `README.md`, `Makefile`, `requirements.txt`, `.env.example` | A's modules, `app/`, `agent/` |
| C | `app/`, `agent/`, `tests/test_store.py`, `moneygraph/data_requests.py`, the README "Assistant" section | the rest of `moneygraph/` |

Shared files (`config.yaml`, `requirements.txt`, the contract in `docs/design.md`) belong to B.
If you need to change one, post the exact line in chat and B makes the change, or you make it in a separate tiny commit and tell B.

Every pipeline module exposes one function, `compute(ctx) -> pd.DataFrame` keyed by `gid`, and `run.py` merges the results.
Column names in the contract are **frozen after the first checkpoint**. Adding columns is fine; renaming or removing them is not.

## Branches and commits

- Work only on your track branch: `track/a`, `track/b`, `track/c`. **Nobody pushes to `main` directly.**
- `main` is merged by the reviewer (Alisher's review session) after checking tests, outputs and the app,
  using `git merge --no-ff track/x`. Small fixes found in review land on `main` in the same merge and are announced.
- Small commits with short, plain, lowercase messages: `add fast pass-through feature`, `fix seed pass-through nan`.
- No hardcoded gids in code, and thresholds only in `config.yaml`. Tests check for both.

## When to push

**Every milestone in your track file ends with a push point.** When its "done when" check passes:

```bash
git fetch origin && git merge origin/main        # take what has been merged since you last synced
make run && make test                            # must be green on the combined code
# tick the milestone in your docs/tracks/*.md file, commit that too
git push origin HEAD                             # your track branch only
```

Then post in chat: `track/x ready for review: <milestone>`. Keep working on the next milestone; don't wait for the merge.

If `make test` fails because of someone else's code, don't push. Tell them in chat and keep working.
If the merge from `main` conflicts, you've most likely touched a file outside your ownership. Keep their version and message them.
Never force-push, and never rebase a branch you've already pushed.

Push at least every ~45 minutes even when you're between milestones, as long as things are green.

## Staying in sync

Whenever the reviewer announces "main updated":

```bash
git fetch origin && git merge origin/main && pip install -r requirements.txt && make run
```

## Gotchas found in review

- `flags` is a column **and** a pandas attribute (`DataFrame.flags`, `Series.flags`). Always write `df["flags"]` / `row["flags"]`, never `.flags`.
- gids are 18 digits. Pass them as strings in JSON and to the LLM, since floats lose digits. Only the last 10 digits are unique, so shorter labels collide.
- Seeds' inflow is under-counted. `pass_through` is NaN for seeds, and no rule may use `in_kzt` or `pass_through` for a seed.
- Only the pipeline writes `out/`. The app and the assistant read it and never compute roles or priorities themselves.
- `langfuse.langchain` needs the `langchain` package (now in requirements). Without it, tracing turns itself off silently.

## Checkpoints

Times are measured from when we start. At each one, everyone has pushed their track branch, the reviewer has merged it, `main` is green, and we do a 5-minute sync.

| At | Checkpoint | main must have |
|---|---|---|
| 0:20 | Contract & scaffold | B1: skeleton, stub pipeline writing all outputs, `make run` / `make test` |
| 1:15 | Checkpoint 1 | A: features + temporal + seed flow · B: clusters · C: app on stub outputs |
| 2:15 | Checkpoint 2 | real roles + priority + why · app on real outputs · agent answering using tools |
| 3:00 | **Feature freeze** | truncation model, resilience, eval done or cut. Only fixes after this |
| 3:40 | Docs & rehearsal | README final, diagram, 2 demo run-throughs |
| 4:00 | Submit | clean-clone run passes |

If you're behind at a checkpoint, use the cut list in `docs/design.md` instead of pushing the deadline.

## Where we stand

Each track file has a checklist. Tick a milestone in the same push that delivers it, so
`git pull` alone shows everyone the current state:

```bash
grep -h "^- \[" docs/tracks/*.md
```
