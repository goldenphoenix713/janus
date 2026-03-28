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

            if PANDAS_INSTALLED:
                if isinstance(value, pd.DataFrame):
                    tracked = TrackedDataFrame(value)
                    tracked._janus_engine = self._engine
                    tracked._janus_name = name
                    value = tracked
                elif isinstance(value, pd.Series):
                    tracked = TrackedSeries(value)
                    tracked._janus_engine = self._engine
                    tracked._janus_name = name
                    value = tracked

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

    def extract_timeline(self, label: str) -> list[dict[str, Any]]:
        return self._engine.extract_timeline(label)

    def delete_branch(self, label: str) -> None:
        self._engine.delete_branch(label)
