//! State part 3 (sub-part 3, issue 323): engine.py's `_gave_up` and `_exhausted`, read in Rust. Both ask whether any theory of
//! the session's solver has its flag set (`getattr(t, "gave_up", False)`, `getattr(t, "exhausted", False)`). context.rs
//! (`_build_context`'s fallback, `_complete_check`) and entry.rs (`_ask`'s `theory_gave_up`) called the Python helpers back by
//! name (`ctx:cb_helpers`, `ent:cb_gave_up`); the helpers stay in engine.py for the pure-Python engine and the tests that
//! import them.
//!
//! - **The solver is the session core's copy** (`TableView.bind`'s `set_solver`), not Python's `Session.solver` attribute.
//! - **A Rust LRA theory** (lra_backend's subclass, its `_core` an `LraCore` in the instance dict) is read from the core's
//!   fields: `th:gave_up`, `th:exhausted`. lra_backend's `gave_up`/`exhausted` properties return exactly those fields.
//! - **Any other theory** (the transfer theory, EUF, a user's) is read by `getattr(t, name, False)` as Python does,
//!   counted `th:py_flag`.
//! - **A session with no core** (`s.table.core` not a `SessionCore`) calls the Python helper, counted `th:py_helper`.
//!
//! Plants (SLICE_SESSION_PLANT, set by `th_plant`): 428 `th-gave-up-skip` (an LRA core's gave_up read as false), 429
//! `th-exhausted-skip` (its exhausted read as false), 430 `th-first-only` (only the first theory is read).
use std::sync::atomic::{AtomicU16, Ordering::Relaxed};

use pyo3::exceptions::PyValueError;
use pyo3::intern;
use pyo3::prelude::*;

use crate::lra_py::LraCore;
use crate::session::{core_of, tick, TH_EXHAUSTED, TH_GAVE_UP, TH_PY_FLAG, TH_PY_HELPER};

static PLANT: AtomicU16 = AtomicU16::new(0);
const TH_GAVE_UP_SKIP: u16 = 428;
const TH_EXHAUSTED_SKIP: u16 = 429;
const TH_FIRST_ONLY: u16 = 430;

fn planted(x: u16) -> bool {
    PLANT.load(Relaxed) == x
}

#[derive(Clone, Copy)]
pub(crate) enum Flag {
    GaveUp,
    Exhausted,
}

/// engine.py `_gave_up(s)` / `_exhausted(s)`.
pub(crate) fn theory_flag(s: &Bound<'_, PyAny>, which: Flag) -> PyResult<bool> {
    let p = s.py();
    let (name, helper) = match which {
        Flag::GaveUp => (intern!(p, "gave_up"), intern!(p, "_gave_up")),
        Flag::Exhausted => (intern!(p, "exhausted"), intern!(p, "_exhausted")),
    };
    let solver = match core_of(s) {
        Ok(c) => c.borrow().solver_direct(p)?,
        Err(_) => {
            tick(TH_PY_HELPER);
            let m = p.import(intern!(p, "satassume.engine"))?;
            return m.getattr(helper)?.call1((s,))?.is_truthy();
        }
    };
    for t in solver.call_method0(intern!(p, "theories"))?.try_iter()? {
        let t = t?;
        let core = t.getattr_opt(intern!(p, "_core"))?;
        let v = match core.as_ref().and_then(|c| c.cast::<LraCore>().ok()) {
            Some(c) => {
                let (g, e) = c.borrow().flags();
                match which {
                    Flag::GaveUp => {
                        tick(TH_GAVE_UP);
                        g && !planted(TH_GAVE_UP_SKIP)
                    }
                    Flag::Exhausted => {
                        tick(TH_EXHAUSTED);
                        e && !planted(TH_EXHAUSTED_SKIP)
                    }
                }
            }
            None => {
                tick(TH_PY_FLAG);
                match t.getattr_opt(name)? {
                    Some(v) => v.is_truthy()?,
                    None => false,
                }
            }
        };
        if v {
            return Ok(true);
        }
        if planted(TH_FIRST_ONLY) {
            break;
        }
    }
    Ok(false)
}

/// Sets (or, with None or an unknown name of another family, clears) this module's plant.
#[pyfunction]
#[pyo3(signature = (name=None))]
fn th_plant(name: Option<&str>) -> PyResult<()> {
    let v = match name {
        None => 0,
        Some("th-gave-up-skip") => TH_GAVE_UP_SKIP,
        Some("th-exhausted-skip") => TH_EXHAUSTED_SKIP,
        Some("th-first-only") => TH_FIRST_ONLY,
        Some(x) => return Err(PyValueError::new_err(format!("no plant {x}"))),
    };
    PLANT.store(v, Relaxed);
    Ok(())
}

/// The Python-callable form, for tests: `th_flag(s, "gave_up")`.
#[pyfunction]
fn th_flag(s: &Bound<'_, PyAny>, name: &str) -> PyResult<bool> {
    match name {
        "gave_up" => theory_flag(s, Flag::GaveUp),
        "exhausted" => theory_flag(s, Flag::Exhausted),
        _ => Err(PyValueError::new_err(format!("no flag {name}"))),
    }
}

pub(crate) fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(th_plant, m)?)?;
    m.add_function(wrap_pyfunction!(th_flag, m)?)?;
    Ok(())
}
