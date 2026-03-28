use pyo3::prelude::*;
use std::collections::HashMap;

pub enum Operation {
    UpdateAttr {
        name: String,
        old_value: PyObject,
        new_value: PyObject,
    },
    ListOp(ListOperation),
    DictOp(DictOperation),
    PluginOp {
        path: String,
        adapter_name: String,
        delta_blob: PyObject,
    },
}

pub enum ListOperation {
    Insert {
        path: String,
        index: usize,
        value: PyObject,
    },
    Pop {
        path: String,
        index: usize,
        popped_value: PyObject,
    },
    Replace {
        path: String,
        index: usize,
        old_value: PyObject,
        new_value: PyObject,
    },
    Clear {
        path: String,
        old_values: Vec<PyObject>,
    },
    Extend {
        path: String,
        new_values: Vec<PyObject>,
    },
    Remove {
        path: String,
        value: PyObject,
    },
}

pub enum DictOperation {
    Clear {
        path: String,
        keys: Vec<String>,
        old_values: Vec<PyObject>,
    },
    Pop {
        path: String,
        key: String,
        old_value: PyObject,
    },
    PopItem {
        path: String,
        key: String,
        old_value: PyObject,
    },
    SetDefault {
        path: String,
        key: String,
        value: PyObject,
    },
    Update {
        path: String,
        keys: Vec<String>,
        old_values: Vec<PyObject>,
        new_values: Vec<PyObject>,
    },
    Delete {
        path: String,
        key: String,
        old_value: PyObject,
    },
}

#[derive(Clone)]
pub enum Mode {
    Linear,
    Multiversal,
}

pub struct StateNode {
    pub id: usize,
    pub parents: Vec<usize>,
    pub deltas: Vec<Operation>,
    // pub metadata: HashMap<String, PyObject>,
}

#[pyclass]
pub struct TachyonEngine {
    pub owner: Py<PyAny>,
    nodes: HashMap<usize, StateNode>,
    node_labels: HashMap<String, usize>,
    active_branch: String,
    branch_labels: HashMap<String, usize>,
    current_node: usize,
    next_node_id: usize,
    mode: Mode,
}

#[pymethods]
impl TachyonEngine {
    #[new]
    pub fn new(owner: Py<PyAny>, mode: String) -> Self {
        let mut node_labels = HashMap::new();
        let mut branch_labels = HashMap::new();
        node_labels.insert("__genesis__".to_string(), 0);
        branch_labels.insert("main".to_string(), 0);
        let active_branch = "main".to_string();

        let mut nodes = HashMap::new();
        nodes.insert(
            0,
            StateNode {
                id: 0,
                parents: Vec::new(),
                deltas: Vec::new(),
                // metadata: HashMap::new(),
            },
        );

        let mode = match mode.as_str() {
            "linear" => Mode::Linear,
            "multiversal" => Mode::Multiversal,
            _ => panic!("Invalid mode: {}", mode),
        };

        TachyonEngine {
            owner,
            nodes,
            node_labels,
            branch_labels,
            active_branch,
            current_node: 0,
            next_node_id: 1,
            mode,
        }
    }

    #[getter]
    pub fn owner(&self, py: Python) -> Py<PyAny> {
        self.owner.clone_ref(py)
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

    pub fn undo(&mut self, py: Python) -> PyResult<()> {
        if let Some(node) = self.nodes.get(&self.current_node) {
            if let Some(&parent_id) = node.parents.first() {
                self.move_to_node_id(py, parent_id)?;
            }
        }
        Ok(())
    }

    pub fn redo(&mut self, py: Python) -> PyResult<()> {
        if let Some(node) = self.nodes.get(&(self.current_node + 1)) {
            self.move_to_node_id(py, node.id)?;
        }
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

    #[pyo3(signature = (label=None))]
    pub fn extract_timeline(&self, py: Python, label: Option<String>) -> PyResult<Vec<PyObject>> {
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
                for op in &node.deltas {
                    let op_dict = pyo3::types::PyDict::new(py);
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
                            op_dict.set_item("value", popped_value)?;
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
                    timeline.push(op_dict.into_any().unbind());
                }
            }
        }
        Ok(timeline)
    }

    pub fn log_list_pop(&mut self, path: String, index: usize, popped_value: PyObject) {
        let op = Operation::ListOp(ListOperation::Pop {
            path,
            index,
            popped_value,
        });
        self.append_node(vec![op]);
    }

    pub fn log_list_insert(&mut self, path: String, index: usize, value: PyObject) {
        let op = Operation::ListOp(ListOperation::Insert { path, index, value });
        self.append_node(vec![op]);
    }

    pub fn log_list_replace(
        &mut self,
        path: String,
        index: usize,
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
}

impl TachyonEngine {
    fn append_node(&mut self, deltas: Vec<Operation>) {
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
            // metadata: HashMap::new(),
        };
        self.nodes.insert(node_id, new_node);
        self.current_node = node_id;
        self.next_node_id += 1;

        self.branch_labels
            .insert(self.active_branch.clone(), node_id);
    }

    fn get_shortest_path(&self, from_id: usize, to_id: usize) -> (Vec<usize>, Vec<usize>) {
        if from_id == to_id {
            return (Vec::new(), Vec::new());
        }

        let from_path = self.get_root_to_node_path(from_id);
        let to_path = self.get_root_to_node_path(to_id);

        let mut lca_idx = 0;
        for (i, (f, t)) in from_path.iter().zip(to_path.iter()).enumerate() {
            if f == t {
                lca_idx = i;
            } else {
                break;
            }
        }

        let path_up: Vec<usize> = from_path[lca_idx + 1..].iter().rev().cloned().collect();
        let path_down: Vec<usize> = to_path[lca_idx + 1..].to_vec();

        (path_up, path_down)
    }

    fn move_to_node_id(&mut self, py: Python, node_id: usize) -> PyResult<()> {
        let owner = self.owner.bind(py);
        owner.setattr("_restoring", true)?;

        let (path_up, path_down) = self.get_shortest_path(self.current_node, node_id);

        // 1. Move UP to LCA (apply backwards)
        for node_id in path_up {
            if let Some(node) = self.nodes.get(&node_id) {
                self.apply_node_deltas(py, node, false)?;
            }
        }

        // 2. Move DOWN to target (apply forwards)
        for node_id in path_down {
            if let Some(node) = self.nodes.get(&node_id) {
                self.apply_node_deltas(py, node, true)?;
            }
        }

        owner.setattr("_restoring", false)?;
        self.current_node = node_id;
        Ok(())
    }

    fn get_root_to_node_path(&self, node_id: usize) -> Vec<usize> {
        let mut path = Vec::new();
        let mut curr = Some(node_id);
        while let Some(id) = curr {
            path.push(id);
            curr = self.nodes.get(&id).and_then(|n| n.parents.first().cloned());
        }
        path.reverse();
        path
    }

    fn apply_node_deltas(&self, py: Python, node: &StateNode, forward: bool) -> PyResult<()> {
        let owner = self.owner.bind(py);

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
                Operation::ListOp(ListOperation::Pop {
                    path,
                    index,
                    popped_value,
                }) => {
                    if let Ok(list_attr) = owner.call_method1("_resolve_path", (path.as_str(),)) {
                        if forward {
                            list_attr.call_method1("pop", (*index,))?;
                        } else {
                            list_attr.call_method1("insert", (*index, popped_value))?;
                        }
                    }
                }
                Operation::ListOp(ListOperation::Insert { path, index, value }) => {
                    if let Ok(list_attr) = owner.call_method1("_resolve_path", (path.as_str(),)) {
                        if forward {
                            list_attr.call_method1("insert", (*index, value))?;
                        } else {
                            list_attr.call_method1("pop", (*index,))?;
                        }
                    }
                }
                Operation::ListOp(ListOperation::Replace {
                    path,
                    index,
                    old_value,
                    new_value,
                }) => {
                    if let Ok(list_attr) = owner.call_method1("_resolve_path", (path.as_str(),)) {
                        if forward {
                            list_attr.call_method1("__setitem__", (*index, new_value))?;
                        } else {
                            list_attr.call_method1("__setitem__", (*index, old_value))?;
                        }
                    }
                }
                Operation::ListOp(ListOperation::Clear { path, old_values }) => {
                    if let Ok(list_attr) = owner.call_method1("_resolve_path", (path.as_str(),)) {
                        if forward {
                            list_attr.call_method1("clear", ())?;
                        } else {
                            let list = pyo3::types::PyList::new(py, old_values)?;
                            list_attr.call_method1("extend", (list,))?;
                        }
                    }
                }
                Operation::ListOp(ListOperation::Extend { path, new_values }) => {
                    if let Ok(list_attr) = owner.call_method1("_resolve_path", (path.as_str(),)) {
                        if forward {
                            let list = pyo3::types::PyList::new(py, new_values)?;
                            list_attr.call_method1("extend", (list,))?;
                        } else {
                            for value in new_values.iter().rev() {
                                list_attr.call_method1("remove", (value,))?;
                            }
                        }
                    }
                }
                Operation::ListOp(ListOperation::Remove { path, value }) => {
                    if let Ok(list_attr) = owner.call_method1("_resolve_path", (path.as_str(),)) {
                        if forward {
                            list_attr.call_method1("remove", (value,))?;
                        } else {
                            list_attr.call_method1("append", (value,))?;
                        }
                    }
                }
                Operation::DictOp(DictOperation::Clear {
                    path,
                    keys,
                    old_values,
                }) => {
                    if let Ok(dict_attr) = owner.call_method1("_resolve_path", (path.as_str(),)) {
                        if forward {
                            dict_attr.call_method0("clear")?;
                        } else {
                            for (key, value) in keys.iter().zip(old_values.iter()).rev() {
                                dict_attr.call_method1("__setitem__", (key, value))?;
                            }
                        }
                    }
                }
                Operation::DictOp(DictOperation::Pop {
                    path,
                    key,
                    old_value,
                }) => {
                    if let Ok(dict_attr) = owner.call_method1("_resolve_path", (path.as_str(),)) {
                        if forward {
                            dict_attr.call_method1("pop", (key,))?;
                        } else {
                            dict_attr.call_method1("__setitem__", (key, old_value))?;
                        }
                    }
                }
                Operation::DictOp(DictOperation::PopItem {
                    path,
                    key,
                    old_value,
                }) => {
                    if let Ok(dict_attr) = owner.call_method1("_resolve_path", (path.as_str(),)) {
                        if forward {
                            dict_attr.call_method0("popitem")?;
                        } else {
                            dict_attr.call_method1("__setitem__", (key, old_value))?;
                        }
                    }
                }
                Operation::DictOp(DictOperation::SetDefault { path, key, value }) => {
                    if let Ok(dict_attr) = owner.call_method1("_resolve_path", (path.as_str(),)) {
                        if forward {
                            dict_attr.call_method1("setdefault", (key, value))?;
                        } else {
                            dict_attr.call_method1("__delitem__", (key,))?;
                        }
                    }
                }
                Operation::DictOp(DictOperation::Update {
                    path,
                    keys,
                    old_values,
                    new_values,
                }) => {
                    if let Ok(dict_attr) = owner.call_method1("_resolve_path", (path.as_str(),)) {
                        for ((key, old_value), new_value) in
                            keys.iter().zip(old_values.iter()).zip(new_values.iter())
                        {
                            if forward {
                                dict_attr.call_method1("__setitem__", (key, new_value))?;
                            } else if old_value.is_none(py) {
                                dict_attr.call_method1("__delitem__", (key,))?;
                            } else {
                                dict_attr.call_method1("__setitem__", (key, old_value))?;
                            }
                        }
                    }
                }
                Operation::DictOp(DictOperation::Delete {
                    path,
                    key,
                    old_value,
                }) => {
                    if let Ok(dict_attr) = owner.call_method1("_resolve_path", (path.as_str(),)) {
                        if forward {
                            dict_attr.call_method1("__delitem__", (key,))?;
                        } else {
                            dict_attr.call_method1("__setitem__", (key, old_value))?;
                        }
                    }
                }
                Operation::PluginOp {
                    path,
                    adapter_name,
                    delta_blob,
                } => {
                    let registry = py.import("janus.registry")?;
                    let registry_attr = registry.getattr("ADAPTER_REGISTRY")?;
                    let adapter_registry = registry_attr.downcast::<pyo3::types::PyDict>()?;
                    for adapter_item in adapter_registry.values() {
                        let class_obj = adapter_item.getattr("__class__")?;
                        let name_attr = class_obj.getattr("__name__")?;
                        let name_str: String = name_attr.extract()?;
                        if name_str == adapter_name.as_str() {
                            let method = if forward {
                                "apply_forward"
                            } else {
                                "apply_backward"
                            };
                            let target = owner.call_method1("_resolve_path", (path.as_str(),))?;
                            adapter_item.call_method1(method, (target, delta_blob))?;
                        }
                    }
                }
            }
        }
        Ok(())
    }
}
