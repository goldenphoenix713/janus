from typing import Any, Protocol


class JanusAdapter(Protocol):
    def get_delta(self, old_state: Any, new_state: Any) -> Any: ...
    def apply_inverse(self, target: Any, delta_blob: Any) -> None: ...


ADAPTER_REGISTRY = {}


def register_adapter(target_class):
    """Decorator to register a custom class adapter for Janus tracking."""

    def wrapper(adapter_class):
        ADAPTER_REGISTRY[target_class] = adapter_class()
        return adapter_class

    return wrapper
