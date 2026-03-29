from __future__ import annotations

from typing import Any

from janus.logger import logger
from janus.plugins.utils import log_post_mutation, log_pre_mutation
from janus.registry import register_adapter, register_wrapper, wrap_value

try:
    import pandas as pd

    PANDAS_INSTALLED = True

except ImportError:
    PANDAS_INSTALLED = False

if PANDAS_INSTALLED:
    # ------- Tracked Indexers ------- #

    class BaseTrackedIndexer:
        """Base class for Janus-aware pandas indexers."""

        def __init__(self, name: str, parent: Any) -> None:
            """
            Initialize the Janus-aware indexer.

            Args:
                name: The name of the indexer (e.g., 'loc', 'iloc').
                parent: The TrackedSeries or TrackedDataFrame being indexed.
            """
            self._name = name
            self._parent = parent
            # Get the original indexer from the base pandas class
            # (Series or DataFrame)
            base_cls = parent.__class__.__bases__[0]
            self._indexer = getattr(base_cls, name).fget(parent)

        def __getattr__(self, name: str) -> Any:
            """Delegate any unknown attributes to the underlying pandas indexer."""
            return getattr(self._indexer, name)

        def __getitem__(self, key: Any) -> Any:
            """
            Retrieve an item from the underlying indexer and wrap it if it's a
            Pandas object.

            Args:
                key: The indexer key (e.g., slice, label, integer).

            Returns:
                The retrieved value, wrapped in Janus if it's a Series or DataFrame.
            """
            result = self._indexer[key]

            if isinstance(result, pd.DataFrame):
                return wrap_value(
                    result,
                    self._parent._janus_engine,
                    self._parent._janus_name,
                    owner=self._parent,
                )
            if isinstance(result, pd.Series):
                return wrap_value(
                    result,
                    self._parent._janus_engine,
                    self._parent._janus_name,
                    owner=self._parent,
                )
            return result

        def __setitem__(self, key: Any, value: Any) -> None:
            """
            Set an item via the underlying indexer and log the mutation.

            Args:
                key: The indexer key.
                value: The new value to set.
            """
            if getattr(self._parent, "_restoring", False) or (
                hasattr(self._parent, "_janus_engine")
                and self._parent._janus_engine is not None
                and getattr(self._parent._janus_engine.owner, "_restoring", False)
            ):
                self._indexer[key] = value
                return

            log_pre_mutation(self._parent)
            try:
                self._indexer[key] = value
            finally:
                log_post_mutation(self._parent)

    class TrackedLocIndexer(BaseTrackedIndexer):
        """Janus-aware .loc indexer."""

        def __init__(self, parent: Any) -> None:
            super().__init__("loc", parent)

    class TrackedIlocIndexer(BaseTrackedIndexer):
        """Janus-aware .iloc indexer."""

        def __init__(self, parent: Any) -> None:
            super().__init__("iloc", parent)

    class TrackedAtIndexer(BaseTrackedIndexer):
        """Janus-aware .at indexer."""

        def __init__(self, parent: Any) -> None:
            super().__init__("at", parent)

    class TrackedIatIndexer(BaseTrackedIndexer):
        """Janus-aware .iat indexer."""

        def __init__(self, parent: Any) -> None:
            super().__init__("iat", parent)

    @register_wrapper(pd.DataFrame)
    def wrap_dataframe(value: Any, engine: Any, path: str, owner: Any = None) -> Any:
        """
        Wrap a pandas DataFrame in a TrackedDataFrame with Janus metadata.

        Args:
            value: The DataFrame to wrap.
            engine: The Janus engine instance.
            path: The name or path of the object in the store.
            owner: The parent object, if any (used for view-linkage).

        Returns:
            The DataFrame, swapped to the TrackedDataFrame class.
        """
        if not isinstance(value, TrackedDataFrame):
            value.__class__ = TrackedDataFrame
            if not hasattr(value, "_restoring"):
                object.__setattr__(value, "_restoring", False)
        value._janus_engine = engine
        value._janus_name = path
        if owner is not None:
            value._janus_parent = owner
        return value

    @register_wrapper(pd.Series)
    def wrap_series(value: Any, engine: Any, path: str, owner: Any = None) -> Any:
        """
        Wrap a pandas Series in a TrackedSeries with Janus metadata.

        Args:
            value: The Series to wrap.
            engine: The Janus engine instance.
            path: The name or path of the object in the store.
            owner: The parent object, if any (used for view-linkage).

        Returns:
            The Series, swapped to the TrackedSeries class.
        """
        if not isinstance(value, TrackedSeries):
            value.__class__ = TrackedSeries
            if not hasattr(value, "_restoring"):
                object.__setattr__(value, "_restoring", False)
        value._janus_engine = engine
        value._janus_name = path
        if owner is not None:
            value._janus_parent = owner
        return value

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
            "_restoring",
            "_janus_snapshot",
            "_janus_initiator",
            "_janus_adapter_name",
            "_janus_parent",
        ]
        _janus_adapter_name: str = "PandasAdapter"

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            """
            Initialize a TrackedSeries and ensure the restoration flag is set.
            """
            super().__init__(*args, **kwargs)
            if not hasattr(self, "_restoring"):
                object.__setattr__(self, "_restoring", False)

        def __finalize__(
            self, other: Any, method: str | None = None, **kwargs: Any
        ) -> Any:
            """
            Propagate Janus metadata during Pandas operations.
            """
            result = super().__finalize__(other, method=method, **kwargs)
            if not hasattr(result, "_restoring"):
                object.__setattr__(result, "_restoring", False)
            return result

        @property
        def _constructor(self) -> type:
            """
            Constructor for new Series instances.
            """
            return TrackedSeries

        @property
        def _constructor_expanddim(self) -> type:
            """
            Constructor for expanding to a DataFrame.
            """
            return TrackedDataFrame

        @property
        def _is_restoring(self) -> bool:
            """
            Return True if the object or its parent engine is in a restoration state.
            """
            return bool(
                getattr(self, "_restoring", False)
                or (
                    hasattr(self, "_janus_engine")
                    and self._janus_engine is not None
                    and getattr(self._janus_engine.owner, "_restoring", False)
                )
            )

        def __setitem__(self, key: Any, value: Any) -> None:
            """
            Set an item and log the mutation to Janus.
            """
            if self._is_restoring:
                super().__setitem__(key, value)
                return

            log_pre_mutation(self)
            super().__setitem__(key, value)
            log_post_mutation(self)

        def __setattr__(self, key: str, value: Any) -> None:
            """
            Set an attribute and log the mutation if it's not internal metadata.
            """
            if key in [*self._metadata, "_restoring"]:
                super().__setattr__(key, value)
                return

            if self._is_restoring:
                super().__setattr__(key, value)
                return

            log_pre_mutation(self)
            super().__setattr__(key, value)
            log_post_mutation(self)

        @property
        def loc(self) -> Any:
            """
            Label-based indexer for the TrackedSeries.
            """
            return TrackedLocIndexer(self)

        @property
        def iloc(self) -> Any:
            """
            Integer-based indexer for the TrackedSeries.
            """
            return TrackedIlocIndexer(self)

        @property
        def at(self) -> Any:
            """
            Fast label-based scalar accessor for the TrackedSeries.
            """
            return TrackedAtIndexer(self)

        @property
        def iat(self) -> Any:
            """
            Fast integer-based scalar accessor for the TrackedSeries.
            """
            return TrackedIatIndexer(self)

    class TrackedDataFrame(pd.DataFrame):  # type: ignore[misc]
        """
        A `pd.DataFrame` subclass that automatically logs mutations to Janus.

        TrackedDataFrame intercepts attribute and item assignments to ensure that
        changes are recorded in the Janus engine. It also provides wrapped
        indexers (`loc`, `iloc`, `at`, `iat`) to track cell-level mutations.
        """

        _metadata = [
            "_janus_engine",
            "_janus_name",
            "_restoring",
            "_janus_snapshot",
            "_janus_initiator",
            "_janus_adapter_name",
            "_janus_parent",
        ]
        _janus_adapter_name: str = "PandasAdapter"

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            """
            Initialize a TrackedDataFrame and ensure the restoration flag is set.
            """
            super().__init__(*args, **kwargs)
            if not hasattr(self, "_restoring"):
                object.__setattr__(self, "_restoring", False)

        def __finalize__(
            self, other: Any, method: str | None = None, **kwargs: Any
        ) -> Any:
            """
            Propagate Janus metadata during Pandas operations.
            """
            result = super().__finalize__(other, method=method, **kwargs)
            if not hasattr(result, "_restoring"):
                object.__setattr__(result, "_restoring", False)
            return result

        @property
        def _constructor(self) -> type:
            """
            Constructor for new DataFrame instances.
            """
            return TrackedDataFrame

        @property
        def _constructor_sliced(self) -> type:
            """
            Constructor for sliced Series instances.
            """
            return TrackedSeries

        @property
        def _is_restoring(self) -> bool:
            """
            Return True if the object or its parent engine is in a restoration state.
            """
            return bool(
                getattr(self, "_restoring", False)
                or (
                    hasattr(self, "_janus_engine")
                    and self._janus_engine is not None
                    and getattr(self._janus_engine.owner, "_restoring", False)
                )
            )

        def __setitem__(self, key: Any, value: Any) -> None:
            """
            Set an item and log the mutation to Janus.
            """
            if self._is_restoring:
                super().__setitem__(key, value)
                return

            log_pre_mutation(self)
            super().__setitem__(key, value)
            log_post_mutation(self)

        def __setattr__(self, key: str, value: Any) -> None:
            """
            Set an attribute and log the mutation if it's not internal metadata.
            """
            if key in [*self._metadata, "_restoring"]:
                super().__setattr__(key, value)
                return

            if self._is_restoring:
                super().__setattr__(key, value)
                return

            log_pre_mutation(self)
            super().__setattr__(key, value)
            log_post_mutation(self)

        @property
        def loc(self) -> Any:
            """
            Label-based indexer for the TrackedDataFrame.
            """
            return TrackedLocIndexer(self)

        @property
        def iloc(self) -> Any:
            """
            Integer-based indexer for the TrackedDataFrame.
            """
            return TrackedIlocIndexer(self)

        @property
        def at(self) -> Any:
            """
            Fast label-based scalar accessor for the TrackedDataFrame.
            """
            return TrackedAtIndexer(self)

        @property
        def iat(self) -> Any:
            """
            Fast integer-based scalar accessor for the TrackedDataFrame.
            """
            return TrackedIatIndexer(self)

    @register_adapter(TrackedDataFrame)
    @register_adapter(TrackedSeries)
    class PandasAdapter:
        """
        Janus adapter for Pandas DataFrames and Series.
        """

        @staticmethod
        def apply_forward(target: Any, delta_blob: Any) -> None:
            """
            Apply a forward mutation to the Pandas object.

            Args:
                target: The object to update.
                delta_blob: A tuple of (old_state, new_state).
            """
            _, new_state = delta_blob
            if new_state is None:
                return

            logger.trace("PandasAdapter applying forward mutation")
            object.__setattr__(target, "_restoring", True)
            try:
                if isinstance(target, (pd.DataFrame, pd.Series)):
                    target.update(new_state)
            finally:
                object.__setattr__(target, "_restoring", False)

        @staticmethod
        def apply_backward(target: Any, delta_blob: Any) -> None:
            """
            Apply a backward mutation to the Pandas object.

            Args:
                target: The object to restore.
                delta_blob: A tuple of (old_state, new_state).
            """
            old_state, _ = delta_blob
            if old_state is None:
                return

            logger.trace("PandasAdapter applying backward mutation")
            object.__setattr__(target, "_restoring", True)
            try:
                if isinstance(target, (pd.DataFrame, pd.Series)):
                    target.update(old_state)
            finally:
                object.__setattr__(target, "_restoring", False)

        @staticmethod
        def get_delta(old_state: Any, new_state: Any) -> Any:
            """
            Calculate the delta between two states of a Pandas object.

            For DataFrames, this only stores columns that have changed.

            Args:
                old_state: The previous state snapshot.
                new_state: The current state snapshot.

            Returns:
                A tuple containing the changed portions of (old_state, new_state).
            """
            if old_state is None:
                return None, new_state

            if isinstance(new_state, pd.DataFrame):
                # Only store columns that have actually changed
                changed_cols = []
                for col in new_state.columns:
                    if col not in old_state.columns or not new_state[col].equals(
                        old_state[col]
                    ):
                        changed_cols.append(col)
                return old_state[changed_cols], new_state[changed_cols]

            return old_state, new_state

        @staticmethod
        def get_snapshot(value: Any) -> Any:
            """
            Create a deep copy of the Pandas object for snapshotting.
            """
            return value.copy()
