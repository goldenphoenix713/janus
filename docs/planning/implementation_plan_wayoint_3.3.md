# Waypoint 3.3 — Pandas & NumPy Adapters + Plugin Authoring Guide

## Background

Janus's adapter system flow:

1. [JanusBase.__setattr__](file:///Users/eduardo.ruiz/PycharmProjects/Janus/janus/base.py#L10-L42) checks `ADAPTER_REGISTRY` → calls [get_delta(shadow, new)](file:///Users/eduardo.ruiz/PycharmProjects/Janus/janus/registry.py#5-6) + [get_snapshot(new)](file:///Users/eduardo.ruiz/PycharmProjects/Janus/janus/registry.py#8-9)
2. Rust engine logs a `PluginOp { path, adapter_name, delta_blob }` node
3. On undo/branch-switch, Rust calls back into Python: `adapter.apply_inverse(target, delta)` or [apply_forward(target, delta)](file:///Users/eduardo.ruiz/PycharmProjects/Janus/janus/registry.py#7-8)

This plan delivers __two production adapters__ (Pandas, NumPy) using __structural diffs__, and a __plugin authoring guide__ with PyArrow/Polars documentation examples.

---

## Proposed Changes

### Adapters Package

#### [NEW] [\_\_init\_\_.py](file:///Users/eduardo.ruiz/PycharmProjects/Janus/janus/adapters/__init__.py)

Empty [__init__.py](file:///Users/eduardo.ruiz/PycharmProjects/Janus/janus/__init__.py) — adapters are opt-in via explicit import.

---

#### [NEW] [pandas_adapter.py](file:///Users/eduardo.ruiz/PycharmProjects/Janus/janus/adapters/pandas_adapter.py)

__Delta strategy: column-level structural diffs.__ The delta blob is a dict with:

```python
{
    "added_cols":   {col: series_values, ...},   # columns in new but not old
    "removed_cols": {col: series_values, ...},   # columns in old but not new
    "modified_cells": {col: {idx: (old_val, new_val), ...}, ...},  # per-cell changes
    "index_old":    old_index,                   # for index restoration
    "index_new":    new_index,
}
```

```python
"""Janus adapter for pandas DataFrames — structural diffs."""
from __future__ import annotations

from typing import Any

import pandas as pd

from janus.registry import JanusAdapter, register_adapter


@register_adapter(pd.DataFrame)
class PandasAdapter(JanusAdapter):
    """Track DataFrame mutations via column-level structural diffs."""

    def get_snapshot(self, value: pd.DataFrame) -> pd.DataFrame:
        return value.copy(deep=True)

    def get_delta(
        self, old_state: pd.DataFrame | None, new_state: pd.DataFrame
    ) -> dict[str, Any]:
        if old_state is None:
            return {
                "added_cols": {c: new_state[c].tolist() for c in new_state.columns},
                "removed_cols": {},
                "modified_cells": {},
                "index_old": None,
                "index_new": new_state.index.tolist(),
            }

        old_cols = set(old_state.columns)
        new_cols = set(new_state.columns)

        added = {c: new_state[c].tolist() for c in (new_cols - old_cols)}
        removed = {c: old_state[c].tolist() for c in (old_cols - new_cols)}

        # Cell-level diffs for shared columns
        shared = old_cols & new_cols
        modified_cells: dict[str, dict[int, tuple]] = {}
        for col in shared:
            old_s = old_state[col]
            new_s = new_state[col]
            # Align on common index; detect changes
            common_idx = old_s.index.intersection(new_s.index)
            mask = old_s.loc[common_idx] != new_s.loc[common_idx]
            # Handle NaN != NaN  (both NaN means NOT changed)
            both_nan = old_s.loc[common_idx].isna() & new_s.loc[common_idx].isna()
            mask = mask & ~both_nan
            if mask.any():
                changed_idx = common_idx[mask]
                modified_cells[col] = {
                    int(i): (old_s.at[i], new_s.at[i]) for i in changed_idx
                }
            # Rows only in old or only in new are captured via index diff

        return {
            "added_cols": added,
            "removed_cols": removed,
            "modified_cells": modified_cells,
            "index_old": old_state.index.tolist(),
            "index_new": new_state.index.tolist(),
        }

    def apply_inverse(self, target: pd.DataFrame, delta_blob: dict) -> None:
        _apply_delta(target, delta_blob, forward=False)

    def apply_forward(self, target: pd.DataFrame, delta_blob: dict) -> None:
        _apply_delta(target, delta_blob, forward=True)


def _apply_delta(target: pd.DataFrame, delta: dict, *, forward: bool) -> None:
    """Apply or reverse a structural delta in-place."""
    if forward:
        # Remove columns that were removed
        # (in forward: removed_cols were removed, added_cols were added)
        for col in delta["removed_cols"]:
            if col in target.columns:
                del target[col]
        for col, vals in delta["added_cols"].items():
            target[col] = vals
        # Apply cell changes
        for col, changes in delta["modified_cells"].items():
            for idx, (_, new_val) in changes.items():
                target.at[idx, col] = new_val
        if delta["index_new"] is not None:
            target.index = pd.Index(delta["index_new"])
    else:
        # Inverse: undo added → remove them; undo removed → restore them
        for col in delta["added_cols"]:
            if col in target.columns:
                del target[col]
        for col, vals in delta["removed_cols"].items():
            target[col] = vals
        for col, changes in delta["modified_cells"].items():
            for idx, (old_val, _) in changes.items():
                target.at[idx, col] = old_val
        if delta["index_old"] is not None:
            target.index = pd.Index(delta["index_old"])
```

__Design notes:__

- __In-place mutations preserve object identity__ — required because the engine restores via [apply_inverse(owner.attr, delta)](file:///Users/eduardo.ruiz/PycharmProjects/Janus/janus/registry.py#6-7).
- __NaN-safe comparison__ — `both_nan` mask prevents false positives from `NaN != NaN`.
- __Index changes tracked__ — handles `reset_index()`, reindexing, and row additions.

---

#### [NEW] [numpy_adapter.py](file:///Users/eduardo.ruiz/PycharmProjects/Janus/janus/adapters/numpy_adapter.py)

__Delta strategy: sparse index-based diffs.__ The delta blob stores only changed indices:

```python
{
    "changed_indices": [(flat_idx, old_val, new_val), ...],
    "old_shape": tuple,
    "new_shape": tuple,
    "old_dtype": dtype,
    "new_dtype": dtype,
}
```

For shape changes (resize/reshape), falls back to full snapshot since the index mapping is ambiguous.

```python
"""Janus adapter for NumPy ndarrays — sparse index diffs."""
from __future__ import annotations

from typing import Any

import numpy as np

from janus.registry import JanusAdapter, register_adapter


@register_adapter(np.ndarray)
class NumpyAdapter(JanusAdapter):
    """Track NumPy array mutations via sparse changed-index diffs."""

    def get_snapshot(self, value: np.ndarray) -> np.ndarray:
        return value.copy()

    def get_delta(
        self, old_state: np.ndarray | None, new_state: np.ndarray
    ) -> dict[str, Any]:
        if old_state is None:
            return {
                "full_old": None,
                "full_new": new_state.copy(),
                "old_shape": None,
                "new_shape": new_state.shape,
            }

        old_shape = old_state.shape
        new_shape = new_state.shape

        if old_shape != new_shape:
            # Shape change → store full snapshots (index mapping is ambiguous)
            return {
                "full_old": old_state.copy(),
                "full_new": new_state.copy(),
                "old_shape": old_shape,
                "new_shape": new_shape,
            }

        # Same shape → sparse diff on flattened view
        old_flat = old_state.ravel()
        new_flat = new_state.ravel()
        diff_mask = old_flat != new_flat
        # Handle NaN: np.nan != np.nan is True, so exclude both-NaN
        if np.issubdtype(old_state.dtype, np.floating):
            both_nan = np.isnan(old_flat) & np.isnan(new_flat)
            diff_mask = diff_mask & ~both_nan
        changed = np.where(diff_mask)[0]

        return {
            "changed_indices": changed.tolist(),
            "old_values": old_flat[changed].tolist(),
            "new_values": new_flat[changed].tolist(),
            "old_shape": old_shape,
            "new_shape": new_shape,
        }

    def apply_inverse(self, target: np.ndarray, delta_blob: dict) -> None:
        _apply_delta(target, delta_blob, forward=False)

    def apply_forward(self, target: np.ndarray, delta_blob: dict) -> None:
        _apply_delta(target, delta_blob, forward=True)


def _apply_delta(target: np.ndarray, delta: dict, *, forward: bool) -> None:
    """Apply or reverse a sparse delta in-place."""
    if "full_old" in delta:
        # Full-snapshot fallback (shape change or initial assignment)
        source = delta["full_new"] if forward else delta["full_old"]
        if source is None:
            return
        shape = delta["new_shape"] if forward else delta["old_shape"]
        if target.shape != shape:
            target.resize(shape, refcheck=False)
        np.copyto(target, source)
    else:
        # Sparse application
        flat = target.ravel()
        values = delta["new_values"] if forward else delta["old_values"]
        for idx, val in zip(delta["changed_indices"], values):
            flat[idx] = val
```

__Design notes:__

- __Sparse diffs__ — only stores indices that changed. For a 1M-element array with 10 changes, stores 10 entries instead of 1M.
- __Shape-change fallback__ — when shapes differ, full snapshots are unavoidable since index correspondence is undefined.
- __`ravel()` + flat indexing__ works for any dimensionality (1D, 2D, 3D, etc.).

---

### Project Configuration

#### [MODIFY] [pyproject.toml](file:///Users/eduardo.ruiz/PycharmProjects/Janus/pyproject.toml)

```diff
 [project]
 ...
 dependencies = []
+
+[project.optional-dependencies]
+pandas = ["pandas>=2.0"]
+numpy = ["numpy>=1.24"]
+all = ["pandas>=2.0", "numpy>=1.24"]
```

---

### Tests

#### [NEW] [test_pandas_adapter.py](file:///Users/eduardo.ruiz/PycharmProjects/Janus/tests/test_pandas_adapter.py)

| # | Test | Description |
| - | ---- | ----------- |
| 1 | `test_assign_and_undo` | Assign DF → mutate → undo → verify original |
| 2 | `test_branch_switch_roundtrip` | Branch → mutate → switch → verify → switch back |
| 3 | `test_column_add_remove` | Add/remove columns, verify undo restores structure |
| 4 | `test_cell_level_diff` | Change a single cell, verify only that cell is in the delta |
| 5 | `test_inplace_mutation` | `df["col"] = ...` → re-assign → undo |
| 6 | `test_nan_handling` | NaN values don't produce false diffs |
| 7 | `test_index_change` | Reset/change index, verify undo restores original index |
| 8 | `test_empty_dataframe` | Edge case: empty DF |
| 9 | `test_timeline_contains_plugin_op` | [extract_timeline](file:///Users/eduardo.ruiz/PycharmProjects/Janus/src/engine.rs#255-406) includes `PluginOp` with correct adapter name |

#### [NEW] [test_numpy_adapter.py](file:///Users/eduardo.ruiz/PycharmProjects/Janus/tests/test_numpy_adapter.py)

| # | Test | Description |
| - | ---- | ----------- |
| 1 | `test_assign_and_undo` | Assign array → mutate → undo → verify |
| 2 | `test_branch_switch_roundtrip` | Branch → mutate → switch → verify |
| 3 | `test_sparse_diff_efficiency` | Change 1 element in large array, verify delta has 1 entry |
| 4 | `test_shape_change` | Resize array, verify undo restores shape + data |
| 5 | `test_dtype_preservation` | Verify dtype survives round-trip |
| 6 | `test_multidimensional` | 2D/3D array mutations |
| 7 | `test_nan_handling` | NaN-safe comparison |
| 8 | `test_empty_array` | Edge case: empty array |

---

### Documentation

#### [NEW] [plugin_authoring_guide.md](file:///Users/eduardo.ruiz/PycharmProjects/Janus/docs/plugin_authoring_guide.md)

Contents:

1. __Adapter protocol__ — the 4 required methods and their contracts
2. __Step-by-step tutorial__ — building a minimal adapter
3. __Design constraints__ — object identity, shadow snapshots, `_restoring` flag
4. __PyArrow example__ — complete `PyArrowAdapter` for `pyarrow.Table` (documentation only)
5. __Polars example__ — complete `PolarsAdapter` for `polars.DataFrame` (documentation only)
6. __Testing recipe__ — template test that any adapter author can copy
7. __Performance tips__ — full-snapshot vs. structural diffs trade-offs

---

## Verification Plan

```bash
# Rebuild Rust engine
uv run maturin develop

# Run adapter tests
uv run pytest tests/test_pandas_adapter.py tests/test_numpy_adapter.py -v

# Regression check
uv run pytest tests/ -v

# Lints
uv run ruff check janus/ tests/
uv run mypy janus/
```
