import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from agent import config
from agent.identifiers import cited_gids, ordered_gids
from moneygraph.paths import PROJECT_ROOT


def test_citations_keep_full_ids_and_first_appearance_order():
    first = "100000000000000555"
    second = "200000000000000999"
    text = f"{second}, {first}, {second}, 000000000000000020; 1234; {first}999"

    assert ordered_gids(text) == [second, first, "20"]
    assert cited_gids(text) == {int(first), int(second), 20}
    assert ordered_gids(None) == []


def test_offline_modules_do_not_require_assistant_dependencies(tmp_path):
    script = """
import importlib.abc
import sys

class BlockAssistantImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {
            'dotenv', 'langchain', 'langchain_core', 'langchain_openai', 'langgraph', 'langfuse'
        }:
            raise ImportError(f'Optional dependency imported: {fullname}')

sys.meta_path.insert(0, BlockAssistantImports())
from agent import cards, config, eval, identifiers, store
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_environment_file_is_resolved_from_project_root(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("OPENAI_API_KEY=test-key\n", encoding="utf-8")
    other_directory = tmp_path / "elsewhere"
    other_directory.mkdir()
    monkeypatch.chdir(other_directory)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(config, "_env_loaded", False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert config.enabled()
    assert os.environ["OPENAI_API_KEY"] == "test-key"


@pytest.mark.parametrize(
    ("requested", "environment_model", "expected"),
    [
        (None, "", config.DEFAULT_MODEL),
        (None, "configured", "configured"),
        ("explicit", "configured", "explicit"),
    ],
)
def test_model_configuration_precedence(
    monkeypatch, tmp_path, requested, environment_model, expected
):
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(config, "_env_loaded", False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", environment_model)
    monkeypatch.setenv("OPENAI_BASE_URL", " ")
    monkeypatch.setitem(
        sys.modules, "langchain_openai", SimpleNamespace(ChatOpenAI=lambda **kwargs: kwargs)
    )

    assert config.create_llm(requested) == {"model": expected, "temperature": 0, "base_url": None}
