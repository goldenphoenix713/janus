# Container Hardening: Recursive Tracking & Restoration

## Goal
Ensure that Janus's state tracking is "unbreakable" across nested structures and consistent after branch switching.

### Problem Statement
1. **Shallow Tracking**: [TrackedList](file:///Users/eddie/python_projects/janus/src/containers.rs#7-12) and [TrackedDict](file:///Users/eddie/python_projects/janus/src/containers.rs#231-236) do not wrap nested [list](file:///Users/eddie/python_projects/janus/src/engine.rs#157-160)/[dict](file:///Users/eddie/python_projects/janus/src/engine.rs#461-469) objects upon assignment or mutation.
2. **Restoration Leak**: When [TachyonEngine](file:///Users/eddie/python_projects/janus/src/engine.rs#107-117) restores state via [setattr](file:///Users/eddie/python_projects/janus/janus/plugins/pandas.py#102-113), it uses raw Python types, losing the tracking proxies.

## Proposed Changes

### [Component] Rust Engine ([src/containers.rs](file:///Users/eddie/python_projects/janus/src/containers.rs))

#### [MODIFY] `wrap_value` Utility
Implement a helper function to recursively wrap Python containers.

```rust
fn wrap_value(py: Python, value: PyObject, engine: Py<TachyonEngine>, name: String) -> PyObject {
    if let Ok(list) = value.downcast::<PyList>(py) {
        TrackedList::new(list.to_object(py), engine, name).into_py(py)
    } else if let Ok(dict) = value.downcast::<PyDict>(py) {
        TrackedDict::new(dict.to_object(py), engine, name).into_py(py)
    } else {
        value
    }
}
```

#### [MODIFY] `TrackedDict::__setitem__` & [update](file:///Users/eddie/python_projects/janus/src/containers.rs#365-387)
- Call `wrap_value` for every new value being inserted.
- Construct the child `name` as `"{}.{}".format(self.name, key)`.

#### [MODIFY] `TrackedList::append`, [insert](file:///Users/eddie/python_projects/janus/src/containers.rs#101-119), [extend](file:///Users/eddie/python_projects/janus/src/containers.rs#160-173), [__setitem__](file:///Users/eddie/python_projects/janus/src/containers.rs#76-96)
- Call `wrap_value` for every new value.
- Construct the child `name` using index or path logic.

---

### [Component] Rust Engine ([src/engine.rs](file:///Users/eddie/python_projects/janus/src/engine.rs))

#### [MODIFY] `TachyonEngine::apply_node_deltas`
- When applying an `UpdateAttr` or `ListOp`/`DictOp` forward/backward, check if the attribute being restored is a container that was originally tracked.
- Re-wrap restored containers in their [TrackedList](file:///Users/eddie/python_projects/janus/src/containers.rs#7-12)/[TrackedDict](file:///Users/eddie/python_projects/janus/src/containers.rs#231-236) proxies.

---

### [Component] Python Tests (`tests/test_container_hardening.py`) [NEW]

#### [NEW] `test_nested_list_mutation`
Verify that `hero.data["inventory"].append("Shield")` is tracked when `hero.data` is a [TrackedDict](file:///Users/eddie/python_projects/janus/src/containers.rs#231-236).

#### [NEW] `test_restoration_type_persistence`
Verify that after [undo()](file:///Users/eddie/python_projects/janus/src/engine.rs#216-224) or [switch_branch()](file:///Users/eddie/python_projects/janus/janus/base.py#106-109), `type(hero.items)` remains [TrackedList](file:///Users/eddie/python_projects/janus/src/containers.rs#7-12), not [list](file:///Users/eddie/python_projects/janus/src/engine.rs#157-160).

## Verification Plan

### Automated Tests
- `pytest tests/test_container_hardening.py`
- `pytest tests/test_tracked_list_api.py` (regression)
- `pytest tests/test_tracked_dict_api.py` (regression)

### Manual Verification
- Inspect the [extract_timeline()](file:///Users/eddie/python_projects/janus/src/engine.rs#255-406) output for nested operations to ensure paths like `data.inventory` are correctly logged.
