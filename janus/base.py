from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

from janus.logger import logger
from janus.options import options
from janus.persistence import JanusPersistence
from janus.registry import ADAPTER_REGISTRY, wrap_value
from janus.tachyon_rs import TachyonEngine
from janus.utils import resolve_path
from janus.viz import get_backend

try:
    import pandas as pd

    PANDAS_INSTALLED = True
except ImportError:
    PANDAS_INSTALLED = False

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


class JanusBase:
    """
    Base class for Janus state tracking, providing history, undo/redo, and persistence.

    JanusBase intercepts attribute assignments and container mutations to build a
    directed acyclic graph (DAG) of state transitions. This enables features like
    multiverse branching, state restoration, and timeline squashing.
    """

    def __init__(self, mode: str, max_history: int = 50000) -> None:
        """
        Initialize a new Janus tracking instance.

        Args:
            mode: The tracking mode ("linear" or "multiversal").
            max_history: Max number of state nodes in the engine.
        """
        self._engine = TachyonEngine(self, mode, max_history)
        self._restoring = False
        self._adapters = {type(a).__name__: a for a in ADAPTER_REGISTRY.values()}

    def _resolve_path(self, path: str) -> Any:
        """Resolve a nested path like 'data[0].key' and return the object."""
        return resolve_path(self, path)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ["_engine", "_restoring"]:
            super().__setattr__(name, value)
            return

        if getattr(self, "_restoring", False):
            super().__setattr__(name, value)
            return

        # Capture old value for delta calculation
        old_value = getattr(self, name, None)

        # 1. Handle Plugin/Container Wrapping & Special Assignment Logging
        value, logged_plugin = self._handle_assignment(name, value)

        # 2. Log Standard Attribute Update
        if not logged_plugin:
            self._log_attr_update(name, old_value, value)

        super().__setattr__(name, value)

    def _handle_assignment(self, name: str, value: Any) -> tuple[Any, bool]:
        """Handle plugin-specific assignment logic and container wrapping."""
        # If the value is a type directly registered for an adapter
        value_type = type(value)
        if value_type in ADAPTER_REGISTRY:
            adapter = ADAPTER_REGISTRY[value_type]
            shadow_name = f"_shadow_{name}"
            shadow_value = getattr(self, shadow_name, None)
            delta_blob = adapter.get_delta(shadow_value, value)
            if not self._restoring:
                self._engine.log_plugin_op(name, type(adapter).__name__, delta_blob)
                logger.trace(f"Logged plugin op: {name} via {type(adapter).__name__}")
            super().__setattr__(shadow_name, adapter.get_snapshot(value))
            return value, True

        # Otherwise, use the generic wrap_value
        return wrap_value(value, self._engine, name, owner=self), False

    def _log_attr_update(self, name: str, old_value: Any, new_value: Any) -> None:
        """Log a standard attribute change to the engine."""
        if name.startswith("_"):
            return

        if self._is_value_different(old_value, new_value):
            # Handle snapshotting to prevent DAG history poisoning
            snap_val = self._snapshot_for_history(new_value)
            self._engine.log_update_attr(name, old_value, snap_val)
            logger.trace(f"Logged attribute update: {name}")

    def _is_value_different(self, old: Any, new: Any) -> bool:
        """Compare two values safely, avoiding truth-value ambiguity for arrays."""
        if (
            (PANDAS_INSTALLED and isinstance(new, (pd.DataFrame, pd.Series)))
            or (NUMPY_AVAILABLE and isinstance(new, np.ndarray))
            or (PANDAS_INSTALLED and isinstance(old, (pd.DataFrame, pd.Series)))
            or (NUMPY_AVAILABLE and isinstance(old, np.ndarray))
        ):
            return bool(new is not old)
        try:
            return bool(old != new)
        except Exception:
            return True

    def _snapshot_for_history(self, value: Any) -> Any:
        """Create a deep, untracked copy of a value for storage in history."""
        if isinstance(value, (list, dict)):
            # Helper to recursively unwrap TrackedList/TrackedDict
            def _unwrap(obj: Any) -> Any:
                if isinstance(obj, list):
                    return [_unwrap(x) for x in obj]
                if isinstance(obj, dict):
                    return {k: _unwrap(v) for k, v in obj.items()}
                return obj

            return copy.deepcopy(_unwrap(value))

        if PANDAS_INSTALLED and isinstance(value, (pd.DataFrame, pd.Series)):
            return value.copy()

        if NUMPY_AVAILABLE and isinstance(value, np.ndarray):
            return value.copy()

        return value

    def create_moment_label(self, label: str) -> None:
        """Assign a human-readable label to the current state node."""
        self._engine.label_node(label)

    def jump_to(self, label: str) -> None:
        """Restore the application state to a previously labeled moment."""
        self._engine.move_to(label)

    def get_labeled_moments(self) -> list[str]:
        """Retrieve a list of all labels assigned in the current history."""
        return self._engine.list_nodes()

    def undo(self) -> None:
        """Revert the state to the previous node in the current timeline."""
        self._restoring = True
        try:
            self._engine.undo()
        finally:
            self._restoring = False

    def redo(self) -> None:
        """Advance the state to the next node in the current timeline."""
        self._engine.redo()

    def apply_plugin_op(
        self, path: str, adapter_name: str, delta: Any, forward: bool
    ) -> None:
        """
        Called by the engine to apply a plugin operation to a specific object.

        Args:
            path: The relative path to the object within this Janus instance.
            adapter_name: The name of the adapter to use.
            delta: The delta blob to apply.
            forward: True if applying forward, False for backward (undo).
        """
        target = self._resolve_path(path)
        adapter = self._adapters.get(adapter_name)
        if adapter:
            logger.debug(
                f"Applying plugin op: path='{path}', "
                f"adapter='{adapter_name}', forward={forward}"
            )
            if forward:
                adapter.apply_forward(target, delta)
            else:
                adapter.apply_backward(target, delta)

    def tag_moment(self, **kwargs: Any) -> None:
        """Attach arbitrary metadata tags to the current state node."""
        for key, value in kwargs.items():
            self._engine.set_metadata(key, value)

    def get_all_tag_keys(self, label: str | None = None) -> tuple[str, ...]:
        """Get all metadata keys associated with a specific moment."""
        node_id = self._resolve_label_to_id(label) if label else None
        return tuple(self._engine.get_metadata_keys(node_id))

    def get_all_tag_values(self, label: str | None = None) -> tuple[Any, ...]:
        """Get all metadata values associated with a specific moment."""
        node_id = self._resolve_label_to_id(label) if label else None
        return tuple(self._engine.get_metadata_values(node_id))

    def get_all_tags(self, label: str | None = None) -> dict[str, Any]:
        """Get all metadata key-value pairs associated with a specific moment."""
        node_id = self._resolve_label_to_id(label) if label else None
        return dict(self._engine.get_metadata_items(node_id))

    def get_moment_tag(self, key: str, label: str | None = None) -> Any:
        """Retrieve a specific metadata value by key from a moment."""
        node_id = self._resolve_label_to_id(label) if label else None
        return self._engine.get_metadata(key, node_id)

    def label_node(self, label: str) -> None:
        """Assign a human-readable label to the current state node."""
        self._engine.label_node(label)

    def _resolve_label_to_id(self, label: str) -> int:
        node_id = self._engine.get_node_id(label)
        if node_id is None:
            raise KeyError(f"Label '{label}' not found in timeline or multiverse")
        return node_id

    def squash(
        self, start_label: str | None = None, end_label: str | None = None
    ) -> None:
        """Collapse state nodes into a single node."""
        if end_label is not None:
            if start_label is None:
                raise ValueError("start_label required for range squash")
            self._engine.squash(start_label, end_label)
        else:
            self._engine.squash_branch(start_label)

    def flatten(self, label: str | None = None) -> None:
        """Alias for squash()."""
        self.squash(label)

    def diff(self, start_label: str, end_label: str) -> dict[str, Any]:
        """Compare the state between two moments (labels)."""
        return self._engine.get_diff(start_label, end_label)

    def save(self, path: str | Path) -> None:
        """Persist the entire multiverse/timeline history to a .jns file."""
        JanusPersistence.save(self, path)

    def load(self, path: str | Path) -> None:
        """Restore history and state from a .jns file."""
        JanusPersistence.load(self, path)

    def plot(self, backend: str | None = None, **kwargs: Any) -> Any:
        """Visualize the multiverse DAG using a specialized backend."""
        backend_name = backend or options.plotting.backend
        engine = get_backend(backend_name)
        return engine.plot(self, **kwargs)

    def visualize(self) -> Any:
        """Compatibility shortcut for Mermaid-based visualization."""
        return self.plot(backend="mermaid")


class TimelineBase(JanusBase):
    """A linear state tracking implementation."""

    def __init__(self, max_history: int = 50000) -> None:
        super().__init__("linear", max_history=max_history)


class MultiverseBase(JanusBase):
    """A multiversal state tracking implementation supporting branching and merging."""

    def __init__(self, max_history: int = 50000) -> None:
        super().__init__("multiversal", max_history=max_history)

    @property
    def current_branch(self) -> str:
        """The name of the currently active branch."""
        return self._engine.current_branch

    def branch(self, label: str) -> None:
        """Create a new branch from the current state."""
        self._engine.create_branch(label)

    def create_branch(self, label: str) -> None:
        """Alias for `branch()` for API convenience."""
        self.branch(label)

    def switch_branch(self, label: str) -> None:
        """Alias for `jump_to()` for API convenience."""
        self.jump_to(label)

    def list_branches(self) -> list[str]:
        """List all existing branch names."""
        return self._engine.list_branches()

    def list_nodes(self) -> list[str]:
        return self._engine.list_nodes()

    def create_moment_label(self, label: str) -> None:
        """Alias for branch() to stay compatible with brainstorming terminology."""
        self._engine.label_node(label)

    def merge(
        self, label: str, strategy: str | Callable[..., Any] = "overshadow"
    ) -> None:
        """Merge changes from another branch into the current one."""
        self._engine.merge_branch(label, strategy)

    def extract_timeline(
        self, label: str | None = None, filter_attr: list[str] | str | None = None
    ) -> list[dict[str, Any]]:
        """Extract history of operations from root to a specific node or label."""
        if isinstance(filter_attr, str):
            filter_attr = [filter_attr]
        return self._engine.extract_timeline(label, filter_attr)

    def find_moments(self, **criteria: Any) -> list[str | int]:
        """Search the entire multiverse for nodes matching criteria."""
        if not criteria:
            return []

        all_matches: set[int] | None = None
        for key, value in criteria.items():
            matches = set(self._engine.find_nodes_by_metadata(key, value))
            if all_matches is None:
                all_matches = matches
            else:
                all_matches &= matches

            if not all_matches:
                break

        if not all_matches:
            return []

        results: list[str | int] = []
        branches = self._engine.list_branches()
        head_map = {}
        for b in branches:
            bid = self._engine.get_node_id(b)
            if bid is not None:
                head_map[bid] = b

        for node_id in sorted(all_matches):
            if node_id in head_map:
                results.append(head_map[node_id])
            else:
                results.append(node_id)

        return results

    def delete_branch(self, label: str) -> None:
        """Permanently delete a branch and its head reference."""
        self._engine.delete_branch(label)
