use crate::engine::TachyonEngine;
use pyo3::prelude::*;

#[pyclass]
pub struct TrackedListCore {
    engine: Py<TachyonEngine>,
    name: String,
}

#[pymethods]
impl TrackedListCore {
    #[new]
    pub fn new(engine: Py<TachyonEngine>, name: String) -> Self {
        TrackedListCore { engine, name }
    }

    pub fn log_insert(&self, py: Python, index: usize, value: PyObject) -> PyResult<()> {
        if let Ok(mut engine) = self.engine.try_borrow_mut(py) {
            // Note: We don't check _restoring here because the Python side
            // will check its own _silent flag which handles both restoration
            // AND initial wrapping.
            engine.log_list_insert(self.name.clone(), index, value);
        }
        Ok(())
    }

    pub fn log_pop(&self, py: Python, index: usize, value: PyObject) -> PyResult<()> {
        if let Ok(mut engine) = self.engine.try_borrow_mut(py) {
            engine.log_list_pop(self.name.clone(), index, value);
        }
        Ok(())
    }

    pub fn log_replace(
        &self,
        py: Python,
        index: usize,
        old_value: PyObject,
        new_value: PyObject,
    ) -> PyResult<()> {
        if let Ok(mut engine) = self.engine.try_borrow_mut(py) {
            engine.log_list_replace(self.name.clone(), index, old_value, new_value);
        }
        Ok(())
    }

    pub fn log_clear(&self, py: Python, old_values: Vec<PyObject>) -> PyResult<()> {
        if let Ok(mut engine) = self.engine.try_borrow_mut(py) {
            engine.log_list_clear(self.name.clone(), old_values);
        }
        Ok(())
    }

    pub fn log_extend(&self, py: Python, new_values: Vec<PyObject>) -> PyResult<()> {
        if let Ok(mut engine) = self.engine.try_borrow_mut(py) {
            engine.log_list_extend(self.name.clone(), new_values);
        }
        Ok(())
    }
}

#[pyclass]
pub struct TrackedDictCore {
    engine: Py<TachyonEngine>,
    name: String,
}

#[pymethods]
impl TrackedDictCore {
    #[new]
    pub fn new(engine: Py<TachyonEngine>, name: String) -> Self {
        TrackedDictCore { engine, name }
    }

    pub fn log_update(
        &self,
        py: Python,
        keys: Vec<String>,
        old_values: Vec<PyObject>,
        new_values: Vec<PyObject>,
    ) -> PyResult<()> {
        if let Ok(mut engine) = self.engine.try_borrow_mut(py) {
            engine.log_dict_update(self.name.clone(), keys, old_values, new_values);
        }
        Ok(())
    }

    pub fn log_delete(&self, py: Python, key: String, old_value: PyObject) -> PyResult<()> {
        if let Ok(mut engine) = self.engine.try_borrow_mut(py) {
            engine.log_dict_delete(self.name.clone(), key, old_value);
        }
        Ok(())
    }

    pub fn log_clear(
        &self,
        py: Python,
        keys: Vec<String>,
        old_values: Vec<PyObject>,
    ) -> PyResult<()> {
        if let Ok(mut engine) = self.engine.try_borrow_mut(py) {
            engine.log_dict_clear(self.name.clone(), keys, old_values);
        }
        Ok(())
    }

    pub fn log_pop(&self, py: Python, key: String, old_value: PyObject) -> PyResult<()> {
        if let Ok(mut engine) = self.engine.try_borrow_mut(py) {
            engine.log_dict_pop(self.name.clone(), key, old_value);
        }
        Ok(())
    }
}
