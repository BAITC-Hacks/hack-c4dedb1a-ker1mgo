from moneygraph.formatting import fmt_kzt

PROSE_PROMPT = """Write 3-4 sentences for an AML analyst summarising this client from the facts below.
Use only these facts and their numbers, word it as a hypothesis, cite the gid, and mention any data gaps.
Reply in {lang}.

{facts}"""


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
        f"- {n['in_deg']} payers, {fmt_kzt(n['in_kzt'])} KZT in ({n['in_tx']} tx); "
        f"{n['out_deg']} recipients, {fmt_kzt(n['out_kzt'])} KZT out ({n['out_tx']} tx)",
        f"- seed money in: {fmt_kzt(n['seed_flow_in'])} KZT from {n['n_seed_sources']} seeds",
    ]
    if n.get("secondary_roles"):
        lines.append(f"- also matches: {n['secondary_roles']}")
    if n.get("flags"):
        lines.append(f"- flags: {n['flags'].replace(';', ', ')}")
    for direction, label in (("in", "top payers"), ("out", "top recipients")):
        top = nb[nb.direction == direction].head(3)
        if len(top):
            lines.append(
                f"- {label}: "
                + "; ".join(f"{g} ({fmt_kzt(k)})" for g, k in zip(top.gid, top.sum_kzt))
            )
    if n["is_seed"]:
        lines.append("- gap: seed, incoming transfers not crawled, inflow under-counted")
    if n["depth"] == 4:
        p = n.get("p_has_out")
        lines.append(
            "- gap: depth 4, outgoing transfers not crawled"
            + (f"; model P(sends on) = {p:.2f}" if p is not None else "")
        )
    return "\n".join(lines)


def prose(store, gid, llm=None, lang="Russian"):
    """Optional summary; the viewer and assistant never write pipeline outputs."""
    facts = fact_card(store, gid)
    if facts is None:
        return None
    if llm is None:
        from agent.config import create_llm

        llm = create_llm()
    text = llm.invoke(PROSE_PROMPT.format(lang=lang, facts=facts)).content
    return text
