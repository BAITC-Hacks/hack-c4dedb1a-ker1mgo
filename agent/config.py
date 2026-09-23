"""Optional assistant configuration and chat model construction."""

import os

from moneygraph.paths import PROJECT_ROOT

DEFAULT_MODEL = "gpt-4.1-mini"
_env_loaded = False


def load_env():
    global _env_loaded
    if _env_loaded:
        return

    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
    # Empty endpoint values would otherwise override the SDK defaults.
    for key, value in list(os.environ.items()):
        if key.startswith(("OPENAI_", "LANGFUSE_")) and not value.strip():
            os.environ.pop(key)
    _env_loaded = True


def enabled():
    load_env()
    return bool(os.environ.get("OPENAI_API_KEY"))


def create_llm(model=None):
    from langchain_openai import ChatOpenAI

    load_env()
    return ChatOpenAI(
        model=model or os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL,
        temperature=0,
        base_url=os.environ.get("OPENAI_BASE_URL") or None,
    )
