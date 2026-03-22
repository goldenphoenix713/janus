from .registry import ADAPTER_REGISTRY
from .tachyon_rs import TachyonEngine, TrackedDict, TrackedList


def timeline(cls):
    """Class decorator configuring the state engine mode to linear."""

    """Define and attach the methods for the engine to the class."""
    orig_init = cls.__init__
    orig_setattr = cls.__setattr__

    def __init__(self, *args, **kwargs):
        object.__setattr__(self, "_engine", TachyonEngine(self, "linear"))
        object.__setattr__(self, "_restoring", False)
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

    cls.__init__ = __init__
    cls.__setattr__ = __setattr__
    cls.create_moment_label = create_moment_label
    cls.jump_to = jump_to
    cls.get_labeled_moments = get_labeled_moments
    cls.undo = undo
    cls.redo = redo
    return cls


def multiverse(cls):
    """Class decorator configuring the state engine mode."""

    orig_init = cls.__init__
    orig_setattr = cls.__setattr__

    def __init__(self, *args, **kwargs):
        object.__setattr__(self, "_engine", TachyonEngine(self, "multiversal"))
        object.__setattr__(self, "_restoring", False)
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
        self._engine.create_branch(label)

    def create_moment_label(self, label: str):
        """Alias for branch() to stay compatible with brainstorming terminology."""
        self._engine.label_node(label)

    def jump_to(self, label: str):
        self._engine.move_to(label)

    def extract_timeline(self, label: str):
        return self._engine.extract_timeline(label)

    def get_labeled_moments(self):
        """List all available moment labels."""
        return self._engine.list_nodes()

    def undo(self):
        """Undo the last operation."""
        self._engine.undo()

    def redo(self):
        """Redo the last operation."""
        self._engine.redo()

    cls.__init__ = __init__
    cls.__setattr__ = __setattr__
    cls.branch = branch
    cls.create_moment_label = create_moment_label
    cls.jump_to = jump_to
    cls.extract_timeline = extract_timeline
    return cls
