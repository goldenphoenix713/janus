use pyo3::prelude::*;
use std::collections::HashMap;

use crate::engine::TachyonEngine;

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
            if !engine
                .owner
                .getattr(py, "_restoring")?
                .extract::<bool>(py)?
            {
                engine.log_list_insert(self.name.clone(), index, value);
            }
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
            if !engine
                .owner
                .getattr(py, "_restoring")?
                .extract::<bool>(py)?
            {
                engine.log_list_pop(self.name.clone(), idx, value.clone());
            }
        }
        Ok(value)
    }

    pub fn __getitem__(&self, index: usize) -> PyResult<PyObject> {
        self.inner.get(index).cloned().ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyIndexError, _>("list index out of range")
        })
    }

    pub fn __setitem__(&mut self, py: Python, index: usize, value: PyObject) -> PyResult<()> {
        if index >= self.inner.len() {
            return Err(PyErr::new::<pyo3::exceptions::PyIndexError, _>(
                "list index out of range",
            ));
        }
        let old_value = self.inner.get(index).cloned().unwrap_or_else(|| py.None());
        self.inner[index] = value.clone();

        if let Ok(mut engine) = self.engine.try_borrow_mut(py) {
            if !engine
                .owner
                .getattr(py, "_restoring")?
                .extract::<bool>(py)?
            {
                engine.log_list_replace(self.name.clone(), index, old_value, value);
            }
        }
        Ok(())
    }

    pub fn __len__(&self) -> usize {
        self.inner.len()
    }

    pub fn insert(&mut self, py: Python, index: usize, value: PyObject) -> PyResult<()> {
        if index > self.inner.len() {
            return Err(PyErr::new::<pyo3::exceptions::PyIndexError, _>(
                "list index out of range",
            ));
        }
        self.inner.insert(index, value.clone());
        if let Ok(mut engine) = self.engine.try_borrow_mut(py) {
            if !engine
                .owner
                .getattr(py, "_restoring")?
                .extract::<bool>(py)?
            {
                engine.log_list_insert(self.name.clone(), index, value);
            }
        }
        Ok(())
    }

    pub fn remove(&mut self, py: Python, value: PyObject) -> PyResult<()> {
        if let Some(index) = self.inner.iter().position(|x| {
            x.downcast::<PyAny>(py)
                .unwrap()
                .eq(&value)
                .expect("Failed to compare values")
        }) {
            self.inner.remove(index);
            if let Ok(mut engine) = self.engine.try_borrow_mut(py) {
                if !engine
                    .owner
                    .getattr(py, "_restoring")?
                    .extract::<bool>(py)?
                {
                    engine.log_list_pop(self.name.clone(), index, value);
                }
            }
            Ok(())
        } else {
            Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "value not found in list",
            ))
        }
    }

    pub fn clear(&mut self, py: Python) -> PyResult<()> {
        let old_values = self.inner.clone();
        self.inner.clear();
        if let Ok(mut engine) = self.engine.try_borrow_mut(py) {
            if !engine
                .owner
                .getattr(py, "_restoring")?
                .extract::<bool>(py)?
            {
                engine.log_list_clear(self.name.clone(), old_values);
            }
        }
        Ok(())
    }

    pub fn extend(&mut self, py: Python, values: Vec<PyObject>) -> PyResult<()> {
        self.inner.extend(values.clone());
        if let Ok(mut engine) = self.engine.try_borrow_mut(py) {
            if !engine
                .owner
                .getattr(py, "_restoring")?
                .extract::<bool>(py)?
            {
                engine.log_list_extend(self.name.clone(), values);
            }
        }
        Ok(())
    }

    pub fn __iter__(&self, py: Python) -> PyResult<PyObject> {
        let list = pyo3::types::PyList::new(py, &self.inner);
        Ok(list.call_method0("__iter__")?.to_object(py))
    }

    pub fn __contains__(&self, py: Python, value: PyObject) -> PyResult<bool> {
        for item in &self.inner {
            if item.as_ref(py).eq(&value)? {
                return Ok(true);
            }
        }
        Ok(false)
    }

    pub fn __repr__(&self, py: Python) -> PyResult<String> {
        let items: Vec<String> = self
            .inner
            .iter()
            .map(|v| v.as_ref(py).repr().map(|r| r.to_string()))
            .collect::<Result<Vec<_>, _>>()?;
        Ok(format!("[{}]", items.join(", ")))
    }

    pub fn __eq__(&self, py: Python, other: PyObject) -> PyResult<bool> {
        let other_list: Vec<PyObject> = other.extract(py)?;
        if self.inner.len() != other_list.len() {
            return Ok(false);
        }
        for (a, b) in self.inner.iter().zip(other_list.iter()) {
            if !a.as_ref(py).eq(b)? {
                return Ok(false);
            }
        }
        Ok(true)
    }

    pub fn __delitem__(&mut self, py: Python, index: usize) -> PyResult<()> {
        if index >= self.inner.len() {
            return Err(PyErr::new::<pyo3::exceptions::PyIndexError, _>(
                "list index out of range",
            ));
        }
        let old_value = self.inner.remove(index);
        if let Ok(mut engine) = self.engine.try_borrow_mut(py) {
            if !engine
                .owner
                .getattr(py, "_restoring")?
                .extract::<bool>(py)?
            {
                engine.log_list_pop(self.name.clone(), index, old_value);
            }
        }
        Ok(())
    }
}

#[pyclass]
pub struct TrackedDict {
    inner: HashMap<String, PyObject>,
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
            if !engine
                .owner
                .getattr(py, "_restoring")?
                .extract::<bool>(py)?
            {
                engine.log_dict_update(self.name.clone(), vec![key], vec![old_value], vec![value]);
            }
        }
        Ok(())
    }

    pub fn __delitem__(&mut self, py: Python, key: String) -> PyResult<()> {
        if let Some(old_value) = self.inner.remove(&key) {
            if let Ok(mut engine) = self.engine.try_borrow_mut(py) {
                if !engine
                    .owner
                    .getattr(py, "_restoring")?
                    .extract::<bool>(py)?
                {
                    engine.log_dict_delete(self.name.clone(), key, old_value);
                }
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
        let list = pyo3::types::PyList::new(py, keys);
        Ok(list.call_method0("__iter__")?.to_object(py))
    }

    pub fn keys(&self, py: Python) -> PyResult<PyObject> {
        let keys: Vec<String> = self.inner.keys().cloned().collect();
        Ok(pyo3::types::PyList::new(py, keys).to_object(py))
    }

    pub fn values(&self, py: Python) -> PyResult<PyObject> {
        let values: Vec<PyObject> = self.inner.values().cloned().collect();
        Ok(pyo3::types::PyList::new(py, values).to_object(py))
    }

    pub fn items(&self, py: Python) -> PyResult<PyObject> {
        let mut items = Vec::new();
        for (k, v) in &self.inner {
            items.push((k.clone(), v.clone()));
        }
        Ok(pyo3::types::PyList::new(py, items).to_object(py))
    }

    pub fn __len__(&self) -> usize {
        self.inner.len()
    }

    pub fn __eq__(&self, py: Python, other: PyObject) -> PyResult<bool> {
        let other_dict: HashMap<String, PyObject> = match other.extract(py) {
            Ok(d) => d,
            Err(_) => return Ok(false),
        };
        if self.inner.len() != other_dict.len() {
            return Ok(false);
        }
        for (a_k, a_v) in &self.inner {
            if let Some(b_v) = other_dict.get(a_k) {
                if !a_v.as_ref(py).eq(b_v)? {
                    return Ok(false);
                }
            } else {
                return Ok(false);
            }
        }
        Ok(true)
    }

    pub fn __ne__(&self, py: Python, other: PyObject) -> PyResult<bool> {
        Ok(!self.__eq__(py, other)?)
    }

    pub fn __repr__(&self, py: Python) -> PyResult<String> {
        let mut items = Vec::new();
        for (k, v) in &self.inner {
            let v_repr = v.as_ref(py).repr()?.to_string();
            items.push(format!("'{}': {}", k, v_repr));
        }
        Ok(format!("{{{}}}", items.join(", ")))
    }

    pub fn get(&self, py: Python, key: String, default: Option<PyObject>) -> PyObject {
        self.inner
            .get(&key)
            .cloned()
            .unwrap_or_else(|| default.unwrap_or_else(|| py.None()))
    }

    pub fn update(&mut self, py: Python, other: HashMap<String, PyObject>) -> PyResult<()> {
        let mut keys = Vec::new();
        let mut old_values = Vec::new();
        let mut new_values = Vec::new();
        for (key, value) in other {
            let old_value = self.inner.get(&key).cloned().unwrap_or_else(|| py.None());
            self.inner.insert(key.clone(), value.clone());
            keys.push(key);
            old_values.push(old_value);
            new_values.push(value);
        }
        if let Ok(mut engine) = self.engine.try_borrow_mut(py) {
            if !engine
                .owner
                .getattr(py, "_restoring")?
                .extract::<bool>(py)?
            {
                engine.log_dict_update(self.name.clone(), keys, old_values, new_values);
            }
        }
        Ok(())
    }

    pub fn pop(&mut self, py: Python, key: String) -> PyResult<PyObject> {
        if let Some(old_value) = self.inner.remove(&key) {
            if let Ok(mut engine) = self.engine.try_borrow_mut(py) {
                if !engine
                    .owner
                    .getattr(py, "_restoring")?
                    .extract::<bool>(py)?
                {
                    engine.log_dict_pop(self.name.clone(), key, old_value.clone());
                }
            }
            Ok(old_value)
        } else {
            Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>(key))
        }
    }

    pub fn popitem(&mut self, py: Python) -> PyResult<(String, PyObject)> {
        let key = self.inner.keys().next().cloned().ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyKeyError, _>("popitem(): dictionary is empty")
        })?;

        let old_value = self.inner.remove(&key).unwrap();
        if let Ok(mut engine) = self.engine.try_borrow_mut(py) {
            if !engine
                .owner
                .getattr(py, "_restoring")?
                .extract::<bool>(py)?
            {
                engine.log_dict_popitem(self.name.clone(), key.clone(), old_value.clone());
            }
        }
        Ok((key, old_value))
    }

    pub fn setdefault(&mut self, py: Python, key: String, default: PyObject) -> PyResult<PyObject> {
        if let Some(old_value) = self.inner.get(&key) {
            Ok(old_value.clone())
        } else {
            self.inner.insert(key.clone(), default.clone());
            if let Ok(mut engine) = self.engine.try_borrow_mut(py) {
                if !engine
                    .owner
                    .getattr(py, "_restoring")?
                    .extract::<bool>(py)?
                {
                    engine.log_dict_setdefault(self.name.clone(), key, default.clone());
                }
            }
            Ok(default)
        }
    }

    pub fn clear(&mut self, py: Python) -> PyResult<()> {
        let mut keys = Vec::new();
        let mut old_values = Vec::new();
        for (k, v) in self.inner.drain() {
            keys.push(k);
            old_values.push(v);
        }
        if let Ok(mut engine) = self.engine.try_borrow_mut(py) {
            if !engine
                .owner
                .getattr(py, "_restoring")?
                .extract::<bool>(py)?
            {
                engine.log_dict_clear(self.name.clone(), keys, old_values);
            }
        }
        Ok(())
    }
}
