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

use std::collections::HashMap;

use crate::relations_core::{
    planted, AD_EUF_NODE, AD_EUF_SHARED, AD_LRA_FLAG_KEY, AD_LRA_KIND_KEY, AD_LRA_NOT_EXPR, AD_LRA_PAIR_SWAP, AD_LRA_PATCH_GUARD,
    AD_LRA_SHARED, AD_LRA_SLOT_STALE,
};
use crate::term::py::PyTermTable;
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
    /// State step, part 1: the current query's slot (`LraQuery`), replaced when the query changes.
    slot: std::cell::RefCell<Option<LraQuery>>,
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
        Ok(LraAdapter { theory: theory.unbind(), _solver: None, _shared: PyDict::new(p).unbind(), module: module.unbind(), rust_payloads, slot: std::cell::RefCell::new(None) })
    }

    /// Python's `_memoized(key, read, arg)` through the module attribute, counted `ad:cb_memoized`: only where the slot can't answer.
    fn callback<'py>(&self, p: Python<'py>, key: Bound<'py, PyAny>, read: &Bound<'py, PyString>, arg: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        tick(session::AD_CB_MEMOIZED);
        let m = self.module.bind(p);
        m.getattr(intern!(p, "_memoized"))?.call1((key, m.getattr(read)?, arg))
    }

    /// `_memoized(key, read, arg)` with lra_live's `memoized` and `read` (state step, part 1). On a query with a table the slot
    /// answers: the query's table, ids and objects, the atoms' term ids and the results, all held here and dropped when the query
    /// changes. Everything else is Python's call, counted by reason.
    fn memoized<'py>(&self, p: Python<'py>, kind: usize, key: Bound<'py, PyAny>, read: &Bound<'py, PyString>, arg: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let live = LIVE.with(|l| l.borrow().as_ref().map(|x| x.clone_ref(p)));
        let Some(live) = live else {
            tick(session::AD_CBM_OFF);
            return self.callback(p, key, read, arg);
        };
        if live.check {
            tick(session::AD_CBM_CHECK);
            return self.callback(p, key, read, arg);
        }
        let m = self.module.bind(p);
        if !planted(AD_LRA_PATCH_GUARD)
            && (!m.getattr(intern!(p, "_memoized"))?.is(live.memoized.bind(p)) || !m.getattr(read)?.is(live.reads[kind].bind(p)))
        {
            tick(session::AD_CBM_PATCHED);
            return self.callback(p, key, read, arg);
        }
        let Some(q) = top_query(live.local.bind(p))? else {
            tick(session::AD_CBM_NOQUERY);
            return self.callback(p, key, read, arg);
        };
        let flag = m.getattr(intern!(p, "GENERIC_CONSTANTS"))?.is_truthy()?;
        let fresh = match &*self.slot.borrow() {
            Some(s) => !s.query.bind(p).is(&q) && !planted(AD_LRA_SLOT_STALE),
            None => true,
        };
        if fresh {
            let s = LraQuery::new(&q)?;
            *self.slot.borrow_mut() = Some(s);
        }
        let mk = (if planted(AD_LRA_KIND_KEY) { 0 } else { kind as u8 }, arg.as_ptr() as usize, flag && !planted(AD_LRA_FLAG_KEY));
        if let Some((_, r)) = self.slot.borrow().as_ref().unwrap().memo.get(&mk) {
            tick(session::AD_LRA_NATIVE);
            tick(session::AD_LRA_HIT);
            return Ok(r.bind(p).clone());
        }
        // No borrow is held across Python: relation, term_id and scaffold run Python.
        let (query, table, ids, objects, n_input) = {
            let b = self.slot.borrow();
            let s = b.as_ref().unwrap();
            (s.query.clone_ref(p), s.table.clone_ref(p), s.ids.clone_ref(p), s.objects.clone_ref(p), s.n_input)
        };
        let r = Reader { p, live: &live, q: query.bind(p).clone(), table: table.bind(p).clone(), ids: ids.bind(p).clone(), objects: objects.bind(p).clone(), n_input, flag };
        let got = match kind {
            K_INTERPRET => r.interpret(arg)?,
            K_SIDES => r.order_sides(arg)?,
            _ => r.integer_form(arg)?,
        };
        let Some(out) = got else {
            tick(session::AD_CBM_NOID);
            return self.callback(p, key, read, arg);
        };
        tick(session::AD_LRA_NATIVE);
        if let Some(s) = self.slot.borrow_mut().as_mut() {
            if s.query.bind(p).is(&query) {
                s.memo.insert(mk, (arg.clone().unbind(), out.clone().unbind()));
                EXPORT.with(|x| {
                    if let Some(v) = x.borrow_mut().as_mut() {
                        v.push((query.clone_ref(p), mk.0, arg.clone().unbind(), mk.2, out.clone().unbind()));
                    }
                });
            }
        }
        Ok(out)
    }

}

const K_INTERPRET: usize = 0;
const K_SIDES: usize = 1;
const K_INTEGER: usize = 2;

/// lra_live's functions and term_live's, set by `lra_live.install` and cleared by its undo (`ad_lra_live`).
struct LraLive {
    memoized: Py<PyAny>,
    /// `interpret`, `order_sides`, `integer_form` as lra_live installs them, by kind.
    reads: [Py<PyAny>; 3],
    /// `term_live._local`: its `stack`'s last `_Query`. Read, never called.
    local: Py<PyAny>,
    relation: Py<PyAny>,
    term_id: Py<PyAny>,
    scaffold: Py<PyAny>,
    /// `lra_live._fault(site, exc)`: counts and returns the TermFault lra_live's `_rust` raises.
    fault: Py<PyAny>,
    check: bool,
}

impl LraLive {
    fn clone_ref(&self, p: Python<'_>) -> LraLive {
        LraLive {
            memoized: self.memoized.clone_ref(p),
            reads: [self.reads[0].clone_ref(p), self.reads[1].clone_ref(p), self.reads[2].clone_ref(p)],
            local: self.local.clone_ref(p),
            relation: self.relation.clone_ref(p),
            term_id: self.term_id.clone_ref(p),
            scaffold: self.scaffold.clone_ref(p),
            fault: self.fault.clone_ref(p),
            check: self.check,
        }
    }
}

static EXPR: pyo3::sync::PyOnceLock<Py<PyAny>> = pyo3::sync::PyOnceLock::new();

type Exported = Vec<(Py<PyAny>, u8, Py<PyAny>, bool, Py<PyAny>)>;

thread_local! {
    static LIVE: std::cell::RefCell<Option<LraLive>> = const { std::cell::RefCell::new(None) };
    /// Test-only snapshot export: while on, every slot entry as it's stored, `(query, kind, arg, flag, result)`.
    static EXPORT: std::cell::RefCell<Option<Exported>> = const { std::cell::RefCell::new(None) };
}

/// Test-only snapshot export of the adapters' slots (test_lra_slot.py): `ad_lra_export(True)` starts recording every slot
/// entry as it's stored; `ad_lra_export(False)` stops and returns them, `[(query, kind, arg, flag, result)]` in order.
/// Kinds: 0 interpret, 1 order_sides, 2 integer_form. Adapters die with their sessions, so the slots can't be read later.
#[pyfunction]
fn ad_lra_export<'py>(p: Python<'py>, on: bool) -> PyResult<Bound<'py, PyList>> {
    let got = EXPORT.with(|x| std::mem::replace(&mut *x.borrow_mut(), if on { Some(Vec::new()) } else { None }));
    let out = PyList::empty(p);
    for (q, k, a, f, r) in got.unwrap_or_default() {
        out.append((q, k, a, f, r))?;
    }
    Ok(out)
}

/// `lra_live.install`'s registration: `(memoized, interpret, order_sides, integer_form, local, relation, term_id, scaffold, fault,
/// check)`, or None to clear.
#[pyfunction]
#[pyo3(signature = (cfg=None))]
fn ad_lra_live(cfg: Option<Bound<'_, PyTuple>>) -> PyResult<()> {
    let v = match cfg {
        None => None,
        Some(t) => {
            let g = |i: usize| -> PyResult<Py<PyAny>> { Ok(t.get_item(i)?.unbind()) };
            Some(LraLive {
                memoized: g(0)?,
                reads: [g(1)?, g(2)?, g(3)?],
                local: g(4)?,
                relation: g(5)?,
                term_id: g(6)?,
                scaffold: g(7)?,
                fault: g(8)?,
                check: t.get_item(9)?.is_truthy()?,
            })
        }
    };
    LIVE.with(|l| *l.borrow_mut() = v);
    Ok(())
}

/// term_live's `current()` when it has a table: the stack's last `_Query` with `kept` None.
fn top_query<'py>(local: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyAny>>> {
    let p = local.py();
    let s = match local.getattr(intern!(p, "stack")) {
        Ok(s) => s,
        Err(e) if e.is_instance_of::<pyo3::exceptions::PyAttributeError>(p) => return Ok(None),
        Err(e) => return Err(e),
    };
    let n = s.len()?;
    if n == 0 {
        return Ok(None);
    }
    let q = s.get_item(n - 1)?;
    Ok(if q.getattr(intern!(p, "kept"))?.is_none() { Some(q) } else { None })
}

/// One query's state on the adapter: its table, ids and objects, and what the adapter has read on it, keyed by
/// `(kind, the argument's identity, GENERIC_CONSTANTS)`. The argument is held, so its identity can't be reused while the slot lives.
struct LraQuery {
    query: Py<PyAny>,
    table: Py<PyTermTable>,
    ids: Py<PyDict>,
    objects: Py<PyAny>,
    n_input: usize,
    memo: HashMap<(u8, usize, bool), (Py<PyAny>, Py<PyAny>)>,
}

impl LraQuery {
    fn new(q: &Bound<'_, PyAny>) -> PyResult<LraQuery> {
        let p = q.py();
        let table = q.getattr(intern!(p, "table"))?.cast_into::<PyTermTable>()?;
        let n_input = table.borrow().n_input_rows();
        Ok(LraQuery {
            query: q.clone().unbind(),
            table: table.unbind(),
            ids: q.getattr(intern!(p, "ids"))?.cast_into::<PyDict>()?.unbind(),
            objects: q.getattr(intern!(p, "objects"))?.unbind(),
            n_input,
            memo: HashMap::new(),
        })
    }
}

/// lra_live's `interpret`, `order_sides` and `integer_form` on ids, line for line. `Ok(None)`: a side has no id, so Python reads it.
struct Reader<'a, 'py> {
    p: Python<'py>,
    live: &'a LraLive,
    q: Bound<'py, PyAny>,
    table: Bound<'py, PyTermTable>,
    ids: Bound<'py, PyDict>,
    objects: Bound<'py, PyAny>,
    n_input: usize,
    flag: bool,
}

impl<'py> Reader<'_, 'py> {
    /// term_live's `term_id`: an input row of the term's own class here; anything else is term_live's rule, counted.
    fn id(&self, e: &Bound<'py, PyAny>, site: &str) -> PyResult<Option<u32>> {
        let p = self.p;
        if let Ok(Some(i)) = self.ids.get_item(e) {
            let i: u32 = i.extract()?;
            let o = self.objects.get_item(i)?;
            return Ok(if o.get_type().is(&e.get_type()) { Some(i) } else { None });
        }
        tick(session::AD_LRA_TERM_ID_PY);
        let got = self.live.term_id.bind(p).call1((&self.q, e, site))?;
        if got.is_none() { Ok(None) } else { Ok(Some(got.extract()?)) }
    }

    fn rel(&self, atom: &Bound<'py, PyAny>) -> PyResult<Option<(String, Bound<'py, PyAny>, Bound<'py, PyAny>)>> {
        tick(session::AD_LRA_RELATION);
        let r = self.live.relation.bind(self.p).call1((atom,))?;
        if r.is_none() {
            return Ok(None);
        }
        Ok(Some((r.get_item(0)?.extract()?, r.get_item(1)?, r.get_item(2)?)))
    }

    fn obj(&self, i: &Bound<'py, PyAny>, site: &str) -> PyResult<Bound<'py, PyAny>> {
        let n: usize = i.extract()?;
        if n < self.n_input {
            return self.objects.get_item(n);
        }
        tick(session::AD_LRA_SCAFFOLD);
        self.live.scaffold.bind(self.p).call1((&self.q, i, site))
    }

    fn objs(&self, ids: &Bound<'py, PyAny>, site: &str) -> PyResult<Bound<'py, PyList>> {
        let out = PyList::empty(self.p);
        for i in ids.try_iter()? {
            out.append(self.obj(&i?, site)?)?;
        }
        Ok(out)
    }

    fn pairs(&self, items: &Bound<'py, PyAny>, site: &str) -> PyResult<Bound<'py, PyTuple>> {
        let mut v: Vec<(Bound<'py, PyAny>, Bound<'py, PyAny>)> = Vec::new();
        for it in items.try_iter()? {
            let it = it?;
            v.push((self.obj(&it.get_item(0)?, site)?, it.get_item(1)?));
        }
        if v.len() >= 2 && planted(AD_LRA_PAIR_SWAP) {
            let c0 = v[0].1.clone();
            v[0].1 = v[1].1.clone();
            v[1].1 = c0;
        }
        let ts: Vec<Bound<'py, PyTuple>> = v.into_iter().map(|(a, b)| PyTuple::new(self.p, [a, b])).collect::<PyResult<_>>()?;
        PyTuple::new(self.p, ts)
    }

    /// lra_live `_rust`'s `except Exception`: an `Exception` becomes its TermFault; a BaseException, `TermRefuse` above all,
    /// goes up unchanged, so the query is refused and rerun on Python as on lra_live's path (sa-port-198's bar: 14 suite tests).
    fn fault(&self, site: &str, e: PyErr) -> PyErr {
        let p = self.p;
        if !e.is_instance_of::<pyo3::exceptions::PyException>(p) {
            return e;
        }
        match self.live.fault.bind(p).call1((site, e.value(p))) {
            Ok(v) => PyErr::from_value(v),
            Err(e2) => e2,
        }
    }

    fn interpret(&self, atom: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyAny>>> {
        let p = self.p;
        let Some((name, l, r)) = self.rel(atom)? else { return Ok(Some(p.None().into_bound(p))) };
        let Some(a) = self.id(&l, "interpret")? else { return Ok(None) };
        let Some(b) = self.id(&r, "interpret")? else { return Ok(None) };
        let got = self.table.borrow_mut().lra_interpret(p, &name, a, b, self.flag, self.objects.clone()).map_err(|e| self.fault("interpret", e))?;
        if got.is_none() {
            return Ok(Some(got));
        }
        let mut c = got.get_item(0)?;
        let terms = got.get_item(1)?;
        if !c.is_instance_of::<pyo3::types::PyBool>() {
            let pairs = self.pairs(&c.get_item(0)?, "interpret")?.into_any();
            let inner = PyTuple::new(p, [pairs, c.get_item(1)?, c.get_item(2)?, c.get_item(3)?])?.into_any();
            c = PyTuple::new(p, [inner, c.get_item(4)?])?.into_any();
        }
        let objs = self.objs(&terms, "interpret")?.into_any();
        Ok(Some(PyTuple::new(p, [c, objs])?.into_any()))
    }

    fn order_sides(&self, atom: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyAny>>> {
        let p = self.p;
        let none = || Ok(Some(p.None().into_bound(p)));
        let Some((name, l, r)) = self.rel(atom)? else { return none() };
        if name != "lt" {
            return none();
        }
        let Some(a) = self.id(&l, "order_sides")? else { return Ok(None) };
        let Some(b) = self.id(&r, "order_sides")? else { return Ok(None) };
        let got = self.table.borrow_mut().lra_order_sides(p, a, b, self.flag, self.objects.clone()).map_err(|e| self.fault("order_sides", e))?;
        if got.is_none() {
            return Ok(Some(got));
        }
        let mut out = Vec::new();
        for side in got.try_iter()? {
            let side = side?;
            let d = PyDict::new(p);
            for kv in self.pairs(&side.get_item(0)?, "order_sides")?.iter() {
                d.set_item(kv.get_item(0)?, kv.get_item(1)?)?;
            }
            out.push(PyTuple::new(p, [d.into_any(), side.get_item(1)?])?);
        }
        Ok(Some(PyTuple::new(p, out)?.into_any()))
    }

    fn integer_form(&self, e: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyAny>>> {
        let p = self.p;
        // lra_adapter.integer_form's first line: a side that isn't an `Expr` (glue's `link_objects` on a plain int side) is
        // None, decided by its type alone, so it needs no row (state step part 2 (i): the `ad:cbm_noid` fallback on scope).
        let expr = EXPR.get_or_try_init(p, || -> PyResult<Py<PyAny>> { Ok(p.import("sympy.core.expr")?.getattr("Expr")?.unbind()) })?;
        let i = if e.is_instance(expr.bind(p))? {
            self.id(e, "integer_form")?
        } else if planted(AD_LRA_NOT_EXPR) && e.is_instance_of::<pyo3::types::PyInt>() {
            let n: i64 = e.extract()?;
            Some(self.table.borrow_mut().number(n.into(), 1.into()))
        } else {
            tick(session::AD_LRA_NOT_EXPR);
            return Ok(Some(p.None().into_bound(p)));
        };
        let Some(i) = i else { return Ok(None) };
        let got = self.table.borrow_mut().lra_integer_form(p, i, self.flag, self.objects.clone()).map_err(|e| self.fault("integer_form", e))?;
        if got.is_none() {
            return Ok(Some(got));
        }
        let pairs = self.pairs(&got.get_item(0)?, "integer_form")?;
        let integral = p.get_type::<crate::payloads::Integral>().call1((pairs, got.get_item(1)?))?;
        let objs = self.objs(&got.get_item(2)?, "integer_form")?.into_any();
        Ok(Some(PyTuple::new(p, [integral, objs])?.into_any()))
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

    /// Test-only snapshot export of the slot (state step, part 1): `(query, [(kind, arg, flag, result)])`, in no set order, or
    /// None with no slot. Kinds: 0 interpret, 1 order_sides, 2 integer_form.
    fn _slot_items<'py>(&self, p: Python<'py>) -> PyResult<Option<(Bound<'py, PyAny>, Bound<'py, PyList>)>> {
        let b = self.slot.borrow();
        let Some(s) = b.as_ref() else { return Ok(None) };
        let out = PyList::empty(p);
        for ((k, _, f), (a, r)) in s.memo.iter() {
            out.append((*k, a.bind(p), *f, r.bind(p)))?;
        }
        Ok(Some((s.query.bind(p).clone(), out)))
    }

    fn _attach(&mut self, p: Python<'_>, solver: &Bound<'_, PyAny>) -> PyResult<()> {
        attach_to(p, &mut self._solver, &self.theory, solver, "LRAAdapter")
    }

    fn interpret<'py>(&self, p: Python<'py>, atom: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        self.memoized(p, K_INTERPRET, atom.clone(), intern!(p, "interpret"), atom)
    }

    fn order_sides<'py>(&self, p: Python<'py>, atom: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let key = PyTuple::new(p, [intern!(p, "sides").clone().into_any(), atom.clone()])?.into_any();
        self.memoized(p, K_SIDES, key, intern!(p, "order_sides"), atom)
    }

    fn integer_form<'py>(&self, p: Python<'py>, e: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let key = PyTuple::new(p, [intern!(p, "integer").clone().into_any(), e.clone()])?.into_any();
        self.memoized(p, K_INTEGER, key, intern!(p, "integer_form"), e)
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
    m.add_function(wrap_pyfunction!(ad_lra_live, m)?)?;
    m.add_function(wrap_pyfunction!(ad_lra_export, m)?)?;
    Ok(())
}
