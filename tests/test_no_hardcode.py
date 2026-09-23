import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "moneygraph"


def test_no_gid_literals_in_pipeline():
    hits = []
    for p in SRC.rglob("*.py"):
        for i, line in enumerate(p.read_text().splitlines(), 1):
            if re.search(r"\b\d{15,}\b", line):
                hits.append(f"{p.name}:{i}")
    assert not hits, f"gid-like literals found: {hits}"
