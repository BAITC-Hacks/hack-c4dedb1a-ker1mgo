"""Client identifiers shared by graph queries, citations, and evaluation."""

import re

_GID_PATTERN = re.compile(r"(?<!\d)\d{15,20}(?!\d)")


def to_gid(value):
    return int(str(value).strip())


def ordered_gids(text):
    """Return normalized client IDs in order of first citation."""
    return list(dict.fromkeys(str(to_gid(match)) for match in _GID_PATTERN.findall(text or "")))


def cited_gids(text):
    return {to_gid(gid) for gid in ordered_gids(text)}
