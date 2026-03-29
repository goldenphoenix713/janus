# Janus Documentation

> **Extensible, non-linear state travel powered by the Tachyon-RS engine.**

Janus provides a Git-like API for branching, switching, and flattening the state of complex Python objects, powered by a lightning-fast Rust backend.

```{toctree}
:maxdepth: 2
:caption: Contents:

self
getting_started
architecture/index
api/index
```

(features)=

## Features

- **Linear History**: Simple undo/redo functionality for any Python object.
- **Multiversal Branching**: Create, switch, and merge branches of object state.
- **Container Awareness**: Intelligent 3-way reconciliation for lists and dicts.
- **Pluggable Backends**: Extensible registry for tracking specialized types (Pandas, NumPy, etc.).
- **Rust Engine**: Near-zero performance overhead using the Tachyon-RS engine.

## Indices and tables

- {ref}`genindex`
- {ref}`modindex`
- {ref}`search`
