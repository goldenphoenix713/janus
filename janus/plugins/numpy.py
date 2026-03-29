from __future__ import annotations

from typing import Any

from janus.registry import register_adapter

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

from .utils import log_post_mutation, log_pre_mutation

if NUMPY_AVAILABLE:

    class TrackedNumpyArray(np.ndarray):
        """
        A proxy subclass of `np.ndarray` that intercepts in-place mutations.

        All views created from a `TrackedNumpyArray` (slices, etc.) share the same
        Janus engine reference and name, ensuring that any mutation anywhere in
        the array hierarchy is logged as a single plugin operation.
        """

        _janus_engine: Any | None
        _janus_name: str | None
        _janus_parent: TrackedNumpyArray | None
        _restoring: bool
        _janus_snapshot: np.ndarray | None
        _janus_initiator: int | None
        _janus_adapter_name: str = "NumpyAdapter"

        _metadata = [
            "_janus_engine",
            "_janus_name",
            "_janus_parent",
            "_restoring",
            "_janus_snapshot",
            "_janus_initiator",
            "_janus_adapter_name",
        ]

        def __new__(cls, input_array: np.ndarray) -> TrackedNumpyArray:
            """Create a new TrackedNumpyArray from an existing array."""
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
            if self._restoring or (
                hasattr(self, "_janus_engine")
                and self._janus_engine is not None
                and getattr(self._janus_engine.owner, "_restoring", False)
            ):
                super().__setitem__(key, value)
                return

            log_pre_mutation(self)
            super().__setitem__(key, value)
            log_post_mutation(self)

    @register_adapter(TrackedNumpyArray)
    class NumpyAdapter:
        """
        Janus adapter for NumPy arrays.

        Handles forward and backward state transitions by copying array data
        between snapshots and the live target. This is a sparse-compatible adapter
        as it could be extended to handle only modified indices if needed.
        """

        @staticmethod
        def apply_forward(
            target: np.ndarray, delta_blob: tuple[np.ndarray, np.ndarray]
        ) -> None:
            """
            Synchronize the target array forward to a newer state.

            Args:
                target: The live NumPy array to update.
                delta_blob: A tuple of (old_state, new_state) arrays.
            """
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
            """
            Roll back the target array to a previous state.

            Args:
                target: The live NumPy array to update.
                delta_blob: A tuple of (old_state, new_state) arrays.
            """
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
            """
            Calculate the difference between two array states.

            For NumPy, this currently returns a full snapshot pair. We copy
            the new state to ensure the delta remains stable.
            """
            return (old, new.copy())

        @staticmethod
        def get_snapshot(target: np.ndarray) -> np.ndarray:
            """Create a deep copy of the array for state tracking."""
            return target.copy()

        @staticmethod
        def get_size(target: np.ndarray) -> int:
            """Return the memory usage of the array in bytes."""
            return target.nbytes
