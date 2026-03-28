from __future__ import annotations

from typing import Any

from janus.registry import JanusAdapter, register_adapter

try:
    import pandas as pd

    # ------- Helper Functions ------- #

    def _log_pre_mutation(obj: TrackedDataFrame | TrackedSeries, name: str) -> None:
        root = getattr(obj, "_janus_parent", obj)
        if hasattr(root, "_janus_engine"):
            # Avoid nested logging: if a snapshot already exists, we are already
            # being tracked by a higher-level operation (like an Indexer).
            if hasattr(root, "_janus_snapshot"):
                return

            snapshot: pd.DataFrame | pd.Series
            if isinstance(root, pd.DataFrame):
                snapshot = pd.DataFrame(
                    root.values.copy(),
                    index=root.index.copy(),
                    columns=root.columns.copy(),
                )
            elif isinstance(root, pd.Series):
                snapshot = pd.Series(
                    root.values.copy(), index=root.index.copy(), name=root.name
                )
            else:
                raise TypeError(f"Unsupported type for snapshot: {type(root)}")

            # Mark who started this snapshot to ensure they are the one to close it
            object.__setattr__(root, "_janus_snapshot", snapshot)
            object.__setattr__(root, "_janus_initiator", id(obj))

    def _log_post_mutation(obj: TrackedDataFrame | TrackedSeries, name: str) -> None:
        root = getattr(obj, "_janus_parent", obj)
        if hasattr(root, "_janus_engine") and hasattr(root, "_janus_snapshot"):
            # Only the initiator who created the snapshot should finalize the log
            if getattr(root, "_janus_initiator", None) != id(obj):
                return

            current: pd.DataFrame | pd.Series
            if isinstance(root, pd.DataFrame):
                current = pd.DataFrame(
                    root.values.copy(),
                    index=root.index.copy(),
                    columns=root.columns.copy(),
                )
            elif isinstance(root, pd.Series):
                current = pd.Series(
                    root.values.copy(), index=root.index.copy(), name=root.name
                )
            else:
                raise TypeError(f"Unsupported type for snapshot: {type(root)}")

            root._janus_engine.log_plugin_op(
                root._janus_name,
                root._pandas_adapter,
                (root._janus_snapshot, current),
            )
            # Cleanup
            delattr(root, "_janus_snapshot")
            delattr(root, "_janus_initiator")

    # ------- Tracked Data Structures ------- #

    class TrackedSeries(pd.Series):
        _metadata = ["_janus_engine", "_janus_name", "_janus_parent", "_restoring"]
        _pandas_adapter = "TrackedSeriesAdapter"

        def __init__(self, data: Any = None, *args: Any, **kwargs: Any) -> None:
            # Ensure we don't force a copy if data is a view
            if "copy" not in kwargs:
                kwargs["copy"] = False
            super().__init__(data=data, *args, **kwargs)  # type: ignore[call-arg]

        @property
        def _constructor(self) -> type[TrackedSeries]:
            return TrackedSeries

        @property
        def _constructor_expandim(self) -> type[TrackedDataFrame]:
            return TrackedDataFrame

        @property
        def loc(self) -> BaseTrackedIndexer:  # type: ignore[override]
            return BaseTrackedIndexer(self, "loc")

        @property
        def iloc(self) -> BaseTrackedIndexer:  # type: ignore[override]
            return BaseTrackedIndexer(self, "iloc")

        @property
        def at(self) -> BaseTrackedIndexer:  # type: ignore[override]
            return BaseTrackedIndexer(self, "at")

        @property
        def iat(self) -> BaseTrackedIndexer:  # type: ignore[override]
            return BaseTrackedIndexer(self, "iat")

        def __setattr__(self, key: str, value: Any) -> None:
            if key in [*self._metadata, "_restoring"]:
                super().__setattr__(key, value)
                return

            if getattr(self, "_restoring", False):
                super().__setattr__(key, value)
                return

            _log_pre_mutation(self, key)
            super().__setattr__(key, value)
            _log_post_mutation(self, key)
            self._sync_to_parent()

        def __setitem__(self, key: Any, value: Any) -> None:
            if key in [*self._metadata, "_restoring"]:
                super().__setitem__(key, value)
                return

            if getattr(self, "_restoring", False):
                super().__setitem__(key, value)
                return

            _log_pre_mutation(self, key)
            super().__setitem__(key, value)
            _log_post_mutation(self, key)
            self._sync_to_parent()

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

    class TrackedDataFrame(pd.DataFrame):
        _metadata = ["_janus_engine", "_janus_name", "_janus_parent", "_restoring"]
        _pandas_adapter = "TrackedDataFrameAdapter"

        def __init__(self, data: Any = None, *args: Any, **kwargs: Any) -> None:
            # Ensure we don't force a copy if data is a view
            if "copy" not in kwargs:
                kwargs["copy"] = False
            super().__init__(data=data, *args, **kwargs)  # type: ignore[call-arg]

        @property
        def _constructor(self) -> type[TrackedDataFrame]:
            return TrackedDataFrame

        @property
        def _constructor_sliced(self) -> type[TrackedSeries]:
            return TrackedSeries

        @property
        def loc(self) -> BaseTrackedIndexer:  # type: ignore[override]
            return BaseTrackedIndexer(self, "loc")

        @property
        def iloc(self) -> BaseTrackedIndexer:  # type: ignore[override]
            return BaseTrackedIndexer(self, "iloc")

        @property
        def at(self) -> BaseTrackedIndexer:  # type: ignore[override]
            return BaseTrackedIndexer(self, "at")

        @property
        def iat(self) -> BaseTrackedIndexer:  # type: ignore[override]
            return BaseTrackedIndexer(self, "iat")

        def __setattr__(self, key: str, value: Any) -> None:
            if key in [*self._metadata, "_restoring"]:
                super().__setattr__(key, value)
                return

            if getattr(self, "_restoring", False):
                super().__setattr__(key, value)
                return

            _log_pre_mutation(self, key)
            super().__setattr__(key, value)
            _log_post_mutation(self, key)
            self._sync_to_parent()

        def __setitem__(self, key: Any, value: Any) -> None:
            if key in [*self._metadata, "_restoring"]:
                super().__setitem__(key, value)
                return

            if getattr(self, "_restoring", False):
                super().__setitem__(key, value)
                return

            _log_pre_mutation(self, key)
            super().__setitem__(key, value)
            _log_post_mutation(self, key)
            self._sync_to_parent()

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
                object.__setattr__(result, "_pandas_adapter", adapter)

            return result

        def __setitem__(self, key: Any, value: Any) -> None:
            if getattr(self._parent, "_restoring", False):
                self._real_indexer.__setitem__(key, value)
                return

            # Intercept for writes
            _log_pre_mutation(self._parent, "indexer")
            self._real_indexer[key] = value
            _log_post_mutation(self._parent, "indexer")

    # ------- Adapters ------- #

    @register_adapter(TrackedDataFrame)
    class TrackedDataFrameAdapter(JanusAdapter):
        def get_delta(self, old_snapshot: Any, new_state: Any) -> Any:
            # In this MVP, the delta object is just (old_df, new_df)
            return (old_snapshot, new_state.copy())

        def apply_backward(self, target: Any, delta_blob: Any) -> None:
            old_df, _ = delta_blob
            object.__setattr__(target, "_restoring", True)
            try:
                # Use public iloc assignment which is more robust than _mgr swapping
                # BaseTrackedIndexer will see _restoring=True and bypass logging.
                target.iloc[:, :] = old_df.values
                target.index = old_df.index
                target.columns = old_df.columns
            except Exception as e:
                object.__setattr__(target, "_restoring", False)
                raise RuntimeError(f"Failed to restore DataFrame: {e}")
            finally:
                object.__setattr__(target, "_restoring", False)

        def apply_forward(self, target: Any, delta_blob: Any) -> None:
            _, new_df = delta_blob
            object.__setattr__(target, "_restoring", True)
            try:
                target.iloc[:, :] = new_df.values
                target.index = new_df.index
                target.columns = new_df.columns
            except Exception as e:
                raise RuntimeError(f"Failed to restore DataFrame: {e}")
            finally:
                object.__setattr__(target, "_restoring", False)

        def get_snapshot(self, value: Any) -> Any:
            return value.copy()

    @register_adapter(TrackedSeries)
    class TrackedSeriesAdapter(JanusAdapter):
        def get_delta(self, old_snapshot: Any, new_state: Any) -> Any:
            # In this MVP, the delta object is just (old_series, new_series)
            return (old_snapshot, new_state.copy())

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
            return value.copy()

except ImportError:
    pass
