# Janus Plugin Development Guide 🏺

Janus is designed to be extensible. While it has built-in support for native Python collections (lists and dictionaries), you can easily add tracking support for third-party libraries like NumPy, Pandas, PyTorch, or your own custom domain objects.

## The Plugin Architecture

Janus plugins consist of two main components:

1. **The Tracked Proxy**: A subclass or wrapper around the target object that intercepts in-place mutations.
2. **The Janus Adapter**: A class that implements the `JanusAdapter` protocol to manage state transitions for that object type.

## 1. Creating a Tracked Proxy

The proxy's job is to detect when a mutation is about to happen and when it has finished. For objects that support subclassing (like `numpy.ndarray` or `pd.DataFrame`), you can override `__setitem__` and other mutation methods.

### Example: Tracking a Custom Object

```python
from janus.plugins.utils import log_pre_mutation, log_post_mutation

class TrackedBox:
    def __init__(self, value):
        self.value = value
        self._janus_engine = None
        self._janus_name = None
        self._restoring = False
        self._janus_adapter_name = "BoxAdapter"

    def update(self, new_value):
        if self._restoring:
            self.value = new_value
            return

        # Notify the engine before and after mutation
        log_pre_mutation(self)
        self.value = new_value
        log_post_mutation(self)
```

## 2. Implementing the `JanusAdapter`

The adapter defines how to calculate deltas between states and how to apply those deltas forward or backward.

### The `JanusAdapter` Protocol

```python
from typing import Any, Protocol

class JanusAdapter(Protocol):
    def get_delta(self, old_snapshot: Any, new_state: Any) -> Any:
        """Calculate the difference between two states."""
        ...

    def apply_forward(self, target: Any, delta_blob: Any) -> None:
        """Apply a delta to move the target to a newer state."""
        ...

    def apply_backward(self, target: Any, delta_blob: Any) -> None:
        """Apply a delta to move the target to a previous state."""
        ...

    def get_snapshot(self, value: Any) -> Any:
        """Create a point-in-time snapshot of the object."""
        ...
```

### Example: A Simple Box Adapter

```python
from janus.registry import register_adapter

@register_adapter(TrackedBox)
class BoxAdapter:
    def get_delta(self, old, new):
        # We just store the old and new values
        return (old.value, new.value)

    def apply_forward(self, target, delta):
        _, new_val = delta
        target.update(new_val)

    def apply_backward(self, target, delta):
        old_val, _ = delta
        target.update(old_val)

    def get_snapshot(self, target):
        return TrackedBox(target.value)
```

## 3. Registering Your Plugin

Use the `@register_adapter` decorator to link your custom class to its adapter. Janus will then automatically use this adapter whenever it encounters your object in a `JanusBase` container.

## Best Practices

- **Shadow Snapshots**: Use `get_snapshot` to create a lightweight copy of the object before mutation.
- **Sparse Deltas**: If your object is large, only store the modified parts in the `delta_blob`.
- **Restoration Safety**: Always check a `_restoring` flag in your proxy's mutation methods to avoid recursive logging during undo/redo operations.
