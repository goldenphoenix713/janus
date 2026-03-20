# Janus 🏺

> **The Extensible Multiverse Engine for Python Objects.**

Janus provides a Git-like API for branching, switching, and flattening the state of complex Python objects, powered by a lightning-fast Rust backend (**Tachyon-RS**). No deep-copying, no manual history tracking, and near-zero performance penalties.

## 🚀 Getting Started

Janus allows you to opt-in to complexity. Start with a simple linear history or dive into multiversal branching.

```python
from janus import janus

@janus(mode="multiversal")
class Simulation:
    def __init__(self):
        self.points = [1, 2, 3]

sim = Simulation()
sim.branch("stable")

# Perform mutations
sim.points.append(999)
print(sim.points) # [1, 2, 3, 999]

# Multiversal rollback via Tachyon-RS
sim.switch("stable")
print(sim.points) # [1, 2, 3]
```

## 🏗️ Architectural Pillars

1. **Tiered Complexity**: Use `mode="linear"` for high-speed undo/redo, or `mode="multiversal"` for Git-like branching and merging.
2. **Extensible Plugin Registry**: Register a `JanusAdapter` to track `pandas.DataFrames`, `torch.Tensors`, or any custom object without slowing down the core engine.
3. **Timeline Extraction**: Flatten complex multiversal paths into linear audit sequences for visualization and debugging.

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

Under the hood, Janus offloads all state delta logic to **Tachyon-RS**, a specialized Rust engine that operates on a Directed Acyclic Graph (DAG) of state nodes. By storing only the "inverse operations" and bi-directional transitions, Tachyon-RS enables time travel with $O(1)$ logging overhead.

## License

Janus is distributed under the terms of both the MIT license and the Apache License (Version 2.0). See LICENSE-MIT and LICENSE-APACHE for details.
