#![allow(non_local_definitions)]
use pyo3::prelude::*;

mod engine;
mod containers;

#[pymodule]
fn tachyon_rs(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<engine::TachyonEngine>()?;
    m.add_class::<engine::TrackedList>()?;
    m.add_class::<engine::TrackedDict>()?;
    Ok(())
}
