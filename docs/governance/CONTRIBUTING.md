# Contributing to Janus

First off, thanks for taking the time to contribute! Whether you're fixing a bug in the **Tachyon-RS** engine or improving the **Janus** Python API, your help makes state-travel safer and faster for everyone.

Janus is a hybrid project: we use **Rust** for high-performance delta tracking and **Python** for a seamless developer experience.

---

## Development Setup

We use `uv` for Python environment management and `cargo` for Rust. You will need both installed on your system.

1. **Clone the repository:**

    ```bash
    git clone https://github.com/goldenphoenix713/janus.git
    cd janus
    ```

2. **Initialize the environment:**

    ```bash
    uv venv
    source .venv/bin/activate  # Or .venv\Scripts\activate on Windows
    uv sync --dev              # Install all dev dependencies
    ```

3. **Compile the Tachyon-RS engine:**

    ```bash
    uv run maturin develop
    ```

    *Note: Using `develop` symlinks the Rust binary into your virtual environment, allowing you to test changes without re-installing.*

---

## Code Quality

All code quality is enforced by **pre-commit hooks** (`.pre-commit-config.yaml`). Install them with:

```bash
pre-commit install
```

Every commit triggers: ruff (lint + format), mypy (strict mode), clippy, rustfmt, and pytest.

### Python

- **Ruff**: Lints and formats all Python files. See `pyproject.toml` under `[tool.ruff]` for the full rule set.
- **Mypy**: Runs in `strict` mode — all functions must have type annotations.
- **All Python source files** must include `from __future__ import annotations`.

### Rust

- **Clippy** runs with `-D warnings` (all warnings are errors).
- **Rustfmt** enforces the default Rust formatting style.

---

## Testing

We maintain a high bar for performance and correctness. If you add a feature, you must add a corresponding test.

```bash
uv run pytest tests/ -v        # Full test suite
uv run pytest -m "not slow"    # Skip slow benchmarks (used in pre-commit)
```

---

## Project Structure

- **`janus/`** (Python): This is the "Face." Focus here for base class logic, container proxies, plugin adapters, and the pandas integration.
- **`src/`** (Rust): This is the "Engine" (Tachyon-RS). Dive here for core DAG operations, delta logging, and low-level container core wrappers.

---

## Submitting a Pull Request

1. **Branch**: Create a feature branch (`git checkout -b feature/your-feature-name`).
2. **Commit**: Use descriptive, imperative commit messages (e.g., `feat(engine): add support for TrackedSet`).
3. **Pre-commit**: Ensure all hooks pass (`pre-commit run --all-files`).
4. **PR**: Open a Pull Request. Describe the change, the impact on performance, and why it's necessary.
5. **Review**: A maintainer will review your code. We value technical excellence and a collaborative spirit!

---

## License

By contributing, you agree that your contributions will be dual-licensed under the MIT and Apache 2.0 licenses.

---

## The Contributor's Creed

> The Golden Rule of Tachyon-RS: If an operation can be done in O(1) time, don't settle for O(N). Janus is built for speed; every microsecond we save in the engine is a microsecond we give back to the developer.
