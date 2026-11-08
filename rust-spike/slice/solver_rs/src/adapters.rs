//! Adapters step, part B (issue 323): `LRAAdapter` (lra_adapter.py:454) and `EUFAdapter` (euf_adapter.py:98) as Rust classes.
//!
//! `rel_default_specs`' two specs are built here, with no `factory()` call into Python (`relations_core::make_adapter`). A spec
//! whose factory is anything else is the user's: it stays a Python call, counted `ad:cb_factory`.
//!
//! The state is what Python's classes keep, in the same Python containers, so whatever reads it later reads the same thing:
//! `theory`, `_solver`, and the dicts `_shared` (LRA), `_terms` and `_node_terms` (EUF), in first-seen order. The term reading
//! the adapters do stays where it already is: the module functions, which the live wrappers (lra_live.py, term_live.py) route to
//! Rust on ids. Each is called through the module attribute at call time, as Python's methods do through their globals, and
//! counted: `_memoized` with `interpret`/`order_sides`/`integer_form` (`ad:cb_memoized`), `constant_bounds`
//! (`ad:cb_constant_bounds`), `EUFAdapter.parse` (`ad:cb_parse`), `structural` (`ad:cb_structural`) and `EUFAdapter.interned`
//! (`ad:cb_interned`). The theory constructor, when no theory is passed, is the module's `LRATheory`/`EUFTheory` at call time,
//! which the Rust backend swaps for its own (lra_backend.py:261, backend.py:88), counted `ad:cb_theory_new`.

use pyo3::exceptions::PyValueError;
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyString, PyTuple};

use crate::relations_core::{planted, AD_EUF_NODE, AD_EUF_SHARED, AD_LRA_SHARED};
use crate::session::{self, tick};

fn module<'py>(p: Python<'py>, sub: &str) -> PyResult<Bound<'py, PyModule>> {
    // Python's classes reach their module's globals; the package is the one `relations` lives in, as `rel_default_specs` reads it.
    let package: String = match crate::relations_core::relations_package(p) {
        Some(s) => s,
        None => "satassume".to_string(),
    };
    p.import(format!("{package}.{sub}").as_str())
}

fn fraction<'py>(p: Python<'py>, n: i64) -> PyResult<Bound<'py, PyAny>> {
    p.import(intern!(p, "fractions"))?.getattr(intern!(p, "Fraction"))?.call1((n,))
}

/// `_attach` / `attach`: one solver per adapter; the theory is attached the first time unless it already is.
fn attach_to(p: Python<'_>, cur: &mut Option<Py<PyAny>>, theory: &Py<PyAny>, solver: &Bound<'_, PyAny>, what: &str) -> PyResult<()> {
    if let Some(s) = cur {
        if s.bind(p).is(solver) {
            return Ok(());
        }
        return Err(PyValueError::new_err(format!("an {what} serves a single solver")));
    }
    let mut found = false;
    for t in solver.call_method0(intern!(p, "theories"))?.try_iter()? {
        if t?.is(theory.bind(p)) {
            found = true;
            break;
        }
    }
    if !found {
        solver.call_method1(intern!(p, "attach_theory"), (theory.bind(p),))?;
    }
    *cur = Some(solver.clone().unbind());
    Ok(())
}

#[pyclass(name = "LRAAdapter", module = "sa_solver", unsendable, weakref)]
pub(crate) struct LraAdapter {
    #[pyo3(get)]
    theory: Py<PyAny>,
    #[pyo3(get)]
    _solver: Option<Py<PyAny>>,
    /// used as a set in first-seen order, as Python's
    #[pyo3(get)]
    _shared: Py<PyDict>,
    module: Py<PyModule>,
    /// Part C: the theory reads Rust payloads (lra_backend.py's `LRATheory`, class attribute `_rust_payloads`). Python's
    /// `LRATheory` gets Python's `Negated`, counted `ad:cb_py_payload`. `theory` can't be reassigned, so it's read once here.
    rust_payloads: bool,
}

impl LraAdapter {
    pub(crate) fn build(p: Python<'_>, theory: Option<Bound<'_, PyAny>>) -> PyResult<LraAdapter> {
        tick(session::AD_LRA_NEW);
        let module = module(p, "theories.lra.lra_adapter")?;
        let theory = match theory {
            Some(t) if !t.is_none() => t,
            _ => {
                tick(session::AD_CB_THEORY_NEW);
                module.getattr(intern!(p, "LRATheory"))?.call0()?
            }
        };
        let rust_payloads = match theory.getattr(intern!(p, "_rust_payloads")) {
            Ok(v) => v.is_truthy()?,
            Err(_) => false,
        };
        Ok(LraAdapter { theory: theory.unbind(), _solver: None, _shared: PyDict::new(p).unbind(), module: module.unbind(), rust_payloads })
    }

    fn memoized<'py>(&self, p: Python<'py>, key: Bound<'py, PyAny>, read: &Bound<'py, PyString>, arg: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        tick(session::AD_CB_MEMOIZED);
        let m = self.module.bind(p);
        m.getattr(intern!(p, "_memoized"))?.call1((key, m.getattr(read)?, arg))
    }
}


#[pymethods]
impl LraAdapter {
    #[new]
    #[pyo3(signature = (theory=None))]
    fn new(p: Python<'_>, theory: Option<Bound<'_, PyAny>>) -> PyResult<LraAdapter> {
        LraAdapter::build(p, theory)
    }

    fn register(&mut self, p: Python<'_>, solver: &Bound<'_, PyAny>, var: &Bound<'_, PyAny>, atom: &Bound<'_, PyAny>) -> PyResult<bool> {
        tick(session::AD_LRA_REGISTER);
        let it = self.interpret(p, atom)?;
        if it.is_none() {
            return Ok(false);
        }
        let r = it.get_item(0)?;
        let atom_terms = it.get_item(1)?;
        let payload = if r.is_instance_of::<pyo3::types::PyBool>() {
            let f = fraction(p, if r.is_truthy()? { 0 } else { -1 })?;
            PyTuple::new(p, [PyTuple::empty(p).into_any(), f, false.into_pyobject(p)?.to_owned().into_any(), false.into_pyobject(p)?.to_owned().into_any()])?.into_any()
        } else {
            let payload = r.get_item(0)?;
            if !r.get_item(1)?.is_truthy()? {
                if self.rust_payloads {
                    Bound::new(p, crate::payloads::Negated::new(p, &payload)?)?.into_any()
                } else {
                    tick(session::AD_CB_PY_PAYLOAD);
                    self.module.bind(p).getattr(intern!(p, "Negated"))?.call1((payload,))?
                }
            } else {
                payload
            }
        };
        attach_to(p, &mut self._solver, &self.theory, solver, "LRAAdapter")?;
        solver.call_method1(intern!(p, "register_atom"), (self.theory.bind(p), var, payload))?;
        if !planted(AD_LRA_SHARED) {
            let sh = self._shared.bind(p);
            for t in atom_terms.try_iter()? {
                let t = t?;
                if !sh.contains(&t)? {
                    sh.set_item(t, p.None())?;
                }
            }
        }
        Ok(true)
    }

    fn _attach(&mut self, p: Python<'_>, solver: &Bound<'_, PyAny>) -> PyResult<()> {
        attach_to(p, &mut self._solver, &self.theory, solver, "LRAAdapter")
    }

    fn interpret<'py>(&self, p: Python<'py>, atom: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        self.memoized(p, atom.clone(), intern!(p, "interpret"), atom)
    }

    fn order_sides<'py>(&self, p: Python<'py>, atom: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let key = PyTuple::new(p, [intern!(p, "sides").clone().into_any(), atom.clone()])?.into_any();
        self.memoized(p, key, intern!(p, "order_sides"), atom)
    }

    fn integer_form<'py>(&self, p: Python<'py>, e: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let key = PyTuple::new(p, [intern!(p, "integer").clone().into_any(), e.clone()])?.into_any();
        self.memoized(p, key, intern!(p, "integer_form"), e)
    }

    fn register_integer(&mut self, p: Python<'_>, solver: &Bound<'_, PyAny>, var: &Bound<'_, PyAny>, form: &Bound<'_, PyAny>) -> PyResult<()> {
        attach_to(p, &mut self._solver, &self.theory, solver, "LRAAdapter")?;
        let mut payload = form.get_item(0)?;
        if !self.rust_payloads {
            // Part C: integer_form's Rust route builds a Rust `Integral` (lra_live.py); Python's LRATheory reads only its own.
            if let Ok(i) = payload.cast::<crate::payloads::Integral>() {
                tick(session::AD_CB_PY_PAYLOAD);
                let (t, o) = i.get().pair(p)?;
                payload = module(p, "theories.lra.lra")?.getattr(intern!(p, "Integral"))?.call1((t, o))?;
            }
        }
        solver.call_method1(intern!(p, "register_atom"), (self.theory.bind(p), var, payload))?;
        Ok(())
    }

    fn terms<'py>(&self, p: Python<'py>, atom: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let r = self.interpret(p, atom)?;
        if r.is_none() { Ok(r) } else { r.get_item(1) }
    }

    fn to_constraint<'py>(&self, p: Python<'py>, atom: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let r = self.interpret(p, atom)?;
        if r.is_none() { Ok(r) } else { r.get_item(0) }
    }

    fn register_bounds<'py>(&self, p: Python<'py>, solver: &Bound<'py, PyAny>, term: &Bound<'py, PyAny>, new_var: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyList>> {
        let out = PyList::empty(p);
        if term.getattr(intern!(p, "free_symbols"))?.is_truthy()? {
            return Ok(out);
        }
        tick(session::AD_CB_CONSTANT_BOUNDS);
        let b = self.module.bind(p).getattr(intern!(p, "constant_bounds"))?.call1((term,))?;
        if b.is_none() {
            return Ok(out);
        }
        let lo = b.get_item(0)?;
        let hi = b.get_item(1)?;
        let t = true.into_pyobject(p)?.to_owned().into_any();
        let f = false.into_pyobject(p)?.to_owned().into_any();
        let pair = |c: i64| -> PyResult<Bound<'py, PyAny>> {
            let item = PyTuple::new(p, [term.clone(), fraction(p, c)?])?;
            Ok(PyTuple::new(p, [item])?.into_any())
        };
        // -c < -lo, then c < hi
        for (items, rhs) in [(pair(-1)?, lo.neg()?), (pair(1)?, hi)] {
            let payload = PyTuple::new(p, [items, rhs, t.clone(), f.clone()])?;
            let v = new_var.call0()?;
            solver.call_method1(intern!(p, "register_atom"), (self.theory.bind(p), &v, payload))?;
            out.append(v)?;
        }
        Ok(out)
    }

    fn shared_terms<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        PyList::new(p, self._shared.bind(p).keys())
    }
}

#[pyclass(name = "EUFAdapter", module = "sa_solver", unsendable, weakref)]
pub(crate) struct EufAdapter {
    #[pyo3(get)]
    theory: Py<PyAny>,
    #[pyo3(get)]
    _terms: Py<PyDict>,
    /// terms interned for the transfer layer only (`node_term`); kept out of `shared_terms`
    #[pyo3(get)]
    _node_terms: Py<PyDict>,
    #[pyo3(get)]
    _solver: Option<Py<PyAny>>,
    module: Py<PyModule>,
    rational: Py<PyAny>,
    /// Part C: the theory is euf_py.rs' `EUFTheory` (or a subclass), which reads a Rust `EqAtom`; any other gets Python's,
    /// counted `ad:cb_py_payload`.
    rust_payloads: bool,
}

impl EufAdapter {
    pub(crate) fn build(p: Python<'_>, theory: Option<Bound<'_, PyAny>>) -> PyResult<EufAdapter> {
        tick(session::AD_EUF_NEW);
        let module = module(p, "theories.euf.euf_adapter")?;
        let theory = match theory {
            Some(t) if !t.is_none() => t,
            _ => {
                tick(session::AD_CB_THEORY_NEW);
                module.getattr(intern!(p, "EUFTheory"))?.call0()?
            }
        };
        let rational = p.import(intern!(p, "sympy"))?.getattr(intern!(p, "Rational"))?.unbind();
        let rust_payloads = theory.is_instance_of::<crate::euf_py::PyEuf>();
        Ok(EufAdapter {
            rust_payloads,
            theory: theory.unbind(),
            _terms: PyDict::new(p).unbind(),
            _node_terms: PyDict::new(p).unbind(),
            _solver: None,
            module: module.unbind(),
            rational,
        })
    }

    /// Python's class, for its `parse` and `interned` (which term_live.py wraps on the class).
    fn py_class<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        // `_PyEUFAdapter` is set where the module's name is swapped for this class (ad_swap.py), so the call isn't to itself.
        let m = self.module.bind(p);
        match m.getattr_opt(intern!(p, "_PyEUFAdapter"))? {
            Some(c) => Ok(c),
            None => m.getattr(intern!(p, "EUFAdapter")),
        }
    }

    fn structural(&self, p: Python<'_>, e: &Bound<'_, PyAny>) -> PyResult<bool> {
        tick(session::AD_CB_STRUCTURAL);
        self.module.bind(p).getattr(intern!(p, "structural"))?.call1((e,))?.is_truthy()
    }

    /// `_intern`: `expr` and its subterms that are in neither `out` nor `known` go into `out`, post-order; returns `expr`'s term.
    fn intern_into<'py>(&self, p: Python<'py>, expr: &Bound<'py, PyAny>, out: &Bound<'py, PyDict>, known: Option<&Bound<'py, PyDict>>) -> PyResult<Bound<'py, PyAny>> {
        let th = self.theory.bind(p);
        let rational = self.rational.bind(p);
        let has = |e: &Bound<'py, PyAny>| -> PyResult<bool> { Ok(out.contains(e)? || known.map_or(Ok(false), |k| k.contains(e))?) };
        let mut stack: Vec<(Bound<'py, PyAny>, bool)> = vec![(expr.clone(), false)];
        while let Some((e, ready)) = stack.pop() {
            if has(&e)? {
                continue;
            }
            if e.is_instance(rational)? {
                out.set_item(&e, th.call_method1(intern!(p, "value"), (&e,))?)?;
            } else if self.structural(p, &e)? {
                if ready {
                    let args = PyList::empty(p);
                    for a in e.getattr(intern!(p, "args"))?.try_iter()? {
                        let a = a?;
                        let t = match known.map(|k| k.get_item(&a)).transpose()?.flatten() {
                            Some(t) => t,
                            None => out.get_item(&a)?.ok_or_else(|| pyo3::exceptions::PyKeyError::new_err(a.clone().unbind()))?,
                        };
                        args.append(t)?;
                    }
                    out.set_item(&e, th.call_method1(intern!(p, "term"), (e.getattr(intern!(p, "func"))?, args))?)?;
                } else {
                    stack.push((e.clone(), true));
                    for a in e.getattr(intern!(p, "args"))?.try_iter()? {
                        let a = a?;
                        if !has(&a)? {
                            stack.push((a, false));
                        }
                    }
                }
            } else {
                out.set_item(&e, th.call_method1(intern!(p, "term"), (&e,))?)?;
            }
        }
        out.get_item(expr)?.ok_or_else(|| pyo3::exceptions::PyKeyError::new_err(expr.clone().unbind()))
    }
}

#[pymethods]
impl EufAdapter {
    #[new]
    #[pyo3(signature = (theory=None))]
    fn new(p: Python<'_>, theory: Option<Bound<'_, PyAny>>) -> PyResult<EufAdapter> {
        EufAdapter::build(p, theory)
    }

    fn parse<'py>(&self, p: Python<'py>, atom: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        tick(session::AD_CB_PARSE);
        self.py_class(p)?.getattr(intern!(p, "parse"))?.call1((atom,))
    }

    fn interprets(&self, p: Python<'_>, atom: &Bound<'_, PyAny>) -> PyResult<bool> {
        Ok(!self.parse(p, atom)?.is_none())
    }

    fn register(&mut self, p: Python<'_>, solver: &Bound<'_, PyAny>, var: &Bound<'_, PyAny>, atom: &Bound<'_, PyAny>) -> PyResult<bool> {
        tick(session::AD_EUF_REGISTER);
        let parsed = self.parse(p, atom)?;
        if parsed.is_none() {
            return Ok(false);
        }
        attach_to(p, &mut self._solver, &self.theory, solver, "EUFAdapter")?;
        let l = self.term(p, &parsed.get_item(0)?)?;
        let r = self.term(p, &parsed.get_item(1)?)?;
        let payload = if self.rust_payloads {
            Bound::new(p, crate::payloads::EqAtom::new(p, &l, &r, Some(&parsed.get_item(2)?))?)?.into_any()
        } else {
            tick(session::AD_CB_PY_PAYLOAD);
            self.module.bind(p).getattr(intern!(p, "EqAtom"))?.call1((l, r, parsed.get_item(2)?))?
        };
        solver.call_method1(intern!(p, "register_atom"), (self.theory.bind(p), var, payload))?;
        Ok(true)
    }

    fn attach(&mut self, p: Python<'_>, solver: &Bound<'_, PyAny>) -> PyResult<()> {
        attach_to(p, &mut self._solver, &self.theory, solver, "EUFAdapter")
    }

    fn term<'py>(&self, p: Python<'py>, expr: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let terms = self._terms.bind(p);
        if let Some(t) = terms.get_item(expr)? {
            if !t.is_none() {
                return Ok(t);
            }
        }
        self.intern_into(p, expr, terms, None)
    }

    fn node_term<'py>(&self, p: Python<'py>, expr: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let terms = self._terms.bind(p);
        if let Some(t) = terms.get_item(expr)? {
            if !t.is_none() {
                return Ok(t);
            }
        }
        let nodes = self._node_terms.bind(p);
        if planted(AD_EUF_NODE) {
            return self.intern_into(p, expr, terms, None);
        }
        if let Some(t) = nodes.get_item(expr)? {
            if !t.is_none() {
                return Ok(t);
            }
        }
        self.intern_into(p, expr, nodes, Some(terms))
    }

    fn interned<'py>(slf: &Bound<'py, Self>, exprs: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let p = slf.py();
        tick(session::AD_CB_INTERNED);
        slf.borrow().py_class(p)?.getattr(intern!(p, "interned"))?.call1((slf, exprs))
    }

    fn term_of<'py>(&self, p: Python<'py>, expr: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyAny>>> {
        self._terms.bind(p).get_item(expr)
    }

    fn terms_since<'py>(&self, p: Python<'py>, start: usize) -> PyResult<Bound<'py, PyList>> {
        let terms = self._terms.bind(p);
        if start >= terms.len() {
            return Ok(PyList::empty(p));
        }
        PyList::new(p, terms.keys().iter().skip(start))
    }

    fn shared_terms<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        let keys = self._terms.bind(p).keys();
        if keys.len() > 1 && planted(AD_EUF_SHARED) {
            return PyList::new(p, keys.iter().take(keys.len() - 1));
        }
        PyList::new(p, keys)
    }
}

pub(crate) fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<LraAdapter>()?;
    m.add_class::<EufAdapter>()?;
    Ok(())
}
