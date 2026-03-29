use crate::engine::TachyonEngine;
use crate::models::{DictOperation, ListOperation, Operation};
use pyo3::prelude::*;

impl TachyonEngine {
    pub fn consolidate_deltas(&self, py: Python, deltas: Vec<Operation>) -> Vec<Operation> {
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

    pub fn get_all_ops(&self, py: Python, base_id: usize, head_id: usize) -> Vec<Operation> {
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

    pub fn reconcile_source_ops(
        &self,
        py: Python,
        target_ops: &[Operation],
        source_ops: Vec<Operation>,
        strategy: &Bound<'_, PyAny>,
    ) -> PyResult<Vec<Operation>> {
        let mut reconciled = Vec::new();
        for s_op in source_ops {
            if let Some(op) = self.rebase_operation(py, s_op, target_ops, strategy)? {
                reconciled.push(op);
            }
        }
        Ok(reconciled)
    }

    pub fn rebase_operation(
        &self,
        py: Python,
        mut op: Operation,
        target_ops: &[Operation],
        strategy: &Bound<'_, PyAny>,
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

    pub fn transform_list_op(
        &self,
        py: Python,
        lo: &ListOperation,
        tlo: &ListOperation,
        _strategy: &Bound<'_, PyAny>,
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

    pub fn transform_dict_op(
        &self,
        py: Python,
        do_op: &DictOperation,
        tdo_op: &DictOperation,
        strategy: &Bound<'_, PyAny>,
    ) -> PyResult<Option<DictOperation>> {
        match (do_op, tdo_op) {
            (
                DictOperation::Update {
                    path,
                    keys,
                    old_values,
                    new_values,
                },
                DictOperation::Update {
                    keys: t_keys,
                    new_values: t_new_values,
                    ..
                },
            ) => {
                let mut final_keys = Vec::new();
                let mut final_old = Vec::new();
                let mut final_new = Vec::new();

                for i in 0..keys.len() {
                    let k = &keys[i];
                    if let Some(t_idx) = t_keys.iter().position(|tk| tk == k) {
                        let base_val = &old_values[i];
                        let source_val = &new_values[i];
                        let target_val = &t_new_values[t_idx];

                        if strategy.is_instance_of::<pyo3::types::PyString>() {
                            let strategy_str = strategy.extract::<String>()?;
                            if strategy_str == "strict" {
                                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                                    format!("Merge conflict on dictionary key '{}'", k),
                                ));
                            } else if strategy_str == "preserve" {
                                continue; // Target wins
                            }
                            // overshadow is default (continue to add)
                        } else if strategy.is_callable() {
                            let key_path = if path.is_empty() {
                                k.clone()
                            } else {
                                format!("{}.{}", path, k)
                            };
                            let merged_val = strategy.call1((
                                key_path,
                                base_val.clone_ref(py),
                                source_val.clone_ref(py),
                                target_val.clone_ref(py),
                            ))?;
                            final_keys.push(k.clone());
                            final_old.push(target_val.clone_ref(py));
                            final_new.push(merged_val.unbind());
                            continue;
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
}
