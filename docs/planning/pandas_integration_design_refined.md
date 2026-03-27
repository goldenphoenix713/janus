# Pandas Integration for Janus — Refined Design

> This document refines the pandas integration strategy based on Janus's core design principle: **non-intrusive state tracking that doesn't change a developer's workflow.**

---

## Design Principle

Janus tracks [list](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#31-32) and [dict](file:///Users/eddie/python_projects/janus/src/engine.rs#461-469) mutations transparently via [TrackedList](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#35-54) and [TrackedDict](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#55-77) — Rust proxy classes that intercept mutations and log operations to the DAG. The developer writes normal Python; Janus handles the bookkeeping.

A `TrackedDataFrame` should follow the same pattern: when a user assigns a `pd.DataFrame` to a tracked object's attribute, Janus silently wraps it in a proxy that intercepts in-place mutations and logs them as `PluginOp` deltas.

---

## The In-Place vs. Non-In-Place Distinction

This is the most important architectural insight:

| Operation Style | Example | Who Handles It? |
| :--- | :--- | :--- |
| **Re-assignment** | `obj.df = obj.df.sort_values("A")` | `JanusBase.__setattr__` — fires naturally |
| **In-place mutation** | `obj.df["new_col"] = [1, 2, 3]` | **`TrackedDataFrame` proxy** — must intercept |
| **`inplace=True`** | `obj.df.drop("col", inplace=True)` | **`TrackedDataFrame` proxy** — must intercept |

Non-inplace pandas methods return a **new** DataFrame, leaving the original untouched. If the user assigns the result back (`obj.df = result`), [__setattr__](file:///Users/eddie/python_projects/janus/janus/base.py#10-43) fires and Janus tracks it automatically. **No proxy needed for this case.**

The proxy's job is strictly to catch mutations that **modify the DataFrame in-place** without triggering [__setattr__](file:///Users/eddie/python_projects/janus/janus/base.py#10-43) on the owning object.

---

## DataFrame Mutation Surface Analysis

### Tier 1 — Direct Item Assignment (Critical)

These are the most common in-place mutations and must be intercepted by the proxy's own dunder methods:

| Pathway | Example | Mechanism |
| :--- | :--- | :--- |
| [__setitem__](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#59-60) | `df["col"] = values` | Column assignment/creation |
| [__delitem__](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#60-61) | `del df["col"]` | Column deletion |

### Tier 2 — Indexer Accessors (Important)

These return intermediate objects (`.loc` → `_LocIndexer`) that themselves support [__setitem__](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#59-60):

| Pathway | Example | Mechanism |
| :--- | :--- | :--- |
| `.loc[r, c] = val` | `df.loc[0, "A"] = 5` | Label-based cell/slice assignment |
| `.iloc[r, c] = val` | `df.iloc[0, 0] = 5` | Position-based cell/slice assignment |
| `.at[r, c] = val` | `df.at[0, "A"] = 5` | Fast scalar label-based |
| `.iat[r, c] = val` | `df.iat[0, 0] = 5` | Fast scalar position-based |

> [!WARNING]
> **The Chained Indexer Problem:** When a user accesses `df.loc`, pandas returns a `_LocIndexer` object. If we return the real indexer, its [__setitem__](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#59-60) mutates the underlying DataFrame without going through our proxy. We must return **wrapped indexers** that intercept the write and log a delta.

### Tier 3 — Methods with `inplace=True` (Lower Priority)

These are methods that accept `inplace=True` to mutate the DataFrame directly:

| Method | What It Does |
| :--- | :--- |
| `drop()` | Remove rows/columns |
| `rename()` | Rename columns/index |
| `fillna()` | Fill missing values |
| [replace()](file:///Users/eddie/python_projects/janus/src/engine.rs#421-436) | Replace values |
| `sort_values()` / `sort_index()` | Reorder rows |
| `reset_index()` / `set_index()` | Change the index |
| `drop_duplicates()` | Remove duplicate rows |
| `dropna()` | Remove rows with NaN |

> [!NOTE]
> Pandas is deprecating `inplace=True` in many methods (targeting removal in pandas 3.0+). The proxy could handle these by snapshotting before the call and diffing after, but this is lower priority since the idiomatic pattern is shifting toward non-inplace returns.

### Tier 4 — Inherently In-Place Methods

| Method | What It Does |
| :--- | :--- |
| [insert(loc, col, value)](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#44-45) | Insert column at position (no [inplace](file:///Users/eddie/python_projects/janus/tests/test_plugins.py#54-77) param — always mutates) |
| [pop(col)](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#40-41) | Remove and return a column |
| [update(other)](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#67-68) | Modify in place using non-NA values from another DataFrame |

---

## The `TrackedDataFrame` Proxy Architecture

```text
┌───────────────────────────────────────────────┐
│  TrackedDataFrame (Python proxy)              │
│                                               │
│  ._df         → actual pd.DataFrame           │
│  ._engine     → TachyonEngine reference        │
│  ._name       → attribute name on owner        │
│                                               │
│  __setitem__   → snapshot, mutate, log delta   │
│  __delitem__   → snapshot, mutate, log delta   │
│  __getattr__   → delegate reads to ._df        │
│  loc / iloc    → return TrackedLocIndexer      │
│  at / iat      → return TrackedAtIndexer       │
│                                               │
│  (Tier 3 inplace methods handled via          │
│   __getattr__ wrapper that detects inplace)    │
└───────────────────────────────────────────────┘
```

### Key Behaviors

1. **Read operations** (selecting, slicing, aggregations, `.head()`, `.describe()`, etc.) → **Pass through unchanged** via `__getattr__` delegation.

2. **Non-inplace method calls** (e.g., `df.sort_values("A")`) → Return a plain `pd.DataFrame`. If the user assigns it back, [__setattr__](file:///Users/eddie/python_projects/janus/janus/base.py#10-43) handles tracking.

3. **[__setitem__](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#59-60) / [__delitem__](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#60-61)** → Snapshot → mutate the inner `_df` → compute delta → log `PluginOp`.

4. **`.loc` / `.iloc` / `.at` / `.iat`** → Return a thin wrapper that intercepts [__setitem__](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#59-60) and delegates [__getitem__](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#61-62) to the real indexer.

5. **`inplace=True` methods** → Intercepted via `__getattr__`: if the method is in a known set and `inplace=True` is in the kwargs, wrap the call with snapshot/delta bookkeeping.

---

## Delta Strategy Within the Proxy

The proxy's delta strategy is independent of how it intercepts mutations. Three options:

### Option A — Full Snapshot Delta

```python
def _log_mutation(self):
    old = self._snapshot
    new = self._df.copy()
    self._engine.log_plugin_op(self._name, "TrackedDataFrame", (old, new))
    self._snapshot = new
```

- **Pro:** Simple, correct, fast delta creation
- **Con:** O(N×M) memory per mutation

### Option B — Column-Level Delta

Detect which columns changed between snapshot and current state. Store only affected columns.

- **Pro:** Good savings for column-centric operations (the common case)
- **Con:** Still O(R) per changed column; falls back to full snapshot for structural changes

### Option C — Sparse Cell Delta

Use numpy element-wise comparison to find changed cells. Store [(row, col, old, new)](file:///Users/eddie/python_projects/janus/src/engine.rs#120-156) patches.

- **Pro:** Optimal for sparse edits
- **Con:** O(N×M) comparison cost; NaN comparison edge cases

> [!TIP]
> **Recommendation:** Start with **Option A** (full snapshot) for correctness, then optimize to **Option B** once the proxy mechanics are proven. Option C can be added later as a configurable strategy for power users.

---

## Hook Into [base.py](file:///Users/eddie/python_projects/janus/janus/base.py)

The proxy integrates into `JanusBase.__setattr__` following the same pattern as [TrackedList](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#35-54) and [TrackedDict](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#55-77):

```python
# In JanusBase.__setattr__
elif isinstance(value, pd.DataFrame):
    value = TrackedDataFrame(value, self._engine, name)
```

This is the simplest integration point. The `TrackedDataFrame` is a Python class (not Rust) because:

1. It needs to interact heavily with pandas Python APIs
2. The mutation interception is at the Python level (dunder methods)
3. The actual delta computation uses pandas/numpy operations
4. The logging still goes through the Rust [TachyonEngine](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#5-34) via [log_plugin_op](file:///Users/eddie/python_projects/janus/src/engine.rs#174-182)

---

## Phased Implementation Scope

### Phase A — Core Proxy (MVP)

- `TrackedDataFrame` with [__setitem__](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#59-60), [__delitem__](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#60-61), `__getattr__` delegation
- Full-snapshot delta strategy (Option A)
- Integration into `base.py.__setattr__`
- Round-trip test: assign → mutate → undo → verify

### Phase B — Indexer Wrappers

- `TrackedLocIndexer`, `TrackedIlocIndexer`, `TrackedAtIndexer`, `TrackedIatIndexer`
- `.loc[r, c] = val` and `.iloc[r, c] = val` mutations logged
- Tests for cell-level, slice, and boolean mask assignment

### Phase C — `inplace=True` Interception

- Wrap known methods that accept `inplace=True`
- Detect `inplace=True` in kwargs and add snapshot/delta bookkeeping
- Test with `drop`, `fillna`, `rename`, `sort_values`

### Phase D — Delta Strategy Optimization

- Column-level diff (Option B) as default
- Configurable strategy parameter
- Benchmark comparisons across strategies

---

## Open Questions

1. **Should `TrackedDataFrame` support `isinstance(obj.df, pd.DataFrame)` checks?** This requires either subclassing `pd.DataFrame` (fragile) or registering with `abc.ABCMeta` (partial). The [TrackedList](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#35-54)/[TrackedDict](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#55-77) in Rust don't pass `isinstance` checks for [list](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#31-32)/[dict](file:///Users/eddie/python_projects/janus/src/engine.rs#461-469) today — is that acceptable for DataFrame too?

2. **What about method chaining?** E.g., `obj.df.dropna().sort_values("A")` — since these are non-inplace, they return plain DataFrames and only matter if assigned back.

3. **Pandas version target?** Pandas 3.0's copy-on-write significantly changes the snapshot cost equation. If targeting 3.0+, [get_snapshot()](file:///Users/eddie/python_projects/janus/janus/registry.py#8-9) via `.copy()` becomes nearly free.
