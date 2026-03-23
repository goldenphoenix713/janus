# Janus Project Roadmap 🏺

This roadmap outlines the path to a full implementation of the **Janus** architecture, as defined in the project blueprint.

---

## 🏗️ Phase 1: The Linear Foundation (Priority 1)

*Goal: Implement the $O(1)$ state logging for basic attributes.*

- **1.1 Attribute Interception**: Complete the `JanusBase` class's `__setattr__` logic to detect changes and call the engine.
- **1.2 Delta Calculation**: Implement basic delta storage for primitives (ints, strings) in `engine.rs/Operation`.
- **1.3 Linear Mode**: Finalize `mode="linear"` to support standard undo/redo without branching.
- **⏱️ ETA: 2 Weeks**

---

## 🌌 Phase 2: Multiversal Branching & DAG (Priority 2)

*Goal: Implement the "Git-like" API for object states.*

- **2.1 Directed Acyclic Graph (DAG)**: Fully implement `StateNode` parent-child relationships in Rust. ✅
- **2.2 Branch Management**: Implement `create_branch(label)` and `switch_branch(label)` in `TachyonEngine`. ✅
- **2.3 State Restoration**: Implement the logic to "revert" an object's attributes by applying inverse deltas during branch switching. ✅ (Including `PluginOp` support!)
- **⏱️ ETA: Complete (95%)**

---

## 🔌 Phase 3: Extensible Plugin & Container System (Priority 3)

*Goal: Support complex objects (Pandas) and nested structures.*

- **3.1 AdapterRegistry**: Complete the `register_adapter` decorator and use it to handle "Plugin Blobs" in the Rust engine.
- **3.2 TrackedList & TrackedDict**: Move beyond stubs. Proxy all mutating operations (append, pop, update) to the engine.
- **3.3 Third-Party Plugins**: Initial adapters for `pandas.DataFrame` and `numpy.ndarray`.
- **⏱️ ETA: 4 Weeks**

---

## 📜 Phase 4: Timeline Extraction & Flattening (Priority 4)

*Goal: Enable path traversal and event history review.*

- **4.1 Path Traversal**: Implement `extract_timeline(label)` to return the reverse-walk from leaf to root.
- **4.2 History Flattening**: Ability to squash a multiversal branch into a linear sequence of events.
- **⏱️ ETA: 2 Weeks**

---

## 🪦 Phase 5: Tombstone Strategy & Memory Safety (Priority 5)

*Goal: Ensure memory footprint remains minimal during complex histories.*

- **5.1 Weak References**: Integrate `PyWeakref` in Rust to let the Python GC function normally.
- **5.2 History Pruning**: Implement logic to discard old nodes based on a depth or memory limit.
- **5.3 O(1) Verification**: Perform benchmarks to ensure the engine meets the performance target.
- **⏱️ ETA: 2 Weeks**

---

## Summary

| Phase | Feature Focus | Blueprint Pillar |
| :--- | :--- | :--- |
| **P1** | Linear Ops | Tiered Complexity |
| **P2** | Branching | Multiversal Mode |
| **P3** | Plugins/Containers | Extensible Plugin System |
| **P4** | Timelines | Timeline Extraction |
| **P5** | Memory Safety | Tombstone Strategy |

**🚀 Estimated Goal: v1.0 Production Ready in ~13 Weeks.**
