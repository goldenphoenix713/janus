use pyo3::prelude::*;
use pyo3::types::{PyDict, PyDictMethods};
use std::collections::HashMap;

use crate::models::{DictOperation, ListOperation, Mode, Operation, StateNode};

#[pyclass]
pub struct TachyonEngine {
    pub owner: Py<pyo3::types::PyWeakref>,
    pub nodes: HashMap<usize, StateNode>,
    pub node_labels: HashMap<String, usize>,
    pub active_branch: String,
    pub branch_labels: HashMap<String, usize>,
    pub current_node: usize,
    pub next_node_id: usize,
    pub mode: Mode,
    pub max_nodes: usize,
}

#[pymethods]
impl TachyonEngine {
    #[new]
    #[pyo3(signature = (owner, mode, max_nodes=50000))]
    pub fn new(owner: Bound<'_, PyAny>, mode: String, max_nodes: usize) -> PyResult<Self> {
        let py = owner.py();
        let weakref_module = py.import("weakref")?;
        let weak_owner = weakref_module
            .call_method1("ref", (&owner,))?
            .downcast_into::<pyo3::types::PyWeakref>()?
            .unbind();

        let mut node_labels = HashMap::new();
        let mut branch_labels = HashMap::new();
        node_labels.insert("__genesis__".to_string(), 0);
        branch_labels.insert("main".to_string(), 0);

        let mut nodes = HashMap::new();
        nodes.insert(
            0,
            StateNode {
                id: 0,
                parents: Vec::new(),
                deltas: Vec::new(),
                metadata: HashMap::new(),
                timestamp: std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap()
                    .as_secs(),
            },
        );

        let mode_enum = match mode.as_str() {
            "linear" => Mode::Linear,
            "multiversal" => Mode::Multiversal,
            _ => {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                    "Invalid mode: {}",
                    mode
                )))
            }
        };

        Ok(TachyonEngine {
            owner: weak_owner,
            nodes,
            node_labels,
            branch_labels,
            active_branch: "main".to_string(),
            current_node: 0,
            next_node_id: 1,
            mode: mode_enum,
            max_nodes,
        })
    }

    pub fn get_graph_data(&self, py: Python) -> PyResult<PyObject> {
        let mut nodes_data = Vec::new();
        for (&id, node) in &self.nodes {
            let mut node_dict = HashMap::<&str, PyObject>::new();
            node_dict.insert("id", id.into_pyobject(py)?.to_owned().into_any().unbind());
            node_dict.insert(
                "parents",
                node.parents
                    .clone()
                    .into_pyobject(py)?
                    .to_owned()
                    .into_any()
                    .unbind(),
            );
            node_dict.insert(
                "is_current",
                (id == self.current_node)
                    .into_pyobject(py)?
                    .to_owned()
                    .into_any()
                    .unbind(),
            );

            let mut labels = Vec::new();
            for (label, &nid) in &self.node_labels {
                if nid == id {
                    labels.push(label.clone());
                }
            }
            node_dict.insert(
                "labels",
                labels.into_pyobject(py)?.to_owned().into_any().unbind(),
            );
            nodes_data.push(node_dict.into_pyobject(py)?);
        }

        if !self.nodes.contains_key(&0) {
            let mut root_dict = HashMap::<&str, PyObject>::new();
            root_dict.insert(
                "id",
                0usize.into_pyobject(py)?.to_owned().into_any().unbind(),
            );
            root_dict.insert(
                "parents",
                Vec::<usize>::new()
                    .into_pyobject(py)?
                    .to_owned()
                    .into_any()
                    .unbind(),
            );
            root_dict.insert(
                "is_current",
                (self.current_node == 0)
                    .into_pyobject(py)?
                    .to_owned()
                    .into_any()
                    .unbind(),
            );

            let mut labels = Vec::new();
            for (label, &nid) in &self.node_labels {
                if nid == 0 {
                    labels.push(label.clone());
                }
            }
            root_dict.insert(
                "labels",
                labels.into_pyobject(py)?.to_owned().into_any().unbind(),
            );
            nodes_data.push(root_dict.into_pyobject(py)?);
        }

        Ok(nodes_data.into_pyobject(py)?.into())
    }

    #[getter]
    pub fn owner(&self, py: Python) -> PyResult<PyObject> {
        Ok(self.upgrade_owner(py)?.into_pyobject(py)?.into())
    }

    pub fn list_nodes(&self) -> Vec<String> {
        self.node_labels.keys().cloned().collect()
    }

    pub fn list_branches(&self) -> Vec<String> {
        self.branch_labels.keys().cloned().collect()
    }

    pub fn log_update_attr(&mut self, name: String, old_value: PyObject, new_value: PyObject) {
        let op = Operation::UpdateAttr {
            name,
            old_value,
            new_value,
        };
        self.append_node(vec![op]);
    }

    pub fn log_plugin_op(&mut self, path: String, adapter_name: String, delta_blob: PyObject) {
        let op = Operation::PluginOp {
            path,
            adapter_name,
            delta_blob,
        };
        self.append_node(vec![op]);
    }

    pub fn label_node(&mut self, node_label: String) -> PyResult<()> {
        if self.node_labels.contains_key(&node_label)
            || self.branch_labels.contains_key(&node_label)
        {
            return Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>(format!(
                "Label '{}' already exists",
                node_label
            )));
        }
        self.node_labels.insert(node_label, self.current_node);
        Ok(())
    }

    pub fn move_to(&mut self, py: Python, label: String) -> PyResult<()> {
        let target_node_id = if let Some(&target_node_id) = self.node_labels.get(&label) {
            target_node_id
        } else if let Some(&target_node_id) = self.branch_labels.get(&label) {
            target_node_id
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>(format!(
                "Label '{}' not found",
                label
            )));
        };

        self.move_to_node_id(py, target_node_id)?;

        if self.branch_labels.contains_key(&label) {
            self.active_branch = label;
        }
        Ok(())
    }

    pub fn get_node_id(&self, label: String) -> Option<usize> {
        self.node_labels
            .get(&label)
            .or(self.branch_labels.get(&label))
            .cloned()
    }

    pub fn set_metadata(&mut self, key: String, value: PyObject) {
        if let Some(node) = self.nodes.get_mut(&self.current_node) {
            node.metadata.insert(key, value);
        }
    }

    #[pyo3(signature = (key, node_id=None))]
    pub fn get_metadata(
        &self,
        py: Python,
        key: String,
        node_id: Option<usize>,
    ) -> Option<PyObject> {
        let id = node_id.unwrap_or(self.current_node);
        self.nodes
            .get(&id)
            .and_then(|n| n.metadata.get(&key))
            .map(|v| v.clone_ref(py))
    }

    #[pyo3(signature = (node_id=None))]
    pub fn get_metadata_keys(&self, node_id: Option<usize>) -> Vec<String> {
        let id = node_id.unwrap_or(self.current_node);
        self.nodes
            .get(&id)
            .map(|n| n.metadata.keys().cloned().collect())
            .unwrap_or_default()
    }

    #[pyo3(signature = (node_id=None))]
    pub fn get_metadata_values(&self, py: Python, node_id: Option<usize>) -> Vec<PyObject> {
        let id = node_id.unwrap_or(self.current_node);
        self.nodes
            .get(&id)
            .map(|n| n.metadata.values().map(|v| v.clone_ref(py)).collect())
            .unwrap_or_default()
    }

    #[pyo3(signature = (node_id=None))]
    pub fn get_metadata_items(
        &self,
        py: Python,
        node_id: Option<usize>,
    ) -> Vec<(String, PyObject)> {
        let id = node_id.unwrap_or(self.current_node);
        self.nodes
            .get(&id)
            .map(|n| {
                n.metadata
                    .iter()
                    .map(|(k, v)| (k.clone(), v.clone_ref(py)))
                    .collect()
            })
            .unwrap_or_default()
    }

    pub fn find_nodes_by_metadata(&self, py: Python, key: String, value: PyObject) -> Vec<usize> {
        let mut results = Vec::new();
        for (&id, node) in &self.nodes {
            if let Some(v) = node.metadata.get(&key) {
                if v.bind(py).eq(value.bind(py)).unwrap_or(false) {
                    results.push(id);
                }
            }
        }
        results.sort();
        results
    }

    pub fn undo(&mut self, py: Python) -> PyResult<()> {
        if let Some(node) = self.nodes.get(&self.current_node) {
            if let Some(&parent_id) = node.parents.first() {
                self.move_to_node_id(py, parent_id)?;
            }
        }
        Ok(())
    }

    #[pyo3(signature = (label=None))]
    pub fn squash_branch(&mut self, py: Python, label: Option<String>) -> PyResult<()> {
        let leaf_id = if let Some(l) = label {
            *self.branch_labels.get(&l).ok_or_else(|| {
                PyErr::new::<pyo3::exceptions::PyKeyError, _>(format!("Branch '{}' not found", l))
            })?
        } else {
            self.current_node
        };

        if leaf_id == 0 {
            return Ok(());
        }

        let mut path = Vec::new();
        let mut curr = leaf_id;

        while curr != 0 {
            path.push(curr);
            let node = self.nodes.get(&curr).unwrap();
            if node.parents.len() != 1 {
                break;
            }
            let parent_id = node.parents[0];
            if parent_id == 0 {
                break;
            }
            let child_count = self
                .nodes
                .values()
                .filter(|n| n.parents.contains(&parent_id))
                .count();
            if child_count > 1 {
                break;
            }
            curr = parent_id;
        }

        if path.len() < 2 {
            return Ok(());
        }

        path.reverse();
        let anchor_id = self.nodes.get(&path[0]).unwrap().parents[0];
        let mut all_deltas = Vec::new();
        for nid in &path {
            for op in &self.nodes.get(nid).unwrap().deltas {
                all_deltas.push(op.clone_ref(py));
            }
        }

        let consolidated = self.consolidate_deltas(py, all_deltas);
        let mut new_metadata = HashMap::new();
        for (k, v) in &self.nodes.get(&leaf_id).unwrap().metadata {
            new_metadata.insert(k.clone(), v.clone_ref(py));
        }

        let new_id = self.nodes.len();
        let new_node = StateNode {
            id: new_id,
            parents: vec![anchor_id],
            deltas: consolidated,
            metadata: new_metadata,
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs(),
        };

        self.nodes.insert(new_id, new_node);
        let mut branches_to_update = Vec::new();
        for (name, &head_id) in &self.branch_labels {
            if head_id == leaf_id {
                branches_to_update.push(name.clone());
            }
        }
        for name in branches_to_update {
            self.branch_labels.insert(name, new_id);
        }

        let mut node_labels_to_update = Vec::new();
        for (name, &nid) in &self.node_labels {
            if nid == leaf_id {
                node_labels_to_update.push(name.clone());
            }
        }
        for name in node_labels_to_update {
            self.node_labels.insert(name, new_id);
        }

        if self.current_node == leaf_id {
            self.current_node = new_id;
        }

        Ok(())
    }

    pub fn redo(&mut self, py: Python) -> PyResult<()> {
        if let Some(node) = self.nodes.get(&(self.current_node + 1)) {
            if node.parents.contains(&self.current_node) {
                self.move_to_node_id(py, node.id)?;
                return Ok(());
            }
        }

        let mut child_id = None;
        for node in self.nodes.values() {
            if node.parents.contains(&self.current_node) {
                child_id = Some(node.id);
                break;
            }
        }

        if let Some(id) = child_id {
            self.move_to_node_id(py, id)?;
        }

        Ok(())
    }

    pub fn move_to_node_id(&mut self, py: Python, node_id: usize) -> PyResult<()> {
        let (path_up, path_down) = self.get_shortest_path(self.current_node, node_id);

        let owner = self.upgrade_owner(py)?;
        owner.setattr("_restoring", true)?;

        for nid in path_up {
            if let Some(node) = self.nodes.get(&nid) {
                self.apply_node_deltas(py, node, false)?;
            }
        }

        for nid in path_down {
            if let Some(node) = self.nodes.get(&nid) {
                self.apply_node_deltas(py, node, true)?;
            }
        }

        self.current_node = node_id;
        owner.setattr("_restoring", false)?;
        Ok(())
    }

    pub fn sync_from_root(&mut self, py: Python) -> PyResult<()> {
        let owner = self.upgrade_owner(py)?;
        owner.setattr("_restoring", true)?;

        let path = self.get_root_to_node_path(self.current_node);
        for nid in path {
            if let Some(node) = self.nodes.get(&nid) {
                self.apply_node_deltas(py, node, true)?;
            }
        }

        owner.setattr("_restoring", false)?;
        Ok(())
    }

    #[pyo3(signature = (source_label, strategy = "overshadow"))]
    pub fn merge_branch(
        &mut self,
        py: Python,
        source_label: String,
        strategy: &str,
    ) -> PyResult<()> {
        let source_id = *self.branch_labels.get(&source_label).ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyKeyError, _>(format!(
                "Source branch '{}' not found",
                source_label
            ))
        })?;

        let target_id = self.current_node;
        if source_id == target_id {
            return Ok(());
        }

        let lca_id = self.find_lca(target_id, source_id);
        let target_net = self.get_net_deltas_map(py, lca_id, target_id);
        let source_net = self.get_net_deltas_map(py, lca_id, source_id);

        let mut merged_ops = Vec::new();

        for (name, (old_at_base, source_val)) in source_net {
            if let Some((_old_at_base_target, target_val)) = target_net.get(&name) {
                if target_val.bind(py).eq(source_val.bind(py))? {
                    continue;
                }

                match strategy {
                    "overshadow" => {
                        merged_ops.push(Operation::UpdateAttr {
                            name: name.clone(),
                            old_value: target_val.clone_ref(py),
                            new_value: source_val.clone_ref(py),
                        });
                    }
                    "preserve" => {}
                    "strict" => {
                        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                            "Merge conflict on attribute '{}'",
                            name
                        )));
                    }
                    _ => {
                        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                            "Unknown merge strategy '{}'",
                            strategy
                        )));
                    }
                }
            } else {
                merged_ops.push(Operation::UpdateAttr {
                    name,
                    old_value: old_at_base.clone_ref(py),
                    new_value: source_val.clone_ref(py),
                });
            }
        }

        let target_all_ops = self.get_all_ops(py, lca_id, target_id);
        let source_others = self.get_other_ops(py, lca_id, source_id);
        let reconciled_source =
            self.reconcile_source_ops(py, &target_all_ops, source_others, strategy)?;
        merged_ops.extend(reconciled_source);

        if merged_ops.is_empty() && lca_id == source_id {
            return Ok(());
        }

        let new_id = self.next_node_id;
        self.next_node_id += 1;
        let new_node = StateNode {
            id: new_id,
            parents: vec![target_id, source_id],
            deltas: merged_ops,
            metadata: HashMap::new(),
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs(),
        };

        self.nodes.insert(new_id, new_node);
        self.branch_labels
            .insert(self.active_branch.clone(), new_id);
        self.move_to_node_id(py, new_id)?;

        Ok(())
    }

    pub fn move_to_creation(&mut self, py: Python) -> PyResult<()> {
        self.move_to_node_id(py, 0)
    }

    pub fn create_branch(&mut self, label: String) {
        match self.mode {
            Mode::Linear => panic!("Branching is not allowed in linear mode."),
            Mode::Multiversal => {}
        }
        self.branch_labels.insert(label.clone(), self.current_node);
        self.active_branch = label;
    }

    #[getter]
    pub fn current_branch(&self) -> String {
        self.active_branch.to_string()
    }

    #[getter]
    pub fn current_node(&self) -> usize {
        self.current_node
    }

    #[pyo3(signature = (label=None, filter_attr=None))]
    pub fn extract_timeline(
        &self,
        py: Python,
        label: Option<String>,
        filter_attr: Option<Vec<String>>,
    ) -> PyResult<Vec<PyObject>> {
        let target_node_id = match label {
            Some(label) => self
                .node_labels
                .get(&label)
                .or_else(|| self.branch_labels.get(&label))
                .cloned()
                .ok_or_else(|| {
                    PyErr::new::<pyo3::exceptions::PyKeyError, _>(format!(
                        "Label '{}' not found",
                        label
                    ))
                })?,
            None => self.current_node,
        };
        let path = self.get_root_to_node_path(target_node_id);
        let mut timeline = Vec::new();
        for node_id in path {
            if let Some(node) = self.nodes.get(&node_id) {
                let metadata_dict = pyo3::types::PyDict::new(py);
                for (k, v) in &node.metadata {
                    metadata_dict.set_item(k, v.clone_ref(py))?;
                }

                for op in &node.deltas {
                    if let Some(ref filters) = filter_attr {
                        let op_name = op.get_path();
                        if !filters.iter().any(|f| f == op_name) {
                            continue;
                        }
                    }

                    let op_dict = pyo3::types::PyDict::new(py);
                    op_dict.set_item("timestamp", node.timestamp)?;
                    op_dict.set_item("node_id", node.id)?;
                    op_dict.set_item("metadata", &metadata_dict)?;

                    match op {
                        Operation::UpdateAttr {
                            name,
                            old_value,
                            new_value,
                        } => {
                            op_dict.set_item("type", "UpdateAttr")?;
                            op_dict.set_item("name", name)?;
                            op_dict.set_item("old", old_value)?;
                            op_dict.set_item("new", new_value)?;
                        }
                        Operation::ListOp(ListOperation::Pop {
                            path,
                            index,
                            popped_value,
                        }) => {
                            op_dict.set_item("type", "ListPop")?;
                            op_dict.set_item("path", path)?;
                            op_dict.set_item("index", index)?;
                            op_dict.set_item("popped_value", popped_value)?;
                        }
                        Operation::ListOp(ListOperation::Insert { path, index, value }) => {
                            op_dict.set_item("type", "ListInsert")?;
                            op_dict.set_item("path", path)?;
                            op_dict.set_item("index", index)?;
                            op_dict.set_item("value", value)?;
                        }
                        Operation::ListOp(ListOperation::Replace {
                            path,
                            index,
                            old_value,
                            new_value,
                        }) => {
                            op_dict.set_item("type", "ListReplace")?;
                            op_dict.set_item("path", path)?;
                            op_dict.set_item("index", index)?;
                            op_dict.set_item("old", old_value)?;
                            op_dict.set_item("new", new_value)?;
                        }
                        Operation::ListOp(ListOperation::Clear { path, old_values }) => {
                            op_dict.set_item("type", "ListClear")?;
                            op_dict.set_item("path", path)?;
                            op_dict.set_item("old_values", old_values)?;
                        }
                        Operation::ListOp(ListOperation::Extend { path, new_values }) => {
                            op_dict.set_item("type", "ListExtend")?;
                            op_dict.set_item("path", path)?;
                            op_dict.set_item("new_values", new_values)?;
                        }
                        Operation::ListOp(ListOperation::Remove { path, value }) => {
                            op_dict.set_item("type", "ListRemove")?;
                            op_dict.set_item("path", path)?;
                            op_dict.set_item("value", value)?;
                        }
                        Operation::DictOp(DictOperation::Clear {
                            path,
                            keys,
                            old_values,
                        }) => {
                            op_dict.set_item("type", "DictClear")?;
                            op_dict.set_item("path", path)?;
                            op_dict.set_item("keys", keys)?;
                            op_dict.set_item("old_values", old_values)?;
                        }
                        Operation::DictOp(DictOperation::Pop {
                            path,
                            key,
                            old_value,
                        }) => {
                            op_dict.set_item("type", "DictPop")?;
                            op_dict.set_item("path", path)?;
                            op_dict.set_item("key", key)?;
                            op_dict.set_item("old_value", old_value)?;
                        }
                        Operation::DictOp(DictOperation::PopItem {
                            path,
                            key,
                            old_value,
                        }) => {
                            op_dict.set_item("type", "DictPopItem")?;
                            op_dict.set_item("path", path)?;
                            op_dict.set_item("key", key)?;
                            op_dict.set_item("old_value", old_value)?;
                        }
                        Operation::DictOp(DictOperation::SetDefault { path, key, value }) => {
                            op_dict.set_item("type", "DictSetDefault")?;
                            op_dict.set_item("path", path)?;
                            op_dict.set_item("key", key)?;
                            op_dict.set_item("value", value)?;
                        }
                        Operation::DictOp(DictOperation::Update {
                            path,
                            keys,
                            old_values,
                            new_values,
                        }) => {
                            op_dict.set_item("type", "DictUpdate")?;
                            op_dict.set_item("path", path)?;
                            op_dict.set_item("keys", keys)?;
                            op_dict.set_item("old", old_values)?;
                            op_dict.set_item("new", new_values)?;
                        }
                        Operation::DictOp(DictOperation::Delete {
                            path,
                            key,
                            old_value,
                        }) => {
                            op_dict.set_item("type", "DictDelete")?;
                            op_dict.set_item("path", path)?;
                            op_dict.set_item("key", key)?;
                            op_dict.set_item("old", old_value)?;
                        }
                        Operation::PluginOp {
                            path,
                            adapter_name,
                            delta_blob,
                        } => {
                            op_dict.set_item("type", "PluginOp")?;
                            op_dict.set_item("path", path)?;
                            op_dict.set_item("adapter", adapter_name)?;
                            op_dict.set_item("delta", delta_blob)?;
                        }
                    }
                    timeline.push(op_dict.into_pyobject(py)?.into());
                }
            }
        }
        Ok(timeline)
    }

    pub fn log_list_pop(&mut self, path: String, index: i64, popped_value: PyObject) {
        let op = Operation::ListOp(ListOperation::Pop {
            path,
            index,
            popped_value,
        });
        self.append_node(vec![op]);
    }

    pub fn log_list_insert(&mut self, path: String, index: i64, value: PyObject) {
        let op = Operation::ListOp(ListOperation::Insert { path, index, value });
        self.append_node(vec![op]);
    }

    pub fn log_list_replace(
        &mut self,
        path: String,
        index: i64,
        old_val: PyObject,
        new_val: PyObject,
    ) {
        let replace = Operation::ListOp(ListOperation::Replace {
            path,
            index,
            old_value: old_val,
            new_value: new_val,
        });
        self.append_node(vec![replace]);
    }

    pub fn log_list_clear(&mut self, path: String, old_values: Vec<PyObject>) {
        let op = Operation::ListOp(ListOperation::Clear { path, old_values });
        self.append_node(vec![op]);
    }

    pub fn log_list_extend(&mut self, path: String, new_values: Vec<PyObject>) {
        let op = Operation::ListOp(ListOperation::Extend { path, new_values });
        self.append_node(vec![op]);
    }

    pub fn log_list_remove(&mut self, path: String, value: PyObject) {
        let op = Operation::ListOp(ListOperation::Remove { path, value });
        self.append_node(vec![op]);
    }

    pub fn log_dict_clear(&mut self, path: String, keys: Vec<String>, old_values: Vec<PyObject>) {
        let op = Operation::DictOp(DictOperation::Clear {
            path,
            keys,
            old_values,
        });
        self.append_node(vec![op]);
    }

    pub fn log_dict_pop(&mut self, path: String, key: String, old_value: PyObject) {
        let op = Operation::DictOp(DictOperation::Pop {
            path,
            key,
            old_value,
        });
        self.append_node(vec![op]);
    }

    pub fn log_dict_popitem(&mut self, path: String, key: String, old_value: PyObject) {
        let op = Operation::DictOp(DictOperation::PopItem {
            path,
            key,
            old_value,
        });
        self.append_node(vec![op]);
    }

    pub fn log_dict_setdefault(&mut self, path: String, key: String, value: PyObject) {
        let op = Operation::DictOp(DictOperation::SetDefault { path, key, value });
        self.append_node(vec![op]);
    }

    pub fn log_dict_update(
        &mut self,
        path: String,
        keys: Vec<String>,
        old_values: Vec<PyObject>,
        new_values: Vec<PyObject>,
    ) {
        let op = Operation::DictOp(DictOperation::Update {
            path,
            keys,
            old_values,
            new_values,
        });
        self.append_node(vec![op]);
    }

    pub fn log_dict_delete(&mut self, path: String, key: String, old_value: PyObject) {
        let op = Operation::DictOp(DictOperation::Delete {
            path,
            key,
            old_value,
        });
        self.append_node(vec![op]);
    }

    pub fn delete_branch(&mut self, label: String) -> PyResult<()> {
        if label == self.active_branch {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Cannot delete active branch: '{}'",
                label
            )));
        }
        if self.branch_labels.remove(&label).is_none() {
            return Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>(format!(
                "Branch '{}' not found",
                label
            )));
        }
        Ok(())
    }

    pub fn squash(&mut self, py: Python, start_label: String, end_label: String) -> PyResult<()> {
        let start_id = *self.node_labels.get(&start_label).ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyKeyError, _>(format!(
                "Label '{}' not found",
                start_label
            ))
        })?;
        let end_id = *self.node_labels.get(&end_label).ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyKeyError, _>(format!(
                "Label '{}' not found",
                end_label
            ))
        })?;

        let mut chain = Vec::new();
        let mut curr = end_id;
        while curr != start_id {
            chain.push(curr);
            let node = self.nodes.get(&curr).ok_or_else(|| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Inconsistent DAG")
            })?;
            if node.parents.len() != 1 {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "Cannot squash across merge or branch nodes",
                ));
            }
            curr = node.parents[0];
            if curr == 0 && start_id != 0 {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "Start label is not an ancestor of end label",
                ));
            }
        }
        chain.push(start_id);
        chain.reverse();

        let mut all_deltas = Vec::new();
        for &id in &chain {
            if let Some(node) = self.nodes.get(&id) {
                for op in &node.deltas {
                    all_deltas.push(op.clone_ref(py));
                }
            }
        }

        let mut collapsed_ops = Vec::new();
        let mut attr_first_old: HashMap<String, PyObject> = HashMap::new();
        let mut attr_last_new: HashMap<String, PyObject> = HashMap::new();

        for op in all_deltas {
            match op {
                Operation::UpdateAttr {
                    name,
                    old_value,
                    new_value,
                } => {
                    if !attr_first_old.contains_key(&name) {
                        attr_first_old.insert(name.clone(), old_value);
                    }
                    attr_last_new.insert(name, new_value);
                }
                _ => {
                    for (name, first_old) in attr_first_old.drain() {
                        let last_new = attr_last_new.remove(&name).unwrap();
                        collapsed_ops.push(Operation::UpdateAttr {
                            name,
                            old_value: first_old,
                            new_value: last_new,
                        });
                    }
                    collapsed_ops.push(op);
                }
            }
        }
        for (name, first_old) in attr_first_old.drain() {
            let last_new = attr_last_new.remove(&name).unwrap();
            collapsed_ops.push(Operation::UpdateAttr {
                name,
                old_value: first_old,
                new_value: last_new,
            });
        }

        let start_node = self.nodes.get(&start_id).unwrap();
        let parents = start_node.parents.clone();
        let timestamp = self.nodes.get(&end_id).unwrap().timestamp;

        let new_id = self.next_node_id;
        self.next_node_id += 1;

        let mut children = Vec::new();
        for node in self.nodes.values() {
            if node.parents.contains(&end_id) {
                children.push(node.id);
            }
        }

        let new_node = StateNode {
            id: new_id,
            parents,
            deltas: collapsed_ops,
            metadata: HashMap::new(),
            timestamp,
        };

        for child_id in children {
            let child = self.nodes.get_mut(&child_id).unwrap();
            for p in &mut child.parents {
                if *p == end_id {
                    *p = new_id;
                }
            }
        }

        let chain_ids: std::collections::HashSet<usize> = chain.iter().cloned().collect();
        let labels_to_migrate: Vec<String> = self
            .node_labels
            .iter()
            .filter(|(_, &id)| chain_ids.contains(&id))
            .map(|(k, _)| k.clone())
            .collect();
        for label in labels_to_migrate {
            self.node_labels.insert(label, new_id);
        }

        let branches_to_migrate: Vec<String> = self
            .branch_labels
            .iter()
            .filter(|(_, &id)| chain_ids.contains(&id))
            .map(|(k, _)| k.clone())
            .collect();
        for branch in branches_to_migrate {
            self.branch_labels.insert(branch, new_id);
        }

        if chain_ids.contains(&self.current_node) {
            self.current_node = new_id;
        }

        for id in chain {
            if id != 0 {
                self.nodes.remove(&id);
            }
        }

        self.nodes.insert(new_id, new_node);

        Ok(())
    }

    #[pyo3(signature = (start_label, end_label))]
    pub fn get_diff(
        &mut self,
        py: Python,
        start_label: String,
        end_label: String,
    ) -> PyResult<PyObject> {
        let start_id = *self.node_labels.get(&start_label).ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyKeyError, _>(format!(
                "Label '{}' not found",
                start_label
            ))
        })?;
        let end_id = *self.node_labels.get(&end_label).ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyKeyError, _>(format!(
                "Label '{}' not found",
                end_label
            ))
        })?;

        let (path_up, path_down) = self.get_shortest_path(start_id, end_id);
        let mut all_deltas = Vec::new();

        for nid in path_up {
            if let Some(node) = self.nodes.get(&nid) {
                for op in node.deltas.iter().rev() {
                    all_deltas.push(op.invert(py));
                }
            }
        }

        for nid in path_down {
            if let Some(node) = self.nodes.get(&nid) {
                for op in &node.deltas {
                    all_deltas.push(op.clone_ref(py));
                }
            }
        }

        let mut attr_diff: HashMap<String, (PyObject, PyObject)> = HashMap::new();
        let mut container_ops: Vec<PyObject> = Vec::new();

        for op in all_deltas {
            match op {
                Operation::UpdateAttr {
                    name,
                    old_value,
                    new_value,
                } => {
                    if let Some(existing) = attr_diff.get_mut(&name) {
                        existing.1 = new_value;
                    } else {
                        attr_diff.insert(name, (old_value, new_value));
                    }
                }
                _ => {
                    container_ops.push(op.to_object(py)?);
                }
            }
        }

        let result = PyDict::new(py);
        let attrs = PyDict::new(py);
        for (name, (old, new)) in attr_diff {
            let pair = PyDict::new(py);
            pair.set_item("old", old)?;
            pair.set_item("new", new)?;
            attrs.set_item(name, pair)?;
        }
        result.set_item("attributes", attrs)?;
        result.set_item("container_operations", container_ops)?;

        Ok(result.into())
    }

    pub fn get_graph_state(&self, py: Python) -> PyResult<PyObject> {
        // Calls the implementation in serde_py.rs
        self.get_graph_state_impl(py)
    }

    pub fn set_graph_state(&mut self, py: Python, state: PyObject) -> PyResult<()> {
        // Calls the implementation in serde_py.rs
        self.set_graph_state_impl(py, state)
    }
}

impl TachyonEngine {
    pub fn upgrade_owner<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        self.owner.bind(py).upgrade().ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyReferenceError, _>(
                "Janus object has been garbage collected (Tombstone state)",
            )
        })
    }

    pub fn append_node(&mut self, deltas: Vec<Operation>) {
        match self.mode {
            Mode::Linear => {
                if self.current_node != self.next_node_id - 1 {
                    for node_id in (self.current_node + 1)..self.next_node_id {
                        self.nodes.remove(&node_id);
                    }
                    self.node_labels
                        .retain(|_, &mut id| id <= self.current_node);
                    self.next_node_id = self.current_node + 1;
                }
            }
            Mode::Multiversal => {}
        }
        let node_id = self.next_node_id;
        let new_node = StateNode {
            id: node_id,
            parents: vec![self.current_node],
            deltas,
            metadata: HashMap::new(),
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs(),
        };
        self.nodes.insert(node_id, new_node);
        self.current_node = node_id;
        self.next_node_id += 1;
        self.branch_labels
            .insert(self.active_branch.clone(), node_id);
        self.prune();
    }

    pub fn apply_node_deltas(&self, py: Python, node: &StateNode, forward: bool) -> PyResult<()> {
        let owner = self.upgrade_owner(py)?;
        let deltas: Box<dyn Iterator<Item = &Operation>> = if forward {
            Box::new(node.deltas.iter())
        } else {
            Box::new(node.deltas.iter().rev())
        };

        for op in deltas {
            match op {
                Operation::UpdateAttr {
                    name,
                    old_value,
                    new_value,
                } => {
                    let val = if forward { new_value } else { old_value };
                    owner.setattr(name.as_str(), val)?;
                }
                Operation::ListOp(lo) => {
                    let path = lo.get_path();
                    if let Ok(list_attr) = owner.call_method1("_resolve_path", (path,)) {
                        match lo {
                            ListOperation::Pop { index, .. } => {
                                if forward {
                                    list_attr.call_method1("pop", (*index,))?;
                                } else {
                                    let popped_value = match lo {
                                        ListOperation::Pop { popped_value, .. } => popped_value,
                                        _ => unreachable!(),
                                    };
                                    list_attr.call_method1("insert", (*index, popped_value))?;
                                }
                            }
                            ListOperation::Insert { index, value, .. } => {
                                if forward {
                                    list_attr.call_method1("insert", (*index, value))?;
                                } else {
                                    list_attr.call_method1("pop", (*index,))?;
                                }
                            }
                            ListOperation::Replace {
                                index,
                                old_value,
                                new_value,
                                ..
                            } => {
                                let val = if forward { new_value } else { old_value };
                                list_attr.call_method1("__setitem__", (*index, val))?;
                            }
                            ListOperation::Clear { old_values, .. } => {
                                if forward {
                                    list_attr.call_method0("clear")?;
                                } else {
                                    list_attr.call_method1("extend", (old_values,))?;
                                }
                            }
                            ListOperation::Extend { new_values, .. } => {
                                if forward {
                                    list_attr.call_method1("extend", (new_values,))?;
                                } else {
                                    for _ in 0..new_values.len() {
                                        list_attr.call_method1("pop", (-1,))?;
                                    }
                                }
                            }
                            ListOperation::Remove { value, .. } => {
                                if forward {
                                    list_attr.call_method1("remove", (value,))?;
                                } else {
                                    list_attr.call_method1("append", (value,))?;
                                }
                            }
                        }
                    }
                }
                Operation::DictOp(do_op) => {
                    let path = do_op.get_path();
                    if let Ok(dict_attr) = owner.call_method1("_resolve_path", (path,)) {
                        match do_op {
                            DictOperation::Update {
                                keys,
                                old_values,
                                new_values,
                                ..
                            } => {
                                let values = if forward { new_values } else { old_values };
                                for (k, v) in keys.iter().zip(values.iter()) {
                                    if v.bind(py).is_none() {
                                        let _ = dict_attr.call_method1("pop", (k,));
                                    } else {
                                        dict_attr.call_method1("__setitem__", (k, v))?;
                                    }
                                }
                            }
                            DictOperation::Clear {
                                keys, old_values, ..
                            } => {
                                if forward {
                                    dict_attr.call_method0("clear")?;
                                } else {
                                    for (k, v) in keys.iter().zip(old_values.iter()) {
                                        dict_attr.call_method1("__setitem__", (k, v))?;
                                    }
                                }
                            }
                            DictOperation::Pop { key, old_value, .. }
                            | DictOperation::PopItem { key, old_value, .. }
                            | DictOperation::Delete { key, old_value, .. } => {
                                if forward {
                                    let _ = dict_attr.call_method1("pop", (key,));
                                } else {
                                    dict_attr.call_method1("__setitem__", (key, old_value))?;
                                }
                            }
                            DictOperation::SetDefault { key, value, .. } => {
                                if forward {
                                    dict_attr.call_method1("setdefault", (key, value))?;
                                } else {
                                    let _ = dict_attr.call_method1("pop", (key,));
                                }
                            }
                        }
                    }
                }
                Operation::PluginOp {
                    path,
                    adapter_name,
                    delta_blob,
                } => {
                    let adapter = owner.getattr("_adapters")?.get_item(adapter_name)?;
                    let target = owner.call_method1("_resolve_path", (path,))?;
                    if forward {
                        adapter.call_method1("apply_forward", (target, delta_blob))?;
                    } else {
                        adapter.call_method1("apply_backward", (target, delta_blob))?;
                    }
                }
            }
        }
        Ok(())
    }
}
