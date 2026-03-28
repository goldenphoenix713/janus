# [Planning] Waypoint 4.1: Node Metadata & Querying

This milestone will enable the Tachyon Engine to store and retrieve arbitrary metadata associated with individual state nodes. This "semantic tagging" is the prerequisite for visual timeline exploration and result-driven branch selection.

## 🛠 Proposed Changes

### [Rust Engine](src/engine.rs)

#### [MODIFY] [engine.rs](src/engine.rs)

- **`StateNode` Struct**: Re-enable and finalize the `metadata: HashMap<String, PyObject>` field.
- **Metadata Management**:
  - Implement `set_node_metadata(node_id, key, value)` to attach data to a specific node.
  - Implement `get_node_metadata(node_id, key)` for retrieval.
  - Implement `get_all_node_metadata(node_id)` to export all tags for visualization.

### [Janus Core](janus/base.py)

#### [MODIFY] [base.py](janus/base.py)

- **`JanusBase.tag_moment()`**: Introduce a public method to tag the current state:

  ```python
  sim.tag_moment(loss=0.01, epoch=5, description="Initial convergence")
  ```

- **`JanusBase.get_moment_tags()`**: Retrieve metadata for the current or a specified node.

## 🧪 Verification Plan

### Automated Tests

- Create `tests/test_node_metadata.py`.
- Verify that metadata is preserved across branch switches and undos.
- Confirm that multiple tags can be attached and retrieved correctly.

### Manual Verification

- Tag a series of nodes in a loop and verify the exported metadata structure via `extract_timeline()`.
