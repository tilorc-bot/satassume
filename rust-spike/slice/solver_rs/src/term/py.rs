//! The Python face of the term module. Python holds ints; nothing here keeps state across queries.
use super::offline;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

#[pyclass(name = "OfflineData", frozen)]
pub struct PyOfflineData(offline::OfflineData);

#[pymethods]
impl PyOfflineData {
    /// Raises ValueError, naming the reason, for a file it refuses.
    #[new]
    fn new(path: &str, sources_root: &str, sympy: &str) -> PyResult<Self> {
        offline::OfflineData::load(path, sources_root, sympy)
            .map(PyOfflineData)
            .map_err(|e| PyValueError::new_err(format!("offline data refused: {e}")))
    }

    fn roundtrip(&self) -> String {
        self.0.roundtrip()
    }

    fn basis(&self) -> Option<Vec<String>> {
        self.0.basis().map(|b| b.into_iter().map(str::to_string).collect())
    }
}

#[pyfunction]
fn sha256_hex(data: &[u8]) -> String {
    offline::sha256(data)
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyOfflineData>()?;
    m.add_function(wrap_pyfunction!(sha256_hex, m)?)?;
    Ok(())
}
