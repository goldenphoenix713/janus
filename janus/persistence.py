from __future__ import annotations

import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import msgpack

try:
    import pandas as pd

    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

from janus.registry import CONTAINER_REGISTRY

if TYPE_CHECKING:
    from janus.base import JanusBase


def janus_encoder(obj: Any) -> Any:
    """Custom encoder for Janus-tracked objects to ensure msgpack compatibility."""
    # Check for pandas/numpy without causing circular imports or requiring them
    # We look at the class name to avoid direct isinstance checks if possible,
    # or import locally.
    cls_name = type(obj).__name__

    if cls_name in ("TrackedDataFrame", "DataFrame"):
        return {
            "__janus_type__": "pd.DataFrame",
            "data": obj.to_dict(orient="split"),
        }
    if cls_name in ("TrackedSeries", "Series"):
        return {
            "__janus_type__": "pd.Series",
            "data": obj.to_dict(),
            "name": getattr(obj, "name", None),
        }

    dict_cls = CONTAINER_REGISTRY.get("dict")
    if dict_cls and isinstance(obj, dict_cls):
        return dict(obj)  # type: ignore[call-overload]
    list_cls = CONTAINER_REGISTRY.get("list")
    if list_cls and isinstance(obj, list_cls):
        return list(obj)  # type: ignore[call-overload]

    return obj


def janus_decoder(obj: Any) -> Any:
    """Custom decoder for Janus-tracked objects to re-hydrate during load."""
    if isinstance(obj, dict) and "__janus_type__" in obj and PANDAS_AVAILABLE:
        if obj["__janus_type__"] == "pd.DataFrame":
            return pd.DataFrame(**obj["data"])
        if obj["__janus_type__"] == "pd.Series":
            return pd.Series(obj["data"], name=obj.get("name"))
    return obj


class JanusPersistence:
    """Handles serialization and persistence of Janus state histories."""

    @staticmethod
    def save(obj: JanusBase, path: str | Path) -> None:
        """Persist the entire multiverse/timeline history to a .jns file."""
        path = Path(path)
        if path.suffix != ".jns":
            path = path.with_suffix(".jns")

        # 1. Get DAG from Rust
        dag_state = obj._engine.get_graph_state()

        # 2. Extract Python context (shadow snapshots for plugins)
        context = {k: v for k, v in obj.__dict__.items() if k.startswith("_shadow_")}

        # 3. Serialize
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "dag.msgpack",
                msgpack.packb(dag_state, default=janus_encoder, use_bin_type=True),
            )
            zf.writestr(
                "context.msgpack",
                msgpack.packb(context, default=janus_encoder, use_bin_type=True),
            )

    @staticmethod
    def load(obj: JanusBase, path: str | Path) -> None:
        """Restore history and state from a .jns file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Persistence file not found: {path}")

        with zipfile.ZipFile(path, "r") as zf:
            dag_data = msgpack.unpackb(
                zf.read("dag.msgpack"),
                object_hook=janus_decoder,
                strict_map_key=False,
                raw=False,
            )
            ctx_data = msgpack.unpackb(
                zf.read("context.msgpack"),
                object_hook=janus_decoder,
                strict_map_key=False,
                raw=False,
            )

        # 1. Restore Rust engine state
        obj._engine.set_graph_state(dag_data)

        obj._restoring = True
        try:
            # 2. Re-hydrate Python context
            for k, v in ctx_data.items():
                setattr(obj, k, v)

            # 3. Synchronize live objects with the loaded head node
            obj._engine.sync_from_root()

            # 4. Re-link top-level attributes to ensure they are tracked
            for name, value in obj.__dict__.items():
                if not name.startswith("_"):
                    setattr(obj, name, value)
        finally:
            obj._restoring = False
