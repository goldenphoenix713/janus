# Phase 8: Async & High-Concurrency Tracking Implementation Plan

This phase aims to support Janus in high-concurrency and asynchronous environments (e.g., FastAPI, Celery) by ensuring thread-safety in the Rust engine and task-local state isolation in the Python frontend.

## Proposed Changes

### 🦀 Tachyon-RS (Rust Backend)

#### Thread-Safety

- [MODIFY] [src/engine.rs](file:///Users/eduardo.ruiz/PycharmProjects/Janus/src/engine.rs):
  - Replace `HashMap` with `DashMap` or wrap internal state in `Arc<RwLock<TachyonState>>`.
  - Use `py.allow_threads()` in methods that perform CPU-intensive graph traversal (LCA, merge, squash) to release the GIL and allow other tasks to proceed.
- [MODIFY] [src/containers.rs](file:///Users/eduardo.ruiz/PycharmProjects/Janus/src/containers.rs):
  - Ensure [TrackedListCore](file:///Users/eduardo.ruiz/PycharmProjects/Janus/janus/tachyon_rs.pyi#211-219) and [TrackedDictCore](file:///Users/eduardo.ruiz/PycharmProjects/Janus/janus/tachyon_rs.pyi#220-229) use atomic operations or synchronization when logging to the shared engine.

#### Multi-Cursor API

- [MODIFY] [src/engine.rs](file:///Users/eduardo.ruiz/PycharmProjects/Janus/src/engine.rs):
  - Update `log_*` and `move_to_*` methods to optionally accept a `cursor_id` (node ID).
  - If a `cursor_id` is provided, the operation is rooted at that node instead of the engine's default [current_node](file:///Users/eduardo.ruiz/PycharmProjects/Janus/src/engine.rs#589-593).

---

### 🐍 Janus Python (Frontend)

#### Context-Aware Tracking

- [MODIFY] [janus/base.py](file:///Users/eduardo.ruiz/PycharmProjects/Janus/janus/base.py):
  - Introduce `from contextvars import ContextVar`.
  - Add `_current_node_cv: ContextVar[int]` and `_active_branch_cv: ContextVar[str]`.
  - Update `JanusBase.__init__` to initialize these context variables.
  - Update all `_engine` calls to pass the value from the `ContextVar`.

#### Async Plugin API

- [NEW] `janus/async_plugins.py`:
  - Define `JanusAsyncAdapter` protocol.
  - Support `async def apply_forward` and `async def apply_backward`.
  - This is required for objects where state restoration involves async I/O (e.g., reloading from a database).

---

### 🧪 Quality Assurance

#### Concurrency Stress Tests

- [NEW] `tests/test_async_concurrency.py`:
  - Use `anyio` or `asyncio.gather` to mutate a single [JanusBase](file:///Users/eduardo.ruiz/PycharmProjects/Janus/janus/base.py#33-262) object from multiple tasks.
  - Verify that each task maintains its own timeline via `ContextVar`.
  - Verify that no data corruption occurs in the Rust engine.

#### Thread-Safety Benchmarks

- [NEW] `tests/test_thread_benchmarks.py`:
  - Measure performance under contention (multiple threads logging simultaneously).
  - Compare with single-threaded baseline.

## Verification Plan

### Automated Tests

- `uv run pytest tests/test_async_concurrency.py`
- `uv run pytest tests/test_thread_benchmarks.py`

### Manual Verification

- Deploy a sample FastAPI app using a singleton [JanusBase](file:///Users/eduardo.ruiz/PycharmProjects/Janus/janus/base.py#33-262) object and verify state isolation between concurrent requests.
