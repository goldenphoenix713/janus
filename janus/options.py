from dataclasses import dataclass, field
from typing import Any


@dataclass
class PlottingOptions:
    """
    Configuration for Multiverse visualization.

    Attributes:
        backend: The visualization backend to use ("mermaid" or "matplotlib").
        show_labels: Whether to show human-readable labels on nodes.
        color_scheme: The color palette for the rendered graph.
        engine_kwargs: Additional arguments passed to the underlying engine.
    """

    backend: str = "mermaid"
    show_labels: bool = True
    color_scheme: str = "default"
    engine_kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass
class Options:
    """
    Global configuration for Janus objects.

    Attributes:
        plotting: Options for graph visualization.
        max_history: The maximum number of nodes to keep in the DAG.
        default_mode: The default engine mode ("linear" or "multiversal").
    """

    plotting: PlottingOptions = field(default_factory=PlottingOptions)
    max_history: int = 50000
    default_mode: str = "multiversal"


options = Options()
