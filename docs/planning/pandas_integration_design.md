# Pandas Integration for Janus — Final Design

> **Core principle:** Non-intrusive tracking that doesn't change the developer's workflow. Developers should write normal pandas code; Janus handles the bookkeeping transparently.

---

## The Subclass Approach

Pandas officially supports subclassing via three mechanisms:

| Mechanism | Purpose |
| :--- | :--- |
| `_constructor` | Returns the subclass from **every** DataFrame operation |
| `_metadata` | List of custom attributes propagated through operations |
| `_internal_names` | Temporary attributes **not** propagated through operations |

This solves all three open problems simultaneously:

1. **`isinstance`**: `TrackedDataFrame` is a real `pd.DataFrame` subclass → passes `isinstance(obj.df, pd.DataFrame)`
2. **Method chaining**: Every operation calls `_constructor` → returns a `TrackedDataFrame` → each step can be logged
3. **In-place mutations**: Overriding [**setitem**](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#59-60), [**delitem**](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#60-61), and indexer properties intercepts mutations directly

> [!NOTE]
> GeoPandas' `GeoDataFrame` is the canonical real-world example of this pattern, relied upon by thousands of production projects.

---

## Architecture

```python
class TrackedSeries(pd.Series):
    _metadata = ["_janus_engine", "_janus_name"]

    @property
    def _constructor(self):
        return TrackedSeries

    @property
    def _constructor_expanddim(self):
        return TrackedDataFrame


class TrackedDataFrame(pd.DataFrame):
    _metadata = ["_janus_engine", "_janus_name"]

    @property
    def _constructor(self):
        return TrackedDataFrame

    @property
    def _constructor_sliced(self):
        return TrackedSeries
```

### How `_constructor` Enables Method Chain Tracking

```python
obj.df = pd.DataFrame({"A": [1, 2, 3]})
# __setattr__ wraps this as a TrackedDataFrame

result = obj.df.sort_values("A").reset_index(drop=True)
# sort_values() internally calls _constructor → returns TrackedDataFrame
# reset_index() internally calls _constructor → returns TrackedDataFrame
# Each step can optionally log a delta
```

Because `_constructor` returns `TrackedDataFrame`, the Janus-aware type **propagates through every pandas operation** without any intervention.

### How `_metadata` Propagates Engine References

When pandas creates a new DataFrame from an operation, it copies all attributes listed in `_metadata` from the source. So `_janus_engine` and `_janus_name` automatically flow through to derived DataFrames — no manual wiring needed.

---

## Mutation Interception Layers

### Layer 1 — Direct Column Assignment (Critical)

Override [**setitem**](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#59-60) and [**delitem**](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#60-61):

```python
class TrackedDataFrame(pd.DataFrame):
    def __setitem__(self, key, value):
        self._log_pre_mutation()
        super().__setitem__(key, value)
        self._log_post_mutation()

    def __delitem__(self, key):
        self._log_pre_mutation()
        super().__delitem__(key)
        self._log_post_mutation()
```

### Layer 2 — Indexer Wrappers (`.loc`, `.iloc`, `.at`, `.iat`)

Override the indexer properties to return tracked wrappers:

```python
@property
def loc(self):
    return TrackedLocIndexer("loc", self)

class TrackedLocIndexer:
    def __init__(self, name, parent):
        self._parent = parent
        self._indexer = parent.__class__.__bases__[0].loc.fget(parent)

    def __getitem__(self, key):
        return self._indexer[key]

    def __setitem__(self, key, value):
        self._parent._log_pre_mutation()
        self._indexer[key] = value
        self._parent._log_post_mutation()
```

### Layer 3 — `inplace=True` Methods (Lower Priority)

Methods accepting `inplace=True` can be intercepted via `__finalize__`, which pandas calls on all new DataFrame results:

```python
def __finalize__(self, other, method=None, **kwargs):
    result = super().__finalize__(other, method=method, **kwargs)
    # Log if this finalization represents a mutation
    return result
```

> [!NOTE]
> Pandas is deprecating `inplace=True` across many methods. This layer is lower priority.

### Layer 4 — Non-Inplace Method Chaining

When `inplace=False` (the default), the method returns a **new** `TrackedDataFrame` (via `_constructor`). If the user assigns it back to the tracked attribute (`obj.df = result`), `JanusBase.__setattr__` handles logging. No proxy interception needed.

For chain-tracking (logging each step), `__finalize__` or `_constructor` can optionally log deltas. This is configurable because it's memory-intensive.

---

## Delta Strategy

Start with **full-snapshot deltas** for correctness:

```python
def _log_pre_mutation(self):
    if self._janus_engine is not None:
        object.__setattr__(self, "_janus_snapshot", self.copy())

def _log_post_mutation(self):
    if self._janus_engine is not None:
        snapshot = object.__getattribute__(self, "_janus_snapshot")
        self._janus_engine.log_plugin_op(
            self._janus_name,
            "TrackedDataFrameAdapter",
            (snapshot, self.copy()),
        )
```

Later phases optimize to column-diff or sparse-cell deltas.

### Pandas 2.x vs 3.x Performance Note

| Version | `.copy()` Cost | Impact |
| :--- | :--- | :--- |
| **pandas 2.x** | Full deep copy — O(N×M) | Snapshot on every mutation is expensive |
| **pandas 3.x** | Copy-on-write — near O(1) | `.copy()` is lazy; only materializes on write |

> [!IMPORTANT]
> Both pandas 2.x and 3.x will be supported. The user-facing documentation should note that **pandas 3.x is significantly faster** due to copy-on-write making snapshot operations nearly free.

---

## Integration Into [base.py](file:///Users/eddie/python_projects/janus/janus/base.py)

```python
# In JanusBase.__setattr__
elif isinstance(value, pd.DataFrame):
    tracked = TrackedDataFrame(value)
    tracked._janus_engine = self._engine
    tracked._janus_name = name
    value = tracked
```

A corresponding adapter is registered for restoration during branch switching:

```python
@register_adapter(TrackedDataFrame)
class TrackedDataFrameAdapter(JanusAdapter):
    def get_delta(self, old_snapshot, new_state):
        return (old_snapshot, new_state.copy())

    def apply_inverse(self, target, delta_blob): ...
    def apply_forward(self, target, delta_blob): ...
    def get_snapshot(self, value): return value.copy()
```

---

## Phased Implementation Scope

### Phase A — Core Subclass (MVP)

- `TrackedDataFrame(pd.DataFrame)` with `_constructor`, `_metadata`
- `TrackedSeries(pd.Series)` companion
- [**setitem**](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#59-60) / [**delitem**](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#60-61) interception with full-snapshot deltas
- Integration into `base.py.__setattr__`
- Round-trip test: assign → mutate column → undo → verify
- Adapter for branch-switching restoration

### Phase B — Indexer Wrappers

- `TrackedLocIndexer`, `TrackedIlocIndexer`, `TrackedAtIndexer`, `TrackedIatIndexer`
- `.loc[r, c] = val` and `.iloc[r, c] = val` mutations logged
- Tests for cell-level, slice, and boolean mask assignment

### Phase C — `inplace=True` + Chain Tracking

- Optional `__finalize__`-based chain tracking (configurable)
- `inplace=True` detection and snapshot wrapping
- User-configurable `track_chain_steps=False` default

### Phase D — Delta Strategy Optimization

- Column-level diff as default strategy
- Sparse cell-level diff as opt-in
- Benchmark comparisons across strategies
- Pandas version detection for CoW optimization hints

---

## Risks and Mitigations

| Risk | Mitigation |
| :--- | :--- |
| `_constructor` doesn't propagate `_janus_engine` in edge cases | `_metadata` is the official pandas mechanism; well-tested in geopandas |
| [**setitem**](file:///Users/eddie/python_projects/janus/janus/tachyon_rs.pyi#59-60) override misses some assignment pathways | Indexer wrappers (Phase B) cover `.loc`/`.iloc`; shadow snapshot catches remaining drift |
| Subclass returned from operations loses engine ref | `_metadata` propagation handles this; add defensive `None` checks on `_janus_engine` |
| Memory cost of snapshots on pandas 2.x | Document clearly; recommend pandas 3.x for production use |
| Pandas internal API changes break subclass behavior | Pin minimum pandas version; test against 2.x and 3.x in CI |
