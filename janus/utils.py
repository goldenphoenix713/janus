from __future__ import annotations

import contextlib
import re
from typing import Any


def get_engine(obj: Any) -> Any | None:
    """
    Find the Janus engine by traversing the view/proxy hierarchy.

    Args:
        obj: The tracked object (or a view of one).

    Returns:
        The TachyonEngine if found, otherwise None.
    """
    curr = obj
    while curr is not None:
        engine = getattr(curr, "_janus_engine", None)
        if engine is not None:
            return engine
        curr = getattr(curr, "_janus_parent", None)
    return None


def resolve_path(owner: Any, path: str) -> Any:
    """
    Resolve a nested path like 'data[0].key' relative to an owner object.

    Args:
        owner: The object to start resolution from (usually a JanusBase instance).
        path: The dot-separated and bracketed path string.

    Returns:
        The object reached by the path.
    """
    parts = re.split(r"(\[.*?\]|\.)", path)
    curr: Any = owner
    for part in parts:
        if not part or part == ".":
            continue
        if part.startswith("["):
            idx: Any = part[1:-1]
            with contextlib.suppress(ValueError):
                idx = int(idx)
            curr = curr[idx]
        else:
            curr = getattr(curr, part)
    return curr
