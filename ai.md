# Janus — AI Agent Onboarding Document

> **Purpose**: This document is the authoritative quick-start reference for any AI agent or new contributor that needs to understand the full scope, architecture, internal conventions, and current development state of the **Janus** project. Read this document in its entirety before making changes to the codebase.

**Local overrides**: If the file `ai.local.md` exists in the project root, you **must** read it after this document and treat its contents as additional binding rules. This file contains developer-specific preferences, interaction guidelines, and workflow conventions that supplement the project-wide standards defined here. It is gitignored (`*.local.md`) so each contributor can maintain personal configuration without affecting the shared repository.

---

## 1. Project Identity

| Field | Value |
| :--- | :--- |
| **Name** | Janus |
| **Package Name (PyPI)** | `janus` |
| **Crate Name (crates.io)** | `tachyon-rs` |
| **Version** | `0.2.0` |
| **License** | MIT OR Apache-2.0 (dual-licensed) |
| **Python** | `>= 3.12` |
| **Rust Edition** | `2021` |
| **Build System** | [Maturin](https://www.maturin.rs/) via PyO3 |
| **Dependency Manager** | [uv](https://docs.astral.sh/uv/) |
| **Repository** | `goldenphoenix713/janus` |

**One-liner**: Janus is a high-performance, extensible Python library for non-linear state travel and branching of arbitrary Python objects, powered by a Rust DAG engine called **Tachyon-RS**.

---

## 2. Architectural Overview

Janus follows a strict **two-layer** architecture:

```text
┌──────────────────────────────────────────────────┐
│  THE FACE  (Python)                              │
│  janus/                                          │
│   ├── base.py         — Janus Base & Mixin Classes  │
│   ├── registry.py     — Plugin AdapterRegistry   │
│   └── __init__.py     — Public exports           │
├──────────────────────────────────────────────────┤
│  THE ENGINE  (Rust → PyO3)                       │
│  src/                                            │
│   ├── lib.rs          — PyModule registration    │
│   ├── engine.rs       — TachyonEngine (API layer)│
│   ├── models.rs       — Core Data Structures     │
│   ├── graph.rs        — Graph/DAG Algorithms     │
│   ├── reconcile.rs    — Conflict Resolution      │
│   ├── serde_py.rs     — Python Serialization     │
│   └── containers.rs   — TrackedContainer Cores   │
└──────────────────────────────────────────────────┘
```

### 2.1 The Face (`janus/`)

The Python layer is user-facing. It provides:

- **`base.py`**: Contains the `JanusBase` logic and the public mixins `TimelineBase` (linear) and `MultiverseBase` (branching). It intercepts `__setattr__` calls to log attribute mutations to the Rust engine. It provides `_adapters` for plugin lookup, `_resolve_path` for resolving object paths in Rust, and manages history pruning via `max_history`.
- **`containers.py`**: Python-side proxy classes (`TrackedList`, `TrackedDict`) that subclass native `list` and `dict` respectively. Each mutating method logs the appropriate `Operation` via Rust-backed `Core` objects (`TrackedListCore`, `TrackedDictCore`). Also contains `wrap_value()` for recursive container wrapping.
- **`registry.py`**: An `AdapterRegistry` mapping Python types to `JanusAdapter` implementations. Adapters define `get_delta`, `apply_backward`, `apply_forward`, and `get_snapshot`, allowing third-party types (e.g., `pandas.DataFrame`) to participate in state tracking via opaque delta blobs.
- **`tachyon_rs.pyi`**: Type stubs for the Rust extension module, providing IDE autocompletion and `mypy` compatibility.
- **`plugins/pandas.py`**: Production-quality pandas adapter with `TrackedDataFrame`, `TrackedSeries`, `BaseTrackedIndexer` (wrapping `.loc`, `.iloc`, `.at`, `.iat`), and corresponding `TrackedDataFrameAdapter` / `TrackedSeriesAdapter` classes.

### 2.2 The Engine (`src/`)

The Rust layer is the performance-critical backend:

- **`lib.rs`**: Registers `TachyonEngine`, `TrackedListCore`, and `TrackedDictCore` as PyO3 classes under the `tachyon_rs` Python module.
- **`engine.rs`**: The main API entry point. Contains the `TachyonEngine` struct and its `#[pymethods]` implementation.
- **`models.rs`**: Defines core enums like `Operation`, `ListOperation`, `DictOperation`, and structs like `StateNode`.
- **`graph.rs`**: Implements DAG traversal, pathfinding, and Lowest Common Ancestor (LCA) resolution.
- **`reconcile.rs`**: Contains the 3-way reconciliation and operation rebasing logic for containers.
- **`serde_py.rs`**: Specialized serialization logic for converting Rust-side state to Python-ready dicts/lists.
- **`containers.rs`**: Implements the `TrackedListCore` and `TrackedDictCore` structures that provide the back-end for Python's `TrackedList` and `TrackedDict`.

---

## 3. Core Data Model

### 3.1 Operation Enum (Rust)

The `Operation` enum defines all trackable state mutations. Every mutation in Janus is ultimately recorded as one of these variants:

| Variant | Fields | Semantics |
| :--- | :--- | :--- |
| `UpdateAttr` | `name`, `old_value`, `new_value` | Scalar attribute assignment (e.g., `obj.hp = 50`) |
| `ListPop` | `path`, `index`, `popped_value` | Element removal from a `TrackedList` |
| `ListInsert` | `path`, `index`, `value` | Element insertion into a `TrackedList` |
| `DictUpdate` | `path`, `key`, `old_value`, `new_value` | Key update in a `TrackedDict` |
| `DictDelete` | `path`, `key`, `old_value` | Key deletion from a `TrackedDict` |
| `PluginOp` | `path`, `adapter_name`, `delta_blob` | Opaque delta from a registered `JanusAdapter` |

All values are stored as `PyObject` (GIL-bound Python object references).

### 3.2 StateNode

```rust
pub struct StateNode {
    pub id: usize,
    pub parents: Vec<usize>,       // DAG parent linkage (typically 1 parent)
    pub deltas: Vec<Operation>,    // Operations transitioning from parent → this node
    pub metadata: HashMap<String, PyObject>,  // Extensible metadata (currently unused)
}
```

### 3.3 TachyonEngine

```rust
pub struct TachyonEngine {
    pub owner: Py<pyo3::types::PyWeakref>,
    pub nodes: HashMap<usize, StateNode>,
    pub node_labels: HashMap<String, usize>,
    pub active_branch: String,
    pub branch_labels: HashMap<String, usize>,
    pub current_node: usize,
    pub next_node_id: usize,
    pub mode: Mode,
    pub max_history: Option<usize>,
}
```

- In **linear mode**, every `append_node` call auto-advances the `"main"` branch pointer to the new node.
- In **multiversal mode**, branches are explicit and do not auto-advance.

### 3.4 Branch Switching Algorithm

Branch switching (`switch_branch`) implements LCA-based DAG traversal:

1. Compute root-to-node paths for both `current_node` and `target_node`.
2. Find the **Lowest Common Ancestor (LCA)** via prefix comparison.
3. **Path up** (current → LCA): Apply deltas in **reverse** order with **inverse** semantics (e.g., `UpdateAttr` restores `old_value`; `ListInsert` is undone by `pop`; `ListPop` is undone by `insert`).
4. **Path down** (LCA → target): Apply deltas in **forward** order with **forward** semantics.
5. A `_restoring` flag is set on the Python owner to prevent the `__setattr__` interceptor from re-logging mutations during restoration.

---

## 4. Tracked Containers

Janus containers use a **hybrid Python/Rust architecture**: Python-side proxy classes (`TrackedList`, `TrackedDict`) subclass native `list` and `dict` for full `isinstance` compatibility, while delegating mutation logging to Rust-backed `Core` objects (`TrackedListCore`, `TrackedDictCore`) for performance.

### 4.1 `TrackedList` (Python `list` subclass + Rust `TrackedListCore`)

Raw `list` attribute values are automatically wrapped in `TrackedList` by `wrap_value()` during `__setattr__`. All standard `list` methods are supported:

| Method | Status | Operation Logged |
| :--- | :--- | :--- |
| `append(value)` | ✅ | `ListInsert` at `len()` |
| `extend(values)` | ✅ | `ListExtend` |
| `insert(index, value)` | ✅ | `ListInsert` |
| `pop(index?)` | ✅ | `ListPop` at resolved index |
| `remove(value)` | ✅ | `ListPop` at found index |
| `clear()` | ✅ | `ListClear` |
| `__setitem__(i, val)` | ✅ | `ListReplace` |
| `__delitem__(i)` | ✅ | `ListPop` |
| `__getitem__`, `__len__`, `__iter__`, `__repr__`, `__eq__`, `__contains__` | ✅ | None (read-only, inherited from `list`) |

### 4.2 `TrackedDict` (Python `dict` subclass + Rust `TrackedDictCore`)

Raw `dict` attribute values are automatically wrapped in `TrackedDict` by `wrap_value()`. All standard `dict` methods are supported:

| Method | Status | Operation Logged |
| :--- | :--- | :--- |
| `__setitem__(key, val)` | ✅ | `DictUpdate` |
| `__delitem__(key)` | ✅ | `DictDelete` |
| `update(other, **kw)` | ✅ | `DictUpdate` (batched) |
| `pop(key, default?)` | ✅ | `DictPop` |
| `popitem()` | ✅ | `DictPop` |
| `setdefault(key, default?)` | ✅ | `DictUpdate` (if key absent) |
| `clear()` | ✅ | `DictClear` |
| `__getitem__`, `__contains__`, `__iter__`, `keys`, `values`, `items`, `get`, `__len__`, `__repr__`, `__eq__` | ✅ | None (read-only, inherited from `dict`) |

---

## 5. Plugin System

The plugin system allows Janus to track mutations on arbitrary third-party types without the engine understanding their internals.

**JanusAdapter Protocol** (defined in `registry.py`):

| Method | Purpose |
| :--- | :--- |
| `get_delta(old_state, new_state) -> Any` | Compute a delta blob from old snapshot to current state |
| `apply_backward(target, delta_blob) -> None` | Restore target to pre-delta state using the blob |
| `apply_forward(target, delta_blob) -> None` | Apply delta to reach the post-mutation state |
| `get_snapshot(value) -> Any` | Capture a snapshot of the current value for future delta calculation |

**Registration flow**:

```python
from typing import Any

from janus import JanusAdapter, register_adapter


class Data:
    def __init__(self, value: str) -> None:
        self.value = value


@register_adapter(Data)
class DataAdapter(JanusAdapter):
    def get_delta(self, old_state: Any, new_state: Any) -> Any:
        return (old_state, new_state.value)

    def apply_backward(self, target: Any, delta_blob: Any) -> None:
        old_val, _ = delta_blob
        target.value = old_val

    def apply_forward(self, target: Any, delta_blob: Any) -> None:
        _, new_val = delta_blob
        target.value = new_val

    def get_snapshot(self, value: Any) -> Any:
        return value.value
```

**Runtime behavior**: When `__setattr__` detects a value whose `type()` is a key in `ADAPTER_REGISTRY`, it uses a **Shadow Snapshot** mechanism: it calls `adapter.get_delta(shadow_value, new_value)` and logs a `PluginOp` in the Rust engine, then updates the shadow via `get_snapshot()`. During branch switching, the engine calls `apply_backward` (path up to LCA) or `apply_forward` (path down to target) on the adapter.

---

## 6. Project Directory Structure

```tree
janus/
├── Cargo.toml                      # Rust crate config (tachyon-rs)
├── Cargo.lock
├── pyproject.toml                   # Python project config (maturin build backend)
├── README.md
├── ai.md                            # THIS FILE — agent onboarding
├── main.py                          # Minimal entry point (placeholder)
├── benchmark.py                     # Standalone benchmark script
│
├── src/                             # Rust source (Tachyon-RS engine)
│   ├── lib.rs                       # PyModule registration
│   ├── engine.rs                    # TachyonEngine API
│   ├── models.rs                    # Core Data Models (Operation, StateNode)
│   ├── graph.rs                     # DAG traversal logic
│   ├── reconcile.rs                 # Reconciliation / 3-way merge
│   ├── serde_py.rs                  # Python serialization logic
│   └── containers.rs                # TrackedListCore, TrackedDictCore
│
├── janus/                           # Python source (public API)
│   ├── __init__.py                  # Exports: Base Classes, register_adapter
│   ├── base.py                      # JanusBase, TimelineBase, MultiverseBase
│   ├── containers.py                # TrackedList, TrackedDict, wrap_value()
│   ├── registry.py                  # AdapterRegistry + JanusAdapter Protocol
│   ├── tachyon_rs.pyi               # Type stubs for the Rust extension
│   ├── tachyon_rs.abi3.so           # Compiled Rust shared library (platform-specific)
│   ├── py.typed                     # PEP 561 marker
│   └── plugins/
│       ├── pandas.py                # TrackedDataFrame, TrackedSeries, indexer wrappers, adapters
│       └── numpy.py                 # TrackedNumpyArray proxy and adapter
│
├── tests/                           # Test suite (pytest)
│   ├── test_basic_revert.py         # Label creation + jump_to round-trip
│   ├── test_linear_behavior.py      # Undo/redo, overwrite-future, label pruning
│   ├── test_multiverse.py           # Branching, branch deletion, error guards
│   ├── test_plugins.py              # Plugin registration + PluginOp verification
│   ├── test_timeline_containers.py  # TrackedList/TrackedDict reversion + timeline extraction
│   ├── test_tracked_list_api.py     # Full TrackedList method coverage
│   ├── test_tracked_dict_api.py     # Full TrackedDict method coverage
│   ├── test_pandas_mvp.py           # Pandas wrapping, mutation rollback, branching, indexers
│   ├── test_performance.py          # O(1) logging latency benchmark
│   └── test_vs_deepcopy.py          # Janus snapshot vs deepcopy comparison
│
├── docs/
│   ├── PERFORMANCE.md               # Benchmark data and performance analysis
│   ├── performance_comparison.png   # Chart: Janus vs deepcopy
│   ├── architecture/
│   │   ├── janus_blueprint.md       # Original architecture blueprint
│   │   └── TECHNICAL_DEEP_DIVE.md   # DAG internals, LCA, merge logic, complexity
│   ├── planning/
│   │   ├── ROADMAP.md               # High-level 5-phase roadmap
│   │   ├── implementation_plan.md   # Detailed waypoint-by-waypoint plan with estimates
│   │   └── IDEAS.md                 # Scratchpad for future features
│   └── governance/
│       └── CONTRIBUTING.md          # Dev setup, code style, PR workflow
│
├── .github/workflows/               # GitHub Actions CI
├── .pre-commit-config.yaml          # Pre-commit hooks
├── .markdownlint.yaml               # Markdown lint config
└── .python-version                  # Python version pin (3.12)
```

---

## 7. Code Style & Quality Enforcement

All code quality is enforced automatically by a **pre-commit** pipeline (`.pre-commit-config.yaml`). Every commit triggers the full chain described below. Agents and contributors **must** ensure all checks pass before proposing changes.

### 7.1 Pre-Commit Hook Pipeline

Hooks run in the following order on every `git commit`:

| Hook | Source | What It Does |
| :--- | :--- | :--- |
| `trailing-whitespace` | `pre-commit-hooks` v4.6.0 | Strips trailing whitespace from all files |
| `end-of-file-fixer` | `pre-commit-hooks` v4.6.0 | Ensures files end with exactly one newline |
| `check-yaml` | `pre-commit-hooks` v4.6.0 | Validates YAML syntax |
| `check-added-large-files` | `pre-commit-hooks` v4.6.0 | Rejects files over the default size threshold |
| `markdownlint` | `markdownlint-cli` v0.41.0 | Lints `.md` files (config: `.markdownlint.yaml`) |
| `ruff` (lint) | `ruff-pre-commit` v0.4.4 | Runs ruff linter with `--fix --exit-non-zero-on-fix` |
| `ruff-format` | `ruff-pre-commit` v0.4.4 | Auto-formats Python code (Black-compatible) |
| `mypy` | local | Static type checking via `uv run mypy .` |
| `clippy` | local | Rust linter: `cargo clippy -- -D warnings` |
| `rustfmt` | local | Rust formatter: `cargo fmt -- --check` |
| `pytest` | local | Runs `uv run pytest -m "not slow"` |

### 7.2 Python — Ruff Configuration

Configured in `pyproject.toml` under `[tool.ruff]` and `[tool.ruff.lint]`:

| Setting | Value | Meaning |
| :--- | :--- | :--- |
| `line-length` | `88` | Maximum line length (Black-compatible default) |
| `target-version` | `"py312"` | Assumes Python 3.12+ syntax |
| `ignore` | `[]` | No rules are suppressed |

**Extended rule sets** (`extend-select`):

| Code | Name | What It Enforces |
| :--- | :--- | :--- |
| `F` | Pyflakes | Undefined names, unused imports, etc. |
| `W` | PyCodeStyle warnings | Whitespace issues, deprecated syntax |
| `E` | PyCodeStyle errors | Syntax errors, indentation, line length |
| `I` | isort | Import ordering and grouping |
| `UP` | pyupgrade | Modernize syntax for target Python version |
| `C4` | flake8-comprehensions | Correct comprehension/dict/list usage |
| `FA` | flake8-future-annotations | Enforce `from __future__ import annotations` |
| `ISC` | flake8-implicit-str-concat | Good string concatenation practices |
| `ICN` | flake8-import-conventions | Common import aliases (e.g., `import numpy as np`) |
| `RET` | flake8-return | Consistent return practices (e.g., no implicit `return None` after `return val`) |
| `SIM` | flake8-simplify | Common simplification patterns (e.g., ternary, `contextlib.suppress`) |
| `TID` | flake8-tidy-imports | Import hygiene (e.g., prefer absolute over relative parent imports) |
| `TC` | flake8-type-checking | Move type-only imports into `TYPE_CHECKING` blocks |
| `PTH` | flake8-use-pathlib | Prefer `pathlib` over `os.path` |
| `TD` | flake8-todos | Enforce TODO comment format |
| `NPY` | NumPy-specific rules | NumPy best practices |

**Key implications for agents:**

- **Import order matters**: Imports must follow isort conventions — stdlib → third-party → local, alphabetized within groups, separated by blank lines.
- **Absolute imports for parent packages**: Use `from janus.registry import ...` not `from ..registry import ...` (`TID252`).
- **Modern syntax**: Use `X | Y` union types over `Union[X, Y]`, `list[T]` over `List[T]`, etc.
- **`from __future__ import annotations`**: Required in all Python source files (`FA100`).
- **Explicit returns**: If a function has *any* `return <value>` branch, all branches must have an explicit `return` statement. Do not mix `return super().__setattr__(...)` with implicit fall-through (`RET503`).
- **Use `contextlib.suppress`**: Prefer `with contextlib.suppress(Error)` over bare `try/except/pass` (`SIM105`).
- **Use ternary operators**: Simple `if/else` assignments should use ternary form (`SIM108`).
- **88-char lines**: Break long lines at 88 characters, not 79 or 120.

### 7.3 Python — Mypy Configuration

Configured in `pyproject.toml` under `[tool.mypy]`:

| Setting | Value | Meaning |
| :--- | :--- | :--- |
| `python_version` | `"3.12"` | Type-check targeting Python 3.12 |
| `strict` | `true` | Enables **all** strict-mode flags (see below) |
| `check_untyped_defs` | `true` | Checks function bodies even if they lack annotations |
| `ignore_missing_imports` | `true` | Suppresses errors for missing third-party stubs |
| `warn_return_any` | `true` | Warns when a function typed as returning a specific type returns `Any` |
| `warn_unused_configs` | `true` | Warns about unused mypy config sections |

> **Note**: `strict = true` enables a comprehensive set of flags including `disallow_untyped_defs`, `disallow_untyped_calls`, `disallow_incomplete_defs`, `no_implicit_optional`, `warn_redundant_casts`, `warn_unused_ignores`, and more.

**Key implications for agents:**

- **All functions must have type annotations.** Every function and method signature must include parameter types and return types (e.g., `def foo(self, x: int) -> None:`). This is enforced by `strict = true`.
- **Calls to untyped functions are errors.** If you call a function that lacks annotations, mypy will flag it (`no-untyped-call`).
- **`# type: ignore` comments must be valid.** Stale or unnecessary `# type: ignore` comments will cause `unused-ignore` errors. Only add them when truly needed, and always specify the error code (e.g., `# type: ignore[override]`).
- **The `tachyon_rs.pyi` stub file provides types for the Rust extension** — keep it in sync with any `#[pymethods]` or `#[getter]` changes in `engine.rs`.
- **Use `Any` sparingly but deliberately.** For dynamic containers and PyO3 boundaries, `Any` is acceptable. For pure Python logic, prefer concrete types.

### 7.4 Rust — Clippy & Rustfmt

- **Clippy** runs with `-D warnings` (all warnings are treated as errors). Code must be idiomatically correct.
- **Rustfmt** enforces the default Rust formatting style. All Rust code is checked with `cargo fmt -- --check`.

### 7.5 Markdown — Markdownlint

Configured in `.markdownlint.yaml`:

| Rule | Status | Notes |
| :--- | :--- | :--- |
| All rules | ✅ Enabled | `default: true` |
| `MD013` (line length) | ❌ Disabled | Long lines are permitted in Markdown |
| `MD033` (inline HTML) | ❌ Disabled | Raw HTML is allowed (e.g., `<br>`, `<img>`) |
| `MD041` (first-line heading) | ❌ Disabled | Files don't need to start with `# H1` |

### 7.6 Pytest Configuration

Configured in `pyproject.toml` under `[tool.pytest.ini_options]`:

- Custom marker: `@pytest.mark.slow` — marks long-running tests.
- Pre-commit runs: `pytest -m "not slow"` (slow tests are skipped in the commit hook but should be run before merging).

### 7.7 Documentation Standards

Documentation is held to the same standard as code. The following rules apply to all `.md` files in the project:

1. **Fenced code blocks must always specify a language identifier.** Every triple-backtick block must declare its content type. This keeps the intent of each block explicit and enables proper syntax highlighting. Common identifiers used in this project:

    | Content Type | Language Identifier | Example Use |
    | :--- | :--- | :--- |
    | Python source | `python` | Code examples, API snippets |
    | Rust source | `rust` | Engine structs, enums |
    | Shell commands | `bash` | Build steps, CLI usage |
    | TOML config | `toml` | `pyproject.toml`, `Cargo.toml` excerpts |
    | Directory layouts | `tree` | Project structure diagrams |
    | Plain text / ASCII art | `text` | Architecture diagrams, non-code output |
    | Mermaid diagrams | `mermaid` | Dependency graphs, flowcharts |
    | Diffs | `diff` | Code change summaries |

2. **Heading hierarchy must be sequential.** Do not skip levels (e.g., `##` → `####`). Every document should have exactly one `#` top-level heading.

3. **Use numbered sections for long-form documents.** Section numbers (e.g., `## 7. Code Style`) make cross-references unambiguous and easier to navigate.

4. **Tables over prose for structured data.** When presenting settings, method lists, or comparisons, use Markdown tables instead of bullet lists.

5. **No trailing whitespace, single terminal newline.** Enforced by `trailing-whitespace` and `end-of-file-fixer` pre-commit hooks.

6. **Blank line before and after fenced code blocks.** Required by markdownlint (`MD031`).

7. **Lists must be consistent.** Use `-` for unordered lists throughout. Do not mix `-`, `*`, and `+` within a document (`MD004`).

8. **Link references should use descriptive text.** Avoid bare URLs in prose; wrap them in `[descriptive text](url)` format.

---

## 8. Build & Development Workflow

### 8.1 Environment Setup

```bash
uv venv && source .venv/bin/activate
uv sync --dev                  # Install all dev dependencies
```

### 8.2 Compile the Rust Engine

```bash
uv run maturin develop         # Builds Rust + symlinks .so into the venv
```

> **Critical**: You must run `maturin develop` after **any** change to files in `src/`. Python-only changes do not require recompilation.

### 8.3 Run Tests

```bash
uv run pytest tests/ -v        # Full test suite
```

### 8.4 Linting

```bash
uv run ruff check janus/ tests/    # Python linter (ruff)
uv run ruff format --check janus/ tests/  # Format check (dry-run)
uv run mypy janus/                 # Static type checking
cargo clippy -- -D warnings        # Rust linter
cargo fmt -- --check               # Rust format check
```

### 8.5 Benchmarks

```bash
uv run python tests/test_performance.py    # O(1) logging verification
uv run python tests/test_vs_deepcopy.py    # Janus vs deepcopy comparison
```

---

## 9. Current API Surface

### 9.1 Base Classes

```python
from janus import MultiverseBase, TimelineBase

class MyTimelineObj(TimelineBase):
    def __init__(self) -> None:
        super().__init__()
        self.value = 0

class MyMultiverseObj(MultiverseBase):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[int] = []    # Auto-wrapped to TrackedList
        self.config: dict[str, str] = {}  # Auto-wrapped to TrackedDict
```

#### 9.2 Complete API Reference

| Method | Availability | Description |
| :--- | :--- | :--- |
| `undo()` | Both modes | Undo the last operation |
| `redo()` | Both modes | Redo the last undone operation |
| `create_moment_label(label)` | Both modes | Label the current state node for future jumps |
| `jump_to(label)` | Both modes | Restore state to a labeled moment via LCA traversal |
| `get_labeled_moments()` | Both modes | List all available moment labels |
| `branch(label)` | Multiversal only | Create a named branch at the current state node |
| `create_branch(label)` | Multiversal only | Alias for `branch()` |
| `switch_branch(label)` | Multiversal only | Switch to a different branch |
| `list_branches()` | Multiversal only | List all branch names |
| `delete_branch(label)` | Multiversal only | Delete a branch (cannot delete the active branch) |
| `current_branch` | Multiversal only | Property returning the active branch name |
| `extract_timeline(label)` | Multiversal only | Returns a list of operation dicts from root to the named branch |
| `merge(label, strategy)` | Multiversal only | 3-way merge of a branch into current. Supports `overshadow`, `preserve`, `strict`, or a custom `Callable`. |
| `prune()` | Both modes | Manually trigger DAG pruning to `max_history` depth. |
| `max_history` | Both modes | Property/Setter to configure the maximum retained history depth. |

### 9.3 Plugin Registration

```python
from typing import Any

from janus import JanusAdapter, register_adapter


@register_adapter(TargetType)
class MyAdapter(JanusAdapter):
    def get_delta(self, old_state: Any, new_state: Any) -> Any: ...
    def apply_backward(self, target: Any, delta_blob: Any) -> None: ...
    def apply_forward(self, target: Any, delta_blob: Any) -> None: ...
    def get_snapshot(self, value: Any) -> Any: ...
```

---

## 10. Performance Characteristics

| Operation | Time Complexity | Notes |
| :--- | :--- | :--- |
| **Mutation logging** | $O(1)$ | Appends a node to the DAG; independent of history depth |
| **Branch creation** | $O(1)$ | Inserts a label → node_id mapping |
| **Branch switching** | $O(D)$ | $D$ = path distance between current and target nodes via LCA |
| **Timeline extraction** | $O(P)$ | $P$ = path length from root to the target branch |
| **Memory** | $O(H)$ | $H$ = total number of mutations logged |

Verified benchmarks show **constant logging latency (~6μs)** and **constant-time branching (~7–20μs)** even as history scales to 100,000+ nodes, ensured by automated history pruning and O(1) DAG append logic.

---

## 11. Development State & Known Gaps

### 11.1 Phase Completion Summary

| Phase | Status | Key Gaps |
| :--- | :--- | :--- |
| **P1 — Linear Foundation** | **100%** | — (complete: undo/redo, overwrite-future, linear guards) |
| **P2 — Multiversal Branching** | **100%** | — (complete: DAG, branching, deletion, listing, moments) |
| **P3 — Plugins & Containers** | **100%** | `TrackedList`/`TrackedDict` fully implemented; pandas & numpy adapters complete |
| **P4 — Timeline & Flattening** | **100%** | — (complete: timeline extraction, filtering, Squash/Flatten, and get_diff) |
| **P5 — Tombstone & Memory** | **100%** | — (complete: WeakRef-based safety, Tombstone raising, and history pruning with delta-merging) |
| **P6 — Custom Merging** | **100%** | — (complete: `Union[str, Callable]` strategies for attribute and dictionary conflicts) |
| **P12 — Modular Engine** | **100%** | — (complete: Separation of `graph.rs`, `reconcile.rs`, `serde_py.rs`, and `models.rs`) |

### 11.2 Completed Milestones

- **Decorator → Base Classes**: The refactor from the `@janus` decorator to explicit `TimelineBase` and `MultiverseBase` is complete.
- **`apply_inverse` → `apply_backward`**: Adapter protocol method renamed for clarity. `apply_forward` and `get_snapshot` added for bidirectional support.
- **Shadow Snapshots**: `JanusBase.__setattr__` now stashes `_shadow_` attributes to correctly compute deltas for in-place mutated plugin objects.
- **Container Hardening**: `TrackedList` and `TrackedDict` now subclass native Python `list`/`dict` (full `isinstance` compat) and delegate logging to Rust `Core` classes.
- **Pandas & NumPy Integration**: `TrackedDataFrame`, `TrackedSeries`, and `TrackedNumpyArray` are fully operational with undo/redo and branching.
- **Branch Management**: Methods for listing (`list_branches`) and deleting (`delete_branch`) branches are complete.
- **Strict Type Checking**: `mypy` runs in `strict` mode; all source and test files have comprehensive type annotations.
- **Modular Engine Architecture**: The Rust engine has been refactored into specialized modules (`models`, `graph`, `reconcile`, `serde_py`, `containers`) for better maintainability.
- **PyO3 0.23 Migration**: The codebase has been fully updated to the latest PyO3 stable version, utilizing `Bound` handles and the new ownership model.

---

## 12. Key Conventions & Gotchas

1. **`_restoring` flag**: During `switch_branch` / `undo()`, the engine sets `owner._restoring = True` to suppress `__setattr__` interception. Any code that bypasses this flag will cause infinite recursion or double-logging. Tracked containers also check this flag via their `_is_silent` property.

2. **`_engine` bypass**: Assignments to `_engine` and `_restoring` use `super().__setattr__()` or `object.__setattr__()` to avoid interception. Any attribute prefixed with `_` is **not logged** by the engine (see `base.py`: `if not name.startswith("_")`).

3. **Maturin develop**: After any Rust change, you **must** run `uv run maturin develop` before testing. The `.so` file is symlinked into the venv, but changes are not hot-reloaded.

4. **PyO3 `abi3` stable ABI**: The crate uses `abi3-py38`, meaning the compiled `.so` works across Python 3.8+. However, `pyproject.toml` requires `>= 3.12` at the project level.

5. **No thread safety**: `TachyonEngine` is not `Send` or `Sync`. Janus is designed for single-threaded Python usage only.

6. **`from __future__ import annotations`**: Required in all Python source files by the `FA` ruff rule. Without this, forward references in type annotations will fail at runtime.

7. **Strict typing**: All functions must have parameter and return type annotations. `# type: ignore` comments must specify the error code (e.g., `# type: ignore[override]`).

---

## 13. Documentation Map

| Document | Purpose | Path |
| :--- | :--- | :--- |
| **This file** | Agent onboarding and quick reference | `ai.md` |
| **README** | User-facing overview and getting started | `README.md` |
| **Blueprint** | Original architecture and design decisions | `docs/architecture/janus_blueprint.md` |
| **Technical Deep Dive** | DAG internals, LCA, merge, complexity analysis | `docs/architecture/TECHNICAL_DEEP_DIVE.md` |
| **Roadmap** | High-level 5-phase feature plan | `docs/planning/ROADMAP.md` |
| **Implementation Plan** | Waypoint-by-waypoint deliverables with estimates | `docs/planning/implementation_plan.md` |
| **Ideas** | Scratchpad for future features and explorations | `docs/planning/IDEAS.md` |
| **Performance** | Benchmark data and O(1) verification | `docs/PERFORMANCE.md` |
| **Contributing** | Dev setup, code style, PR process | `docs/governance/CONTRIBUTING.md` |
