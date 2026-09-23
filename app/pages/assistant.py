import streamlit as st

from app.ui import OUT, assistant_enabled, get_agent, get_store, open_dossier, page_header

store = get_store()
page_header(
    "Ассистент по материалам дела",
    "Задайте вопрос на русском или английском. Каждый ID в ответе проверяется по графу.",
)
if not assistant_enabled():
    st.info(
        "Ассистент не подключён: проверьте зависимости ассистента и ключ API. Исследование графа, досье и все остальные разделы работают без него."
    )
    st.markdown("**Когда подключение появится, можно спросить:**")
    st.write(
        "Кто получает деньги от этих клиентов? Каких распределителей проверить первыми? На чём основана гипотеза о кластере?"
    )
    st.page_link("pages/investigate.py", label="Перейти к исследованию", icon=":material/hub:")
    with st.expander("Как подключить ассистента"):
        st.write(
            "Укажите `OPENAI_API_KEY` в `.env` и перезапустите приложение. При необходимости настройте `OPENAI_MODEL` и `OPENAI_BASE_URL`."
        )
    st.stop()


chat = st.session_state.setdefault("chat", [])
for i, message in enumerate(chat):
    with st.chat_message(message["role"]):
        st.markdown(message["text"])
        for gid in message.get("gids", []):
            if st.button(f"Досье {gid}", key=f"citation_{i}_{gid}"):
                open_dossier(gid)
        if message.get("tools"):
            st.caption("Источники ответа: " + ", ".join(message["tools"]))
question = st.chat_input("Спросите о клиентах, переводах или кластерах")
if not chat:
    examples = [
        store.demo_question(),
        "Каких распределителей проверить первыми?",
        "Кого проверить первым и почему?",
    ]
    for i, example in enumerate(filter(None, examples)):
        if st.button(example, key=f"example_{i}"):
            question = example
if question:
    history = [(m["role"], m["text"]) for m in chat][-10:]
    chat.append({"role": "user", "text": question})
    with st.spinner("Проверяем материалы…"):
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
                    "text": "Не удалось получить ответ. Проверьте подключение и повторите запрос или откройте раздел «Исследование».",
                }
            )
    st.rerun()
if chat and st.button("Очистить переписку"):
    st.session_state.chat = []
    st.rerun()
