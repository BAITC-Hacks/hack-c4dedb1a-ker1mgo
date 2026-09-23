import hashlib
import os
from pathlib import Path

from agent.store import to_gid

CARDS = Path("out") / "cards"

PROSE_PROMPT = """Write 3-4 sentences for an AML analyst summarising this client from the facts below.
Use only these facts and their numbers, word it as a hypothesis, cite the gid, and mention any data gaps.
Reply in {lang}.

{facts}"""


def _kzt(x):
    x = float(x or 0)
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if abs(x) >= div:
            return f"{x / div:.2f}{suf}"
    return f"{x:.0f}"


def fact_card(store, gid):
    """Deterministic markdown card built only from computed columns."""
    n = store.get_node(gid)
    if n is None:
        return None
    nb = store.neighbors(gid)
    lines = [
        f"**{n['gid']}**: {n['role']} ({n['role_detail']}), role score {n['role_score']:.2f}, "
        f"depth {n['depth']}{', seed' if n['is_seed'] else ''}, cluster {n['cluster_id']}",
        f"- evidence: {n['evidence']}",
        f"- priority {n['priority_score']:.2f}: {n['why']}",
        f"- {n['in_deg']} payers, {_kzt(n['in_kzt'])} KZT in ({n['in_tx']} tx); "
        f"{n['out_deg']} recipients, {_kzt(n['out_kzt'])} KZT out ({n['out_tx']} tx)",
        f"- seed money in: {_kzt(n['seed_flow_in'])} KZT from {n['n_seed_sources']} seeds",
    ]
    if n.get("secondary_roles"):
        lines.append(f"- also matches: {n['secondary_roles']}")
    if n.get("flags"):
        lines.append(f"- flags: {n['flags'].replace(';', ', ')}")
    for direction, label in (("in", "top payers"), ("out", "top recipients")):
        top = nb[nb.direction == direction].head(3)
        if len(top):
            lines.append(f"- {label}: " + "; ".join(f"{g} ({_kzt(k)})" for g, k in zip(top.gid, top.sum_kzt)))
    if n["is_seed"]:
        lines.append("- gap: seed, incoming transfers not crawled, inflow under-counted")
    if n["depth"] == 4:
        p = n.get("p_has_out")
        lines.append("- gap: depth 4, outgoing transfers not crawled"
                     + (f"; model P(sends on) = {p:.2f}" if p is not None else ""))
    return "\n".join(lines)


def prose(store, gid, llm=None, lang="Russian"):
    """Optional LLM summary of the fact card, cached per card content so a rerun of the pipeline refreshes it."""
    facts = fact_card(store, gid)
    if facts is None:
        return None
    key = hashlib.sha1(f"{lang}\n{facts}".encode()).hexdigest()[:10]
    path = CARDS / f"{to_gid(gid)}_{key}.md"
    if path.exists():
        return path.read_text()
    if llm is None:
        from langchain_openai import ChatOpenAI

        from agent.graph import DEFAULT_MODEL, load_env
        load_env()
        llm = ChatOpenAI(model=os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL, temperature=0,
                         base_url=os.environ.get("OPENAI_BASE_URL") or None)
    text = llm.invoke(PROSE_PROMPT.format(lang=lang, facts=facts)).content
    CARDS.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return text
