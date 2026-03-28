from __future__ import annotations

import contextlib
from typing import Any

from .containers import wrap_value
from .registry import ADAPTER_REGISTRY
from .tachyon_rs import TachyonEngine

try:
    import pandas as pd

    from .plugins.pandas import TrackedDataFrame, TrackedSeries

    PANDAS_INSTALLED = True
except ImportError:
    PANDAS_INSTALLED = False

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

if NUMPY_AVAILABLE:
    from .plugins.numpy import TrackedNumpyArray


class JanusBase:
    def __init__(self, mode: str) -> None:
        self._engine = TachyonEngine(self, mode)
        self._restoring = False

    def _resolve_path(self, path: str) -> Any:
        """Resolve a nested path like 'data[0].key' and return the object."""
        import re

        parts = re.split(r"(\[.*?\]|\.)", path)
        curr: Any = self
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

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ["_engine", "_restoring"]:
            super().__setattr__(name, value)
            return

        # Check if we are currently in a state restoration
        if self._restoring:
            super().__setattr__(name, value)
            return

        # Capture old value for delta calculation
        old_value = getattr(self, name, None)

        # Plugin Check Foundation
        value_type = type(value)
        if value_type in ADAPTER_REGISTRY:
            adapter = ADAPTER_REGISTRY[value_type]
            shadow_name = f"_shadow_{name}"
            shadow_value = getattr(self, shadow_name, None)
            delta_blob = adapter.get_delta(shadow_value, value)
            self._engine.log_plugin_op(name, type(adapter).__name__, delta_blob)
            super().__setattr__(shadow_name, adapter.get_snapshot(value))
        else:
            # Recursive Container Wrapping
            value = wrap_value(value, self._engine, name)

            if PANDAS_INSTALLED and isinstance(value, pd.DataFrame):
                value = TrackedDataFrame(value)
                value._janus_engine = self._engine
                value._janus_name = name
            elif PANDAS_INSTALLED and isinstance(value, pd.Series):
                value = TrackedSeries(value)
                value._janus_engine = self._engine
                value._janus_name = name
            elif NUMPY_AVAILABLE and isinstance(value, np.ndarray):
                if not isinstance(value, TrackedNumpyArray):
                    value = TrackedNumpyArray(value)

                # Ensure engine is set on the root of the array chain
                root = getattr(value, "_janus_parent", value)
                if root is None:  # Should not happen with new logic, but for safety
                    root = value

                root._janus_engine = self._engine
                root._janus_name = name

                # Also ensure the current view has the engine reference
                value._janus_engine = self._engine
                value._janus_name = name

        # Log standard attribute update to Rust engine
        if not name.startswith("_"):
            self._engine.log_update_attr(name, old_value, value)

        super().__setattr__(name, value)

    def create_moment_label(self, label: str) -> None:
        """Label the current moment for future restoration."""
        self._engine.label_node(label)

    def jump_to(self, label: str) -> None:
        """Restore the state to a different moment."""
        self._engine.move_to(label)

    def get_labeled_moments(self) -> list[str]:
        """List all available moment labels."""
        return self._engine.list_nodes()

    def undo(self) -> None:
        """Undo the last operation."""
        self._restoring = True
        try:
            self._engine.undo()
        finally:
            self._restoring = False

    def redo(self) -> None:
        """Redo the last operation."""
        self._engine.redo()

    def tag_moment(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            self._engine.set_metadata(key, value)

    def get_all_tag_keys(self, label: str | None = None) -> tuple[str, ...]:
        node_id = self._resolve_label_to_id(label) if label else None
        return tuple(self._engine.get_metadata_keys(node_id))

    def get_all_tag_values(self, label: str | None = None) -> tuple[Any, ...]:
        node_id = self._resolve_label_to_id(label) if label else None
        return tuple(self._engine.get_metadata_values(node_id))

    def get_all_tags(self, label: str | None = None) -> dict[str, Any]:
        node_id = self._resolve_label_to_id(label) if label else None
        return dict(self._engine.get_metadata_items(node_id))

    def get_moment_tag(self, key: str, label: str | None = None) -> Any:
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


class TimelineBase(JanusBase):
    def __init__(self) -> None:
        super().__init__("linear")


class MultiverseBase(JanusBase):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__("multiversal")

    @property
    def current_branch(self) -> str:
        return self._engine.current_branch

    def branch(self, label: str) -> None:
        self._engine.create_branch(label)

    def create_branch(self, label: str) -> None:
        """Alias for branch() for API convenience."""
        self.branch(label)

    def switch_branch(self, label: str) -> None:
        """Alias for jump_to() for API convenience."""
        self.jump_to(label)

    def list_branches(self) -> list[str]:
        return self._engine.list_branches()

    def list_nodes(self) -> list[str]:
        return self._engine.list_nodes()

    def create_moment_label(self, label: str) -> None:
        """Alias for branch() to stay compatible with brainstorming terminology."""
        self._engine.label_node(label)

    def merge(self, label: str, strategy: str = "overshadow") -> None:
        """
        Merge changes from another branch into the current one.
        Supported strategies:
        - "overshadow": (Default) Source branch changes overwrite target
          changes on conflict.
        - "preserve": Target branch changes are kept on conflict.
        - "strict": Raise an error if any conflicts are detected.
        """
        self._engine.merge_branch(label, strategy)

    def extract_timeline(
        self, label: str | None = None, filter_attr: list[str] | str | None = None
    ) -> list[dict[str, Any]]:
        """
        Extract the history of operations from root to a specific node or label.
        If filter_attr is provided (string or list of strings), only operations
        affecting those attributes are returned.
        """
        if isinstance(filter_attr, str):
            filter_attr = [filter_attr]
        return self._engine.extract_timeline(label, filter_attr)

    def find_moments(self, **criteria: Any) -> list[str | int]:
        """
        Search the entire multiverse for nodes matching the given metadata criteria.
        Returns a list of labels (if the node is labeled) or node IDs.
        """
        # For now, we search for the first criterion to narrow down
        if not criteria:
            return []

        # Get all node IDs matching all criteria
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

        # Resolve IDs to labels where possible
        results: list[str | int] = []
        # Check if any matching node is a branch head
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

    def squash(self, label: str | None = None) -> None:
        """
        Collapse a sequence of state nodes into a single composite node.
        Optimizes memory and simplifies the timeline.
        """
        self._engine.squash_branch(label)

    def flatten(self, label: str | None = None) -> None:
        """Alias for squash()."""
        self.squash(label)

    def delete_branch(self, label: str) -> None:
        self._engine.delete_branch(label)

    def plot(self, backend: str | None = None, **kwargs: Any) -> Any:
        """
        Visualize the multiverse DAG using a specialized backend.
        Default backend can be configured via `janus.options.plotting.backend`.
        """
        from .options import options
        from .viz import get_backend

        backend_name = backend or options.plotting.backend
        engine = get_backend(backend_name)
        return engine.plot(self, **kwargs)

    def visualize(self) -> Any:
        """
        Compatibility shortcut for Mermaid-based visualization.
        """
        return self.plot(backend="mermaid")
