from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from janus.base import JanusBase


class VizBackend(Protocol):
    """Protocol for Janus visualization backends."""

    def plot(self, obj: JanusBase, **kwargs: Any) -> Any:
        """Render the multiverse DAG."""
        ...


class MermaidBackend:
    """
    Renders the multiverse DAG as a Mermaid diagram string.
    """

    def plot(self, obj: JanusBase, **kwargs: Any) -> str:
        """
        Generate a Mermaid diagram for the given Janus object.

        Args:
            obj: The JanusBase instance to visualize.
            **kwargs: Additional plotting options.

        Returns:
            A string containing the Mermaid diagram definition.
        """
        data = obj._engine.get_graph_data()
        data.sort(key=lambda x: x["id"])

        lines = ["graph LR"]
        for node in data:
            nid = node["id"]
            labels = node["labels"]
            is_current = node["is_current"]

            label_text = f"<br/><b>{', '.join(labels)}</b>" if labels else ""
            node_text = f"Node {nid}{label_text}"

            if is_current:
                lines.append(f'    node{nid}(("{node_text}"))')
                lines.append(
                    f"    style node{nid} fill:#ff9ce6,stroke:#333,stroke-width:4px"
                )
            elif labels:
                lines.append(f'    node{nid}("{node_text}")')
                lines.append(f"    style node{nid} fill:#e1f5fe,stroke:#01579b")
            else:
                lines.append(f'    node{nid}["{node_text}"]')

        for node in data:
            nid = node["id"]
            for p_id in node["parents"]:
                lines.append(f"    node{p_id} --> node{nid}")

        return "\n".join(lines)


VIZ_BACKENDS: dict[str, VizBackend] = {
    "mermaid": MermaidBackend(),
}


def get_backend(name: str) -> VizBackend:
    """Retrieve a visualization backend by name."""
    if name not in VIZ_BACKENDS:
        # Simple lazy loading for matplotlib if it's added later
        if name == "matplotlib":
            try:
                from janus.viz_mpl import MatplotlibBackend

                VIZ_BACKENDS["matplotlib"] = MatplotlibBackend()
                return VIZ_BACKENDS["matplotlib"]
            except ImportError:
                raise ImportError(
                    "Matplotlib backend requires 'matplotlib' and 'networkx'. "
                    "Install them to use this feature."
                )

        raise ValueError(f"Unknown visualization backend: {name}")
    return VIZ_BACKENDS[name]


def register_backend(name: str, backend: VizBackend) -> None:
    """Register a new visualization backend."""
    VIZ_BACKENDS[name] = backend
