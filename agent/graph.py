import os
import re
import sys
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from agent.store import to_gid
from agent.tools import cited_gids, make_tools

DEFAULT_MODEL = "gpt-4.1-mini"
MAX_STEPS = 8

SYSTEM = """You help an AML analyst explore a graph of money transfers between bank clients (gids).
Rules:
- Use only facts returned by the tools. If the tools don't answer the question, say so.
- Cite every client by its full gid exactly as the tools return it. Never invent or shorten a gid.
- Roles, priorities and evidence are computed by the pipeline; report them, never assign your own.
- Word conclusions as hypotheses ("looks like", "may be"), not accusations.
- No personal data: clients are gids only.
- Reply in the language of the question (Russian or English), briefly, with numbers.
- Lead with the few strongest results; don't paste whole tool tables."""


def load_env():
    load_dotenv()
    # an empty OPENAI_BASE_URL in .env would be taken as the endpoint
    for k in [k for k, v in os.environ.items() if k.startswith(("OPENAI_", "LANGFUSE_")) and not v.strip()]:
        os.environ.pop(k)


def enabled():
    load_env()
    return bool(os.environ.get("OPENAI_API_KEY"))


def callbacks():
    if not (os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY")):
        return []
    try:
        from langfuse.langchain import CallbackHandler
        return [CallbackHandler()]
    except Exception as e:  # tracing is optional
        print(f"langfuse disabled: {e}", file=sys.stderr)
        return []


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    steps: int
    retried: bool
    unknown: list[str]


def build(store, model=None, llm=None):
    tools = make_tools(store)
    if llm is None:
        from langchain_openai import ChatOpenAI
        load_env()
        llm = ChatOpenAI(model=model or os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL, temperature=0,
                         base_url=os.environ.get("OPENAI_BASE_URL") or None)
    with_tools = llm.bind_tools(tools)

    def agent(state):
        msgs = [SystemMessage(SYSTEM)] + state["messages"]
        if state["steps"] >= MAX_STEPS - 1:
            # out of budget: answer from what we have
            reply = llm.invoke(msgs + [HumanMessage("Step limit reached. Answer now from the tool results above.")])
        else:
            reply = with_tools.invoke(msgs)
        return {"messages": [reply], "steps": state["steps"] + 1}

    def route(state):
        last = state["messages"][-1]
        return "tools" if getattr(last, "tool_calls", None) else "guardrail"

    def guardrail(state):
        answer = state["messages"][-1]
        unknown = sorted(str(g) for g in cited_gids(answer.content) if not store.has(g))
        if unknown and not state["retried"]:
            note = (f"These gids are not in the graph: {', '.join(unknown)}. "
                    "Rewrite the answer citing only gids returned by the tools.")
            return {"messages": [HumanMessage(note)], "retried": True, "unknown": unknown}
        if unknown:
            text = answer.content
            for g in unknown:
                text = text.replace(g, "[unknown gid]")
            return {"messages": [AIMessage(text)], "unknown": unknown}
        return {"unknown": []}

    def after_guardrail(state):
        return "agent" if isinstance(state["messages"][-1], HumanMessage) else END

    g = StateGraph(State)
    g.add_node("agent", agent)
    g.add_node("tools", ToolNode(tools))
    g.add_node("guardrail", guardrail)
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", route, ["tools", "guardrail"])
    g.add_edge("tools", "agent")
    g.add_conditional_edges("guardrail", after_guardrail, ["agent", END])
    return g.compile()


def ask(app, question, history=()):
    """Run one question. history: earlier (role, text) pairs, role 'user' or 'assistant'."""
    msgs = [HumanMessage(t) if r == "user" else AIMessage(t) for r, t in history] + [HumanMessage(question)]
    out = app.invoke({"messages": msgs, "steps": 0, "retried": False, "unknown": []},
                     config={"callbacks": callbacks(), "recursion_limit": 3 * MAX_STEPS})
    answer = out["messages"][-1].content
    new = out["messages"][len(msgs):]
    used = [c["name"] for m in new for c in (getattr(m, "tool_calls", None) or [])]
    order = [m.group() for m in re.finditer(r"(?<!\d)\d{15,20}(?!\d)", answer)]
    gids = list(dict.fromkeys(str(to_gid(g)) for g in order))
    return {"answer": answer, "gids": gids, "tools": used,
            "steps": out["steps"], "unknown": out["unknown"]}


if __name__ == "__main__":
    from agent.store import GraphStore
    q = " ".join(sys.argv[1:]) or "Who should I look at first and why?"
    r = ask(build(GraphStore.load()), q)
    print(r["answer"])
    print("\ncited:", r["gids"], "\ntools:", r["tools"], "\nsteps:", r["steps"])
