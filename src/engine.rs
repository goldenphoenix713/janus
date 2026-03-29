use pyo3::prelude::*;
use pyo3::types::{PyAnyMethods, PyDict, PyDictMethods};
use std::collections::HashMap;

#[derive(Debug)]
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

impl Operation {
    #[allow(dead_code)]
    pub fn get_path(&self) -> &str {
        match self {
            Operation::UpdateAttr { name, .. } => name,
            Operation::ListOp(lo) => lo.get_path(),
            Operation::DictOp(do_op) => do_op.get_path(),
            Operation::PluginOp { path, .. } => path,
        }
    }

    pub fn clone_ref(&self, py: Python) -> Self {
        match self {
            Operation::UpdateAttr {
                name,
                old_value,
                new_value,
            } => Operation::UpdateAttr {
                name: name.clone(),
                old_value: old_value.clone_ref(py),
                new_value: new_value.clone_ref(py),
            },
            Operation::ListOp(lo) => Operation::ListOp(lo.clone_ref(py)),
            Operation::DictOp(do_op) => Operation::DictOp(do_op.clone_ref(py)),
            Operation::PluginOp {
                path,
                adapter_name,
                delta_blob,
            } => Operation::PluginOp {
                path: path.clone(),
                adapter_name: adapter_name.clone(),
                delta_blob: delta_blob.clone_ref(py),
            },
        }
    }

    pub fn to_object(&self, py: Python) -> PyResult<PyObject> {
        let mut dict = HashMap::<&str, PyObject>::new();
        match self {
            Operation::UpdateAttr {
                name,
                old_value,
                new_value,
            } => {
                dict.insert("type", "update_attr".into_pyobject(py)?.into());
                dict.insert("name", name.clone().into_pyobject(py)?.into());
                dict.insert("old_value", old_value.clone_ref(py));
                dict.insert("new_value", new_value.clone_ref(py));
            }
            Operation::ListOp(lo) => {
                dict.insert("type", "list_op".into_pyobject(py)?.into());
                dict.insert("op", lo.to_object(py)?);
            }
            Operation::DictOp(do_op) => {
                dict.insert("type", "dict_op".into_pyobject(py)?.into());
                dict.insert("op", do_op.to_object(py)?);
            }
            Operation::PluginOp {
                path,
                adapter_name,
                delta_blob,
            } => {
                dict.insert("type", "plugin_op".into_pyobject(py)?.into());
                dict.insert("path", path.clone().into_pyobject(py)?.into());
                dict.insert(
                    "adapter_name",
                    adapter_name.clone().into_pyobject(py)?.into(),
                );
                dict.insert("delta_blob", delta_blob.clone_ref(py));
            }
        }
        Ok(dict.into_pyobject(py)?.into())
    }

    pub fn from_object(py: Python, obj: PyObject) -> PyResult<Self> {
        let dict = obj.bind(py).downcast::<pyo3::types::PyDict>()?;
        let op_type: String = dict
            .get_item("type")?
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("Missing type"))?
            .extract()?;

        match op_type.as_str() {
            "update_attr" => {
                let name: String = dict.get_item("name")?.unwrap().extract()?;
                let old_value = dict.get_item("old_value")?.unwrap().unbind();
                let new_value = dict.get_item("new_value")?.unwrap().unbind();
                Ok(Operation::UpdateAttr {
                    name,
                    old_value,
                    new_value,
                })
            }
            "list_op" => {
                let op_obj = dict.get_item("op")?.unwrap().unbind();
                Ok(Operation::ListOp(ListOperation::from_object(py, op_obj)?))
            }
            "dict_op" => {
                let op_obj = dict.get_item("op")?.unwrap().unbind();
                Ok(Operation::DictOp(DictOperation::from_object(py, op_obj)?))
            }
            "plugin_op" => {
                let path: String = dict.get_item("path")?.unwrap().extract()?;
                let adapter_name: String = dict.get_item("adapter_name")?.unwrap().extract()?;
                let delta_blob = dict.get_item("delta_blob")?.unwrap().unbind();
                Ok(Operation::PluginOp {
                    path,
                    adapter_name,
                    delta_blob,
                })
            }
            _ => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Unknown op type: {}",
                op_type
            ))),
        }
    }
}

#[derive(Debug)]
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

impl ListOperation {
    pub fn get_path(&self) -> &str {
        match self {
            ListOperation::Insert { path, .. } => path,
            ListOperation::Pop { path, .. } => path,
            ListOperation::Replace { path, .. } => path,
            ListOperation::Clear { path, .. } => path,
            ListOperation::Extend { path, .. } => path,
            ListOperation::Remove { path, .. } => path,
        }
    }

    pub fn clone_ref(&self, py: Python) -> Self {
        match self {
            ListOperation::Insert { path, index, value } => ListOperation::Insert {
                path: path.clone(),
                index: *index,
                value: value.clone_ref(py),
            },
            ListOperation::Pop {
                path,
                index,
                popped_value,
            } => ListOperation::Pop {
                path: path.clone(),
                index: *index,
                popped_value: popped_value.clone_ref(py),
            },
            ListOperation::Replace {
                path,
                index,
                old_value,
                new_value,
            } => ListOperation::Replace {
                path: path.clone(),
                index: *index,
                old_value: old_value.clone_ref(py),
                new_value: new_value.clone_ref(py),
            },
            ListOperation::Clear { path, old_values } => ListOperation::Clear {
                path: path.clone(),
                old_values: old_values.iter().map(|v| v.clone_ref(py)).collect(),
            },
            ListOperation::Extend { path, new_values } => ListOperation::Extend {
                path: path.clone(),
                new_values: new_values.iter().map(|v| v.clone_ref(py)).collect(),
            },
            ListOperation::Remove { path, value } => ListOperation::Remove {
                path: path.clone(),
                value: value.clone_ref(py),
            },
        }
    }

    pub fn to_object(&self, py: Python) -> PyResult<PyObject> {
        let mut dict = HashMap::<&str, PyObject>::new();
        match self {
            ListOperation::Insert { path, index, value } => {
                dict.insert("type", "insert".into_pyobject(py)?.into());
                dict.insert("path", path.clone().into_pyobject(py)?.into());
                dict.insert("index", index.into_pyobject(py)?.into());
                dict.insert("value", value.clone_ref(py));
            }
            ListOperation::Pop {
                path,
                index,
                popped_value,
            } => {
                dict.insert("type", "pop".into_pyobject(py)?.into());
                dict.insert("path", path.clone().into_pyobject(py)?.into());
                dict.insert("index", index.into_pyobject(py)?.into());
                dict.insert("popped_value", popped_value.clone_ref(py));
            }
            ListOperation::Replace {
                path,
                index,
                old_value,
                new_value,
            } => {
                dict.insert("type", "replace".into_pyobject(py)?.into());
                dict.insert("path", path.clone().into_pyobject(py)?.into());
                dict.insert("index", index.into_pyobject(py)?.into());
                dict.insert("old_value", old_value.clone_ref(py));
                dict.insert("new_value", new_value.clone_ref(py));
            }
            ListOperation::Clear { path, old_values } => {
                dict.insert("type", "clear".into_pyobject(py)?.into());
                dict.insert("path", path.clone().into_pyobject(py)?.into());
                let old_values_py: Vec<PyObject> =
                    old_values.iter().map(|v| v.clone_ref(py)).collect();
                dict.insert("old_values", old_values_py.into_pyobject(py)?.into());
            }
            ListOperation::Extend { path, new_values } => {
                dict.insert("type", "extend".into_pyobject(py)?.into());
                dict.insert("path", path.clone().into_pyobject(py)?.into());
                let new_values_py: Vec<PyObject> =
                    new_values.iter().map(|v| v.clone_ref(py)).collect();
                dict.insert("new_values", new_values_py.into_pyobject(py)?.into());
            }
            ListOperation::Remove { path, value } => {
                dict.insert("type", "remove".into_pyobject(py)?.into());
                dict.insert("path", path.clone().into_pyobject(py)?.into());
                dict.insert("value", value.clone_ref(py));
            }
        }
        Ok(dict.into_pyobject(py)?.into())
    }

    pub fn from_object(py: Python, obj: PyObject) -> PyResult<Self> {
        let dict = obj.bind(py).downcast::<pyo3::types::PyDict>()?;
        let op_type: String = dict.get_item("type")?.unwrap().extract()?;
        let path: String = dict.get_item("path")?.unwrap().extract()?;

        match op_type.as_str() {
            "insert" => {
                let index: usize = dict.get_item("index")?.unwrap().extract()?;
                let value = dict.get_item("value")?.unwrap().unbind();
                Ok(ListOperation::Insert { path, index, value })
            }
            "pop" => {
                let index: usize = dict.get_item("index")?.unwrap().extract()?;
                let popped_value = dict.get_item("popped_value")?.unwrap().unbind();
                Ok(ListOperation::Pop {
                    path,
                    index,
                    popped_value,
                })
            }
            "replace" => {
                let index: usize = dict.get_item("index")?.unwrap().extract()?;
                let old_value = dict.get_item("old_value")?.unwrap().unbind();
                let new_value = dict.get_item("new_value")?.unwrap().unbind();
                Ok(ListOperation::Replace {
                    path,
                    index,
                    old_value,
                    new_value,
                })
            }
            "clear" => {
                let old_values: Vec<PyObject> = dict.get_item("old_values")?.unwrap().extract()?;
                Ok(ListOperation::Clear { path, old_values })
            }
            "extend" => {
                let new_values: Vec<PyObject> = dict.get_item("new_values")?.unwrap().extract()?;
                Ok(ListOperation::Extend { path, new_values })
            }
            "remove" => {
                let value = dict.get_item("value")?.unwrap().unbind();
                Ok(ListOperation::Remove { path, value })
            }
            _ => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Unknown list op type: {}",
                op_type
            ))),
        }
    }
}

#[derive(Debug)]
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

impl DictOperation {
    pub fn get_path(&self) -> &str {
        match self {
            DictOperation::Clear { path, .. } => path,
            DictOperation::Pop { path, .. } => path,
            DictOperation::PopItem { path, .. } => path,
            DictOperation::SetDefault { path, .. } => path,
            DictOperation::Update { path, .. } => path,
            DictOperation::Delete { path, .. } => path,
        }
    }

    pub fn clone_ref(&self, py: Python) -> Self {
        match self {
            DictOperation::Clear {
                path,
                keys,
                old_values,
            } => DictOperation::Clear {
                path: path.clone(),
                keys: keys.clone(),
                old_values: old_values.iter().map(|v| v.clone_ref(py)).collect(),
            },
            DictOperation::Pop {
                path,
                key,
                old_value,
            } => DictOperation::Pop {
                path: path.clone(),
                key: key.clone(),
                old_value: old_value.clone_ref(py),
            },
            DictOperation::PopItem {
                path,
                key,
                old_value,
            } => DictOperation::PopItem {
                path: path.clone(),
                key: key.clone(),
                old_value: old_value.clone_ref(py),
            },
            DictOperation::SetDefault { path, key, value } => DictOperation::SetDefault {
                path: path.clone(),
                key: key.clone(),
                value: value.clone_ref(py),
            },
            DictOperation::Update {
                path,
                keys,
                old_values,
                new_values,
            } => DictOperation::Update {
                path: path.clone(),
                keys: keys.clone(),
                old_values: old_values.iter().map(|v| v.clone_ref(py)).collect(),
                new_values: new_values.iter().map(|v| v.clone_ref(py)).collect(),
            },
            DictOperation::Delete {
                path,
                key,
                old_value,
            } => DictOperation::Delete {
                path: path.clone(),
                key: key.clone(),
                old_value: old_value.clone_ref(py),
            },
        }
    }

    pub fn to_object(&self, py: Python) -> PyResult<PyObject> {
        let mut dict = HashMap::<&str, PyObject>::new();
        match self {
            DictOperation::Clear {
                path,
                keys,
                old_values,
            } => {
                dict.insert("type", "clear".into_pyobject(py)?.into());
                dict.insert("path", path.clone().into_pyobject(py)?.into());
                dict.insert("keys", keys.clone().into_pyobject(py)?.into());
                let old_values_py: Vec<PyObject> =
                    old_values.iter().map(|v| v.clone_ref(py)).collect();
                dict.insert("old_values", old_values_py.into_pyobject(py)?.into());
            }
            DictOperation::Pop {
                path,
                key,
                old_value,
            } => {
                dict.insert("type", "pop".into_pyobject(py)?.into());
                dict.insert("path", path.clone().into_pyobject(py)?.into());
                dict.insert("key", key.clone().into_pyobject(py)?.into());
                dict.insert("old_value", old_value.clone_ref(py));
            }
            DictOperation::PopItem {
                path,
                key,
                old_value,
            } => {
                dict.insert("type", "popitem".into_pyobject(py)?.into());
                dict.insert("path", path.clone().into_pyobject(py)?.into());
                dict.insert("key", key.clone().into_pyobject(py)?.into());
                dict.insert("old_value", old_value.clone_ref(py));
            }
            DictOperation::SetDefault { path, key, value } => {
                dict.insert("type", "setdefault".into_pyobject(py)?.into());
                dict.insert("path", path.clone().into_pyobject(py)?.into());
                dict.insert("key", key.clone().into_pyobject(py)?.into());
                dict.insert("value", value.clone_ref(py));
            }
            DictOperation::Update {
                path,
                keys,
                old_values,
                new_values,
            } => {
                dict.insert("type", "update".into_pyobject(py)?.into());
                dict.insert("path", path.clone().into_pyobject(py)?.into());
                dict.insert("keys", keys.clone().into_pyobject(py)?.into());
                let old_values_py: Vec<PyObject> =
                    old_values.iter().map(|v| v.clone_ref(py)).collect();
                dict.insert("old_values", old_values_py.into_pyobject(py)?.into());
                let new_values_py: Vec<PyObject> =
                    new_values.iter().map(|v| v.clone_ref(py)).collect();
                dict.insert("new_values", new_values_py.into_pyobject(py)?.into());
            }
            DictOperation::Delete {
                path,
                key,
                old_value,
            } => {
                dict.insert("type", "delete".into_pyobject(py)?.into());
                dict.insert("path", path.clone().into_pyobject(py)?.into());
                dict.insert("key", key.clone().into_pyobject(py)?.into());
                dict.insert("old_value", old_value.clone_ref(py));
            }
        }
        Ok(dict.into_pyobject(py)?.into())
    }

    pub fn from_object(py: Python, obj: PyObject) -> PyResult<Self> {
        let dict = obj.bind(py).downcast::<pyo3::types::PyDict>()?;
        let op_type: String = dict.get_item("type")?.unwrap().extract()?;
        let path: String = dict.get_item("path")?.unwrap().extract()?;

        match op_type.as_str() {
            "clear" => {
                let keys: Vec<String> = dict.get_item("keys")?.unwrap().extract()?;
                let old_values: Vec<PyObject> = dict.get_item("old_values")?.unwrap().extract()?;
                Ok(DictOperation::Clear {
                    path,
                    keys,
                    old_values,
                })
            }
            "pop" => {
                let key: String = dict.get_item("key")?.unwrap().extract()?;
                let old_value = dict.get_item("old_value")?.unwrap().unbind();
                Ok(DictOperation::Pop {
                    path,
                    key,
                    old_value,
                })
            }
            "popitem" => {
                let key: String = dict.get_item("key")?.unwrap().extract()?;
                let old_value = dict.get_item("old_value")?.unwrap().unbind();
                Ok(DictOperation::PopItem {
                    path,
                    key,
                    old_value,
                })
            }
            "setdefault" => {
                let key: String = dict.get_item("key")?.unwrap().extract()?;
                let value = dict.get_item("value")?.unwrap().unbind();
                Ok(DictOperation::SetDefault { path, key, value })
            }
            "update" => {
                let keys: Vec<String> = dict.get_item("keys")?.unwrap().extract()?;
                let old_values: Vec<PyObject> = dict.get_item("old_values")?.unwrap().extract()?;
                let new_values: Vec<PyObject> = dict.get_item("new_values")?.unwrap().extract()?;
                Ok(DictOperation::Update {
                    path,
                    keys,
                    old_values,
                    new_values,
                })
            }
            "delete" => {
                let key: String = dict.get_item("key")?.unwrap().extract()?;
                let old_value = dict.get_item("old_value")?.unwrap().unbind();
                Ok(DictOperation::Delete {
                    path,
                    key,
                    old_value,
                })
            }
            _ => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Unknown dict op type: {}",
                op_type
            ))),
        }
    }
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
    pub metadata: HashMap<String, PyObject>,
    pub timestamp: u64,
}

#[pyclass]
pub struct TachyonEngine {
    pub owner: Py<pyo3::types::PyWeakref>,
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
    pub fn new(owner: Bound<'_, PyAny>, mode: String) -> PyResult<Self> {
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
        let active_branch = "main".to_string();

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

        let mode = match mode.as_str() {
            "linear" => Mode::Linear,
            "multiversal" => Mode::Multiversal,
            _ => panic!("Invalid mode: {}", mode),
        };

        Ok(TachyonEngine {
            owner: weak_owner,
            nodes,
            node_labels,
            branch_labels,
            active_branch,
            current_node: 0,
            next_node_id: 1,
            mode,
        })
    }

    pub fn get_graph_data(&self, py: Python) -> PyResult<PyObject> {
        let mut nodes_data = Vec::new();
        for (&id, node) in &self.nodes {
            let mut node_dict = HashMap::<&str, PyObject>::new();
            node_dict.insert("id", id.into_pyobject(py)?.to_owned().unbind().into_any());
            node_dict.insert(
                "parents",
                node.parents
                    .clone()
                    .into_pyobject(py)?
                    .to_owned()
                    .unbind()
                    .into_any(),
            );
            node_dict.insert(
                "is_current",
                (id == self.current_node)
                    .into_pyobject(py)?
                    .to_owned()
                    .unbind()
                    .into_any(),
            );
            let mut labels = Vec::new();
            for (label, &nid) in &self.node_labels {
                if nid == id {
                    labels.push(label.clone());
                }
            }
            node_dict.insert(
                "labels",
                labels.into_pyobject(py)?.to_owned().unbind().into_any(),
            );
            nodes_data.push(node_dict.into_pyobject(py)?);
        }

        // Include root node if it has labels and current node is root
        if !self.nodes.contains_key(&0) {
            let mut root_dict = HashMap::<&str, PyObject>::new();
            root_dict.insert(
                "id",
                0usize.into_pyobject(py)?.to_owned().unbind().into_any(),
            );
            root_dict.insert(
                "parents",
                Vec::<usize>::new()
                    .into_pyobject(py)?
                    .to_owned()
                    .unbind()
                    .into_any(),
            );
            root_dict.insert(
                "is_current",
                (self.current_node == 0)
                    .into_pyobject(py)?
                    .to_owned()
                    .unbind()
                    .into_any(),
            );

            let mut labels = Vec::new();
            for (label, &nid) in &self.node_labels {
                if nid == 0 {
                    labels.push(label.clone());
                }
            }
            root_dict.insert(
                "labels",
                labels.into_pyobject(py)?.to_owned().unbind().into_any(),
            );
            nodes_data.push(root_dict.into_pyobject(py)?);
        }

        Ok(nodes_data.into_pyobject(py)?.into())
    }

    pub fn get_graph_state(&self, py: Python) -> PyResult<PyObject> {
        let mut state = HashMap::<&str, PyObject>::new();

        // 1. Nodes
        let mut nodes_list = Vec::new();
        for (&id, node) in &self.nodes {
            let mut n_dict = HashMap::<&str, PyObject>::new();
            n_dict.insert("id", id.into_pyobject(py)?.into());
            n_dict.insert("parents", node.parents.clone().into_pyobject(py)?.into());
            n_dict.insert("timestamp", node.timestamp.into_pyobject(py)?.into());

            // Metadata
            let mut meta_dict = HashMap::<String, PyObject>::new();
            for (k, v) in &node.metadata {
                meta_dict.insert(k.clone(), v.clone_ref(py));
            }
            n_dict.insert("metadata", meta_dict.into_pyobject(py)?.into());

            // Deltas
            let mut deltas_list = Vec::new();
            for op in &node.deltas {
                deltas_list.push(op.to_object(py)?);
            }
            n_dict.insert("deltas", deltas_list.into_pyobject(py)?.into());

            nodes_list.push(n_dict.into_pyobject(py)?);
        }
        state.insert("nodes", nodes_list.into_pyobject(py)?.into());

        // 2. Head/Branch state
        state.insert(
            "active_branch",
            self.active_branch.clone().into_pyobject(py)?.into(),
        );
        state.insert("current_node", self.current_node.into_pyobject(py)?.into());
        state.insert("next_node_id", self.next_node_id.into_pyobject(py)?.into());
        state.insert(
            "branch_labels",
            self.branch_labels.clone().into_pyobject(py)?.into(),
        );
        state.insert(
            "node_labels",
            self.node_labels.clone().into_pyobject(py)?.into(),
        );
        state.insert(
            "mode",
            match self.mode {
                Mode::Linear => "linear",
                Mode::Multiversal => "multiversal",
            }
            .into_pyobject(py)?
            .into(),
        );

        Ok(state.into_pyobject(py)?.into())
    }

    pub fn set_graph_state(&mut self, py: Python, state: PyObject) -> PyResult<()> {
        let dict = state.bind(py).downcast::<pyo3::types::PyDict>()?;

        // 1. Clear current state
        self.nodes.clear();
        self.branch_labels.clear();
        self.node_labels.clear();

        // 2. Load Nodes
        let nodes_list: Vec<Bound<PyDict>> = dict.get_item("nodes")?.unwrap().extract()?;
        for n_dict in nodes_list {
            let id: usize = n_dict.get_item("id")?.unwrap().extract()?;
            let parents: Vec<usize> = n_dict.get_item("parents")?.unwrap().extract()?;
            let timestamp: u64 = n_dict.get_item("timestamp")?.unwrap().extract()?;

            let meta_dict_py: Bound<PyDict> = n_dict
                .get_item("metadata")?
                .unwrap()
                .downcast::<PyDict>()?
                .clone();
            let mut metadata = HashMap::new();
            for (k, v) in meta_dict_py {
                metadata.insert(k.extract::<String>()?, v.unbind());
            }

            let deltas_list: Vec<PyObject> = n_dict.get_item("deltas")?.unwrap().extract()?;
            let mut deltas = Vec::new();
            for op_obj in deltas_list {
                deltas.push(Operation::from_object(py, op_obj)?);
            }

            self.nodes.insert(
                id,
                StateNode {
                    id,
                    parents,
                    deltas,
                    metadata,
                    timestamp,
                },
            );
        }

        // 3. Global State
        self.active_branch = dict.get_item("active_branch")?.unwrap().extract()?;
        self.current_node = dict.get_item("current_node")?.unwrap().extract()?;
        self.next_node_id = dict.get_item("next_node_id")?.unwrap().extract()?;
        self.branch_labels = dict.get_item("branch_labels")?.unwrap().extract()?;
        self.node_labels = dict.get_item("node_labels")?.unwrap().extract()?;

        let mode_str: String = dict.get_item("mode")?.unwrap().extract()?;
        self.mode = match mode_str.as_str() {
            "linear" => Mode::Linear,
            "multiversal" => Mode::Multiversal,
            _ => {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "Invalid mode",
                ))
            }
        };

        Ok(())
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
        let node = self.nodes.get_mut(&self.current_node).unwrap();
        node.metadata.insert(key, value);
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
            return Ok(()); // Root cannot be squashed
        }

        let mut path = Vec::new();
        let mut curr = leaf_id;

        // Walk back to find the "stable ancestor"
        // A stable ancestor is the first node that is either:
        // 1. Root (id=0)
        // 2. A node with multiple parents (confluence point)
        // 3. A node whose parent has other children (branching point)
        while curr != 0 {
            path.push(curr);
            let node = self.nodes.get(&curr).unwrap();

            // If node has multiple parents, it's a merge point - stop here.
            if node.parents.len() != 1 {
                break;
            }

            let parent_id = node.parents[0];
            if parent_id == 0 {
                break;
            }

            // Check if parent has other children
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
            return Ok(()); // Nothing to squash (only 0 or 1 node in the chain)
        }

        path.reverse();
        // The common ancestor is the parent of the first node in our chain
        let anchor_id = self.nodes.get(&path[0]).unwrap().parents[0];

        // Collect all deltas
        let mut all_deltas = Vec::new();
        for nid in &path {
            let node_deltas = &self.nodes.get(nid).unwrap().deltas;
            for op in node_deltas {
                all_deltas.push(op.clone_ref(py));
            }
        }

        // Consolidate deltas
        let consolidated = self.consolidate_deltas(py, all_deltas);

        let mut new_metadata = HashMap::new();
        for (k, v) in &self.nodes.get(&leaf_id).unwrap().metadata {
            new_metadata.insert(k.clone(), v.clone_ref(py));
        }

        // Create new node
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

        // Update branch labels pointing to this leaf
        let mut branches_to_update = Vec::new();
        for (name, &head_id) in &self.branch_labels {
            if head_id == leaf_id {
                branches_to_update.push(name.clone());
            }
        }
        for name in branches_to_update {
            self.branch_labels.insert(name, new_id);
        }

        // Update node labels pointing to this leaf
        let mut node_labels_to_update = Vec::new();
        for (name, &nid) in &self.node_labels {
            if nid == leaf_id {
                node_labels_to_update.push(name.clone());
            }
        }
        for name in node_labels_to_update {
            self.node_labels.insert(name, new_id);
        }

        // Move current_node to the new squashed node if it was on the squashed branch
        if self.current_node == leaf_id {
            self.current_node = new_id;
        }

        Ok(())
    }
}

impl TachyonEngine {
    fn consolidate_deltas(&self, py: Python, deltas: Vec<Operation>) -> Vec<Operation> {
        use std::collections::HashMap;
        let mut attr_map = HashMap::<String, (PyObject, PyObject)>::new();
        let mut others = Vec::new();

        for op in deltas {
            match op {
                Operation::UpdateAttr {
                    name,
                    old_value,
                    new_value,
                } => {
                    if let Some(entry) = attr_map.get_mut(&name) {
                        entry.1 = new_value.clone_ref(py);
                    } else {
                        attr_map.insert(name, (old_value.clone_ref(py), new_value.clone_ref(py)));
                    }
                }
                _ => others.push(op), // Keep Container/Plugin ops as is for now
            }
        }

        let mut result = Vec::new();
        // Deterministic order for testing
        let mut keys: Vec<_> = attr_map.keys().cloned().collect();
        keys.sort();

        for name in keys {
            let (old_value, new_value) = attr_map.remove(&name).unwrap();
            result.push(Operation::UpdateAttr {
                name,
                old_value,
                new_value,
            });
        }
        result.extend(others);
        result
    }

    fn get_all_ops(&self, py: Python, base_id: usize, head_id: usize) -> Vec<Operation> {
        let path = self.get_path_between(base_id, head_id);
        let mut all_ops = Vec::new();
        for node_id in path {
            if let Some(node) = self.nodes.get(&node_id) {
                for op in &node.deltas {
                    all_ops.push(op.clone_ref(py));
                }
            }
        }
        all_ops
    }

    fn reconcile_source_ops(
        &self,
        py: Python,
        target_ops: &[Operation],
        source_ops: Vec<Operation>,
        strategy: &str,
    ) -> PyResult<Vec<Operation>> {
        let mut reconciled = Vec::new();
        for s_op in source_ops {
            if let Some(op) = self.rebase_operation(py, s_op, target_ops, strategy)? {
                reconciled.push(op);
            }
        }
        Ok(reconciled)
    }

    fn rebase_operation(
        &self,
        py: Python,
        mut op: Operation,
        target_ops: &[Operation],
        strategy: &str,
    ) -> PyResult<Option<Operation>> {
        for t_op in target_ops {
            match (&op, t_op) {
                (Operation::ListOp(lo), Operation::ListOp(tlo)) => {
                    if lo.get_path() == tlo.get_path() {
                        if let Some(new_lo) = self.transform_list_op(py, lo, tlo, strategy)? {
                            op = Operation::ListOp(new_lo);
                        } else {
                            return Ok(None);
                        }
                    }
                }
                (Operation::DictOp(do_op), Operation::DictOp(tdo_op)) => {
                    if do_op.get_path() == tdo_op.get_path() {
                        if let Some(new_do) = self.transform_dict_op(py, do_op, tdo_op, strategy)? {
                            op = Operation::DictOp(new_do);
                        } else {
                            return Ok(None);
                        }
                    }
                }
                _ => {}
            }
        }
        Ok(Some(op))
    }

    fn transform_list_op(
        &self,
        py: Python,
        lo: &ListOperation,
        tlo: &ListOperation,
        _strategy: &str,
    ) -> PyResult<Option<ListOperation>> {
        match (lo, tlo) {
            (
                ListOperation::Insert { path, index, value },
                ListOperation::Insert { index: t_index, .. },
            ) => {
                let mut new_index = *index;
                if *t_index <= *index {
                    new_index += 1;
                }
                Ok(Some(ListOperation::Insert {
                    path: path.clone(),
                    index: new_index,
                    value: value.clone_ref(py),
                }))
            }
            (
                ListOperation::Insert { path, index, value },
                ListOperation::Pop { index: t_index, .. },
            ) => {
                let mut new_index = *index;
                if *t_index < *index {
                    new_index -= 1;
                }
                Ok(Some(ListOperation::Insert {
                    path: path.clone(),
                    index: new_index,
                    value: value.clone_ref(py),
                }))
            }
            _ => Ok(Some(lo.clone_ref(py))),
        }
    }

    fn transform_dict_op(
        &self,
        py: Python,
        do_op: &DictOperation,
        tdo_op: &DictOperation,
        strategy: &str,
    ) -> PyResult<Option<DictOperation>> {
        match (do_op, tdo_op) {
            (
                DictOperation::Update {
                    path,
                    keys,
                    old_values,
                    new_values,
                },
                DictOperation::Update { keys: t_keys, .. },
            ) => {
                let mut final_keys = Vec::new();
                let mut final_old = Vec::new();
                let mut final_new = Vec::new();

                for i in 0..keys.len() {
                    let k = &keys[i];
                    if t_keys.contains(k) {
                        if strategy == "strict" {
                            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                                "Merge conflict on dictionary key '{}'",
                                k
                            )));
                        } else if strategy == "preserve" {
                            continue; // Target wins
                        }
                    }
                    final_keys.push(k.clone());
                    final_old.push(old_values[i].clone_ref(py));
                    final_new.push(new_values[i].clone_ref(py));
                }

                if final_keys.is_empty() {
                    return Ok(None);
                }

                Ok(Some(DictOperation::Update {
                    path: path.clone(),
                    keys: final_keys,
                    old_values: final_old,
                    new_values: final_new,
                }))
            }
            _ => Ok(Some(do_op.clone_ref(py))),
        }
    }

    fn find_lca(&self, a: usize, b: usize) -> usize {
        use std::collections::HashSet;
        let mut ancestors_a = HashSet::new();
        let mut curr = a;
        while curr != 0 {
            ancestors_a.insert(curr);
            let node = self.nodes.get(&curr).unwrap();
            if node.parents.is_empty() {
                break;
            }
            curr = node.parents[0];
        }
        ancestors_a.insert(0);

        curr = b;
        while curr != 0 {
            if ancestors_a.contains(&curr) {
                return curr;
            }
            let node = self.nodes.get(&curr).unwrap();
            if node.parents.is_empty() {
                break;
            }
            curr = node.parents[0];
        }
        0
    }

    fn get_net_deltas_map(
        &self,
        py: Python,
        base_id: usize,
        head_id: usize,
    ) -> HashMap<String, (PyObject, PyObject)> {
        let mut attr_map = HashMap::<String, (PyObject, PyObject)>::new();
        let path = self.get_path_between(base_id, head_id);

        for nid in path {
            let node = self.nodes.get(&nid).unwrap();
            for op in &node.deltas {
                if let Operation::UpdateAttr {
                    name,
                    old_value,
                    new_value,
                } = op
                {
                    if let Some(entry) = attr_map.get_mut(name) {
                        entry.1 = new_value.clone_ref(py);
                    } else {
                        attr_map.insert(
                            name.clone(),
                            (old_value.clone_ref(py), new_value.clone_ref(py)),
                        );
                    }
                }
            }
        }
        attr_map
    }

    fn get_other_ops(&self, py: Python, base_id: usize, head_id: usize) -> Vec<Operation> {
        let mut others = Vec::new();
        let path = self.get_path_between(base_id, head_id);
        for nid in path {
            let node = self.nodes.get(&nid).unwrap();
            for op in &node.deltas {
                match op {
                    Operation::UpdateAttr { .. } => {}
                    _ => others.push(op.clone_ref(py)),
                }
            }
        }
        others
    }

    fn get_path_between(&self, base_id: usize, head_id: usize) -> Vec<usize> {
        let mut path = Vec::new();
        let mut curr = head_id;
        while curr != base_id && curr != 0 {
            path.push(curr);
            let node = self.nodes.get(&curr).unwrap();
            if node.parents.is_empty() {
                break;
            }
            curr = node.parents[0];
        }
        path.reverse();
        path
    }
}

#[pymethods]
impl TachyonEngine {
    pub fn redo(&mut self, py: Python) -> PyResult<()> {
        if let Some(node) = self.nodes.get(&(self.current_node + 1)) {
            self.move_to_node_id(py, node.id)?;
        }
        Ok(())
    }

    pub fn move_to_node_id(&mut self, py: Python, node_id: usize) -> PyResult<()> {
        let owner = self.upgrade_owner(py)?;
        owner.setattr("_restoring", true)?;

        let (path_up, path_down) = self.get_shortest_path(self.current_node, node_id);

        // 1. Move UP to LCA (apply backwards)
        for nid in path_up {
            if let Some(node) = self.nodes.get(&nid) {
                self.apply_node_deltas(py, node, false)?;
            }
        }

        // 2. Move DOWN to target (apply forwards)
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
            return Ok(()); // Already merged
        }

        let lca_id = self.find_lca(target_id, source_id);

        // Get net changes for both paths from LCA
        let target_net = self.get_net_deltas_map(py, lca_id, target_id);
        let source_net = self.get_net_deltas_map(py, lca_id, source_id);

        let mut merged_ops = Vec::new();

        // 3-Way Reconciliation
        for (name, (old_at_base, source_val)) in source_net {
            if let Some((_old_at_base_target, target_val)) = target_net.get(&name) {
                // Conflict!
                if target_val.bind(py).eq(source_val.bind(py))? {
                    // Same value, no conflict
                    continue;
                }

                match strategy {
                    "overshadow" => {
                        // Source wins: set from current target_val to source_val
                        merged_ops.push(Operation::UpdateAttr {
                            name: name.clone(),
                            old_value: target_val.clone_ref(py),
                            new_value: source_val.clone_ref(py),
                        });
                    }
                    "preserve" => {
                        // Target wins: do nothing
                    }
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
                // Key only in source: apply it to current target
                // Since it wasn't in target_net, the target value matches base
                merged_ops.push(Operation::UpdateAttr {
                    name,
                    old_value: old_at_base.clone_ref(py),
                    new_value: source_val.clone_ref(py),
                });
            }
        }

        // Handle other operations (Containers/Plugins) via reconciliation
        let target_all_ops = self.get_all_ops(py, lca_id, target_id);
        let source_others = self.get_other_ops(py, lca_id, source_id);
        let reconciled_source =
            self.reconcile_source_ops(py, &target_all_ops, source_others, strategy)?;
        merged_ops.extend(reconciled_source);

        if merged_ops.is_empty() && lca_id == source_id {
            return Ok(()); // Source is already an ancestor of target
        }

        // Create merge node
        let new_id = self.next_node_id;
        self.next_node_id += 1;
        let new_node = StateNode {
            id: new_id,
            parents: vec![target_id, source_id], // Two parents!
            deltas: merged_ops,
            metadata: HashMap::new(),
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs(),
        };

        self.nodes.insert(new_id, new_node);
        // Do not update current_node manually! move_to_node_id will do it after applying deltas.
        self.branch_labels
            .insert(self.active_branch.clone(), new_id);

        // Apply state changes to the live object
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
                        let op_name = match op {
                            Operation::UpdateAttr { name, .. } => name.as_str(),
                            Operation::ListOp(lo) => match lo {
                                ListOperation::Insert { path, .. } => path.as_str(),
                                ListOperation::Pop { path, .. } => path.as_str(),
                                ListOperation::Replace { path, .. } => path.as_str(),
                                ListOperation::Clear { path, .. } => path.as_str(),
                                ListOperation::Extend { path, .. } => path.as_str(),
                                ListOperation::Remove { path, .. } => path.as_str(),
                            },
                            Operation::DictOp(do_alt) => match do_alt {
                                DictOperation::Clear { path, .. } => path.as_str(),
                                DictOperation::Pop { path, .. } => path.as_str(),
                                DictOperation::PopItem { path, .. } => path.as_str(),
                                DictOperation::SetDefault { path, .. } => path.as_str(),
                                DictOperation::Update { path, .. } => path.as_str(),
                                DictOperation::Delete { path, .. } => path.as_str(),
                            },
                            Operation::PluginOp { path, .. } => path.as_str(),
                        };
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

    fn upgrade_owner<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        self.owner.bind(py).upgrade().ok_or_else(move || {
            PyErr::new::<pyo3::exceptions::PyReferenceError, _>(
                "Janus object has been garbage collected (Tombstone state).",
            )
        })
    }
}
