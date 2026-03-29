from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:
    import matplotlib.pyplot as plt
    import networkx as nx

    MPL_AVAILABLE = True
except ImportError:
    MPL_AVAILABLE = False

if TYPE_CHECKING:
    from janus.base import JanusBase


class MatplotlibBackend:
    """
    Renders the multiverse DAG using Matplotlib and NetworkX.

    This backend provides a more traditional node-link diagram with
    customizable colors and layout.
    """

    def plot(self, obj: JanusBase, **kwargs: Any) -> Any:
        """
        Renders the multiverse graph using Matplotlib.

        Args:
            obj: The Multiverse instance to visualize.
            show: Whether to call plt.show() immediately.
            figsize: Tuple of (width, height) for the figure.
            node_size: Size of the nodes in the plot.
            font_size: Size of the text labels.
            title: Custom title for the plot.

        Returns:
            A Matplotlib Figure object.
        """
        if not MPL_AVAILABLE:
            raise ImportError(
                "Matplotlib backend requires 'matplotlib' and 'networkx'. "
                "Install them to use this feature."
            )

        data = obj._engine.get_graph_data()

        G = nx.DiGraph()
        node_labels = {}
        node_colors = []

        for node in data:
            nid = node["id"]
            labels = node["labels"]
            is_current = node["is_current"]

            G.add_node(nid)

            label_suffix = f"\n({', '.join(labels)})" if labels else ""
            node_labels[nid] = f"N{nid}{label_suffix}"

            if is_current:
                node_colors.append("#ff9ce6")
            elif labels:
                node_colors.append("#e1f5fe")
            else:
                node_colors.append("#f5f5f5")

        for node in data:
            nid = node["id"]
            for p_id in node["parents"]:
                G.add_edge(p_id, nid)

        # Layout: Rank by topological generation for a balanced timeline look
        try:
            generations = list(nx.topological_generations(G))
            pos = {}
            for x, nodes in enumerate(generations):
                # Spread nodes vertically within the same generation
                offset = (len(nodes) - 1) / 2.0
                for y, nid in enumerate(nodes):
                    pos[nid] = (x, offset - y)
        except (nx.NetworkXUnfeasible, nx.NetworkXError):
            pos = nx.spring_layout(G)

        fig, ax = plt.subplots(figsize=kwargs.get("figsize", (8, 5)))
        nx.draw(
            G,
            pos,
            labels=node_labels,
            with_labels=True,
            node_color=node_colors,
            node_size=kwargs.get("node_size", 1200),
            node_shape="o",
            font_size=kwargs.get("font_size", 7),
            arrows=True,
            ax=ax,
            edge_color="#888",
            width=1.0,
            edgecolors="#333",
        )

        ax.set_title(kwargs.get("title", f"Janus History: {type(obj).__name__}"))

        if kwargs.get("show", False):
            plt.show()

        return fig
