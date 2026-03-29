from __future__ import annotations

from typing import Any, Protocol


class JanusAdapter(Protocol):
    """
    Protocol for defining custom object tracking logic.

    Adapters allow Janus to track third-party objects (like NumPy arrays or
    Pandas DataFrames) by defining how to calculate deltas and apply them
    forward or backward in time.
    """

    def get_delta(self, old_state: Any, new_state: Any) -> Any:
        """
        Calculate the difference (delta) between two states of the object.

        This delta should contain enough information to transition from
        `old_state` to `new_state` and vice versa. It is typically a
        custom blob (tuple, dict, etc.) understood by the adapter's
        `apply_forward` and `apply_backward` methods.

        Args:
            old_state: The previous state snapshot.
            new_state: The current live state.

        Returns:
            A delta blob representing the changes.
        """
        ...

    def apply_backward(self, target: Any, delta_blob: Any) -> None:
        """
        Apply a delta in reverse to restore a previous state.

        Args:
            target: The live object to be modified in-place.
            delta_blob: The delta calculated by `get_delta`.
        """
        ...

    def apply_forward(self, target: Any, delta_blob: Any) -> None:
        """
        Apply a delta forward to reach a newer state.

        Args:
            target: The live object to be modified in-place.
            delta_blob: The delta calculated by `get_delta`.
        """
        ...

    def get_snapshot(self, value: Any) -> Any:
        """
        Create a serializable snapshot of the object's current state.

        This snapshot is used by Janus for persistence and to provide the
        `old_state` for future `get_delta` calls. It should be a deep
        copy or a representation that remains stable even if the original
        object is mutated.

        Args:
            value: The object to snapshot.

        Returns:
            A serializable snapshot of the object.
        """
        ...


ADAPTER_REGISTRY: dict[type, JanusAdapter] = {}


def register_adapter(target_class: type) -> Any:
    """
    Decorator to register a JanusAdapter for a specific class.

    Args:
        target_class: The class that this adapter is designed to track.
    """

    def wrapper(adapter_class: type) -> type:
        ADAPTER_REGISTRY[target_class] = adapter_class()
        return adapter_class

    return wrapper
