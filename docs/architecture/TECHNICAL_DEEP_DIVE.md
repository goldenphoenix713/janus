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

## 3. Planned Features (Phase 4 & 5)

### 3.1 3-Way Merge Logic (Planned)

Merging two branches requires resolving potential conflicts. The proposed algorithm will use a 3-way merge by comparing the **Base** (Common Ancestor), the **Left** (Current Branch), and the **Right** (Target Branch).

For any given attribute or container element $x$:
...

$$
\text{Result}(x) =
\begin{cases}
L & \text{if } L \neq B \text{ and } R = B \text{ (Only Left changed)} \\
R & \text{if } R \neq B \text{ and } L = B \text{ (Only Right changed)} \\
L & \text{if } L = R \text{ (Both changed to same value)} \\
\text{CONFLICT} & \text{if } L \neq B, R \neq B, \text{ and } L \neq R
\end{cases}
$$

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
    Insert { path: String, index: usize, value: PyObject },
    Pop { path: String, index: usize, popped_value: PyObject },
    Replace { path: String, index: usize, old_value: PyObject, new_value: PyObject },
    Clear { path: String, old_values: Vec<PyObject> },
    Extend { path: String, new_values: Vec<PyObject> },
    Remove { path: String, value: PyObject },
}

pub enum DictOperation {
    Clear { path: String, keys: Vec<String>, old_values: Vec<PyObject> },
    Pop { path: String, key: String, old_value: PyObject },
    PopItem { path: String, key: String, old_value: PyObject },
    SetDefault { path: String, key: String, value: PyObject },
    Update { path: String, keys: Vec<String>, old_values: Vec<PyObject>, new_values: Vec<PyObject> },
    Delete { path: String, key: String, old_value: PyObject },
}

pub struct StateNode {
    pub id: usize,
    pub parents: Vec<usize>,
    pub deltas: Vec<Operation>,
    // Planned: pub metadata: HashMap<String, PyObject> (Waypoint 4.1)
}
```

## 5. Memory Safety: The Tombstone Strategy (Planned - Phase 5)

To prevent history logs from causing memory leaks, Tachyon-RS will employ a **Hybrid Reference Strategy**:

* **Strong References:** For immutable primitives (int, str, bool).
* **Weak References (`PyWeakref`):** For complex Python objects.
* **Tombstones:** If a `revert()` or `switch()` encounters a cleared WeakRef, Tachyon marks that branch as "collapsed".

## 6. Computational Complexity

| Operation | Complexity | Description |
| :--- | :--- | :--- |
| **Mutation** | $O(1)$ | Appending a delta to the current edge. |
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
