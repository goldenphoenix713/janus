from __future__ import annotations

from typing import Any

from janus.registry import JanusAdapter, register_adapter

from .utils import log_post_mutation, log_pre_mutation

try:
    import pandas as pd

    # ------- Tracked Data Structures ------- #

    class TrackedSeries(pd.Series):  # type: ignore[misc]
        """
        A `pd.Series` subclass that automatically logs mutations to Janus.

        TrackedSeries intercepts attribute and item assignments to ensure that
        changes are recorded in the Janus engine. It also provides wrapped
        indexers (`loc`, `iloc`, `at`, `iat`) to track cell-level mutations.
        """

        _metadata = [
            "_janus_engine",
            "_janus_name",
            "_janus_parent",
            "_restoring",
            "_janus_adapter_name",
        ]
        _janus_adapter_name = "TrackedSeriesAdapter"

        def __init__(self, data: Any = None, *args: Any, **kwargs: Any) -> None:
            # Ensure we don't force a copy if data is a view
            if "copy" not in kwargs:
                kwargs["copy"] = False
            super().__init__(data=data, *args, **kwargs)

        @property
        def _constructor(self) -> type[TrackedSeries]:
            return TrackedSeries

        @property
        def _constructor_expandim(self) -> type[TrackedDataFrame]:
            return TrackedDataFrame

        @property
        def loc(self) -> BaseTrackedIndexer:
            return BaseTrackedIndexer(self, "loc")

        @property
        def iloc(self) -> BaseTrackedIndexer:
            return BaseTrackedIndexer(self, "iloc")

        @property
        def at(self) -> BaseTrackedIndexer:
            return BaseTrackedIndexer(self, "at")

        @property
        def iat(self) -> BaseTrackedIndexer:
            return BaseTrackedIndexer(self, "iat")

        def __setattr__(self, key: str, value: Any) -> None:
            if key in [*self._metadata, "_restoring"]:
                super().__setattr__(key, value)
                return

            if getattr(self, "_restoring", False) or (
                hasattr(self, "_janus_engine")
                and getattr(self._janus_engine.owner, "_restoring", False)
            ):
                super().__setattr__(key, value)
                return

            log_pre_mutation(self)
            super().__setattr__(key, value)
            self._sync_to_parent()
            log_post_mutation(self)

        def __setitem__(self, key: Any, value: Any) -> None:
            if key in [*self._metadata, "_restoring"]:
                super().__setitem__(key, value)
                return

            if getattr(self, "_restoring", False) or (
                hasattr(self, "_janus_engine")
                and getattr(self._janus_engine.owner, "_restoring", False)
            ):
                super().__setitem__(key, value)
                return

            log_pre_mutation(self)
            super().__setitem__(key, value)
            self._sync_to_parent()
            log_post_mutation(self)

        def _sync_to_parent(self) -> None:
            parent = getattr(self, "_janus_parent", None)
            key = getattr(self, "_janus_index_key", None)
            indexer_name = getattr(self, "_janus_indexer", None)

            if parent is not None and key is not None and indexer_name is not None:
                # Avoid recursive logging by setting _restoring on parent
                object.__setattr__(parent, "_restoring", True)
                try:
                    indexer = getattr(parent, indexer_name)
                    indexer[key] = self
                finally:
                    object.__setattr__(parent, "_restoring", False)

    class TrackedDataFrame(pd.DataFrame):  # type: ignore[misc]
        """
        A `pd.DataFrame` subclass that automatically logs mutations to Janus.

        TrackedDataFrame intercepts attribute and item assignments to ensure
        that changes are recorded in the Janus engine. It also provides wrapped
        indexers (`loc`, `iloc`, `at`, `iat`) to track cell-level and slice-level
        mutations.
        """

        _metadata = [
            "_janus_engine",
            "_janus_name",
            "_janus_parent",
            "_restoring",
            "_janus_adapter_name",
        ]
        _janus_adapter_name = "TrackedDataFrameAdapter"

        def __init__(self, data: Any = None, *args: Any, **kwargs: Any) -> None:
            # Ensure we don't force a copy if data is a view
            if "copy" not in kwargs:
                kwargs["copy"] = False
            super().__init__(data=data, *args, **kwargs)

        @property
        def _constructor(self) -> type[TrackedDataFrame]:
            return TrackedDataFrame

        @property
        def _constructor_sliced(self) -> type[TrackedSeries]:
            return TrackedSeries

        @property
        def loc(self) -> BaseTrackedIndexer:
            return BaseTrackedIndexer(self, "loc")

        @property
        def iloc(self) -> BaseTrackedIndexer:
            return BaseTrackedIndexer(self, "iloc")

        @property
        def at(self) -> BaseTrackedIndexer:
            return BaseTrackedIndexer(self, "at")

        @property
        def iat(self) -> BaseTrackedIndexer:
            return BaseTrackedIndexer(self, "iat")

        def __setattr__(self, key: str, value: Any) -> None:
            if key in [*self._metadata, "_restoring"]:
                super().__setattr__(key, value)
                return

            if getattr(self, "_restoring", False) or (
                hasattr(self, "_janus_engine")
                and getattr(self._janus_engine.owner, "_restoring", False)
            ):
                super().__setattr__(key, value)
                return

            log_pre_mutation(self)
            super().__setattr__(key, value)
            self._sync_to_parent()
            log_post_mutation(self)

        def __setitem__(self, key: Any, value: Any) -> None:
            if key in [*self._metadata, "_restoring"]:
                super().__setitem__(key, value)
                return

            if getattr(self, "_restoring", False) or (
                hasattr(self, "_janus_engine")
                and getattr(self._janus_engine.owner, "_restoring", False)
            ):
                super().__setitem__(key, value)
                return

            log_pre_mutation(self)
            super().__setitem__(key, value)
            self._sync_to_parent()
            log_post_mutation(self)

        def _sync_to_parent(self) -> None:
            parent = getattr(self, "_janus_parent", None)
            key = getattr(self, "_janus_index_key", None)
            indexer_name = getattr(self, "_janus_indexer", None)

            if parent is not None and key is not None and indexer_name is not None:
                # Avoid recursive logging by setting _restoring on parent
                object.__setattr__(parent, "_restoring", True)
                try:
                    indexer = getattr(parent, indexer_name)
                    indexer[key] = self
                finally:
                    object.__setattr__(parent, "_restoring", False)

    # ------- Indexer Wrappers ------- #

    class BaseTrackedIndexer:
        """
        A proxy for Pandas indexers that intercepts mutations for tracking.

        This class wraps `.loc`, `.iloc`, `.at`, and `.iat` to ensure that
        any mutation performed through them is captured by the Janus engine.
        It also ensures that any resulting slices are themselves wrapped in
        `TrackedSeries` or `TrackedDataFrame` proxies.
        """

        def __init__(
            self,
            parent_df: TrackedDataFrame | TrackedSeries,
            indexer_name: str,
        ) -> None:
            self._parent = parent_df
            self._indexer_name = indexer_name
            # Get the real pandas indexer (e.g., df.loc) from the base class
            self._real_indexer = getattr(
                super(self._parent.__class__, self._parent), indexer_name
            )

        def __getattr__(self, name: str) -> Any:
            # Proxy missing attributes (like _setitem_with_indexer) to the real indexer
            return getattr(self._real_indexer, name)

        def __getitem__(self, key: Any) -> Any:
            # Transparency for reads
            result = self._real_indexer[key]

            # Use class-swapping or metadata injection to "Janus-ify" the result.
            # This is critical for preserving view-links in pandas subclasses.
            if isinstance(result, (pd.Series, pd.DataFrame)):
                if isinstance(result, pd.Series) and not isinstance(
                    result, TrackedSeries
                ):
                    result.__class__ = TrackedSeries
                elif isinstance(result, pd.DataFrame) and not isinstance(
                    result, TrackedDataFrame
                ):
                    result.__class__ = TrackedDataFrame

                # Always apply/update metadata for this view relationship
                object.__setattr__(
                    result,
                    "_janus_engine",
                    getattr(self._parent, "_janus_engine", None),
                )
                object.__setattr__(
                    result, "_janus_name", getattr(self._parent, "_janus_name", "view")
                )
                object.__setattr__(result, "_janus_parent", self._parent)
                object.__setattr__(result, "_janus_index_key", key)
                object.__setattr__(result, "_janus_indexer", self._indexer_name)

                is_series = isinstance(result, pd.Series)
                adapter = (
                    "TrackedSeriesAdapter" if is_series else "TrackedDataFrameAdapter"
                )
                object.__setattr__(result, "_janus_adapter_name", adapter)

            return result

        def __setitem__(self, key: Any, value: Any) -> None:
            if getattr(self._parent, "_restoring", False) or (
                hasattr(self._parent, "_janus_engine")
                and getattr(self._parent._janus_engine.owner, "_restoring", False)
            ):
                self._real_indexer.__setitem__(key, value)
                return

            # Intercept for writes
            log_pre_mutation(self._parent)
            self._real_indexer[key] = value
            log_post_mutation(self._parent)

    # ------- Adapters ------- #

    @register_adapter(TrackedDataFrame)
    class TrackedDataFrameAdapter(JanusAdapter):
        """
        Janus adapter for Pandas DataFrames.

        Optimizes state tracking by calculating sparse column-level deltas
        instead of full-object snapshots where possible.
        """

        def get_delta(self, old_snapshot: Any, new_state: Any) -> Any:
            """Calculate sparse column-level delta."""
            old_delta = {}
            new_delta = {}

            # Detect changes in existing columns
            for col in new_state.columns:
                if col not in old_snapshot.columns or not new_state[col].equals(
                    old_snapshot[col]
                ):
                    # Ensure we store raw pd.Series, not Tracked versions
                    new_val = new_state[col]
                    if isinstance(new_val, pd.Series):
                        new_delta[col] = pd.Series(new_val, copy=True)
                    else:
                        new_delta[col] = new_val

                    if col in old_snapshot.columns:
                        old_val = old_snapshot[col]
                        old_delta[col] = pd.Series(old_val, copy=True)
                    else:
                        old_delta[col] = None  # New column

            # Detect dropped columns
            for col in old_snapshot.columns:
                if col not in new_state.columns:
                    old_delta[col] = pd.Series(old_snapshot[col], copy=True)
                    new_delta[col] = None

            # Handle index/column name changes if necessary (Omitted for MVP simplicity)
            return (old_delta, new_delta)

        def apply_backward(self, target: Any, delta_blob: Any) -> None:
            old_cols, _ = delta_blob
            object.__setattr__(target, "_restoring", True)
            try:
                for col, val in old_cols.items():
                    if val is None:
                        if col in target.columns:
                            del target[col]
                    else:
                        target[col] = val
            finally:
                object.__setattr__(target, "_restoring", False)

        def apply_forward(self, target: Any, delta_blob: Any) -> None:
            _, new_cols = delta_blob
            object.__setattr__(target, "_restoring", True)
            try:
                for col, val in new_cols.items():
                    if val is None:
                        if col in target.columns:
                            del target[col]
                    else:
                        target[col] = val
            finally:
                object.__setattr__(target, "_restoring", False)

        def get_snapshot(self, value: Any) -> Any:
            # Ensure raw dataframe is returned for serialization
            return pd.DataFrame(value)

    @register_adapter(TrackedSeries)
    class TrackedSeriesAdapter(JanusAdapter):
        """
        Janus adapter for Pandas Series.

        Handles forward and backward state transitions for individual Series objects.
        """

        def get_delta(self, old_snapshot: Any, new_state: Any) -> Any:
            # Ensure raw series are stored
            return (pd.Series(old_snapshot), pd.Series(new_state))

        def apply_backward(self, target: Any, delta_blob: Any) -> None:
            old_series, _ = delta_blob
            object.__setattr__(target, "_restoring", True)
            try:
                # Use public iloc assignment for robust restoration
                target.iloc[:] = old_series.values
                target.index = old_series.index
                target.name = old_series.name
            except Exception as e:
                raise RuntimeError(f"Failed to restore Series: {e}")
            finally:
                object.__setattr__(target, "_restoring", False)

        def apply_forward(self, target: Any, delta_blob: Any) -> None:
            _, new_series = delta_blob
            object.__setattr__(target, "_restoring", True)
            try:
                target.iloc[:] = new_series.values
                target.index = new_series.index
                target.name = new_series.name
            except Exception as e:
                raise RuntimeError(f"Failed to restore Series: {e}")
            finally:
                object.__setattr__(target, "_restoring", False)

        def get_snapshot(self, value: Any) -> Any:
            # Ensure raw series is returned
            return pd.Series(value)

except ImportError:
    pass
