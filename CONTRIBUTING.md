# Contributing to Janus

First off, thank you for considering contributing to Janus! It's people like you that make Janus such a great tool.

## Our Workflow: Fork & Pull Request

We follow a typical "Fork and Pull Request" workflow to maintain code quality and security. This means:

1. **Fork** the repository to your own account.
2. **Clone** your fork to your local machine.
3. **Create a branch** for your specific feature or fix.
4. **Implement your changes** (ensure tests pass and typing is correct).
5. **Push** your branch to your fork.
6. **Open a Pull Request** (PR) from your fork back to the main Janus repository.

## Development Setup

We use `uv` and `maturin` for development.

```bash
# Clone and setup
git clone https://github.com/your-username/janus.git
cd janus

# Build the Rust extension in develop mode
uv run maturin develop
```

## Quality Standards

Every Pull Request must pass our automated CI pipeline:

- **Linting**: `pre-commit run --all-files`
- **Testing**: `uv run pytest` (must maintain >90% coverage)
- **Typing**: `uv run mypy .` (must be `strict` compliant)
- **Docs**: Documentation must build without warnings.

## Branch Protection

The `main` branch is protected. **Direct pushes to `main` are disabled.** All changes must come through a Pull Request that has been approved and passes all CI status checks.

Thank you for helping us build the future of non-linear state management!
