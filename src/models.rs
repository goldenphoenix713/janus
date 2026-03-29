use pyo3::prelude::*;
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

#[derive(Debug)]
pub enum ListOperation {
    Insert {
        path: String,
        index: i64,
        value: PyObject,
    },
    Pop {
        path: String,
        index: i64,
        popped_value: PyObject,
    },
    Replace {
        path: String,
        index: i64,
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

#[derive(Clone, Debug)]
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

impl Operation {
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

    pub fn invert(&self, py: Python) -> Self {
        match self {
            Operation::UpdateAttr {
                name,
                old_value,
                new_value,
            } => Operation::UpdateAttr {
                name: name.clone(),
                old_value: new_value.clone_ref(py),
                new_value: old_value.clone_ref(py),
            },
            Operation::ListOp(lo) => Operation::ListOp(lo.invert(py)),
            Operation::DictOp(do_op) => Operation::DictOp(do_op.invert(py)),
            Operation::PluginOp {
                path,
                adapter_name,
                delta_blob,
            } => {
                // Plugin inversion is complex and requires Python-side adapter support.
                Operation::PluginOp {
                    path: path.clone(),
                    adapter_name: adapter_name.clone(),
                    delta_blob: delta_blob.clone_ref(py),
                }
            }
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
                dict.insert(
                    "type",
                    "update_attr"
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
                dict.insert(
                    "name",
                    name.clone()
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
                dict.insert("old_value", old_value.clone_ref(py));
                dict.insert("new_value", new_value.clone_ref(py));
            }
            Operation::ListOp(lo) => {
                dict.insert(
                    "type",
                    "list_op".into_pyobject(py)?.to_owned().into_any().unbind(),
                );
                dict.insert("op", lo.to_object(py)?);
            }
            Operation::DictOp(do_op) => {
                dict.insert(
                    "type",
                    "dict_op".into_pyobject(py)?.to_owned().into_any().unbind(),
                );
                dict.insert("op", do_op.to_object(py)?);
            }
            Operation::PluginOp {
                path,
                adapter_name,
                delta_blob,
            } => {
                dict.insert(
                    "type",
                    "plugin_op"
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
                dict.insert(
                    "path",
                    path.clone()
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
                dict.insert(
                    "adapter_name",
                    adapter_name
                        .clone()
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
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

    pub fn invert(&self, py: Python) -> Self {
        match self {
            ListOperation::Insert { path, index, value } => ListOperation::Pop {
                path: path.clone(),
                index: *index,
                popped_value: value.clone_ref(py),
            },
            ListOperation::Pop {
                path,
                index,
                popped_value,
            } => ListOperation::Insert {
                path: path.clone(),
                index: *index,
                value: popped_value.clone_ref(py),
            },
            ListOperation::Replace {
                path,
                index,
                old_value,
                new_value,
            } => ListOperation::Replace {
                path: path.clone(),
                index: *index,
                old_value: new_value.clone_ref(py),
                new_value: old_value.clone_ref(py),
            },
            ListOperation::Clear { path, old_values } => ListOperation::Extend {
                path: path.clone(),
                new_values: old_values.iter().map(|v| v.clone_ref(py)).collect(),
            },
            ListOperation::Extend { path, new_values } => ListOperation::Clear {
                path: path.clone(),
                old_values: new_values.iter().map(|v| v.clone_ref(py)).collect(),
            },
            ListOperation::Remove { path, value } => ListOperation::Insert {
                path: path.clone(),
                index: -1,
                value: value.clone_ref(py),
            },
        }
    }

    pub fn to_object(&self, py: Python) -> PyResult<PyObject> {
        let mut dict = HashMap::<&str, PyObject>::new();
        match self {
            ListOperation::Insert { path, index, value } => {
                dict.insert(
                    "type",
                    "insert".into_pyobject(py)?.to_owned().into_any().unbind(),
                );
                dict.insert(
                    "path",
                    path.clone()
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
                dict.insert(
                    "index",
                    index.into_pyobject(py)?.to_owned().into_any().unbind(),
                );
                dict.insert("value", value.clone_ref(py));
            }
            ListOperation::Pop {
                path,
                index,
                popped_value,
            } => {
                dict.insert(
                    "type",
                    "pop".into_pyobject(py)?.to_owned().into_any().unbind(),
                );
                dict.insert(
                    "path",
                    path.clone()
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
                dict.insert(
                    "index",
                    index.into_pyobject(py)?.to_owned().into_any().unbind(),
                );
                dict.insert("popped_value", popped_value.clone_ref(py));
            }
            ListOperation::Replace {
                path,
                index,
                old_value,
                new_value,
            } => {
                dict.insert(
                    "type",
                    "replace".into_pyobject(py)?.to_owned().into_any().unbind(),
                );
                dict.insert(
                    "path",
                    path.clone()
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
                dict.insert(
                    "index",
                    index.into_pyobject(py)?.to_owned().into_any().unbind(),
                );
                dict.insert("old_value", old_value.clone_ref(py));
                dict.insert("new_value", new_value.clone_ref(py));
            }
            ListOperation::Clear { path, old_values } => {
                dict.insert(
                    "type",
                    "clear".into_pyobject(py)?.to_owned().into_any().unbind(),
                );
                dict.insert(
                    "path",
                    path.clone()
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
                let old_values_py: Vec<PyObject> =
                    old_values.iter().map(|v| v.clone_ref(py)).collect();
                dict.insert(
                    "old_values",
                    old_values_py
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
            }
            ListOperation::Extend { path, new_values } => {
                dict.insert(
                    "type",
                    "extend".into_pyobject(py)?.to_owned().into_any().unbind(),
                );
                dict.insert(
                    "path",
                    path.clone()
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
                let new_values_py: Vec<PyObject> =
                    new_values.iter().map(|v| v.clone_ref(py)).collect();
                dict.insert(
                    "new_values",
                    new_values_py
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
            }
            ListOperation::Remove { path, value } => {
                dict.insert(
                    "type",
                    "remove".into_pyobject(py)?.to_owned().into_any().unbind(),
                );
                dict.insert(
                    "path",
                    path.clone()
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
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
                let index: i64 = dict.get_item("index")?.unwrap().extract()?;
                let value = dict.get_item("value")?.unwrap().unbind();
                Ok(ListOperation::Insert { path, index, value })
            }
            "pop" => {
                let index: i64 = dict.get_item("index")?.unwrap().extract()?;
                let popped_value = dict.get_item("popped_value")?.unwrap().unbind();
                Ok(ListOperation::Pop {
                    path,
                    index,
                    popped_value,
                })
            }
            "replace" => {
                let index: i64 = dict.get_item("index")?.unwrap().extract()?;
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

    pub fn invert(&self, py: Python) -> Self {
        match self {
            DictOperation::Update {
                path,
                keys,
                old_values,
                new_values,
            } => DictOperation::Update {
                path: path.clone(),
                keys: keys.clone(),
                old_values: new_values.iter().map(|v| v.clone_ref(py)).collect(),
                new_values: old_values.iter().map(|v| v.clone_ref(py)).collect(),
            },
            DictOperation::Pop {
                path,
                key,
                old_value,
            }
            | DictOperation::PopItem {
                path,
                key,
                old_value,
            }
            | DictOperation::Delete {
                path,
                key,
                old_value,
            } => DictOperation::Update {
                path: path.clone(),
                keys: vec![key.clone()],
                old_values: vec![py.None()],
                new_values: vec![old_value.clone_ref(py)],
            },
            DictOperation::SetDefault { path, key, value } => DictOperation::Delete {
                path: path.clone(),
                key: key.clone(),
                old_value: value.clone_ref(py),
            },
            DictOperation::Clear {
                path,
                keys,
                old_values,
            } => DictOperation::Update {
                path: path.clone(),
                keys: keys.clone(),
                old_values: (0..keys.len()).map(|_| py.None()).collect(),
                new_values: old_values.iter().map(|v| v.clone_ref(py)).collect(),
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
                dict.insert(
                    "type",
                    "clear".into_pyobject(py)?.to_owned().into_any().unbind(),
                );
                dict.insert(
                    "path",
                    path.clone()
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
                dict.insert(
                    "keys",
                    keys.clone()
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
                let old_values_py: Vec<PyObject> =
                    old_values.iter().map(|v| v.clone_ref(py)).collect();
                dict.insert(
                    "old_values",
                    old_values_py
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
            }
            DictOperation::Pop {
                path,
                key,
                old_value,
            } => {
                dict.insert(
                    "type",
                    "pop".into_pyobject(py)?.to_owned().into_any().unbind(),
                );
                dict.insert(
                    "path",
                    path.clone()
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
                dict.insert(
                    "key",
                    key.clone()
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
                dict.insert("old_value", old_value.clone_ref(py));
            }
            DictOperation::PopItem {
                path,
                key,
                old_value,
            } => {
                dict.insert(
                    "type",
                    "popitem".into_pyobject(py)?.to_owned().into_any().unbind(),
                );
                dict.insert(
                    "path",
                    path.clone()
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
                dict.insert(
                    "key",
                    key.clone()
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
                dict.insert("old_value", old_value.clone_ref(py));
            }
            DictOperation::SetDefault { path, key, value } => {
                dict.insert(
                    "type",
                    "setdefault"
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
                dict.insert(
                    "path",
                    path.clone()
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
                dict.insert(
                    "key",
                    key.clone()
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
                dict.insert("value", value.clone_ref(py));
            }
            DictOperation::Update {
                path,
                keys,
                old_values,
                new_values,
            } => {
                dict.insert(
                    "type",
                    "update".into_pyobject(py)?.to_owned().into_any().unbind(),
                );
                dict.insert(
                    "path",
                    path.clone()
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
                dict.insert(
                    "keys",
                    keys.clone()
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
                let old_values_py: Vec<PyObject> =
                    old_values.iter().map(|v| v.clone_ref(py)).collect();
                dict.insert(
                    "old_values",
                    old_values_py
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
                let new_values_py: Vec<PyObject> =
                    new_values.iter().map(|v| v.clone_ref(py)).collect();
                dict.insert(
                    "new_values",
                    new_values_py
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
            }
            DictOperation::Delete {
                path,
                key,
                old_value,
            } => {
                dict.insert(
                    "type",
                    "delete".into_pyobject(py)?.to_owned().into_any().unbind(),
                );
                dict.insert(
                    "path",
                    path.clone()
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
                dict.insert(
                    "key",
                    key.clone()
                        .into_pyobject(py)?
                        .to_owned()
                        .into_any()
                        .unbind(),
                );
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
