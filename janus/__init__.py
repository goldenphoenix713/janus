"""
Janus: A library for tracking and branching state transitions in Python objects.

Janus provides a Git-like interface for Python objects, allowing you to:
1. Track mutations to lists, dictionaries, and third-party objects (NumPy, Pandas).
2. Navigate history with undo/redo operations.
3. Create branches and merge changes between them.
4. Visualize state transition graphs (DAGs).
"""

from .base import JanusBase, MultiverseBase, TimelineBase
from .options import options
from .registry import JanusAdapter, register_adapter

__all__ = [
    "register_adapter",
    "JanusAdapter",
    "JanusBase",
    "MultiverseBase",
    "TimelineBase",
    "options",
]
