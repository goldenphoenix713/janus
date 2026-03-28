from __future__ import annotations

from typing import Any

from .tachyon_rs import TachyonEngine, TrackedDictCore, TrackedListCore

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

if NUMPY_AVAILABLE:
    from .plugins.numpy import TrackedNumpyArray


class TrackedList(list):  # type: ignore[type-arg]
    def __init__(self, items: list[Any], engine: TachyonEngine, name: str) -> None:
        super().__init__(items)
        self._core = TrackedListCore(engine, name)
        self._engine = engine
        self._owner = engine.owner
        self._name = name
        self._silent = False

    @property
    def _is_silent(self) -> bool:
        return self._silent or getattr(self._owner, "_restoring", False)

    def append(self, value: Any) -> None:
        wrapped = wrap_value(value, self._engine, f"{self._name}[{len(self)}]")
        super().append(wrapped)
        if not self._is_silent:
            self._core.log_insert(len(self) - 1, wrapped)

    def extend(self, values: Any) -> None:
        start_idx = len(self)
        wrapped_values = [
            wrap_value(v, self._engine, f"{self._name}[{start_idx + i}]")
            for i, v in enumerate(values)
        ]
        super().extend(wrapped_values)
        if not self._is_silent:
            self._core.log_extend(wrapped_values)

    def insert(self, index: int, value: Any) -> None:  # type: ignore[override]
        wrapped = wrap_value(value, self._engine, f"{self._name}[{index}]")
        super().insert(index, wrapped)
        if not self._is_silent:
            self._core.log_insert(index, wrapped)

    def pop(self, index: int = -1) -> Any:  # type: ignore[override]
        if index < 0:
            index = len(self) + index
        value = super().pop(index)
        if not self._is_silent:
            self._core.log_pop(index, value)
        return value

    def clear(self) -> None:
        old_values = list(self)
        super().clear()
        if not self._is_silent:
            self._core.log_clear(old_values)

    def __setitem__(self, index: Any, value: Any) -> None:
        old_value = self[index]
        wrapped = wrap_value(value, self._engine, f"{self._name}[{index}]")
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
    def __init__(
        self, initial_dict: dict[str, Any], engine: TachyonEngine, name: str
    ) -> None:
        super().__init__(initial_dict)
        self._core = TrackedDictCore(engine, name)
        self._engine = engine
        self._owner = engine.owner
        self._name = name
        self._silent = False

    @property
    def _is_silent(self) -> bool:
        return self._silent or getattr(self._owner, "_restoring", False)

    def __setitem__(self, key: Any, value: Any) -> None:
        old_value = self.get(key)
        wrapped = wrap_value(value, self._engine, f"{self._name}.{key}")
        super().__setitem__(key, wrapped)
        if not self._is_silent:
            self._core.log_update([str(key)], [old_value], [wrapped])

    def __delitem__(self, key: Any) -> None:
        old_value = self[key]
        super().__delitem__(key)
        if not self._is_silent:
            self._core.log_delete(str(key), old_value)

    def update(self, other: Any = (), /, **kwargs: Any) -> None:
        actual_other = other if hasattr(other, "keys") else dict(other)
        actual_other.update(kwargs)

        keys: list[str] = []
        old_vals: list[Any] = []
        new_vals: list[Any] = []
        for k, v in actual_other.items():
            keys.append(str(k))
            old_vals.append(self.get(k))
            wrapped = wrap_value(v, self._engine, f"{self._name}.{k}")
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

    def setdefault(self, key: str, default: Any = None) -> Any:
        if key in self:
            return self[key]
        wrapped = wrap_value(default, self._engine, f"{self._name}.{key}")
        super().__setitem__(key, wrapped)
        if not self._is_silent:
            self._core.log_update([str(key)], [None], [wrapped])
        return wrapped

    def clear(self) -> None:
        keys = [str(k) for k in self.keys()]
        values = list(self.values())
        super().clear()
        if not self._is_silent:
            self._core.log_clear(keys, values)


def wrap_value(value: Any, engine: TachyonEngine, path: str) -> Any:
    """Recursively wrap containers in Janus proxies."""
    if isinstance(value, (TrackedList, TrackedDict)):
        return value

    if (
        NUMPY_AVAILABLE
        and isinstance(value, np.ndarray)
        and not isinstance(value, TrackedNumpyArray)
    ):
        wrapped = TrackedNumpyArray(value)
        wrapped._janus_engine = engine
        wrapped._janus_name = path
        return wrapped

    if isinstance(value, list):
        wrapped_list = TrackedList([], engine, path)
        wrapped_list._silent = True
        for v in value:
            wrapped_list.append(v)
        wrapped_list._silent = False
        return wrapped_list

    if isinstance(value, dict):
        wrapped_dict = TrackedDict({}, engine, path)
        wrapped_dict._silent = True
        for k, v in value.items():
            wrapped_dict[k] = v
        wrapped_dict._silent = False
        return wrapped_dict

    return value
