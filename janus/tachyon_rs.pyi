from __future__ import annotations

from collections.abc import Callable
from typing import Any

class TachyonEngine:
    """
    The core Janus engine implemented in Rust.

    TachyonEngine manages the state transition graph (DAG), branch history,
    and metadata. It provides methods for logging operations, navigating
    history, and performing complex graph operations like merging and squashing.
    """

    def __init__(
        self, owner: Any, mode: str = "multiversal", max_nodes: int = 50000
    ) -> None:
        """
        Initialize the Janus engine.

        Args:
            owner: The JanusBase instance that owns this engine.
            mode: The operation mode ("linear" or "multiversal").
            max_nodes: The maximum number of nodes to keep in history.
        """
        ...

    @property
    def owner(self) -> Any:
        """The JanusBase instance that owns this engine."""
        ...

    def get_graph_data(self) -> list[dict[str, Any]]:
        """Retrieve the current DAG structure and node metadata for visualization."""
        ...

    def list_nodes(self) -> list[str]:
        """List all human-readable labels and branch heads."""
        ...

    def list_branches(self) -> list[str]:
        """List all active branch names."""
        ...

    def log_update_attr(self, name: str, old_value: Any, new_value: Any) -> None:
        """Log a standard attribute assignment."""
        ...

    def log_plugin_op(self, path: str, adapter_name: str, delta_blob: Any) -> None:
        """Log a custom operation from a plugin adapter."""
        ...

    def label_node(self, label: str) -> None:
        """Assign a human-readable label to the current node."""
        ...

    def move_to(self, label: str) -> None:
        """Move the 'head' to a labeled node or branch head."""
        ...

    def get_node_id(self, label: str) -> int | None:
        """Get the internal node ID for a given label."""
        ...

    def set_metadata(self, key: str, value: Any) -> None:
        """Set metadata on the current node."""
        ...

    def get_metadata(self, key: str, node_id: int | None = None) -> Any | None:
        """Get metadata from the current or specified node."""
        ...

    def get_metadata_keys(self, node_id: int | None = None) -> list[str]:
        """List all metadata keys for the specified node."""
        ...

    def get_metadata_values(self, node_id: int | None = None) -> list[Any]:
        """List all metadata values for the specified node."""
        ...

    def get_metadata_items(self, node_id: int | None = None) -> list[tuple[str, Any]]:
        """List all metadata key-value pairs for the specified node."""
        ...

    def find_nodes_by_metadata(self, key: str, value: Any) -> list[int]:
        """Find all node IDs where metadata[key] == value."""
        ...

    def undo(self) -> None:
        """Step back to the parent of the current node."""
        ...

    def redo(self) -> None:
        """Step forward to a child of the current node (if unambiguous)."""
        ...

    def move_to_node_id(self, node_id: int) -> None:
        """Move the 'head' to a specific internal node ID."""
        ...

    def sync_from_root(self) -> None:
        """Synchronize the live state from the genesis node forward."""
        ...

    def merge_branch(
        self, source_label: str, strategy: str | Callable[..., Any] | None = None
    ) -> None:
        """Merge another branch into the current one."""
        ...

    def move_to_creation(self) -> None:
        """Move to the genesis node (Node 0)."""
        ...

    def create_branch(self, label: str) -> None:
        """Create a new branch head at the current node."""
        ...

    @property
    def current_branch(self) -> str:
        """The name of the currently active branch."""
        ...

    @property
    def current_node(self) -> int:
        """The internal ID of the current head node."""
        ...

    def extract_timeline(
        self, label: str | None = None, filter_attr: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Extract linear history from root to the specified node."""
        ...

    def log_list_pop(self, path: str, index: int, popped_value: Any) -> None:
        """Log a list pop operation."""
        ...

    def log_list_insert(self, path: str, index: int, value: Any) -> None:
        """Log a list insert operation."""
        ...

    def log_list_replace(
        self, path: str, index: int, old_value: Any, new_value: Any
    ) -> None:
        """Log a list item replacement."""
        ...

    def log_list_clear(self, path: str, old_values: list[Any]) -> None:
        """Log a list clear operation."""
        ...

    def log_list_extend(self, path: str, new_values: list[Any]) -> None:
        """Log a list extension."""
        ...

    def log_list_remove(self, path: str, value: Any) -> None:
        """Log a list element removal."""
        ...

    def log_dict_clear(self, path: str, keys: list[str], old_values: list[Any]) -> None:
        """Log a dictionary clear operation."""
        ...

    def log_dict_pop(self, path: str, key: str, old_value: Any) -> None:
        """Log a dictionary pop operation."""
        ...

    def log_dict_popitem(self, path: str, key: str, old_value: Any) -> None:
        """Log a dictionary popitem operation."""
        ...

    def log_dict_setdefault(self, path: str, key: str, value: Any) -> None:
        """Log a dictionary setdefault operation."""
        ...

    def log_dict_update(
        self, path: str, keys: list[str], old_values: list[Any], new_values: list[Any]
    ) -> None:
        """Log a dictionary update operation."""
        ...

    def log_dict_delete(self, path: str, key: str, old_value: Any) -> None:
        """Log a dictionary key deletion."""
        ...

    def delete_branch(self, label: str) -> None:
        """Delete a branch head label."""
        ...

    def squash(self, start_label: str, end_label: str) -> None:
        """Consolidate a linear chain of nodes into a single node."""
        ...

    def squash_branch(self, label: str | None = None) -> None:
        """Consolidate the current branch (or specified) into a single path."""
        ...

    def get_diff(self, start_label: str, end_label: str) -> dict[str, Any]:
        """Calculate the net state difference between two nodes."""
        ...

    def get_graph_state(self) -> dict[str, Any]:
        """Export the entire engine state for persistence."""
        ...

    def set_graph_state(self, state: dict[str, Any]) -> None:
        """Import an engine state from a previous export."""
        ...

class TrackedListCore:
    """Low-level tracking core for lists."""
    def __init__(self, engine: TachyonEngine, name: str) -> None: ...
    def log_insert(self, index: int, value: Any) -> None: ...
    def log_pop(self, index: int, value: Any) -> None: ...
    def log_replace(self, index: int, old_value: Any, new_value: Any) -> None: ...
    def log_clear(self, old_values: list[Any]) -> None: ...
    def log_extend(self, new_values: list[Any]) -> None: ...

class TrackedDictCore:
    """Low-level tracking core for dictionaries."""
    def __init__(self, engine: TachyonEngine, name: str) -> None: ...
    def log_update(
        self, keys: list[str], old_values: list[Any], new_values: list[Any]
    ) -> None: ...
    def log_delete(self, key: str, old_value: Any) -> None: ...
    def log_clear(self, keys: list[str], old_values: list[Any]) -> None: ...
    def log_pop(self, key: str, old_value: Any) -> None: ...
