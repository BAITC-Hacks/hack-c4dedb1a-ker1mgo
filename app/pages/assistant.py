import streamlit as st

from app.ui import OUT, assistant_enabled, get_agent, get_store, open_dossier, page_header

store = get_store()
page_header(
    "Ask a question. Inspect the references.",
    "The optional assistant queries the case outputs and checks every cited client ID against the graph.",
)
if not assistant_enabled():
    st.info(
        "The assistant is not connected. To enable it, install the optional assistant dependencies, set `OPENAI_API_KEY` in `.env` and restart the app. Investigations, dossiers and all other pages work locally without a key."
    )
    st.markdown("**Questions you can ask when connected**")
    st.write(
        "Who receives money from these clients? Which distributors should I review first? What evidence supports this cluster hypothesis?"
    )
    st.page_link("pages/investigate.py", label="Continue investigating locally")
    st.stop()


chat = st.session_state.setdefault("chat", [])
for i, message in enumerate(chat):
    with st.chat_message(message["role"]):
        st.markdown(message["text"])
        for gid in message.get("gids", []):
            if st.button(f"Open {gid}", key=f"citation_{i}_{gid}"):
                open_dossier(gid)
        if message.get("tools"):
            st.caption("Evidence tools: " + ", ".join(message["tools"]))
question = st.chat_input("Ask about clients, routes or clusters")
if not chat:
    examples = [
        store.demo_question(),
        "Who are the top distributors?",
        "Кого проверить первым и почему?",
    ]
    for i, example in enumerate(filter(None, examples)):
        if st.button(example, key=f"example_{i}"):
            question = example
if question:
    history = [(m["role"], m["text"]) for m in chat][-10:]
    chat.append({"role": "user", "text": question})
    with st.spinner("Checking the case evidence…"):
        try:
            from agent.graph import ask

            response = ask(
                get_agent((OUT / "features.parquet").stat().st_mtime_ns, store), question, history
            )
            chat.append(
                {
                    "role": "assistant",
                    "text": response["answer"],
                    "gids": response["gids"],
                    "tools": response["tools"],
                }
            )
        except Exception:
            chat.append(
                {
                    "role": "assistant",
                    "text": "The assistant could not complete this request. Check the model connection and try again, or use Investigate to inspect the evidence locally.",
                }
            )
    st.rerun()
if chat and st.button("Clear conversation"):
    st.session_state.chat = []
    st.rerun()
