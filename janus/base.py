from .registry import ADAPTER_REGISTRY
from .tachyon_rs import TachyonEngine, TrackedDict, TrackedList

try:
    import pandas as pd

    from .plugins.pandas import TrackedDataFrame, TrackedSeries

    PANDAS_INSTALLED = True
except ImportError:
    PANDAS_INSTALLED = False


class JanusBase:
    def __init__(self, mode: str):
        self._engine = TachyonEngine(self, mode)
        self._restoring = False

    def __setattr__(self, name, value):
        if name in ["_engine", "_restoring"]:
            return super().__setattr__(name, value)

        # Check if we are currently in a state restoration triggered by the engine
        if self._restoring:
            return super().__setattr__(name, value)

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
        elif isinstance(value, list):
            # TrackedList will handle its own internal mutations,
            # but initial assignment is logged as an attribute update.
            value = TrackedList(value, self._engine, name)
        elif isinstance(value, dict):
            # TrackedDict handles internal mutations
            value = TrackedDict(value, self._engine, name)

        elif PANDAS_INSTALLED:
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

    def create_moment_label(self, label: str):
        """Label the current moment for future restoration."""
        self._engine.label_node(label)

    def jump_to(self, label: str):
        """Restore the state to a different moment."""
        self._engine.move_to(label)

    def get_labeled_moments(self):
        """List all available moment labels."""
        return self._engine.list_nodes()

    def undo(self):
        """Undo the last operation."""
        self._engine.undo()

    def redo(self):
        """Redo the last operation."""
        self._engine.redo()


class TimelineBase(JanusBase):
    def __init__(self):
        super().__init__("linear")


class MultiverseBase(JanusBase):
    def __init__(self, *args, **kwargs):
        super().__init__("multiversal")

    @property
    def current_branch(self):
        return self._engine.current_branch

    def branch(self, label: str):
        self._engine.create_branch(label)

    def create_branch(self, label: str):
        """Alias for branch() for API convenience."""
        self.branch(label)

    def switch_branch(self, label: str):
        """Alias for jump_to() for API convenience."""
        self.jump_to(label)

    def list_branches(self):
        return self._engine.list_branches()

    def list_nodes(self):
        return self._engine.list_nodes()

    def create_moment_label(self, label: str):
        """Alias for branch() to stay compatible with brainstorming terminology."""
        self._engine.label_node(label)

    def extract_timeline(self, label: str):
        return self._engine.extract_timeline(label)

    def delete_branch(self, label: str):
        self._engine.delete_branch(label)
