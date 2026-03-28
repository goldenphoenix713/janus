use pyo3::prelude::*;

mod containers;
mod engine;

#[pymodule]
fn tachyon_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<engine::TachyonEngine>()?;
    m.add_class::<containers::TrackedListCore>()?;
    m.add_class::<containers::TrackedDictCore>()?;
    Ok(())
}
