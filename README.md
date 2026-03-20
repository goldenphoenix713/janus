# Janus 🏺

> **The Extensible Multiverse Engine for Python Objects.**

Janus provides a Git-like API for branching, switching, and flattening the state of complex Python objects, powered by a lightning-fast Rust backend (**Tachyon-RS**).

## 🚀 Tiered Complexity

Choose the right tool for the job. Use `mode="linear"` for high-speed, standard undo/redo, or opt into `mode="multiversal"` to enable parallel state branching and graph traversal.

## 🔌 Extensible Plugin Registry

Need to track a `pandas.DataFrame` or a complex custom object? Register a `JanusAdapter` and let Tachyon-RS safely manage the state blobs without slowing down the core engine.

---

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

Under the hood, Janus offloads all state delta logic to **Tachyon-RS**, a specialized Rust engine that tracks changes with faster-than-light efficiency. By storing only the "inverse operations," Tachyon-RS allows you to move back and forth through time with near-zero overhead.

## License

Janus is distributed under the terms of both the MIT license and the Apache License (Version 2.0). See LICENSE-MIT and LICENSE-APACHE for details.
