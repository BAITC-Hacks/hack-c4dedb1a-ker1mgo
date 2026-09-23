import streamlit as st

from app.navigation import focus
from app.resources import FEATURES_PATH, assistant_enabled, get_agent

EXAMPLES = [
    "Кого проверить первым и почему?",
    "Какие кластеры похожи на сборочные ячейки?",
    "Who are the top distributors?",
]


def render(store):
    st.subheader("Assistant")
    if not assistant_enabled():
        st.info(
            "The assistant needs its optional dependencies and `OPENAI_API_KEY` in `.env`. Everything else works without them."
        )
        return
    st.caption(
        "Answers come only from the graph tools; every cited gid is checked against the graph. "
        "Treat conclusions as hypotheses."
    )
    chat = st.session_state.setdefault("chat", [])

    for i, m in enumerate(chat):
        with st.chat_message(m["role"]):
            st.markdown(m["text"])
            if m.get("gids"):
                cols = st.columns(min(len(m["gids"]), 6))
                for j, g in enumerate(m["gids"]):
                    cols[j % len(cols)].button(
                        g, key=f"cite_{i}_{g}", on_click=focus, args=(g, "Node card")
                    )
            if m.get("tools"):
                st.caption(
                    "tools: "
                    + ", ".join(m["tools"])
                    + (f" · steps {m['steps']}" if m.get("steps") else "")
                )

    q = st.chat_input("Ask about clients, flows or clusters")
    if not chat:
        demo_question = store.demo_question()
        examples = ([demo_question] if demo_question else []) + EXAMPLES
        cols = st.columns(len(examples))
        for c, ex in zip(cols, examples):
            if c.button(ex):
                q = ex
    if q:
        from agent.graph import ask

        history = [(m["role"], m["text"]) for m in chat][-10:]
        chat.append({"role": "user", "text": q})
        with st.spinner("looking through the graph"):
            try:
                r = ask(get_agent(FEATURES_PATH.stat().st_mtime, store), q, history)
                chat.append(
                    {
                        "role": "assistant",
                        "text": r["answer"],
                        "gids": r["gids"],
                        "tools": r["tools"],
                        "steps": r["steps"],
                    }
                )
            except Exception as e:
                chat.append({"role": "assistant", "text": f"Assistant error: {e}"})
        st.rerun()
    if chat and st.button("clear chat"):
        chat.clear()
        st.rerun()
