from __future__ import annotations

import contextlib
import zipfile
from pathlib import Path
from typing import Any

import msgpack

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


def janus_encoder(obj: Any) -> Any:
    """Custom encoder for Janus-tracked objects to ensure msgpack compatibility."""
    from janus.containers import TrackedDict, TrackedList

    if PANDAS_INSTALLED:
        from janus.plugins.pandas import TrackedDataFrame, TrackedSeries

        if isinstance(obj, (TrackedDataFrame, pd.DataFrame)):
            return {
                "__janus_type__": "pd.DataFrame",
                "data": obj.to_dict(orient="split"),
            }
        if isinstance(obj, (TrackedSeries, pd.Series)):
            return {
                "__janus_type__": "pd.Series",
                "data": obj.to_dict(),
                "name": obj.name,
            }

    if isinstance(obj, TrackedDict):
        return dict(obj)
    if isinstance(obj, TrackedList):
        return list(obj)

    # If it's something else we don't know, let msgpack try its best
    return obj


def janus_decoder(obj: Any) -> Any:
    """Custom decoder for Janus-tracked objects to re-hydrate during load."""
    if isinstance(obj, dict) and "__janus_type__" in obj:
        try:
            import pandas as pd

            if obj["__janus_type__"] == "pd.DataFrame":
                # pd.DataFrame.from_dict doesn't support 'split', but constructor does
                return pd.DataFrame(**obj["data"])
            if obj["__janus_type__"] == "pd.Series":
                return pd.Series(obj["data"], name=obj.get("name"))
        except ImportError:
            pass
    return obj


class JanusBase:
    def __init__(self, mode: str) -> None:
        self._engine = TachyonEngine(self, mode)
        self._restoring = False
        self._adapters = {type(a).__name__: a for a in ADAPTER_REGISTRY.values()}

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
        if getattr(self, "_restoring", False):
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
            if not self._restoring:
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
            # Avoid redundant logging when loading/sync_from_root
            # has already mapped identity
            try:
                # Use identity for numpy/pandas to avoid value error,
                # equality for others
                if (
                    PANDAS_INSTALLED
                    and isinstance(value, (pd.DataFrame, pd.Series))
                    or NUMPY_AVAILABLE
                    and isinstance(value, np.ndarray)
                ):
                    changed = value is not old_value
                else:
                    changed = old_value != value
            except Exception:
                changed = True

            if changed:
                # Handle snapshotting to prevent DAG history poisoning
                snap_val = value
                if isinstance(value, (list, dict)):

                    def _unwrap(obj: Any) -> Any:
                        if isinstance(obj, list):
                            return [_unwrap(x) for x in obj]
                        if isinstance(obj, dict):
                            return {k: _unwrap(v) for k, v in obj.items()}
                        return obj

                    import copy

                    snap_val = copy.deepcopy(_unwrap(value))

                self._engine.log_update_attr(name, old_value, snap_val)

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

    def squash(
        self, start_label: str | None = None, end_label: str | None = None
    ) -> None:
        """
        Collapse state nodes into a single node.

        Usage:
        - obj.squash(start, end): Collapses nodes between start and end.
        - obj.squash(label): Collapses the entire branch up to label.
        - obj.squash(): Collapses the current branch up to current node.
        """
        if end_label is not None:
            if start_label is None:
                raise ValueError("start_label required for range squash")
            self._engine.squash(start_label, end_label)
        else:
            # Re-use engine's branch-based squashing logic
            self._engine.squash_branch(start_label)

    def flatten(self, label: str | None = None) -> None:
        """Alias for squash()."""
        self.squash(label)

    def diff(self, start_label: str, end_label: str) -> dict[str, Any]:
        """
        Compare the state between two moments (labels).
        Returns a dictionary with 'attributes' and 'container_operations'.
        """
        return self._engine.get_diff(start_label, end_label)

    def save(self, path: str | Path) -> None:
        """
        Persist the entire multiverse/timeline history to a .jns file.
        Uses a ZIP container with MessagePack serialization.
        """
        path = Path(path)
        if path.suffix != ".jns":
            path = path.with_suffix(".jns")

        # 1. Get DAG from Rust
        dag_state = self._engine.get_graph_state()

        # 2. Extract Python context (shadow snapshots for plugins)
        context = {k: v for k, v in self.__dict__.items() if k.startswith("_shadow_")}

        # 3. Serialize.
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "dag.msgpack",
                msgpack.packb(dag_state, default=janus_encoder, use_bin_type=True),
            )
            zf.writestr(
                "context.msgpack",
                msgpack.packb(context, default=janus_encoder, use_bin_type=True),
            )

    def load(self, path: str | Path) -> None:
        """
        Restore history and state from a .jns file.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Persistence file not found: {path}")

        with zipfile.ZipFile(path, "r") as zf:
            dag_data = msgpack.unpackb(
                zf.read("dag.msgpack"),
                object_hook=janus_decoder,
                strict_map_key=False,
                raw=False,
            )
            ctx_data = msgpack.unpackb(
                zf.read("context.msgpack"),
                object_hook=janus_decoder,
                strict_map_key=False,
                raw=False,
            )

        # 1. Restore Rust engine state
        self._engine.set_graph_state(dag_data)

        self._restoring = True
        try:
            # 2. Re-hydrate Python context
            for k, v in ctx_data.items():
                setattr(self, k, v)

            # 3. Synchronize live objects with the loaded head node
            self._engine.sync_from_root()

            # 4. Re-link top-level attributes to ensure they are tracked
            for name, value in self.__dict__.items():
                if not name.startswith("_"):
                    # Re-trigger wrapping and engine linkage
                    setattr(self, name, value)
        finally:
            self._restoring = False


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
