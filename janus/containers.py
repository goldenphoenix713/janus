from __future__ import annotations

from typing import Any

from janus.logger import logger
from janus.registry import CONTAINER_REGISTRY, wrap_value
from janus.tachyon_rs import TachyonEngine, TrackedDictCore, TrackedListCore


class TrackedList(list):  # type: ignore[type-arg]
    """
    A list subclass that automatically logs mutations to the Janus engine.

    TrackedList intercepts methods like `append`, `extend`, `insert`, `pop`,
    `clear`, and `__setitem__` to ensure the Janus engine can track and
    revert changes to the collection.
    """

    def __init__(
        self, items: list[Any], engine: TachyonEngine, name: str, owner: Any = None
    ) -> None:
        """
        Initialize a tracked list.

        Args:
            items: The initial items for the list.
            engine: The TachyonEngine instance for logging.
            name: The attribute name or path of this container.
            owner: The JanusBase object that owns this container.
        """
        super().__init__(items)
        self._core = TrackedListCore(engine, name)
        self._engine = engine
        self._owner = owner if owner is not None else getattr(engine, "owner", None)
        self._name = name
        self._silent = False

    @property
    def _is_silent(self) -> bool:
        return self._silent or getattr(self._owner, "_restoring", False)

    def append(self, value: Any) -> None:
        wrapped = wrap_value(
            value, self._engine, f"{self._name}[{len(self)}]", owner=self._owner
        )
        super().append(wrapped)
        if not self._is_silent:
            # Snapshot for DAG
            dag_val = wrapped
            if isinstance(wrapped, list):
                dag_val = list(wrapped)
            elif isinstance(wrapped, dict):
                dag_val = dict(wrapped)
            self._core.log_insert(len(self) - 1, dag_val)
            logger.trace(f"TrackedList ({self._name}) appended item")

    def extend(self, values: Any) -> None:
        start_idx = len(self)
        wrapped_values = [
            wrap_value(
                v, self._engine, f"{self._name}[{start_idx + i}]", owner=self._owner
            )
            for i, v in enumerate(values)
        ]
        super().extend(wrapped_values)
        if not self._is_silent:
            self._core.log_extend(wrapped_values)
            logger.trace(
                f"TrackedList ({self._name}) extended with {len(values)} items"
            )

    def insert(self, index: int, value: Any) -> None:  # type: ignore[override]
        wrapped = wrap_value(
            value, self._engine, f"{self._name}[{index}]", owner=self._owner
        )
        super().insert(index, wrapped)
        if not self._is_silent:
            # Snapshot for DAG
            dag_val = wrapped
            if isinstance(wrapped, list):
                dag_val = list(wrapped)
            elif isinstance(wrapped, dict):
                dag_val = dict(wrapped)
            self._core.log_insert(index, dag_val)

    def pop(self, index: int = -1) -> Any:  # type: ignore[override]
        if index < 0:
            index = len(self) + index
        value = super().pop(index)
        if not self._is_silent:
            self._core.log_pop(index, value)
            logger.trace(f"TrackedList ({self._name}) popped item at {index}")
        return value

    def clear(self) -> None:
        old_values = list(self)
        super().clear()
        if not self._is_silent:
            self._core.log_clear(old_values)

    def __setitem__(self, index: Any, value: Any) -> None:
        old_value = self[index]
        wrapped = wrap_value(
            value, self._engine, f"{self._name}[{index}]", owner=self._owner
        )
        super().__setitem__(index, wrapped)
        if not self._is_silent:
            self._core.log_replace(index, old_value, wrapped)

    def __delitem__(self, index: Any) -> None:
        value = self[index]
        super().__delitem__(index)
        if not self._is_silent:
            self._core.log_pop(index, value)

    def remove(self, value: Any) -> None:
        index = self.index(value)
        super().remove(value)
        if not self._is_silent:
            self._core.log_pop(index, value)


class TrackedDict(dict):  # type: ignore[type-arg]
    """
    A dict subclass that automatically logs mutations to the Janus engine.

    TrackedDict intercepts key assignments, deletions, and updates to ensure
    the Janus engine can track and revert changes to the collection.
    """

    def __init__(
        self, items: dict[str, Any], engine: TachyonEngine, name: str, owner: Any = None
    ) -> None:
        """
        Initialize a tracked dictionary.

        Args:
            items: The initial key-value pairs.
            engine: The TachyonEngine instance for logging.
            name: The attribute name or path of this container.
            owner: The JanusBase object that owns this container.
        """
        super().__init__(items)
        self._core = TrackedDictCore(engine, name)
        self._engine = engine
        self._owner = owner if owner is not None else getattr(engine, "owner", None)
        self._name = name
        self._silent = False

    @property
    def _is_silent(self) -> bool:
        return self._silent or getattr(self._owner, "_restoring", False)

    def __setitem__(self, key: Any, value: Any) -> None:
        try:
            old_value = self[key]
        except KeyError:
            old_value = None

        wrapped = wrap_value(
            value, self._engine, f"{self._name}.{key}", owner=self._owner
        )
        super().__setitem__(key, wrapped)
        if not self._is_silent:
            # Snapshot for DAG
            dag_val = wrapped
            if isinstance(wrapped, list):
                dag_val = list(wrapped)
            elif isinstance(wrapped, dict):
                dag_val = dict(wrapped)

            dag_old = old_value
            if isinstance(old_value, list):
                dag_old = list(old_value)
            elif isinstance(old_value, dict):
                dag_old = dict(old_value)

            self._core.log_update([str(key)], [dag_old], [dag_val])

    def __delitem__(self, key: Any) -> None:
        old_value = self[key]
        super().__delitem__(key)
        if not self._is_silent:
            self._core.log_delete(str(key), old_value)
            logger.trace(f"TrackedDict ({self._name}) deleted key: {key}")

    def update(self, other: Any = (), /, **kwargs: Any) -> None:
        actual_other = other if hasattr(other, "keys") else dict(other)
        actual_other.update(kwargs)

        keys: list[str] = []
        old_vals: list[Any] = []
        new_vals: list[Any] = []
        for k, v in actual_other.items():
            keys.append(str(k))
            old_vals.append(self.get(k))
            wrapped = wrap_value(
                v, self._engine, f"{self._name}.{k}", owner=self._owner
            )
            new_vals.append(wrapped)
            super().__setitem__(k, wrapped)
        if not self._is_silent:
            self._core.log_update(keys, old_vals, new_vals)

    def pop(self, key: str, default: Any = None) -> Any:
        if key in self:
            val = self[key]
            res = super().pop(key)
            if not self._is_silent:
                self._core.log_pop(str(key), val)
            return res
        return default

    def popitem(self) -> tuple[str, Any]:
        key, value = super().popitem()
        if not self._is_silent:
            self._core.log_pop(str(key), value)
        return key, value

    def setdefault(self, key: Any, default: Any = None) -> Any:
        if key not in self:
            wrapped = wrap_value(
                default, self._engine, f"{self._name}.{key}", owner=self._owner
            )
            self[key] = wrapped
        return self[key]

    def clear(self) -> None:
        keys = [str(k) for k in self.keys()]
        values = list(self.values())
        super().clear()
        if not self._is_silent:
            self._core.log_clear(keys, values)


# Register containers to avoid circular imports in registry.py
CONTAINER_REGISTRY["list"] = TrackedList
CONTAINER_REGISTRY["dict"] = TrackedDict
