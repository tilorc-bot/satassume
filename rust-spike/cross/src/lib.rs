//! Crossing costs between Python and Rust (issue 323, throwaway). Every b_* and c_* loop runs inside Rust and
//! returns its own elapsed seconds, with the arguments already in Rust's hands before the clock starts.
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use std::hint::black_box;
use std::time::Instant;

// ------------------------------------------------------------------ (a) Python into Rust, once per query
#[pyfunction]
fn a_noop() {}

#[pyfunction]
fn a_int(x: i64) -> i64 {
    x
}

/// The shape of one query: encoded bytes in by reference (no copy), three-valued answer out.
#[pyfunction]
fn a_bytes(b: &[u8]) -> Option<bool> {
    let s: u64 = b.iter().map(|&c| c as u64).sum();
    if s % 3 == 0 {
        None
    } else {
        Some(s % 3 == 1)
    }
}

#[pyclass]
struct Eng {
    calls: u64,
}

#[pymethods]
impl Eng {
    #[new]
    fn new() -> Self {
        Eng { calls: 0 }
    }
    /// The same through a method on a session-like object, which adds the borrow check.
    fn ask(&mut self, b: &[u8]) -> Option<bool> {
        self.calls += 1;
        a_bytes(b)
    }
}

// ------------------------------------------------------------------ (b) Rust into Python
#[pyfunction]
fn b_empty(n: u64) -> f64 {
    let t = Instant::now();
    for i in 0..n {
        black_box(i);
    }
    t.elapsed().as_secs_f64()
}

#[pyfunction]
fn b_call0(f: &Bound<'_, PyAny>, n: u64) -> PyResult<f64> {
    let t = Instant::now();
    for _ in 0..n {
        black_box(f.call0()?);
    }
    Ok(t.elapsed().as_secs_f64())
}

/// One int out, one int back, both converted: the shape of a hook or an id-based ask.
#[pyfunction]
fn b_call1_int(f: &Bound<'_, PyAny>, n: u64) -> PyResult<f64> {
    let t = Instant::now();
    let mut s = 0i64;
    for i in 0..n {
        s = s.wrapping_add(f.call1((i as i64,))?.extract::<i64>()?);
    }
    black_box(s);
    Ok(t.elapsed().as_secs_f64())
}

/// One object out by handle, a three-valued answer back.
#[pyfunction]
fn b_call1_obj(f: &Bound<'_, PyAny>, o: &Bound<'_, PyAny>, n: u64) -> PyResult<f64> {
    let t = Instant::now();
    let mut s = 0i64;
    for _ in 0..n {
        let r = f.call1((o,))?;
        if !r.is_none() {
            s += r.is_truthy()? as i64;
        }
    }
    black_box(s);
    Ok(t.elapsed().as_secs_f64())
}

#[pyfunction]
fn b_method(o: &Bound<'_, PyAny>, n: u64) -> PyResult<f64> {
    let py = o.py();
    let name = intern!(py, "m");
    let t = Instant::now();
    let mut s = 0i64;
    for i in 0..n {
        s = s.wrapping_add(o.call_method1(name, (i as i64,))?.extract::<i64>()?);
    }
    black_box(s);
    Ok(t.elapsed().as_secs_f64())
}

/// Rust running with the interpreter lock released, taking it back for each callback.
#[pyfunction]
fn b_reattach(py: Python<'_>, f: Py<PyAny>, n: u64) -> PyResult<f64> {
    py.detach(|| {
        let t = Instant::now();
        let mut s = 0i64;
        for i in 0..n {
            let v = Python::attach(|py| f.bind(py).call1((i as i64,))?.extract::<i64>());
            s = s.wrapping_add(v?);
        }
        black_box(s);
        Ok(t.elapsed().as_secs_f64())
    })
}

/// The C call under PyO3, to see what PyO3 adds. Not available with abi3-py39.
#[cfg(not(feature = "abi3"))]
#[pyfunction]
fn b_raw(py: Python<'_>, f: &Bound<'_, PyAny>, n: u64) -> PyResult<f64> {
    use pyo3::ffi;
    let fp = f.as_ptr();
    let t = Instant::now();
    let mut s = 0i64;
    unsafe {
        for i in 0..n {
            let a = ffi::PyLong_FromLongLong(i as i64);
            // One slot in front of the argument, as PY_VECTORCALL_ARGUMENTS_OFFSET allows.
            let args = [std::ptr::null_mut(), a];
            let r = ffi::PyObject_Vectorcall(
                fp,
                args.as_ptr().add(1),
                1 | ffi::PY_VECTORCALL_ARGUMENTS_OFFSET,
                std::ptr::null_mut(),
            );
            ffi::Py_DECREF(a);
            if r.is_null() {
                return Err(PyErr::fetch(py));
            }
            s = s.wrapping_add(ffi::PyLong_AsLongLong(r));
            ffi::Py_DECREF(r);
        }
    }
    black_box(s);
    Ok(t.elapsed().as_secs_f64())
}

// ------------------------------------------------------------------ (c) real SymPy objects, called from Rust
fn handles<'py>(xs: &Bound<'py, PyList>) -> Vec<Bound<'py, PyAny>> {
    xs.iter().collect()
}

#[pyfunction]
fn c_walk(xs: &Bound<'_, PyList>) -> f64 {
    let v = handles(xs);
    let t = Instant::now();
    for o in &v {
        black_box(o.as_ptr());
    }
    t.elapsed().as_secs_f64()
}

#[pyfunction]
fn c_hash(xs: &Bound<'_, PyList>) -> PyResult<f64> {
    let v = handles(xs);
    let t = Instant::now();
    let mut s = 0isize;
    for o in &v {
        s = s.wrapping_add(o.hash()?);
    }
    black_box(s);
    Ok(t.elapsed().as_secs_f64())
}

#[pyfunction]
fn c_eq(xs: &Bound<'_, PyList>, ys: &Bound<'_, PyList>) -> PyResult<f64> {
    let (a, b) = (handles(xs), handles(ys));
    let t = Instant::now();
    let mut s = 0u64;
    for (x, y) in a.iter().zip(&b) {
        s += x.eq(y)? as u64;
    }
    black_box(s);
    Ok(t.elapsed().as_secs_f64())
}

/// The id of an object from a Python dict: hash + eq in C, and the int back.
#[pyfunction]
fn c_intern(d: &Bound<'_, PyDict>, xs: &Bound<'_, PyList>) -> PyResult<f64> {
    let v = handles(xs);
    let t = Instant::now();
    let mut s = 0i64;
    for o in &v {
        s = s.wrapping_add(d.get_item(o)?.unwrap().extract::<i64>()?);
    }
    black_box(s);
    Ok(t.elapsed().as_secs_f64())
}

/// A read: `o.args`, then a handle kept on each element, as a Rust structure would.
#[pyfunction]
fn c_args(xs: &Bound<'_, PyList>) -> PyResult<f64> {
    let py = xs.py();
    let v = handles(xs);
    let name = intern!(py, "args");
    let mut keep: Vec<Bound<'_, PyAny>> = Vec::with_capacity(64);
    let t = Instant::now();
    for o in &v {
        keep.clear();
        for e in o.getattr(name)?.try_iter()? {
            keep.push(e?);
        }
        black_box(keep.len());
    }
    Ok(t.elapsed().as_secs_f64())
}

/// A flag read: `o.is_number`, as a Rust bool.
#[pyfunction]
fn c_isnum(xs: &Bound<'_, PyList>) -> PyResult<f64> {
    let py = xs.py();
    let v = handles(xs);
    let name = intern!(py, "is_number");
    let t = Instant::now();
    let mut s = 0u64;
    for o in &v {
        s += o.getattr(name)?.is_truthy()? as u64;
    }
    black_box(s);
    Ok(t.elapsed().as_secs_f64())
}

#[pymodule]
fn xbench(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Eng>()?;
    m.add("ABI3", cfg!(feature = "abi3"))?;
    m.add_function(wrap_pyfunction!(a_noop, m)?)?;
    m.add_function(wrap_pyfunction!(a_int, m)?)?;
    m.add_function(wrap_pyfunction!(a_bytes, m)?)?;
    m.add_function(wrap_pyfunction!(b_empty, m)?)?;
    m.add_function(wrap_pyfunction!(b_call0, m)?)?;
    m.add_function(wrap_pyfunction!(b_call1_int, m)?)?;
    m.add_function(wrap_pyfunction!(b_call1_obj, m)?)?;
    m.add_function(wrap_pyfunction!(b_method, m)?)?;
    m.add_function(wrap_pyfunction!(b_reattach, m)?)?;
    #[cfg(not(feature = "abi3"))]
    m.add_function(wrap_pyfunction!(b_raw, m)?)?;
    m.add_function(wrap_pyfunction!(c_walk, m)?)?;
    m.add_function(wrap_pyfunction!(c_hash, m)?)?;
    m.add_function(wrap_pyfunction!(c_eq, m)?)?;
    m.add_function(wrap_pyfunction!(c_intern, m)?)?;
    m.add_function(wrap_pyfunction!(c_args, m)?)?;
    m.add_function(wrap_pyfunction!(c_isnum, m)?)?;
    Ok(())
}
