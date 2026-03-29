use crate::engine::TachyonEngine;
use crate::models::{Mode, Operation, StateNode};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyDictMethods};
use pyo3::Bound;
use std::collections::HashMap;

impl TachyonEngine {
    pub fn get_graph_state_impl(&self, py: Python) -> PyResult<PyObject> {
        let mut state = HashMap::<&str, PyObject>::new();

        let mut nodes_list = Vec::new();
        for (&id, node) in &self.nodes {
            let mut n_dict = HashMap::<&str, PyObject>::new();
            n_dict.insert("id", id.into_pyobject(py)?.to_owned().into_any().unbind());
            n_dict.insert(
                "parents",
                node.parents
                    .clone()
                    .into_pyobject(py)?
                    .to_owned()
                    .into_any()
                    .unbind(),
            );
            n_dict.insert(
                "timestamp",
                node.timestamp
                    .into_pyobject(py)?
                    .to_owned()
                    .into_any()
                    .unbind(),
            );

            let mut meta_dict = HashMap::<String, PyObject>::new();
            for (k, v) in &node.metadata {
                meta_dict.insert(k.clone(), v.clone_ref(py));
            }
            n_dict.insert(
                "metadata",
                meta_dict.into_pyobject(py)?.to_owned().into_any().unbind(),
            );

            let mut deltas_list = Vec::new();
            for op in &node.deltas {
                deltas_list.push(op.to_object(py)?);
            }
            n_dict.insert(
                "deltas",
                deltas_list
                    .into_pyobject(py)?
                    .to_owned()
                    .into_any()
                    .unbind(),
            );

            nodes_list.push(n_dict.into_pyobject(py)?);
        }
        state.insert(
            "nodes",
            nodes_list.into_pyobject(py)?.to_owned().into_any().unbind(),
        );

        state.insert(
            "active_branch",
            self.active_branch
                .clone()
                .into_pyobject(py)?
                .to_owned()
                .into_any()
                .unbind(),
        );
        state.insert(
            "current_node",
            self.current_node
                .into_pyobject(py)?
                .to_owned()
                .into_any()
                .unbind(),
        );
        state.insert(
            "next_node_id",
            self.next_node_id
                .into_pyobject(py)?
                .to_owned()
                .into_any()
                .unbind(),
        );
        state.insert(
            "branch_labels",
            self.branch_labels
                .clone()
                .into_pyobject(py)?
                .to_owned()
                .into_any()
                .unbind(),
        );
        state.insert(
            "node_labels",
            self.node_labels
                .clone()
                .into_pyobject(py)?
                .to_owned()
                .into_any()
                .unbind(),
        );
        state.insert(
            "mode",
            match self.mode {
                Mode::Linear => "linear",
                Mode::Multiversal => "multiversal",
            }
            .into_pyobject(py)?
            .to_owned()
            .into_any()
            .unbind(),
        );

        Ok(state.into_pyobject(py)?.into())
    }

    pub fn set_graph_state_impl(&mut self, py: Python, state: PyObject) -> PyResult<()> {
        let dict = state.bind(py).downcast::<pyo3::types::PyDict>()?;

        self.nodes.clear();
        self.branch_labels.clear();
        self.node_labels.clear();

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

    pub fn get_net_deltas_map(
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

    pub fn get_other_ops(&self, py: Python, base_id: usize, head_id: usize) -> Vec<Operation> {
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
}
