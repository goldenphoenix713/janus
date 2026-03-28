# Janus: Project Initialization & Architecture Blueprint (Platform Edition)

## 1. Project Scope and Intent

**Janus** is a high-performance Python utility package providing non-linear "Time Travel," state-branching, and extensible state management for complex Python objects.

**The Platform Architecture:**

* **The Face (Janus):** An elegant, tiered Python API. Users can operate by inheriting from `TimelineBase` for standard undo/redo or `MultiverseBase` for Git-like branching and merging. It includes a **Plugin Registry** to extend state-tracking to third-party classes (e.g., Pandas DataFrames, PyTorch Tensors).
* **The Engine (Tachyon-RS):** A cutting-edge Rust backend accessed via PyO3. It maintains a **Directed Acyclic Graph (DAG)** of object states. By treating linear history as a constrained subset of a DAG, the engine remains unified. It logs bi-directional operations and opaque "Plugin Blobs" to achieve $O(1)$ performance overhead.

### Key Architectural Pillars

1. **Tiered Complexity:** Inheriting from `TimelineBase` vs `MultiverseBase` allows developers to opt-in to complexity.
2. **Extensible Plugin System:** An `AdapterRegistry` allows developers to define custom delta-calculators and inverse-appliers for unsupported types, feeding opaque blobs to the Rust engine.
3. **Timeline Extraction:** The ability to flatten a complex multiversal path into a single linear sequence of events.
4. **Tombstones**: If a `jump_to()` or `undo()` encounters a cleared WeakRef (meaning the object was garbage collected by Python), Tachyon marks that branch as "collapsed" and prevents invalid memory access.

---

## 2. Project Directory Structure

```text
janus/
├── Cargo.toml
├── pyproject.toml
├── README.md
├── src/
│   ├── lib.rs
│   ├── engine.rs             # DAG-based Tachyon Multiverse logic & Timeline extraction
│   └── containers.rs
├── janus/
│   ├── __init__.py
│   ├── base.py               # JanusBase, TimelineBase, MultiverseBase
│   ├── containers.py         # TrackedList, TrackedDict, wrap_value()
│   ├── registry.py           # Plugin AdapterRegistry for 3rd-party types
│   ├── tachyon_rs.pyi        # Type stubs for the Rust extension
│   └── plugins/
│       └── pandas.py         # TrackedDataFrame, TrackedSeries, indexer wrappers
└── tests/
    ├── __init__.py
    ├── test_multiverse.py    # E2E branching and switching tests
    ├── test_plugins.py       # Tests for custom adapter registration
    └── ...                   # Additional test files
```

---

## 3. Configuration Files

### `pyproject.toml`

```toml
[build-system]
requires = ["maturin>=1.5,<2.0"]
build-backend = "maturin"

[project]
name = "janus"
version = "0.2.0"
description = "Extensible, non-linear state travel powered by the Tachyon-RS engine."
authors = [{ name = "AI Dev Team", email = "dev@example.com" }]
requires-python = ">=3.12"
dependencies = []
readme = "README.md"
license = { text = "MIT OR Apache-2.0" }

[tool.maturin]
module-name = "janus.tachyon_rs"
features = ["pyo3/extension-module"]
include = ["src/**/*", "Cargo.toml"]
```

### `Cargo.toml`

```toml
[package]
name = "tachyon-rs"
version = "0.2.0"
edition = "2021"
license = "MIT OR Apache-2.0"

[lib]
name = "tachyon_rs"
crate-type = ["cdylib"]

[dependencies]
pyo3 = { version = "0.20", features = ["extension-module", "abi3-py38", "multiple-pymethods"] }
```

---

## 4. Rust Backend Implementation (`src/`)

### `src/engine.rs` (The Extensible DAG Engine)

```rust
use pyo3::prelude::*;
use std::collections::HashMap;

#[derive(Clone)]
pub enum Operation {
    UpdateAttr { name: String, old_value: PyObject, new_value: PyObject },
    ListPop { path: String, index: usize, popped_value: PyObject },
    ListInsert { path: String, index: usize, value: PyObject },
    // THE FOUNDATION FOR PLUGINS:
    // Tachyon doesn't need to know what a DataFrame is. It just stores the blob.
    PluginOp { path: String, adapter_name: String, delta_blob: PyObject },
}

// Foundation for Timeline Extraction: Nodes know their parents.
#[derive(Clone)]
pub struct StateNode {
    pub id: usize,
    pub parents: Vec<usize>,
    pub deltas: Vec<Operation>,
}

#[pyclass]
pub struct TachyonEngine {
    owner: Py<PyAny>,
    nodes: HashMap<usize, StateNode>,
    branches: HashMap<String, usize>,
    current_node: usize,
    next_node_id: usize,
    mode: String, // "linear" or "multiversal"
}

#[pymethods]
impl TachyonEngine {
    #[new]
    pub fn new(owner: Py<PyAny>, mode: String) -> Self {
        let mut branches = HashMap::new();
        branches.insert("main".to_string(), 0);

        let mut nodes = HashMap::new();
        nodes.insert(0, StateNode { id: 0, parent_id: None, deltas: Vec::new() });

        TachyonEngine {
            owner, nodes, branches,
            current_node: 0, next_node_id: 1, mode
        }
    }

    pub fn log_op(&mut self, op: Operation) {
        // Creates a new node and edge.
        // If mode == "linear", it may prune future history if we were in an "undone" state.
        let new_node = StateNode {
            id: self.next_node_id,
            parents: vec![self.current_node],
            deltas: vec![op],
        };
        self.nodes.insert(self.next_node_id, new_node);
        self.current_node = self.next_node_id;
        self.next_node_id += 1;
    }

    pub fn extract_timeline(&self, py: Python, label: String) -> PyResult<Vec<PyObject>> {
        // Walks backwards from the target leaf to the root (parent_id == None),
        // reverses the list, and returns a flat timeline of events.
        // (Implementation stubbed for blueprint)
        Ok(Vec::new())
    }

    // ... create_branch, switch_branch, and apply_inverse omitted for brevity ...
}
```

---

## 5. Python Frontend Implementation (`janus/`)

### `janus/registry.py` (The Plugin Architecture)

```python
from typing import Any, Protocol

class JanusAdapter(Protocol):
    def get_delta(self, old_state: Any, new_state: Any) -> Any: ...
    def apply_backward(self, target: Any, delta_blob: Any) -> None: ...
    def apply_forward(self, target: Any, delta_blob: Any) -> None: ...
    def get_snapshot(self, value: Any) -> Any: ...

ADAPTER_REGISTRY = {}

def register_adapter(target_class):
    """Decorator to register a custom class adapter for Janus tracking."""
    def wrapper(adapter_class):
        ADAPTER_REGISTRY[target_class] = adapter_class()
        return adapter_class
    return wrapper
```

### `janus/base.py`

```python
from .tachyon_rs import TachyonEngine
from .containers import wrap_value
from .registry import ADAPTER_REGISTRY


class JanusBase:
    """Core logic: intercepts __setattr__, delegates to TachyonEngine."""

    def __init__(self, mode: str = "multiversal") -> None:
        super().__setattr__("_restoring", False)
        super().__setattr__("_engine", TachyonEngine(self, mode))

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ["_engine", "_restoring"]:
            super().__setattr__(name, value)
            return

        if self._restoring:
            super().__setattr__(name, value)
            return

        old_value = getattr(self, name, None)

        # Plugin check via ADAPTER_REGISTRY
        value_type = type(value)
        if value_type in ADAPTER_REGISTRY:
            adapter = ADAPTER_REGISTRY[value_type]
            # ... log PluginOp with shadow snapshot ...
        else:
            value = wrap_value(value, self._engine, name)

        if not name.startswith("_"):
            self._engine.log_update_attr(name, old_value, value)

        super().__setattr__(name, value)

    def undo(self) -> None:
        self._engine.undo()

    def redo(self) -> None:
        self._engine.redo()

    def create_moment_label(self, label: str) -> None:
        self._engine.create_moment(label)

    def jump_to(self, label: str) -> None:
        self._engine.move_to(label)


class TimelineBase(JanusBase):
    def __init__(self) -> None:
        super().__init__(mode="linear")


class MultiverseBase(JanusBase):
    def __init__(self) -> None:
        super().__init__(mode="multiversal")

    def branch(self, label: str) -> None:
        self._engine.create_branch(label)

    def switch_branch(self, label: str) -> None:
        self._engine.switch_branch(label)

    def extract_timeline(self, label: str) -> list:
        return self._engine.extract_timeline(label)
```

---

## 6. AI Agent Initialization Protocol

Execute the following shell commands sequentially:

1. `mkdir janus && cd janus`
2. *Create the directory tree and paste the file contents defined in Sections 3, 4, and 5.*
3. `uv venv && source .venv/bin/activate` (or `.venv\Scripts\activate` on Windows)
4. `uv add --dev maturin pytest`
5. `uv run maturin develop`
6. `uv run pytest tests/`

---

## 7. Documentation Template Snippet (`README.md`)

```markdown
# Janus 🏺
> **The Extensible Multiverse Engine for Python Objects.**

Janus provides a Git-like API for branching, switching, and flattening the state of complex Python objects, powered by a lightning-fast Rust backend (**Tachyon-RS**).

### 🚀 Tiered Complexity
Choose the right tool for the job. Use `mode="linear"` for high-speed, standard undo/redo, or opt into `mode="multiversal"` to enable parallel state branching and graph traversal.

### 🔌 Extensible Plugin Registry
Need to track a `pandas.DataFrame` or a complex custom object? Register a `JanusAdapter` and let Tachyon-RS safely manage the state blobs without slowing down the core engine.
```
