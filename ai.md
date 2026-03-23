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
│   ├── engine.rs       — TachyonEngine (DAG core) │
│   ├── containers.rs   — (placeholder)            │
│   └── lib.rs          — PyModule registration    │
└──────────────────────────────────────────────────┘
```

### 2.1 The Face (`janus/`)

The Python layer is user-facing. It provides:

- **`base.py`**: Contains the `JanusBase` logic and the public mixins `TimelineBase` (linear) and `MultiverseBase` (branching). It intercepts `__setattr__` calls to log attribute mutations to the Rust engine and explicitly defines methods like `undo()`, `redo()`, and `branch()`.
- **`registry.py`**: An `AdapterRegistry` mapping Python types to `JanusAdapter` implementations. Adapters define `get_delta(old, new) -> blob` and `apply_inverse(target, blob) -> None`, allowing third-party types (e.g., `pandas.DataFrame`) to participate in state tracking via opaque delta blobs.
- **`tachyon_rs.pyi`**: Type stubs for the Rust extension module, providing IDE autocompletion and `mypy` compatibility.

### 2.2 The Engine (`src/`)

The Rust layer is the performance-critical backend:

- **`engine.rs`** (~530 lines): Contains the full `TachyonEngine` implementation, `TrackedList`, and `TrackedDict`. The engine maintains a **Directed Acyclic Graph (DAG)** of `StateNode` objects. Each node stores a vector of `Operation` deltas relative to its parent. Branch switching uses **Lowest Common Ancestor (LCA)** path resolution with bi-directional delta application.
- **`lib.rs`**: Registers `TachyonEngine`, `TrackedList`, and `TrackedDict` as PyO3 classes under the `tachyon_rs` Python module.
- **`containers.rs`**: Currently a placeholder file. `TrackedList` and `TrackedDict` are implemented directly in `engine.rs`.

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
    owner: Py<PyAny>,                       // Weak-ish reference to the decorated Python object
    nodes: HashMap<usize, StateNode>,       // All nodes in the DAG
    branches: HashMap<String, usize>,       // Named branch → node_id mapping
    current_node: usize,                    // HEAD pointer
    next_node_id: usize,                    // Monotonic ID counter
    mode: String,                           // "linear" or "multiversal"
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

> **Known gap**: `PluginOp` variants are silently skipped during switch (`_ => {}` wildcard in `apply_node_deltas`). This is tracked as Waypoint 2.1 in the implementation plan.

---

## 4. Tracked Containers

### 4.1 `TrackedList` (Rust `#[pyclass]`)

A proxy for Python `list` objects. On construction, the decorator replaces raw `list` attribute values with `TrackedList` instances. Each mutating method logs the appropriate `Operation`:

| Method | Implemented | Operation Logged |
| :--- | :--- | :--- |
| `append(value)` | ✅ | `ListInsert` at `len()` |
| `pop(index?)` | ✅ | `ListPop` at resolved index |
| `__getitem__(i)` | ✅ | None (read-only) |
| `__len__()` | ✅ | None (read-only) |
| `__setitem__` | ❌ | — |
| `extend`, `insert`, `remove`, `clear` | ❌ | — |
| `__iter__`, `__repr__`, `__eq__`, `__contains__` | ❌ | — |

### 4.2 `TrackedDict` (Rust `#[pyclass]`)

A proxy for Python `dict` objects. Uses `HashMap<String, PyObject>` internally (string keys only).

| Method | Implemented | Operation Logged |
| :--- | :--- | :--- |
| `__setitem__(key, val)` | ✅ | `DictUpdate` |
| `__delitem__(key)` | ✅ | `DictDelete` |
| `__getitem__`, `__contains__`, `__iter__`, `keys`, `__len__`, `get` | ✅ | None (read-only) |
| `update`, `pop`, `values`, `items`, `setdefault`, `clear` | ❌ | — |
| `__repr__`, `__eq__` | ❌ | — |

---

## 5. Plugin System

The plugin system allows Janus to track mutations on arbitrary third-party types without the engine understanding their internals.

**Registration flow**:

```python
from typing import Any

from janus import JanusAdapter, register_adapter


class Data:
    def __init__(self, value: str) -> None:
        self.value = value


@register_adapter(Data)
class DataAdapter(JanusAdapter):
    def get_delta(self, old_state: Any, new_state: Any) -> str:
        return f"diff:{getattr(old_state, 'value', None)}->{new_state.value}"

    def apply_inverse(self, target: Any, delta_blob: Any) -> None:
        # Restore target to pre-delta state using the blob
        pass
```

**Runtime behavior**: When `__setattr__` detects a value whose `type()` is a key in `ADAPTER_REGISTRY`, it calls `adapter.get_delta(old, new)` and logs a `PluginOp` in the Rust engine. The delta blob is opaque to Tachyon-RS.

> **Known gap**: `apply_inverse` is never called during `switch_branch` (see §3.4).

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
│   ├── lib.rs                       # PyO3 module registration
│   ├── engine.rs                    # TachyonEngine, TrackedList, TrackedDict, Operation enum
│   └── containers.rs                # Placeholder (containers live in engine.rs)
│
├── janus/                           # Python source (public API)
│   ├── __init__.py                  # Exports: Base Classes, register_adapter
│   ├── base.py                      # JanusBase, TimelineBase, MultiverseBase
│   ├── registry.py                  # AdapterRegistry + JanusAdapter Protocol
│   ├── tachyon_rs.pyi               # Type stubs for the Rust extension
│   ├── tachyon_rs.abi3.so           # Compiled Rust shared library (platform-specific)
│   └── py.typed                     # PEP 561 marker
│
├── tests/                           # Test suite (pytest)
│   ├── test_basic_revert.py         # Branching + switch_branch round-trip
│   ├── test_multiverse.py           # Basic branching smoke test
│   ├── test_plugins.py              # Plugin registration + PluginOp verification
│   ├── test_timeline_containers.py  # TrackedList/TrackedDict reversion + timeline extraction
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

Configured in `pyproject.toml` under `[tool.ruff]`:

| Setting | Value | Meaning |
| :--- | :--- | :--- |
| `line-length` | `88` | Maximum line length (Black-compatible default) |
| `target-version` | `"py312"` | Assumes Python 3.12+ syntax |
| **Selected rule sets** | `E`, `F`, `I`, `U` | **E** = pycodestyle errors, **F** = Pyflakes, **I** = isort (import ordering), **U** = pyupgrade (modernize syntax) |
| `ignore` | `[]` | No rules are suppressed |

**Key implications for agents:**

- **Import order matters**: Imports must follow isort conventions — stdlib → third-party → local, alphabetized within groups, separated by blank lines.
- **Modern syntax**: Use `X | Y` union types over `Union[X, Y]`, `list[T]` over `List[T]`, etc.
- **88-char lines**: Break long lines at 88 characters, not 79 or 120.

### 7.3 Python — Mypy Configuration

Configured in `pyproject.toml` under `[tool.mypy]`:

| Setting | Value | Meaning |
| :--- | :--- | :--- |
| `python_version` | `"3.12"` | Type-check targeting Python 3.12 |
| `check_untyped_defs` | `true` | Checks function bodies even if they lack annotations |
| `disallow_untyped_defs` | `false` | Untyped function signatures are allowed (not enforced yet) |
| `ignore_missing_imports` | `true` | Suppresses errors for missing third-party stubs |
| `warn_return_any` | `true` | Warns when a function typed as returning a specific type returns `Any` |
| `warn_unused_configs` | `true` | Warns about unused mypy config sections |

**Key implications for agents:**

- Type hints are **strongly encouraged** but not strictly required on every function.
- The `tachyon_rs.pyi` stub file provides types for the Rust extension — keep it in sync with any `#[pymethods]` changes.
- `plotly.*` and `dash.*` modules have explicit `ignore_missing_imports` overrides.

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

### 9.2 Methods Provided by Base Classes

| Method | Availability | Description |
| :--- | :--- | :--- |
| `branch(label)` | Multiversal only | Creates a named branch at the current state node |
| `snapshot(label)` | Both modes | Alias for `branch()` |
| `switch(label)` | Both modes | Restores object state to the target branch via LCA traversal |
| `extract_timeline(label)` | Both modes | Returns a list of operation dicts from root to the named branch |

### 9.3 Plugin Registration

```python
from typing import Any

from janus import JanusAdapter, register_adapter


@register_adapter(TargetType)
class MyAdapter(JanusAdapter):
    def get_delta(self, old_state: Any, new_state: Any) -> Any: ...
    def apply_inverse(self, target: Any, delta_blob: Any) -> None: ...
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

Verified benchmarks show **~27,000× speedup** over `copy.deepcopy()` for objects with 500,000 attributes, and **constant logging latency** (~6.7μs) across 1K–100K history depths.

---

## 11. Development State & Known Gaps

### 11.1 Phase Completion Summary

| Phase | Status | Key Gaps |
| :--- | :--- | :--- |
| **P1 — Linear Foundation** | ~85% | No `undo()`/`redo()` API, no overwrite-future logic, no linear-mode guards |
| **P2 — Multiversal Branching** | ~75% | `PluginOp` silently skipped during `switch_branch`, no merge, no branch deletion/listing |
| **P3 — Plugins & Containers** | ~50% | `TrackedList` missing many standard methods, `TrackedDict` missing `update`/`pop`/`values`/`items`, no pandas/numpy adapters |
| **P4 — Timeline & Flattening** | ~40% | No history squash, no filtering, no timeline diff |
| **P5 — Tombstone & Memory** | 0% | No weak refs, no pruning, no memory benchmarks |

### 11.2 Planned API Change (Completed)

The refactor from the `@janus` decorator to explicit `TimelineBase` and `MultiverseBase` classes is complete. This resolved static analysis issues and improved API discoverability.

---

## 12. Key Conventions & Gotchas

1. **`_restoring` flag**: During `switch_branch`, the engine sets `owner._restoring = True` to suppress `__setattr__` interception. Any code that bypasses this flag will cause infinite recursion or double-logging.

2. **`_engine` bypass**: Assignments to `_engine` and `_restoring` use `super().__setattr__()` or `object.__setattr__()` to avoid interception. Any attribute prefixed with `_` is **not logged** by the engine (see `base.py` line 36: `if not name.startswith("_")`).

3. **Maturin develop**: After any Rust change, you **must** run `uv run maturin develop` before testing. The `.so` file is symlinked into the venv, but changes are not hot-reloaded.

4. **PyO3 `abi3` stable ABI**: The crate uses `abi3-py38`, meaning the compiled `.so` works across Python 3.8+. However, `pyproject.toml` requires `>= 3.12` at the project level.

5. **String-only dict keys**: `TrackedDict` uses `HashMap<String, PyObject>` internally. Non-string keys are not supported and will cause a runtime type error.

6. **No thread safety**: `TachyonEngine` is not `Send` or `Sync`. Janus is designed for single-threaded Python usage only.

7. **Container re-wrapping**: When `switch_branch` restores a `list` or `dict` attribute, the restored value is a raw Python `list`/`dict` (not a `TrackedList`/`TrackedDict`). This is a known bug — subsequent mutations after switching will not be tracked until the attribute is reassigned.

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
