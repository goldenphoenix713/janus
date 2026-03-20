# Contributing to Janus

First off, thanks for taking the time to contribute! Whether you're fixing a bug in the **Tachyon-RS** engine or improving the **Janus** Python API, your help makes state-travel safer and faster for everyone.

Janus is a hybrid project: we use **Rust** for high-performance delta tracking and **Python** for a seamless developer experience.

---

## Development Setup

We use `uv` for Python environment management and `cargo` for Rust. You will need both installed on your system.

1. **Clone the repository:**

    ```bash
    git clone [https://github.com/youruser/janus.git](https://github.com/youruser/janus.git)
    cd janus
    ```

2. **Initialize the environment:**

    ```bash
    uv venv
    source .venv/bin/activate  # Or .venv\Scripts\activate on Windows
    uv add --dev maturin pytest ruff
    ```

3. **Compile the Tachyon-RS engine:**

    ```bash
    uv run maturin develop
    ```

    *Note: Using `develop` symlinks the Rust binary into your virtual environment, allowing you to test changes without re-installing.*

---

## Testing and Quality

We maintain a high bar for performance and correctness. If you add a feature, you must add a corresponding test.

### Python Tests

Run the suite using `pytest`:

```bash
uv run pytest tests/
```

## Rust Lints

​Before submitting Rust code, please run Clippy to ensure idiomatic memory management and performance:

```bash
cargo clippy -- -D warnings
 ```

## Project Structure

​janus/ (Python): This is the "Face." Focus here for decorator logic, proxy implementations, and high-level API improvements.
​src/ (Rust): This is the "Engine" (Tachyon-RS). Dive here for core delta-stack optimizations, memory safety (WeakRefs), and low-level container wrappers.
​

## Submitting a Pull Request

​Branch: Create a feature branch (git checkout -b feature/your-feature-name).
​Commit: Use descriptive, imperative commit messages (e.g., feat(engine): add support for TrackedSet).
​PR: Open a Pull Request. Describe the change, the impact on performance, and why it's necessary.
​Review: A maintainer will review your code. We value technical excellence and a collaborative spirit!
​

## License

​By contributing, you agree that your contributions will be dual-licensed under the MIT and Apache 2.0 licenses.
​

## The Contributor's Creed

​The Golden Rule of Tachyon-RS: If an operation can be done in O(1) time, don't settle for O(N). Janus is built for speed; every microsecond we save in the engine is a microsecond we give back to the developer.
