use pyo3::prelude::*;

mod containers;
pub mod engine;
pub mod graph;
pub mod models;
pub mod reconcile;
pub mod serde_py;

#[pymodule]
fn tachyon_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<engine::TachyonEngine>()?;
    m.add_class::<containers::TrackedListCore>()?;
    m.add_class::<containers::TrackedDictCore>()?;
    Ok(())
}
