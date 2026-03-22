from .registry import ADAPTER_REGISTRY
from .tachyon_rs import TachyonEngine, TrackedDict, TrackedList


def timeline():
    """Class decorator configuring the state engine mode to linear."""

    def decorator(cls):
        """Define and attach the methods for the engine to the class."""
        orig_init = cls.__init__
        orig_setattr = cls.__setattr__

        def __init__(self, *args, **kwargs):
            object.__setattr__(self, "_engine", TachyonEngine(self, "linear"))
            orig_init(self, *args, **kwargs)

        def __setattr__(self, name, value):
            if name == "_engine" or name == "_restoring":
                return object.__setattr__(self, name, value)

            # Check if we are currently in a state restoration triggered by the engine
            if getattr(self, "_restoring", False):
                return orig_setattr(self, name, value)

            # Capture old value for delta calculation
            old_value = getattr(self, name, None)

            # Plugin Check Foundation
            value_type = type(value)
            if value_type in ADAPTER_REGISTRY:
                adapter = ADAPTER_REGISTRY[value_type]
                delta_blob = adapter.get_delta(old_value, value)
                self._engine.log_plugin_op(name, type(adapter).__name__, delta_blob)
            elif isinstance(value, list):
                # TrackedList will handle its own internal mutations,
                # but initial assignment is logged as an attribute update.
                value = TrackedList(value, self._engine, name)
            elif isinstance(value, dict):
                # TrackedDict handles internal mutations
                value = TrackedDict(value, self._engine, name)

            # Log standard attribute update to Rust engine
            if not name.startswith("_"):
                self._engine.log_update_attr(name, old_value, value)

            orig_setattr(self, name, value)

        def snapshot(self, label: str):
            """Create a snapshot of the current state with a given label."""
            # TODO Ensure the labels are unique
            # TODO Maybe a different name than "snapshot"? Something more "timey"?
            self._engine.create_branch(label)

        def restore(self, label: str):
            """Restore the state to a different snapshot."""
            self._engine.switch_branch(label)

        def jump_to(self, label: str):
            """Alias for restore()."""
            self.restore(label)

        def list_snapshots(self):
            """List all available snapshots."""
            # TODO: Write this function in the rust code.
            return self._engine.list_snapshots()

        cls.__init__ = __init__
        cls.__setattr__ = __setattr__
        cls.snapshot = snapshot
        cls.restore = restore
        cls.jump_to = jump_to
        cls.list_snapshots = list_snapshots
        return cls

    return decorator


def janus(mode="multiversal"):
    """Class decorator configuring the state engine mode."""

    def decorator(cls):
        orig_init = cls.__init__
        orig_setattr = cls.__setattr__

        def __init__(self, *args, **kwargs):
            object.__setattr__(self, "_engine", TachyonEngine(self, mode))
            orig_init(self, *args, **kwargs)

        def __setattr__(self, name, value):
            if name == "_engine" or name == "_restoring":
                return object.__setattr__(self, name, value)

            # Check if we are currently in a state restoration triggered by the engine
            if getattr(self, "_restoring", False):
                return orig_setattr(self, name, value)

            # Capture old value for delta calculation
            old_value = getattr(self, name, None)

            # Plugin Check Foundation
            value_type = type(value)
            if value_type in ADAPTER_REGISTRY:
                adapter = ADAPTER_REGISTRY[value_type]
                delta_blob = adapter.get_delta(old_value, value)
                self._engine.log_plugin_op(name, type(adapter).__name__, delta_blob)
            elif isinstance(value, list):
                # TrackedList will handle its own internal mutations,
                # but initial assignment is logged as an attribute update.
                value = TrackedList(value, self._engine, name)
            elif isinstance(value, dict):
                # TrackedDict handles internal mutations
                value = TrackedDict(value, self._engine, name)

            # Log standard attribute update to Rust engine
            if not name.startswith("_"):
                self._engine.log_update_attr(name, old_value, value)

            orig_setattr(self, name, value)

        def branch(self, label: str):
            if mode == "linear":
                raise ValueError("Branching is disabled in linear mode.")
            self._engine.create_branch(label)

        def snapshot(self, label: str):
            """Alias for branch() to stay compatible with brainstorming terminology."""
            self.branch(label)

        def switch(self, label: str):
            self._engine.switch_branch(label)

        def extract_timeline(self, label: str):
            return self._engine.extract_timeline(label)

        cls.__init__ = __init__
        cls.__setattr__ = __setattr__
        cls.branch = branch
        cls.snapshot = snapshot
        cls.switch = switch
        cls.extract_timeline = extract_timeline
        return cls

    return decorator
