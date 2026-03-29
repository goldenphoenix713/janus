# Technical Deep Dive: The Physics of Janus & Tachyon-RS

This document outlines the internal mechanics of the **Janus** state-management library and the **Tachyon-RS** multiverse engine.

## 1. From Linear Stack to State Graph

While early versions of Janus used a simple LIFO (Last-In-First-Out) stack, the current architecture utilizes a **Directed Acyclic Graph (DAG)**.

In this model:

* **Nodes:** Represent a "Snapshot" or a fixed state of the object.
* **Edges:** Represent the **Operations** required to transition between nodes. Every edge in Tachyon-RS is bi-directional, containing both the `ForwardOp` and the `InverseOp`.

## 2. The Multiverse API: Branching and Switching

The DAG architecture allows for "Multiverse" management. Users can create named branches that act as pointers to specific nodes in the graph.

* **Branching:** Creates a new leaf node from the current `HEAD`.
* **Switching:** To move from `Branch_A` to `Branch_B`, Tachyon-RS performs a **Lowest Common Ancestor (LCA)** search. It then:
    1. Plays `InverseOps` from `Branch_A` up to the LCA.
    2. Plays `ForwardOps` from the LCA down to `Branch_B`.

## 3. 3-Way Branch Merging & Reconciliation

Merging two branches requires resolving potential conflicts between the **Base** (Common Ancestor), the **Target** (Current Branch), and the **Source** (Incoming Branch).

### 3.1 Attribute Merging

For simple attributes, Janus uses standard 3-way logic:

* If only one branch changed the value from the Base, that change is accepted.
* If both changed to the same value, it's accepted.
* If both changed to different values, a **Conflict** is raised (or resolved by strategy).

### 3.2 Container Reconciliation (Rebase Model)

For lists and dictionaries, Janus employs a **Rebase Strategy** rather than a simple value-check. Source operations are transformed relative to the Target's history:

* **List Indices**: If the Target inserted an item at index 0, all subsequent Source inserts at indices $\ge 0$ are shifted by 0$ to maintain their relative position.
* **Dictionary Keys**: If both branches edited the same key, a conflict is detected. If they edited different keys, the operations are safely merged.

## 4. The Tachyon-RS Engine Implementation (Rust)

The engine is implemented using an adjacency list to manage the graph nodes efficiently.

```rust
pub enum Operation {
    UpdateAttr { name: String, old_value: PyObject, new_value: PyObject },
    ListOp(ListOperation),
    DictOp(DictOperation),
    PluginOp { path: String, adapter_name: String, delta_blob: PyObject },
}

pub enum ListOperation {
    Insert { path: String, index: i64, value: PyObject },
    Pop { path: String, index: i64, popped_value: PyObject },
    Replace { path: String, index: i64, old_value: PyObject, new_value: PyObject },
    Clear { path: String, old_values: Vec<PyObject> },
    Extend { path: String, new_values: Vec<PyObject> },
    Remove { path: String, value: PyObject },
}

pub enum DictOperation {
    Update { path: String, keys: Vec<String>, old_values: Vec<PyObject>, new_values: Vec<PyObject> },
    Delete { path: String, key: String, old_value: PyObject },
    Clear { path: String, keys: Vec<String>, old_values: Vec<PyObject> },
    Pop { path: String, key: String, old_value: PyObject },
    PopItem { path: String, key: String, old_value: PyObject },
    SetDefault { path: String, key: String, value: PyObject },
}

pub struct StateNode {
    pub id: usize,
    pub parents: Vec<usize>,
    pub deltas: Vec<Operation>,
    pub metadata: HashMap<String, PyObject>,
    pub timestamp: u64,
}
```

## 5. Memory Safety: The Tombstone Strategy

To prevent history logs from causing memory leaks, Tachyon-RS employs a **Hybrid Reference Strategy**:

* **Strong References:** For immutable primitives (int, str, bool).
* **Weak References (`PyWeakref`):** For complex Python objects (the Engine owner).
* **Tombstones:** If the owner object is garbage collected, the engine enters a **Tombstone State**. Any attempt to revert or mutate state will raise a Python `ReferenceError`.

## 6. Computational Complexity

| Operation | Complexity | Description |
| :--- | :--- | :--- |
| **Mutation** | $O(1)$ | Appending a delta to the Direct Acyclic Graph. |
| **Branch** | $O(1)$ | Creating a new pointer to the current node. |
| **Switch** | $O(D)$ | $D$ is the distance to the LCA + distance to target. |
| **Merge** | $O(K)$ | $K$ is the number of deltas since the LCA. |

> *Note: $D$ is almost always significantly smaller than the total object size $N$, maintaining the performance advantage over deep-copying.*

## 7. Path Resolution & Wrap Mechanism

Tachyon-RS tracks mutations via **Hybrid Notation Pathing** (e.g., `sim.data[0].key`). The `JanusBase._resolve_path` method handles recursive resolution:

1. **Standard Attributes**: `getattr(curr, "attr")`
2. **Indexed Access**: `curr[idx]` (detected via `[...]` brackets)

## 8. Shadow Snapshots & In-Place Mutations

For third-party plugins (Pandas, NumPy), Janus uses **Shadow Snapshots** to detect in-place mutations:

1. **On Assignment**: Janus creates a hidden `_shadow_<attr>` copy.
2. **On Modification**: The next time the attribute is accessed or another assignment occurs, Janus compares the current state to the shadow.
3. **Log Delta**: `adapter.get_delta(shadow, current)` is computed and logged as a `PluginOp`.
4. **Update Shadow**: The shadow is refreshed with a new snapshot.

This allows Janus to track `df.iloc[0,0] = 99` even though it's not a direct attribute assignment on the Janus owner.

## 9. Node Metadata & Semantic Tagging

Every node in the state graph can store arbitrary Python objects as metadata. This enables:

* **Timeline Search**: Finding nodes based on user-defined metrics (e.g., `sim.tag_moment(loss=0.01)`).
* **Result Persistence**: Storing non-state data (execution time, external logs) alongside the state version.
* **Global Inspection**: Querying metadata from any node in the multiverse without jumping to it via `sim.get_all_tags(label="branch_name")`.

## 10. Timeline Filtering & Multiversal Search

As the state DAG grows, Janus provides two primary discovery mechanisms:

1. **Vertical Search (Filtering)**: Using `extract_timeline(filter_attr=["x"])`, the engine performs an $O(N)$ walk from root to leaf, but only yields operations that mutated the specified attribute(s). This is critical for debugging "when did this specific value change?".
2. **Horizontal Search (Discovery)**: Using `find_nodes_by_metadata(key, value)`, the engine performs a global lookup across all `StateNode` metadata stores. This allows joining disparite branches based on semantic tags (e.g., "Find all nodes where `loss < 0.1` regardless of branch").

## 11. Visualization Architecture

Janus employs a pluggable registry for state visualization:

### 11.1 Backend Registry

The `janus.viz` module manages a mapping of backend IDs to engine implementations.

* **Mermaid**: (Default) Text-based generator for CI/CD and Markdown environments.
* **Matplotlib**: Graphical generator using NetworkX topological layouts for local exploration.

### 11.2 Global Options

Users can configure project-wide defaults via the `janus.options` store:

```python
import janus
janus.options.plotting.backend = "matplotlib"
```
