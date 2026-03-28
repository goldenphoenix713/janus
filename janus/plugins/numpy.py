from __future__ import annotations

from typing import Any

from janus.registry import register_adapter

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


if NUMPY_AVAILABLE:
    # ------- Mutation Hooks ------- #

    def _get_engine(target: TrackedNumpyArray) -> Any | None:
        """Find the Janus engine by traversing the view hierarchy."""
        curr: TrackedNumpyArray | None = target
        while curr is not None:
            engine = getattr(curr, "_janus_engine", None)
            if engine is not None:
                return engine
            curr = getattr(curr, "_janus_parent", None)
        return None

    def _log_pre_mutation(target: TrackedNumpyArray, key: Any) -> None:
        """Log the state of the array before a mutation."""
        if getattr(target, "_restoring", False):
            return

        engine = _get_engine(target)
        parent = getattr(target, "_janus_parent", None)
        root = parent if parent is not None else target

        if engine is None or hasattr(root, "_janus_snapshot"):
            return

        # Snapshot the current state of the root array
        snapshot = root.copy()
        object.__setattr__(root, "_janus_snapshot", snapshot)
        object.__setattr__(root, "_janus_initiator", id(target))

    def _log_post_mutation(target: TrackedNumpyArray, key: Any) -> None:
        """Log the state of the array after a mutation."""
        if getattr(target, "_restoring", False):
            return

        engine = _get_engine(target)
        parent = getattr(target, "_janus_parent", None)
        root = parent if parent is not None else target
        initiator = getattr(root, "_janus_initiator", None)

        if engine is None or initiator != id(target):
            return

        snapshot = getattr(root, "_janus_snapshot")
        current = root.copy()

        engine.log_plugin_op(
            getattr(root, "_janus_name", "unknown"),
            "NumpyAdapter",
            (snapshot, current),
        )

        delattr(root, "_janus_snapshot")
        delattr(root, "_janus_initiator")

    # ------- Tracked Array Proxy ------- #

    class TrackedNumpyArray(np.ndarray):
        """
        A proxy subclass of np.ndarray that intercepts in-place mutations.
        All views of a TrackedNumpyArray share the same Janus metadata root.
        """

        _janus_engine: Any | None
        _janus_name: str | None
        _janus_parent: TrackedNumpyArray | None
        _restoring: bool
        _janus_snapshot: np.ndarray | None
        _janus_initiator: int | None

        _metadata = [
            "_janus_engine",
            "_janus_name",
            "_janus_parent",
            "_restoring",
            "_janus_snapshot",
            "_janus_initiator",
        ]

        def __new__(cls, input_array: np.ndarray) -> TrackedNumpyArray:
            return np.asarray(input_array).view(cls)

        def __array_finalize__(self, obj: np.ndarray | None) -> None:
            if obj is None:
                return

            # Propagate metadata from parent to view
            self._janus_engine = getattr(obj, "_janus_engine", None)
            self._janus_name = getattr(obj, "_janus_name", None)

            # Ensure we always point to the absolute root of the array hierarchy.
            if isinstance(obj, TrackedNumpyArray):
                parent = getattr(obj, "_janus_parent", None)
                self._janus_parent = parent if parent is not None else obj
            else:
                self._janus_parent = None

            self._restoring = getattr(obj, "_restoring", False)

        def __setitem__(self, key: Any, value: Any) -> None:
            if self._restoring:
                super().__setitem__(key, value)
                return

            _log_pre_mutation(self, key)
            super().__setitem__(key, value)
            _log_post_mutation(self, key)

    @register_adapter(TrackedNumpyArray)
    class NumpyAdapter:
        @staticmethod
        def apply_forward(
            target: np.ndarray, delta_blob: tuple[np.ndarray, np.ndarray]
        ) -> None:
            _, new = delta_blob
            object.__setattr__(target, "_restoring", True)
            try:
                if target.shape == new.shape:
                    target[:] = new
                else:
                    np.copyto(target, new, casting="unsafe")
            finally:
                object.__setattr__(target, "_restoring", False)

        @staticmethod
        def apply_backward(
            target: np.ndarray, delta_blob: tuple[np.ndarray, np.ndarray]
        ) -> None:
            old, _ = delta_blob
            object.__setattr__(target, "_restoring", True)
            try:
                if target.shape == old.shape:
                    target[:] = old
                else:
                    np.copyto(target, old, casting="unsafe")
            finally:
                object.__setattr__(target, "_restoring", False)

        @staticmethod
        def get_delta(
            old: np.ndarray, new: np.ndarray
        ) -> tuple[np.ndarray, np.ndarray]:
            return (old, new)

        @staticmethod
        def get_snapshot(target: np.ndarray) -> np.ndarray:
            return target.copy()

        @staticmethod
        def get_size(target: np.ndarray) -> int:
            return target.nbytes
