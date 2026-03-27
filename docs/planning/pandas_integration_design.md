# Pandas Integration for Janus — Design Analysis

This document evaluates **five distinct implementation approaches** for integrating `pandas.DataFrame` tracking into Janus, analyzing tradeoffs across efficiency, ergonomics, and architectural fit. It also addresses the fundamental question of _how_ to hook into the pandas library.

---

## Context: How Janus Tracks State Today

Janus tracks mutations via `JanusBase.__setattr__`, which intercepts attribute assignments. For registered types, it delegates to a [JanusAdapter](file:///Users/eddie/python_projects/janus/janus/registry.py#4-9) (protocol with [get_delta](file:///Users/eddie/python_projects/janus/tests/test_plugins.py#14-20), [apply_inverse](file:///Users/eddie/python_projects/janus/tests/test_plugins.py#21-24), [apply_forward](file:///Users/eddie/python_projects/janus/tests/test_plugins.py#25-28), [get_snapshot](file:///Users/eddie/python_projects/janus/tests/test_plugins.py#29-32)). Deltas are stored as opaque `PyObject` blobs inside `PluginOp` nodes in the Rust DAG.

The core constraint is: **Janus only sees mutations when [**setattr**](file:///Users/eddie/python_projects/janus/janus/base.py#10-43) fires.** For in-place mutations (e.g., `obj.df["col"] = 5`), Janus requires the user to re-assign (`obj.df = obj.df`) or uses the Shadow Snapshot mechanism to detect drift.

---

## The Hooking Question: How Do We Intercept DataFrame Mutations?

There are three fundamental levels at which we can integrate with pandas:

| Level | Mechanism | Captures In-Place? | Ergonomics |
| :--- | :--- | :--- | :--- |
| **Attribute-level** (current adapter system) | [**setattr**](file:///Users/eddie/python_projects/janus/janus/base.py#10-43) intercept + Shadow Snapshot | Only on re-assignment | User must `obj.df = obj.df` after in-place ops |
| **Accessor-level** (`df.janus.method()`) | `register_dataframe_accessor` | No — advisory only | Natural pandas idiom, but doesn't auto-track |
| **Proxy/Wrapper** (custom class wrapping `DataFrame`) | `__getattr__` delegation + method interception | Yes — intercepts all calls | Transparent, but heavy implementation |

> [!IMPORTANT]
> None of these approaches can transparently intercept arbitrary pandas operations without _some_ tradeoff. The key design decision is where to place the complexity: in the user's workflow, in the adapter's delta strategy, or in a proxy layer.

---

## Approach 1: Full-Snapshot Adapter (Simplest)

**Strategy:** Store a complete `DataFrame.copy()` as the delta on every mutation.

```python
@register_adapter(pd.DataFrame)
class PandasSnapshotAdapter(JanusAdapter):
    def get_delta(self, old_snapshot, new_state):
        return (old_snapshot, new_state.copy())

    def apply_inverse(self, target, delta_blob):
        old_df, _ = delta_blob
        # Replace entire DataFrame contents in-place
        target.__dict__.update(old_df.__dict__)

    def apply_forward(self, target, delta_blob):
        _, new_df = delta_blob
        target.__dict__.update(new_df.__dict__)

    def get_snapshot(self, value):
        return value.copy()
```

| Metric | Assessment |
| :--- | :--- |
| **Memory** | ❌ **O(N × M)** per mutation — stores full copy of entire DataFrame every time |
| **Delta speed** | ✅ O(1) — just `.copy()` |
| **Restore speed** | ✅ O(1) — dict swap |
| **Implementation** | ✅ Trivial — ~20 lines |
| **Correctness** | ✅ Guaranteed — full state snapshot |

**Verdict:** Good for prototyping and small DataFrames (< 10K rows). Becomes a severe memory bottleneck for production-scale data. This is essentially the Memento pattern.

---

## Approach 2: Column-Level Diff Adapter (Balanced)

**Strategy:** Detect which columns changed and store only the affected column data.

```python
@register_adapter(pd.DataFrame)
class PandasColumnDiffAdapter(JanusAdapter):
    def get_delta(self, old_snapshot, new_state):
        old_cols = set(old_snapshot.columns) if old_snapshot is not None else set()
        new_cols = set(new_state.columns)

        delta = {"added": {}, "removed": {}, "modified": {}, "shape_changed": False}

        # Added columns
        for col in new_cols - old_cols:
            delta["added"][col] = new_state[col].copy()

        # Removed columns
        for col in old_cols - new_cols:
            delta["removed"][col] = old_snapshot[col].copy()

        # Modified columns (value comparison)
        for col in old_cols & new_cols:
            if not old_snapshot[col].equals(new_state[col]):
                delta["modified"][col] = {
                    "old": old_snapshot[col].copy(),
                    "new": new_state[col].copy(),
                }

        # Row-level shape change (index change)
        if old_snapshot is not None and not old_snapshot.index.equals(new_state.index):
            delta["shape_changed"] = True
            delta["old_index"] = old_snapshot.index.copy()
            delta["new_index"] = new_state.index.copy()
            # Fall back to full snapshot for row mutations
            delta["old_full"] = old_snapshot.copy()
            delta["new_full"] = new_state.copy()

        return delta

    def apply_inverse(self, target, delta):
        if delta.get("shape_changed"):
            target.__dict__.update(delta["old_full"].__dict__)
            return

        for col, series in delta["added"].items():
            target.drop(columns=[col], inplace=True)
        for col, series in delta["removed"].items():
            target[col] = series
        for col, info in delta["modified"].items():
            target[col] = info["old"]

    def apply_forward(self, target, delta):
        if delta.get("shape_changed"):
            target.__dict__.update(delta["new_full"].__dict__)
            return

        for col, series in delta["removed"].items():
            target.drop(columns=[col], inplace=True)
        for col, series in delta["added"].items():
            target[col] = series
        for col, info in delta["modified"].items():
            target[col] = info["new"]

    def get_snapshot(self, value):
        return value.copy()
```

| Metric | Assessment |
| :--- | :--- |
| **Memory** | 🟡 **O(C × R)** where C = changed columns, R = rows — saves nothing if all columns change |
| **Delta speed** | 🟡 O(cols) — column-by-column equality check |
| **Restore speed** | ✅ O(C) — only touches changed columns |
| **Implementation** | 🟡 Moderate — ~80 lines, needs edge-case handling |
| **Correctness** | 🟡 Falls back to full snapshot for row mutations (safe but costly) |

**Verdict:** A pragmatic middle ground. Efficient for the common case of modifying a few columns. The column-level `equals()` comparison is the main cost.

---

## Approach 3: Cell-Level Sparse Diff Adapter (Most Efficient)

**Strategy:** Identify changed cells and store only [(row, col, old_val, new_val)](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#40-41) tuples.

```python
@register_adapter(pd.DataFrame)
class PandasSparseDiffAdapter(JanusAdapter):
    def get_delta(self, old_snapshot, new_state):
        if old_snapshot is None:
            return {"type": "init", "snapshot": new_state.copy()}

        # Structural changes → fall back to full snapshot
        if not old_snapshot.columns.equals(new_state.columns) or \
           not old_snapshot.index.equals(new_state.index):
            return {
                "type": "structural",
                "old": old_snapshot.copy(),
                "new": new_state.copy(),
            }

        # Cell-level diff using numpy comparison
        import numpy as np
        mask = old_snapshot.values != new_state.values
        changed_rows, changed_cols = np.where(mask)

        patches = []
        for r, c in zip(changed_rows, changed_cols):
            patches.append((
                int(r), int(c),
                old_snapshot.iat[r, c],
                new_state.iat[r, c],
            ))

        return {"type": "patch", "patches": patches}

    def apply_inverse(self, target, delta):
        if delta["type"] in ("init", "structural"):
            target.__dict__.update(delta.get("old", delta["snapshot"]).__dict__)
            return

        for r, c, old_val, _ in delta["patches"]:
            target.iat[r, c] = old_val

    def apply_forward(self, target, delta):
        if delta["type"] in ("init", "structural"):
            target.__dict__.update(delta.get("new", delta["snapshot"]).__dict__)
            return

        for r, c, _, new_val in delta["patches"]:
            target.iat[r, c] = new_val

    def get_snapshot(self, value):
        return value.copy()
```

| Metric | Assessment |
| :--- | :--- |
| **Memory** | ✅ **O(P)** where P = number of changed cells — optimal for sparse edits |
| **Delta speed** | 🟡 **O(N × M)** — full element-wise comparison via numpy |
| **Restore speed** | ✅ O(P) — touches only changed cells |
| **Implementation** | 🟡 Moderate — ~70 lines, numpy required |
| **Correctness** | 🟡 `!=` comparison has edge cases with NaN, mixed dtypes |

**Verdict:** Best memory efficiency for cell-level edits. The [get_snapshot()](file:///Users/eddie/python_projects/janus/tests/test_plugins.py#29-32) call (which triggers a full DataFrame copy for the shadow) is the real bottleneck — it runs on _every_ [**setattr**](file:///Users/eddie/python_projects/janus/janus/base.py#10-43), regardless of whether anything changed.

> [!WARNING]
> **The hidden cost across all adapter approaches:** [get_snapshot()](file:///Users/eddie/python_projects/janus/tests/test_plugins.py#29-32) must produce a full copy of the DataFrame to serve as the "old state" for the next delta. This O(N×M) copy runs on every tracked assignment, even if the adapter's delta is sparse.

---

## Approach 4: Pandas Accessor + Explicit Commands (Most Ergonomic)

**Strategy:** Instead of auto-tracking through [**setattr**](file:///Users/eddie/python_projects/janus/janus/base.py#10-43), provide a pandas-native accessor that users call explicitly to checkpoint and restore state.

```python
import pandas as pd

@pd.api.extensions.register_dataframe_accessor("janus")
class JanusAccessor:
    def __init__(self, df):
        self._df = df
        self._history = []  # Stack of snapshots
        self._redo_stack = []

    def checkpoint(self, label=None):
        """Save the current state."""
        self._history.append((label, self._df.copy()))
        self._redo_stack.clear()

    def undo(self):
        """Restore to the previous checkpoint."""
        if not self._history:
            raise ValueError("Nothing to undo")
        label, snapshot = self._history.pop()
        self._redo_stack.append((label, self._df.copy()))
        # In-place restore
        self._df.__dict__.update(snapshot.__dict__)

    def redo(self):
        """Re-apply the last undone change."""
        if not self._redo_stack:
            raise ValueError("Nothing to redo")
        label, snapshot = self._redo_stack.pop()
        self._history.append((label, self._df.copy()))
        self._df.__dict__.update(snapshot.__dict__)

    @property
    def history(self):
        return [(label or f"step-{i}") for i, (label, _) in enumerate(self._history)]
```

### Usage

```python
df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
df.janus.checkpoint("initial")

df["C"] = [7, 8, 9]
df.janus.checkpoint("added column C")

df.janus.undo()
assert "C" not in df.columns
```

| Metric | Assessment |
| :--- | :--- |
| **Memory** | 🟡 Full copy per checkpoint (but user controls frequency) |
| **Delta speed** | ✅ N/A — no automatic computation |
| **Restore speed** | ✅ O(1) — dict swap |
| **Implementation** | ✅ Simple — ~50 lines, standalone |
| **Correctness** | ✅ Guaranteed — full snapshots |
| **Janus integration** | ❌ **Standalone** — does not integrate with the TachyonEngine DAG or branching |

**Verdict:** Excellent ergonomics as a standalone feature, but **does not integrate with Janus's core value prop** (the Rust DAG, branching, timeline extraction). Best suited as a lightweight companion utility or as a user-facing convenience layer _on top of_ one of the adapter approaches.

---

## Approach 5: Hybrid Proxy Wrapper (Most Complete)

**Strategy:** Wrap a `DataFrame` in a proxy class that intercepts mutating operations and automatically logs to Janus, while also providing a pandas accessor for convenience.

```python
class TrackedDataFrame:
    """A Janus-aware proxy for pd.DataFrame."""

    _MUTATING_METHODS = {
        "drop", "rename", "fillna", "replace", "sort_values",
        "reset_index", "set_index", "assign", "__setitem__",
        "__delitem__", "insert", "pop",
    }

    def __init__(self, df, engine, name):
        object.__setattr__(self, "_df", df.copy())
        object.__setattr__(self, "_engine", engine)
        object.__setattr__(self, "_name", name)

    def __getattr__(self, attr):
        result = getattr(self._df, attr)

        if attr in self._MUTATING_METHODS and callable(result):
            def tracked_method(*args, **kwargs):
                snapshot = self._df.copy()
                ret = result(*args, **kwargs)

                # If method returns a new DataFrame (non-inplace), swap it in
                if isinstance(ret, pd.DataFrame):
                    object.__setattr__(self, "_df", ret)

                self._engine.log_plugin_op(
                    self._name,
                    "TrackedDataFrameAdapter",
                    (snapshot, self._df.copy()),
                )
                return self  # Enable chaining

            return tracked_method

        return result

    def __setitem__(self, key, value):
        snapshot = self._df.copy()
        self._df[key] = value
        self._engine.log_plugin_op(
            self._name,
            "TrackedDataFrameAdapter",
            (snapshot, self._df.copy()),
        )

    def __repr__(self):
        return repr(self._df)
```

| Metric | Assessment |
| :--- | :--- |
| **Memory** | ❌ Full copy before/after every mutating call |
| **Delta speed** | 🟡 O(N×M) — full copy for snapshot |
| **Restore speed** | ✅ O(1) — swap |
| **Implementation** | ❌ **Heavy** — must enumerate all mutating methods, handle chaining, edge cases |
| **Correctness** | 🟡 Risk of missing methods; pandas has ~200 DataFrame methods |
| **Ergonomics** | ✅ Transparent — users work with `obj.df["col"] = val` normally |

**Verdict:** Most transparent UX but extremely heavy to implement correctly. The "enumerate all mutating methods" problem is a maintenance nightmare as pandas evolves.

---

## Recommendation Matrix

| Approach | Memory | Speed | Correctness | Ergonomics | Janus Integration | Recommended For |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Full Snapshot** | ❌ | ✅ | ✅ | 🟡 | ✅ | Small DataFrames, prototyping |
| **2. Column Diff** | 🟡 | 🟡 | 🟡 | 🟡 | ✅ | General use, column-centric workflows |
| **3. Sparse Diff** | ✅ | 🟡 | 🟡 | 🟡 | ✅ | Large DataFrames with sparse edits |
| **4. Accessor** | 🟡 | ✅ | ✅ | ✅ | ❌ | Standalone pandas workflows |
| **5. Proxy Wrapper** | ❌ | 🟡 | 🟡 | ✅ | ✅ | Full transparency (if maintainable) |

---

## Recommended Strategy: Layered Approach

> [!TIP]
> The strongest design combines approaches rather than picking one.

### Layer 1: Column-Diff Adapter (default)

Implement Approach 2 as `PandasAdapter` in `janus/adapters/pandas_adapter.py`. This plugs into the existing adapter registry and works immediately with `JanusBase.__setattr__`. It is the right balance of efficiency and simplicity.

### Layer 2: Configurable Delta Strategy

Allow users to select their diff strategy via a parameter:

```python
@register_adapter(pd.DataFrame)
class PandasAdapter(JanusAdapter):
    strategy: str = "column"  # "full", "column", or "sparse"
```

This lets power users opt into Approach 3 (sparse) for large DataFrames or Approach 1 (full) for guaranteed correctness.

### Layer 3 (Optional): Pandas Accessor as Convenience

Optionally register a `df.janus` accessor that wraps common Janus operations. This is additive and doesn't replace the adapter.

---

## The [get_snapshot](file:///Users/eddie/python_projects/janus/tests/test_plugins.py#29-32) Bottleneck

Across all adapter-based approaches (1–3), the [get_snapshot()](file:///Users/eddie/python_projects/janus/tests/test_plugins.py#29-32) call in [base.py:29](file:///Users/eddie/python_projects/janus/janus/base.py#L29) is potentially the biggest performance concern.  Every [**setattr**](file:///Users/eddie/python_projects/janus/janus/base.py#10-43) that assigns a DataFrame triggers a full `.copy()`. Possible mitigations:

1. **Copy-on-write (pandas 3.0+):** `pd.options.mode.copy_on_write = True` makes `.copy()` nearly free until the copy is mutated.
2. **Lazy snapshots:** Store a reference + generation counter; only materialize the copy when a delta is actually needed.
3. **Structural sharing:** Use PyArrow-backed DataFrames where columnar slices share memory.

These optimizations are independent of the delta strategy and should be considered during implementation.
