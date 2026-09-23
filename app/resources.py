"""Cached graph data and optional assistant resources."""

import json
from importlib.util import find_spec
from pathlib import Path

import pandas as pd
import streamlit as st

from agent.store import GraphStore
from moneygraph.paths import DATA_DIR, OUTPUT_DIR

FEATURES_PATH = OUTPUT_DIR / "features.parquet"


@st.cache_resource
def get_store(mtime):
    return GraphStore.load(OUTPUT_DIR, DATA_DIR)


def assistant_enabled():
    try:
        if any(
            find_spec(name) is None for name in ("langgraph", "langchain_core", "langchain_openai")
        ):
            return False
        from agent.config import enabled

        return enabled()
    except ImportError:
        return False


@st.cache_resource
def get_agent(mtime, _store):
    from agent.graph import build

    return build(_store)


@st.cache_data(show_spinner=False)
def _read_json(path: str, modified: int) -> dict:
    return json.loads(Path(path).read_text())


@st.cache_data(show_spinner=False)
def _read_csv(path: str, modified: int) -> pd.DataFrame:
    return pd.read_csv(path)


def exported_json(name: str) -> dict:
    path = OUTPUT_DIR / name
    return _read_json(str(path), path.stat().st_mtime_ns) if path.exists() else {}


def exported_csv(name: str) -> pd.DataFrame:
    path = OUTPUT_DIR / name
    return _read_csv(str(path), path.stat().st_mtime_ns) if path.exists() else pd.DataFrame()
