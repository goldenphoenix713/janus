from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import MultiverseBase


def to_mermaid(obj: "MultiverseBase") -> str:
    """
    Generate a Mermaid diagram string for the Janus multiverse.

    Returns a string that can be rendered in Mermaid-supported environments
    (like GitHub, GitLab, or VS Code Mermaid plugins).
    """
    data = obj._engine.get_graph_data()

    # Sort by ID for deterministic output
    data.sort(key=lambda x: x["id"])

    lines = ["graph LR"]  # Left to Right looks better for timelines

    # 1. Define nodes and labels
    for node in data:
        nid = node["id"]
        labels = node["labels"]
        is_current = node["is_current"]

        # Format labels: "main, v1.0"
        label_text = f"<br/><b>{', '.join(labels)}</b>" if labels else ""
        node_text = f"Node {nid}{label_text}"

        # Styling and shapes
        if is_current:
            # Current node is a double-circle
            lines.append(f'    node{nid}(("{node_text}"))')
            lines.append(
                f"    style node{nid} fill:#ff9ce6,stroke:#333,stroke-width:4px"
            )
        elif labels:
            # Labeled nodes (milestones/branch heads) are rounded
            lines.append(f'    node{nid}("{node_text}")')
            lines.append(f"    style node{nid} fill:#e1f5fe,stroke:#01579b")
        else:
            # Intermediate nodes are rectangles
            lines.append(f'    node{nid}["{node_text}"]')

    # 2. Define edges
    for node in data:
        nid = node["id"]
        # Parents are stored as a list (supports merge nodes)
        for p_id in node["parents"]:
            lines.append(f"    node{p_id} --> node{nid}")

    return "\n".join(lines)
