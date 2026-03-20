use pyo3::prelude::*;
use std::collections::HashMap;

#[derive(Clone)]
pub enum Operation {
    UpdateAttr {
        name: String,
        old_value: PyObject,
        new_value: PyObject,
    },
    ListPop {
        path: String,
        index: usize,
        popped_value: PyObject,
    },
    ListInsert {
        path: String,
        index: usize,
        value: PyObject,
    },
    DictUpdate {
        path: String,
        key: PyObject,
        old_value: PyObject,
        new_value: PyObject,
    },
    DictDelete {
        path: String,
        key: PyObject,
        old_value: PyObject,
    },
    // THE FOUNDATION FOR PLUGINS:
    PluginOp {
        path: String,
        adapter_name: String,
        delta_blob: PyObject,
    },
}

// Foundation for Timeline Extraction: Nodes know their parents.
#[derive(Clone)]
pub struct StateNode {
    #[allow(dead_code)]
    pub id: usize,
    pub parents: Vec<usize>,
    pub deltas: Vec<Operation>,
    #[allow(dead_code)]
    pub metadata: HashMap<String, PyObject>,
}

#[pyclass]
pub struct TachyonEngine {
    owner: Py<PyAny>,
    nodes: HashMap<usize, StateNode>,
    branches: HashMap<String, usize>,
    current_node: usize,
    next_node_id: usize,
    mode: String, // "linear" or "multiversal"
}

#[pymethods]
impl TachyonEngine {
    #[new]
    pub fn new(owner: Py<PyAny>, mode: String) -> Self {
        let mut branches = HashMap::new();
        branches.insert("main".to_string(), 0);

        let mut nodes = HashMap::new();
        nodes.insert(
            0,
            StateNode {
                id: 0,
                parents: Vec::new(),
                deltas: Vec::new(),
                metadata: HashMap::new(),
            },
        );

        TachyonEngine {
            owner,
            nodes,
            branches,
            current_node: 0,
            next_node_id: 1,
            mode,
        }
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

    pub fn create_branch(&mut self, label: String) {
        self.branches.insert(label, self.current_node);
    }

    pub fn switch_branch(&mut self, py: Python, label: String) -> PyResult<()> {
        if let Some(&target_node_id) = self.branches.get(&label) {
            let owner = self.owner.as_ref(py);
            owner.setattr("_restoring", true)?;

            let (path_up, path_down) = self.get_shortest_path(self.current_node, target_node_id);

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
            self.current_node = target_node_id;
            Ok(())
        } else {
            Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>(format!(
                "Branch '{}' not found",
                label
            )))
        }
    }

    pub fn extract_timeline(&self, py: Python, label: String) -> PyResult<Vec<PyObject>> {
        if let Some(&target_node_id) = self.branches.get(&label) {
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
                            Operation::ListPop {
                                path,
                                index,
                                popped_value,
                            } => {
                                op_dict.set_item("type", "ListPop")?;
                                op_dict.set_item("path", path)?;
                                op_dict.set_item("index", index)?;
                                op_dict.set_item("value", popped_value)?;
                            }
                            Operation::ListInsert { path, index, value } => {
                                op_dict.set_item("type", "ListInsert")?;
                                op_dict.set_item("path", path)?;
                                op_dict.set_item("index", index)?;
                                op_dict.set_item("value", value)?;
                            }
                            Operation::DictUpdate {
                                path,
                                key,
                                old_value,
                                new_value,
                            } => {
                                op_dict.set_item("type", "DictUpdate")?;
                                op_dict.set_item("path", path)?;
                                op_dict.set_item("key", key)?;
                                op_dict.set_item("old", old_value)?;
                                op_dict.set_item("new", new_value)?;
                            }
                            Operation::DictDelete {
                                path,
                                key,
                                old_value,
                            } => {
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
                        timeline.push(op_dict.to_object(py));
                    }
                }
            }
            Ok(timeline)
        } else {
            Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>(format!(
                "Branch '{}' not found",
                label
            )))
        }
    }

    pub fn log_list_pop(&mut self, path: String, index: usize, popped_value: PyObject) {
        let op = Operation::ListPop {
            path,
            index,
            popped_value,
        };
        self.append_node(vec![op]);
    }

    pub fn log_list_insert(&mut self, path: String, index: usize, value: PyObject) {
        let op = Operation::ListInsert { path, index, value };
        self.append_node(vec![op]);
    }

    pub fn log_dict_update(
        &mut self,
        path: String,
        key: PyObject,
        old_value: PyObject,
        new_value: PyObject,
    ) {
        let op = Operation::DictUpdate {
            path,
            key,
            old_value,
            new_value,
        };
        self.append_node(vec![op]);
    }

    pub fn log_dict_delete(&mut self, path: String, key: PyObject, old_value: PyObject) {
        let op = Operation::DictDelete {
            path,
            key,
            old_value,
        };
        self.append_node(vec![op]);
    }
}

impl TachyonEngine {
    fn append_node(&mut self, deltas: Vec<Operation>) {
        let node_id = self.next_node_id;
        let new_node = StateNode {
            id: node_id,
            parents: vec![self.current_node],
            deltas,
            metadata: HashMap::new(),
        };
        self.nodes.insert(node_id, new_node);
        self.current_node = node_id;
        self.next_node_id += 1;

        if self.mode == "linear" {
            self.branches.insert("main".to_string(), node_id);
        }
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
        let owner = self.owner.as_ref(py);
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
                Operation::ListPop {
                    path,
                    index,
                    popped_value,
                } => {
                    if let Ok(list_attr) = owner.getattr(path.as_str()) {
                        if forward {
                            list_attr.call_method1("pop", (*index,))?;
                        } else {
                            list_attr.call_method1("insert", (*index, popped_value))?;
                        }
                    }
                }
                Operation::ListInsert { path, index, value } => {
                    if let Ok(list_attr) = owner.getattr(path.as_str()) {
                        if forward {
                            list_attr.call_method1("insert", (*index, value))?;
                        } else {
                            list_attr.call_method1("pop", (*index,))?;
                        }
                    }
                }
                Operation::DictUpdate {
                    path,
                    key,
                    old_value,
                    new_value,
                } => {
                    if let Ok(dict_attr) = owner.getattr(path.as_str()) {
                        if forward {
                            dict_attr.call_method1("__setitem__", (key, new_value))?;
                        } else if old_value.is_none(py) {
                            dict_attr.call_method1("__delitem__", (key,))?;
                        } else {
                            dict_attr.call_method1("__setitem__", (key, old_value))?;
                        }
                    }
                }
                Operation::DictDelete {
                    path,
                    key,
                    old_value,
                } => {
                    if let Ok(dict_attr) = owner.getattr(path.as_str()) {
                        if forward {
                            dict_attr.call_method1("__delitem__", (key,))?;
                        } else {
                            dict_attr.call_method1("__setitem__", (key, old_value))?;
                        }
                    }
                }
                _ => {}
            }
        }
        Ok(())
    }
}

#[pyclass]
pub struct TrackedList {
    inner: Vec<PyObject>,
    engine: Py<TachyonEngine>,
    name: String,
}

#[pymethods]
impl TrackedList {
    #[new]
    pub fn new(initial: Vec<PyObject>, engine: Py<TachyonEngine>, name: String) -> Self {
        TrackedList {
            inner: initial,
            engine,
            name,
        }
    }

    pub fn append(&mut self, py: Python, value: PyObject) -> PyResult<()> {
        let index = self.inner.len();
        self.inner.push(value.clone());
        if let Ok(mut engine) = self.engine.try_borrow_mut(py) {
            engine.log_list_insert(self.name.clone(), index, value);
        }
        Ok(())
    }

    pub fn pop(&mut self, py: Python, index: Option<isize>) -> PyResult<PyObject> {
        let idx = match index {
            Some(i) => {
                (if i < 0 {
                    self.inner.len() as isize + i
                } else {
                    i
                }) as usize
            }
            None => self.inner.len() - 1,
        };

        if idx >= self.inner.len() {
            return Err(PyErr::new::<pyo3::exceptions::PyIndexError, _>(
                "pop index out of range",
            ));
        }

        let value = self.inner.remove(idx);
        if let Ok(mut engine) = self.engine.try_borrow_mut(py) {
            engine.log_list_pop(self.name.clone(), idx, value.clone());
        }
        Ok(value)
    }

    pub fn __getitem__(&self, index: usize) -> PyResult<PyObject> {
        self.inner.get(index).cloned().ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyIndexError, _>("list index out of range")
        })
    }

    pub fn __len__(&self) -> usize {
        self.inner.len()
    }
}

#[pyclass]
pub struct TrackedDict {
    inner: HashMap<String, PyObject>, // For now, keys are Strings for simplicity
    engine: Py<TachyonEngine>,
    name: String,
}

#[pymethods]
impl TrackedDict {
    #[new]
    pub fn new(
        initial: HashMap<String, PyObject>,
        engine: Py<TachyonEngine>,
        name: String,
    ) -> Self {
        TrackedDict {
            inner: initial,
            engine,
            name,
        }
    }

    pub fn __setitem__(&mut self, py: Python, key: String, value: PyObject) -> PyResult<()> {
        let old_value = self.inner.get(&key).cloned().unwrap_or_else(|| py.None());
        self.inner.insert(key.clone(), value.clone());

        if let Ok(mut engine) = self.engine.try_borrow_mut(py) {
            engine.log_dict_update(self.name.clone(), key.into_py(py), old_value, value);
        }
        Ok(())
    }

    pub fn __delitem__(&mut self, py: Python, key: String) -> PyResult<()> {
        if let Some(old_value) = self.inner.remove(&key) {
            if let Ok(mut engine) = self.engine.try_borrow_mut(py) {
                engine.log_dict_delete(self.name.clone(), key.into_py(py), old_value);
            }
            Ok(())
        } else {
            Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>(key))
        }
    }

    pub fn __getitem__(&self, key: String) -> PyResult<PyObject> {
        self.inner
            .get(&key)
            .cloned()
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>(key))
    }

    pub fn __contains__(&self, key: String) -> bool {
        self.inner.contains_key(&key)
    }

    pub fn __iter__(slf: PyRef<'_, Self>) -> PyResult<PyObject> {
        let py = slf.py();
        let keys: Vec<String> = slf.inner.keys().cloned().collect();
        let list = pyo3::types::PyList::new(py, keys.into_iter().map(|k| k.into_py(py)));
        Ok(list.call_method0("__iter__")?.to_object(py))
    }

    pub fn keys(&self, py: Python) -> PyResult<PyObject> {
        let keys: Vec<String> = self.inner.keys().cloned().collect();
        Ok(pyo3::types::PyList::new(py, keys.into_iter().map(|k| k.into_py(py))).to_object(py))
    }

    pub fn __len__(&self) -> usize {
        self.inner.len()
    }

    pub fn get(&self, py: Python, key: String, default: Option<PyObject>) -> PyObject {
        self.inner
            .get(&key)
            .cloned()
            .unwrap_or_else(|| default.unwrap_or_else(|| py.None()))
    }
}
