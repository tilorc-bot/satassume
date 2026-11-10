//! The rational LRA core as a Python class, for `slice/lra_backend.py`. Terms are ids here: the Python side holds the
//! dict from term to id, so equality and hash are exactly what `_var_of` uses, and hands `check` the list of objects.
//! Numbers cross as `fractions.Fraction`. Rust owns no decision about what is rational: anything else never gets here.
use crate::constfield::{refresh_limits, CfErr, Num};
use crate::lra::{Bound as LraBound, CheckResult, Kind, Payload, Theory, Trail};
use crate::rat::Rat;
use num_bigint::BigInt;
use pyo3::exceptions::PyIndexError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyTuple};

fn pairs_of(terms: &Bound<'_, PyList>) -> PyResult<Vec<(u32, Num)>> {
    let mut out = Vec::with_capacity(terms.len());
    for e in terms.iter() {
        let (i, c): (u32, Bound<'_, PyAny>) = e.extract()?;
        out.push((i, Num::from_py(&c)?));
    }
    Ok(out)
}

fn rat_of(x: &Bound<'_, PyAny>) -> PyResult<Rat> {
    match Num::from_py(x)? {
        Num::Q(r) => Ok(r),
        Num::E(_) => Err(pyo3::exceptions::PyTypeError::new_err("expected a Fraction")),
    }
}

fn kind_text(k: Kind) -> &'static str {
    match k {
        Kind::Le => "<=",
        Kind::Lt => "<",
        Kind::Ge => ">=",
        Kind::Gt => ">",
        Kind::Eq => "=",
        Kind::Ne => "!=",
    }
}

#[pyclass(name = "LraCore", module = "sa_solver", unsendable)]
pub struct LraCore {
    t: Theory,
}

impl LraCore {
    /// (`gave_up`, `exhausted`), for theory_flags.rs (engine.py `_gave_up`/`_exhausted`).
    pub(crate) fn flags(&self) -> (bool, bool) {
        (self.t.gave_up, self.t.exhausted)
    }

    fn bound<'py>(&self, p: Python<'py>, b: &Option<LraBound>) -> PyResult<Bound<'py, PyAny>> {
        match b {
            None => Ok(p.None().into_bound(p)),
            Some((q, d)) => Ok(PyTuple::new(p, [q.to_py(p)?, d.to_py(p)?])?.into_any()),
        }
    }
    fn nums<'py>(&self, p: Python<'py>, xs: &[Num]) -> PyResult<Bound<'py, PyList>> {
        let l = PyList::empty(p);
        for x in xs {
            l.append(x.to_py(p)?)?;
        }
        Ok(l)
    }
    fn pairs<'py>(&self, p: Python<'py>, xs: &[(u32, Num)]) -> PyResult<Bound<'py, PyList>> {
        let l = PyList::empty(p);
        for (k, c) in xs {
            l.append((*k, c.to_py(p)?))?;
        }
        Ok(l)
    }
    /// Python reads the limits live. `Theory` holds no Python, so a hook on a theory with constants reads them first.
    fn limits(&self) -> PyResult<()> {
        if self.t.fields {
            refresh_limits()?;
        }
        Ok(())
    }
}

fn conflict<'py>(p: Python<'py>, c: Vec<i32>) -> PyResult<Bound<'py, PyAny>> {
    Ok((false, PyList::new(p, c)?).into_pyobject(p)?.into_any())
}

fn py_err(e: CfErr) -> PyErr {
    e.into()
}

#[pymethods]
impl LraCore {
    #[new]
    fn new(eager: bool) -> LraCore {
        let mut t = Theory::new();
        t.eager = eager;
        LraCore { t }
    }

    fn registered(&self, literal: u32) -> bool {
        self.t.atoms.contains_key(&literal) || self.t.ground.contains_key(&literal) || self.t.ints.contains_key(&literal)
    }

    /// A term that holds a variable: `_lin` got as far as `_term_var`.
    fn has_term(&self, id: u32) -> bool {
        self.t.var_of.contains_key(&id)
    }

    /// `_lin` when the payload's own number then raises: what it leaves behind. False if `_lin` itself gave up.
    fn touch(&mut self, terms: &Bound<'_, PyList>) -> PyResult<bool> {
        let pairs = pairs_of(terms)?;
        refresh_limits()?;
        self.t.touch(&pairs).map_err(py_err)
    }

    fn set_fields(&mut self) {
        self.t.fields = true;
    }

    fn give_up(&mut self) {
        self.t.give_up();
    }

    #[getter]
    fn gave_up(&self) -> bool {
        self.t.gave_up
    }

    fn register_plain(
        &mut self,
        literal: u32,
        negated: bool,
        strict: bool,
        eq: bool,
        constant: &Bound<'_, PyAny>,
        terms: &Bound<'_, PyList>,
    ) -> PyResult<()> {
        let payload =
            Payload::Plain { neg: negated as u32, strict, eq, constant: Num::from_py(constant)?, terms: pairs_of(terms)? };
        refresh_limits()?;
        self.t.register_atom(literal, &payload).map_err(py_err)
    }

    fn register_integral(&mut self, literal: u32, offset: &Bound<'_, PyAny>, terms: &Bound<'_, PyList>) -> PyResult<()> {
        let payload = Payload::Integral { offset: Num::from_py(offset)?, terms: pairs_of(terms)? };
        refresh_limits()?;
        self.t.register_atom(literal, &payload).map_err(py_err)
    }

    fn assert_lit<'py>(&mut self, p: Python<'py>, literal: i32) -> PyResult<Option<Bound<'py, PyAny>>> {
        self.limits()?;
        match self.t.assert_lit(literal).map_err(py_err)? {
            None => Ok(None),
            Some(c) => conflict(p, c).map(Some),
        }
    }

    fn check<'py>(&mut self, p: Python<'py>, budget: i64, terms: &Bound<'py, PyList>) -> PyResult<Bound<'py, PyAny>> {
        self.limits()?;
        match self.t.check(budget).map_err(py_err)? {
            None => Ok(p.None().into_bound(p)),
            Some(CheckResult::Conflict(c)) => conflict(p, c),
            Some(CheckResult::Sat(m)) => {
                let d = PyDict::new(p);
                for (id, q) in &m {
                    d.set_item(terms.get_item(*id as usize)?, q.to_py(p)?)?;
                }
                Ok((true, d).into_pyobject(p)?.into_any())
            }
        }
    }

    fn propagate<'py>(&mut self, p: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        self.limits()?;
        let out = PyList::empty(p);
        for (lit, why) in self.t.propagate().map_err(py_err)? {
            out.append((lit, PyList::new(p, why)?))?;
        }
        Ok(out)
    }

    fn push_level(&mut self) {
        if !self.t.gave_up {
            self.t.push_level();
        }
    }

    fn pop_level(&mut self) -> PyResult<()> {
        if self.t.gave_up {
            return Ok(());
        }
        if self.t.lims.is_empty() {
            return Err(PyIndexError::new_err("pop from empty list"));
        }
        self.t.pop_level();
        Ok(())
    }

    /// `_certificate`: `(certified, Y)`. `certified` and `certified_with` answer from this too.
    #[pyo3(signature = (values=None))]
    fn certificate<'py>(&mut self, p: Python<'py>, values: Option<&Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyAny>> {
        let v = match values {
            None => None,
            Some(x) => {
                let (top, den): (Bound<'_, PyAny>, BigInt) = x.extract()?;
                Some((rat_of(&top)?, den))
            }
        };
        let (ok, y) = self.t.certificate(v.as_ref()).map_err(py_err)?;
        let y = match y {
            None => p.None().into_bound(p),
            Some(y) => Num::Q(y).to_py(p)?,
        };
        Ok((ok, y).into_pyobject(p)?.into_any())
    }

    /// `rational_values`: `(top, den)`, or None.
    fn rational_values<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        match self.t.rational_values() {
            None => Ok(p.None().into_bound(p)),
            Some((top, den)) => Ok((Num::Q(top).to_py(p)?, den).into_pyobject(p)?.into_any()),
        }
    }

    #[getter]
    fn level(&self) -> usize {
        self.t.lims.len()
    }

    #[getter]
    fn get_exhausted(&self) -> bool {
        self.t.exhausted
    }
    #[setter]
    fn set_exhausted(&mut self, v: bool) {
        self.t.exhausted = v;
    }
    #[setter]
    fn set_eager(&mut self, v: bool) {
        self.t.eager = v;
    }
    #[getter]
    fn branched_rational(&self) -> bool {
        self.t.branched_rational
    }

    #[getter]
    fn stats<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let d = PyDict::new(p);
        let s = &self.t.stats;
        d.set_item("pivots", s.pivots)?;
        d.set_item("checks", s.checks)?;
        d.set_item("conflicts", s.conflicts)?;
        d.set_item("propagations", s.propagations)?;
        d.set_item("branches", s.branches)?;
        d.set_item("gave_up", s.gave_up)?;
        d.set_item("exhausted", s.exhausted)?;
        Ok(d)
    }

    /// The whole state, with term ids for terms: `lra_backend._state` builds LRATheory's fields from it. Every order
    /// here is defined (variable order, registration order, or sorted); no hash map is iterated for its own order.
    fn dump<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let t = &self.t;
        let d = PyDict::new(p);
        d.set_item("key", PyList::new(p, &t.key)?)?;
        let bounds = |xs: &[Option<LraBound>]| -> PyResult<Bound<'py, PyList>> {
            let l = PyList::empty(p);
            for b in xs {
                l.append(self.bound(p, b)?)?;
            }
            Ok(l)
        };
        d.set_item("lo", bounds(&t.lo)?)?;
        d.set_item("up", bounds(&t.up)?)?;
        d.set_item("lo_r", PyList::new(p, &t.lo_r)?)?;
        d.set_item("up_r", PyList::new(p, &t.up_r)?)?;
        d.set_item("vq", self.nums(p, &t.vq)?)?;
        d.set_item("vd", self.nums(p, &t.vd)?)?;
        let rows = PyList::empty(p);
        for b in &t.row_order {
            let r = t.rows[*b as usize].as_ref().expect("row_order holds the rows");
            rows.append((*b, self.pairs(p, &r.0)?))?;
        }
        d.set_item("rows", rows)?;
        let cols = PyList::empty(p);
        for c in &t.cols {
            let mut c = c.clone();
            c.sort_unstable();
            cols.append(PyList::new(p, c)?)?;
        }
        d.set_item("cols", cols)?;
        let (atoms, ground, ints, ints_on) = (PyList::empty(p), PyList::empty(p), PyList::empty(p), PyList::empty(p));
        let mut seen: Vec<u32> = vec![];
        for lit in &t.reg_order {
            if let Some((v, kind, c)) = t.atoms.get(lit) {
                atoms.append((*lit, *v, kind_text(*kind), c.to_py(p)?))?;
            } else if let Some((v, m, k)) = t.ints.get(lit) {
                ints.append((*lit, *v, m.to_py(p)?, k.to_py(p)?))?;
                if !seen.contains(v) {
                    seen.push(*v);
                    ints_on.append((*v, PyList::new(p, &t.ints_on[v])?))?;
                }
            } else if let Some(b) = t.ground.get(lit) {
                ground.append((*lit, *b))?;
            }
        }
        d.set_item("atoms", atoms)?;
        d.set_item("ground", ground)?;
        d.set_item("ints", ints)?;
        d.set_item("ints_on", ints_on)?;
        let on = PyList::empty(p);
        for x in &t.atoms_on {
            on.append(PyList::new(p, x)?)?;
        }
        d.set_item("atoms_on", on)?;
        let (trail, assigned) = (PyList::empty(p), PyList::empty(p));
        for e in &t.trail {
            match e {
                Trail::Lo(v, b, r) => trail.append((0, *v, self.bound(p, b)?, *r))?,
                Trail::Up(v, b, r) => trail.append((1, *v, self.bound(p, b)?, *r))?,
                Trail::Asg(a) => {
                    trail.append((2, *a))?;
                    assigned.append((*a, t.assigned[a]))?;
                }
                Trail::Dis => trail.append((3,))?,
                Trail::Int => trail.append((4,))?,
            }
        }
        d.set_item("trail", trail)?;
        d.set_item("assigned", assigned)?;
        let diseqs = PyList::empty(p);
        for (v, c, l) in &t.diseqs {
            diseqs.append((*v, c.to_py(p)?, *l))?;
        }
        d.set_item("diseqs", diseqs)?;
        let int_lits = PyList::empty(p);
        for (v, m, k, l) in &t.int_lits {
            int_lits.append((*v, m.to_py(p)?, k.to_py(p)?, *l))?;
        }
        d.set_item("int_lits", int_lits)?;
        d.set_item("lims", PyList::new(p, &t.lims)?)?;
        d.set_item("dirty", PyList::new(p, t.dirty.set.iter().copied())?)?;
        d.set_item("pending_ground", PyList::new(p, &t.pending_ground)?)?;
        let sl = PyList::empty(p);
        for form in &t.slack_forms {
            sl.append((self.pairs(p, form)?, t.slack_of[form]))?;
        }
        d.set_item("slack_of", sl)?;
        let fl = PyList::empty(p);
        for key in &t.forms_order {
            let (v, c) = &t.forms[key];
            fl.append((self.pairs(p, key)?, *v, c.to_py(p)?))?;
        }
        d.set_item("forms", fl)?;
        let memo = PyList::empty(p);
        for ((v, m, k, lr, ur), r) in &t.int_memo_order() {
            let r = match r {
                None => p.None().into_bound(p),
                Some((truth, why)) => (*truth, PyList::new(p, why)?).into_pyobject(p)?.into_any(),
            };
            memo.append(((*v, m.to_py(p)?, k.to_py(p)?, *lr, *ur), r))?;
        }
        d.set_item("int_memo", memo)?;
        d.set_item("fields", t.fields)?;
        d.set_item("gave_up", t.gave_up)?;
        d.set_item("exhausted", t.exhausted)?;
        d.set_item("branched_rational", t.branched_rational)?;
        d.set_item("stats", self.stats(p)?)?;
        Ok(d)
    }
}
