from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, TypeVar

T = TypeVar("T", bound=type)
F = TypeVar("F", bound=Callable[..., Any])


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
        """
        ...

    def apply_backward(self, target: Any, delta_blob: Any) -> None:
        """
        Apply a delta in reverse to restore a previous state.
        """
        ...

    def apply_forward(self, target: Any, delta_blob: Any) -> None:
        """
        Apply a delta forward to reach a newer state.
        """
        ...

    def get_snapshot(self, value: Any) -> Any:
        """
        Create a serializable snapshot of the object's current state.
        """
        ...


ADAPTER_REGISTRY: dict[type, JanusAdapter] = {}
WRAPPER_REGISTRY: dict[type, Any] = {}
# Registry for container classes (TrackedList, TrackedDict) to avoid circular imports
CONTAINER_REGISTRY: dict[str, type] = {}


def register_adapter(target_class: type) -> Callable[[T], T]:
    """
    Decorator to register a JanusAdapter for a specific class.
    """

    def wrapper(adapter_class: T) -> T:
        ADAPTER_REGISTRY[target_class] = adapter_class()
        return adapter_class

    return wrapper


def register_wrapper(target_class: type) -> Callable[[F], F]:
    """
    Decorator to register a wrapping function for a specific class.
    """

    def wrapper(func: F) -> F:
        WRAPPER_REGISTRY[target_class] = func
        return func

    return wrapper


def wrap_value(value: Any, engine: Any, path: str, owner: Any = None) -> Any:
    """
    Recursively wrap value in Janus tracking proxies using the registry.
    """
    if hasattr(value, "_janus_engine") and hasattr(value, "_core"):
        return value

    # Check for registered wrappers (e.g., NumPy, Pandas)
    for raw_type, wrapper_func in WRAPPER_REGISTRY.items():
        if isinstance(value, raw_type):
            return wrapper_func(value, engine, path, owner)

    # Standard containers
    if isinstance(value, list):
        list_cls = CONTAINER_REGISTRY.get("list")
        if not list_cls:
            return value
        wrapped_list = list_cls([], engine, path, owner=owner)
        wrapped_list._silent = True
        for v in value:
            wrapped_list.append(v)
        wrapped_list._silent = False
        return wrapped_list

    if isinstance(value, dict):
        dict_cls = CONTAINER_REGISTRY.get("dict")
        if not dict_cls:
            return value
        wrapped_dict = dict_cls({}, engine, path, owner=owner)
        wrapped_dict._silent = True
        for k, v in value.items():
            wrapped_dict[k] = v
        wrapped_dict._silent = False
        return wrapped_dict

    return value
