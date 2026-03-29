# Getting Started

Janus is a powerful state management engine for Python objects, providing Git-like capabilities for branching, switching, and merging state. Powered by the high-performance Rust-based **Tachyon-RS** engine, Janus tracks mutations with near-zero overhead and allows you to travel through the "multiverse" of your object's history.

## Core Features

- **Non-Linear History**: Create branches and jump between different states of your objects.
- **Bi-directional Deltas**: Storing only the changes (deltas) ensures minimal memory usage.
- **Container Awareness**: Intelligent 3-way merging for Python lists and dictionaries.
- **Extensible Plugins**: Built-in support for NumPy and Pandas, with a registry for custom types.
- **Visualization**: Built-in tools for rendering the state DAG using Mermaid or Matplotlib.

## Installation

```bash
uv add janus
```

## Basic Usage

Janus allows you to opt-in to complexity. Start with a simple linear history or dive into multiversal branching.

### Linear Mode (Undo/Redo)

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
```

### Multiversal Mode (Branching)

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

# Multiversal rollback
sim.jump_to("stable")
print(sim.points)  # [1, 2, 3]
```

Refer to the [Core Features](#core-features) section for more details.
