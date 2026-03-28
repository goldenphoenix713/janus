# Janus 🏺

[![Janus CI](https://github.com/goldenphoenix713/janus/actions/workflows/ci.yml/badge.svg)](https://github.com/goldenphoenix713/janus/actions/workflows/ci.yml)
[![License: MIT/Apache-2.0](https://img.shields.io/badge/License-MIT%2FApache--2.0-blue.svg)](LICENSE-MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/release/python-3120/)

> **The Extensible Multiverse Engine for Python Objects.**

Janus provides a Git-like API for branching, switching, and flattening the state of complex Python objects, powered by a lightning-fast Rust backend (**Tachyon-RS**). No deep-copying, no manual history tracking, and near-zero performance penalties.

## 🚀 Getting Started

Janus allows you to opt-in to complexity. Start with a simple linear history or dive into multiversal branching.

### Linear Mode — Undo / Redo

```python
from janus import TimelineBase

class Document(TimelineBase):
    def __init__(self) -> None:
        super().__init__()
        self.text = ""

doc = Document()
doc.text = "Hello"
doc.text = "Hello World"

doc.undo()
print(doc.text)  # "Hello"

doc.redo()
print(doc.text)  # "Hello World"
```

### Multiversal Mode — Branching

```python
from janus import MultiverseBase

class Simulation(MultiverseBase):
    def __init__(self) -> None:
        super().__init__()
        self.points = [1, 2, 3]

sim = Simulation()
sim.branch("stable")

# Perform mutations
sim.points.append(999)
print(sim.points)  # [1, 2, 3, 999]

# Multiversal rollback via Tachyon-RS
sim.jump_to("stable")
print(sim.points)  # [1, 2, 3]
```

## 🏗️ Architectural Pillars

1. **Extensible Plugin Registry**: Register a `JanusAdapter` to track `pandas.DataFrames`, `numpy.ndarrays`, `torch.Tensors`, or any custom object without slowing down the core engine.
2. **Timeline Extraction**: Flatten complex multiversal paths into linear audit sequences for visualization and debugging.
3. **Third-Party Integration**: Built-in `TrackedDataFrame` and `TrackedNumpyArray` support with full indexer and view-tracking.

## 🚀 Use Cases

- **AI Agent Experiments**: Allow agents to test multiple paths in parallel and revert with knowledge of failed states.
- **Data Science Workflows**: Instantly reverse complex object states without rerunning expensive computation cells.
- **Non-Linear Document History**: Manage "what-if" scenarios for complex file and data structures.

## 📚 Documentation

- [Architecture Blueprint](docs/architecture/janus_blueprint.md)
- [Technical Deep Dive](docs/architecture/TECHNICAL_DEEP_DIVE.md)
- [Project Roadmap](docs/planning/ROADMAP.md)
- [Ideas & Scratchpad](docs/planning/IDEAS.md)
- [Contributing Guide](docs/governance/CONTRIBUTING.md)

## ⚡ Powered by Tachyon-RS

Under the hood, Janus offloads all state delta logic to **Tachyon-RS**, a specialized Rust engine that operates on a Directed Acyclic Graph (DAG) of state nodes. By storing only bi-directional operations, Tachyon-RS enables time travel with $O(1)$ logging overhead.

## License

Janus is distributed under the terms of both the [MIT license](LICENSE-MIT) and the [Apache License (Version 2.0)](LICENSE-APACHE).
