from __future__ import annotations

from typing import Any, Protocol


class JanusAdapter(Protocol):
    def get_delta(self, old_state: Any, new_state: Any) -> Any: ...
    def apply_backward(self, target: Any, delta_blob: Any) -> None: ...
    def apply_forward(self, target: Any, delta_blob: Any) -> None: ...
    def get_snapshot(self, value: Any) -> Any: ...


ADAPTER_REGISTRY: dict[type, JanusAdapter] = {}


def register_adapter(target_class: type) -> Any:
    """Decorator to register a custom class adapter for Janus tracking."""

    def wrapper(adapter_class: type) -> type:
        ADAPTER_REGISTRY[target_class] = adapter_class()
        return adapter_class

    return wrapper
