#![allow(non_local_definitions)]
use pyo3::prelude::*;

mod containers;
mod engine;

#[pymodule]
fn tachyon_rs(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<engine::TachyonEngine>()?;
    m.add_class::<containers::TrackedList>()?;
    m.add_class::<containers::TrackedDict>()?;
    Ok(())
}
