from __future__ import annotations

from typing import Any

import janus.registry as registry


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


def log_pre_mutation(obj: Any) -> None:
    """
    Generic pre-mutation hook for Janus plugins.

    Creates a shadow snapshot of the root object if an engine is found and
    the system is not currently in a restoration state.

    Args:
        obj: The object about to be mutated.
    """
    if getattr(obj, "_restoring", False):
        return

    engine = get_engine(obj)
    if engine is None or getattr(engine.owner, "_restoring", False):
        return

    parent = getattr(obj, "_janus_parent", None)
    root = parent if parent is not None else obj
    if hasattr(root, "_janus_snapshot"):
        return

    adapter = registry.ADAPTER_REGISTRY.get(root.__class__)
    if adapter:
        snapshot = adapter.get_snapshot(root)
        object.__setattr__(root, "_janus_snapshot", snapshot)
        object.__setattr__(root, "_janus_initiator", id(obj))


def log_post_mutation(obj: Any, adapter_name: str | None = None) -> None:
    """
    Generic post-mutation hook for Janus plugins.

    Calculates the delta between the current state and the shadow snapshot,
    then logs the operation to the Janus engine.

    Args:
        obj: The object that was mutated.
        adapter_name: Optional override for the adapter name. If None, it
            defaults to the object's `_janus_adapter_name` or the adapter's
            class name.
    """
    if getattr(obj, "_restoring", False):
        return

    engine = get_engine(obj)
    if engine is None or getattr(engine.owner, "_restoring", False):
        return

    parent = getattr(obj, "_janus_parent", None)
    root = parent if parent is not None else obj
    if not hasattr(root, "_janus_snapshot"):
        return

    # Ensure only the initiator who created the snapshot finalizes the log
    if getattr(root, "_janus_initiator", None) != id(obj):
        return

    adapter = registry.ADAPTER_REGISTRY.get(root.__class__)
    if adapter:
        snapshot = getattr(root, "_janus_snapshot")
        delta = adapter.get_delta(snapshot, root)

        if adapter_name is None:
            # Fallback to the object's specified adapter name or class name
            adapter_name = getattr(root, "_janus_adapter_name", type(adapter).__name__)

        engine.log_plugin_op(
            getattr(root, "_janus_name", "unknown"),
            adapter_name,
            delta,
        )

        delattr(root, "_janus_snapshot")
        delattr(root, "_janus_initiator")
