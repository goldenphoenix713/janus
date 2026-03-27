from __future__ import annotations

from typing import Any

from ..registry import JanusAdapter, register_adapter

try:
    import pandas as pd

    def _log_pre_mutation(obj: TrackedDataFrame | TrackedSeries, name: str):
        if hasattr(obj, "_janus_engine"):
            snapshot = obj.copy()
            snapshot._janus_engine = None
            object.__setattr__(obj, "_janus_snapshot", snapshot)

    def _log_post_mutation(obj: TrackedDataFrame | TrackedSeries, name: str):
        if hasattr(obj, "_janus_engine"):
            obj._janus_engine.log_plugin_op(
                obj._janus_name,
                obj._pandas_adapter,
                (obj._janus_snapshot, obj.copy()),
            )

    class TrackedSeries(pd.Series):
        _metadata = ["_janus_engine", "_janus_name", "_restoring"]
        _pandas_adapter = "TrackedSeriesAdapter"

        @property
        def _constructor(self):
            return TrackedSeries

        @property
        def _constructor_expandim(self):
            return TrackedDataFrame

        def __setattr__(self, key: str, value: Any):
            if key in [*self._metadata, "_restoring"]:
                return super().__setattr__(key, value)

            if getattr(self, "_restoring", False):
                return super().__setattr__(key, value)

            _log_pre_mutation(self, key)
            super().__setattr__(key, value)
            _log_post_mutation(self, key)

        def __setitem__(self, key: str, value: Any):
            if key in [*self._metadata, "_restoring"]:
                return super().__setitem__(key, value)

            if getattr(self, "_restoring", False):
                return super().__setitem__(key, value)

            _log_pre_mutation(self, key)
            super().__setitem__(key, value)
            _log_post_mutation(self, key)

    class TrackedDataFrame(pd.DataFrame):
        _metadata = ["_janus_engine", "_janus_name", "_restoring"]
        _pandas_adapter = "TrackedDataFrameAdapter"

        @property
        def _constructor(self):
            return TrackedDataFrame

        @property
        def _constructor_sliced(self):
            return TrackedSeries

        def __setattr__(self, key: str, value: Any):
            if key in [*self._metadata, "_restoring"]:
                return super().__setattr__(key, value)

            if getattr(self, "_restoring", False):
                return super().__setattr__(key, value)

            _log_pre_mutation(self, key)
            super().__setattr__(key, value)
            _log_post_mutation(self, key)

        def __setitem__(self, key: str, value: Any):
            if key in [*self._metadata, "_restoring"]:
                return super().__setitem__(key, value)

            if getattr(self, "_restoring", False):
                return super().__setitem__(key, value)

            _log_pre_mutation(self, key)
            super().__setitem__(key, value)
            _log_post_mutation(self, key)

    @register_adapter(TrackedDataFrame)
    class TrackedDataFrameAdapter(JanusAdapter):
        def get_delta(self, old_snapshot, new_state):
            # In this MVP, the delta object is just (old_df, new_df)
            return (old_snapshot, new_state.copy())

        def apply_inverse(self, target, delta_blob):
            old_df, _ = delta_blob
            target._restoring = True
            # In-place update of the underlying DataFrame
            try:
                target._mgr = old_df._mgr
                target.index = old_df.index
                target.columns = old_df.columns
            except Exception as e:
                raise RuntimeError(f"Failed to restore DataFrame: {e}")
            finally:
                target._restoring = False

        def apply_forward(self, target, delta_blob):
            _, new_df = delta_blob
            target._restoring = True
            try:
                target._mgr = new_df._mgr
                target.index = new_df.index
                target.columns = new_df.columns
            except Exception as e:
                raise RuntimeError(f"Failed to restore DataFrame: {e}")
            finally:
                target._restoring = False

        def get_snapshot(self, value):
            return value.copy()

    @register_adapter(TrackedSeries)
    class TrackedSeriesAdapter(JanusAdapter):
        def get_delta(self, old_snapshot, new_state):
            # In this MVP, the delta object is just (old_series, new_series)
            return (old_snapshot, new_state.copy())

        def apply_inverse(self, target, delta_blob):
            old_series, _ = delta_blob
            target._restoring = True
            # In-place update of the underlying Series
            try:
                target._mgr = old_series._mgr
                target.index = old_series.index
                target.name = old_series.name
            except Exception as e:
                raise RuntimeError(f"Failed to restore Series: {e}")
            finally:
                target._restoring = False

        def apply_forward(self, target, delta_blob):
            _, new_series = delta_blob
            target._restoring = True
            try:
                target._mgr = new_series._mgr
                target.index = new_series.index
                target.name = new_series.name
            except Exception as e:
                raise RuntimeError(f"Failed to restore Series: {e}")
            finally:
                target._restoring = False

        def get_snapshot(self, value):
            return value.copy()

except ImportError:
    pass
