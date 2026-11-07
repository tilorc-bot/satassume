//! The rational LRA core as a Python class, for `slice/lra_backend.py`. Terms are ids here: the Python side holds the
//! dict from term to id, so equality and hash are exactly what `_var_of` uses, and hands `check` the list of objects.
//! Numbers cross as `fractions.Fraction`. Rust owns no decision about what is rational: anything else never gets here.
use crate::lra::{CheckResult, Kind, Payload, Theory, Trail};
use crate::rat::Rat;
use num_bigint::BigInt;
use pyo3::exceptions::PyIndexError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyTuple};

fn rat_of(x: &Bound<'_, PyAny>) -> PyResult<Rat> {
    let n = x.getattr("numerator")?;
    let d = x.getattr("denominator")?;
    if let (Ok(a), Ok(b)) = (n.extract::<i64>(), d.extract::<i64>()) {
        if a != i64::MIN {
            return Ok(Rat::S(a, b));
        }
    }
    Ok(Rat::norm_big(n.extract::<BigInt>()?, d.extract::<BigInt>()?))
}

fn pairs_of(terms: &Bound<'_, PyList>) -> PyResult<Vec<(u32, Rat)>> {
    let mut out = Vec::with_capacity(terms.len());
    for e in terms.iter() {
        let (i, c): (u32, Bound<'_, PyAny>) = e.extract()?;
        out.push((i, rat_of(&c)?));
    }
    Ok(out)
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
    /// Builds a Fraction from coprime parts, or normalises them on a Python without that constructor.
    frac: Py<PyAny>,
    /// Hook calls made so far: "moved at call N" in the report.
    #[pyo3(get)]
    calls: u64,
}

impl LraCore {
    fn frac<'py>(&self, p: Python<'py>, r: &Rat) -> PyResult<Bound<'py, PyAny>> {
        let f = self.frac.bind(p);
        match r {
            Rat::S(n, d) => f.call1((*n, *d)),
            Rat::B(b) => f.call1((b.0.clone(), b.1.clone())),
        }
    }
    fn bound<'py>(&self, p: Python<'py>, b: &Option<(Rat, Rat)>) -> PyResult<Bound<'py, PyAny>> {
        match b {
            None => Ok(p.None().into_bound(p)),
            Some((q, d)) => Ok(PyTuple::new(p, [self.frac(p, q)?, self.frac(p, d)?])?.into_any()),
        }
    }
    fn rats<'py>(&self, p: Python<'py>, xs: &[Rat]) -> PyResult<Bound<'py, PyList>> {
        let l = PyList::empty(p);
        for x in xs {
            l.append(self.frac(p, x)?)?;
        }
        Ok(l)
    }
    fn pairs<'py>(&self, p: Python<'py>, xs: &[(u32, Rat)]) -> PyResult<Bound<'py, PyList>> {
        let l = PyList::empty(p);
        for (k, c) in xs {
            l.append((*k, self.frac(p, c)?))?;
        }
        Ok(l)
    }
}

fn conflict<'py>(p: Python<'py>, c: Vec<i32>) -> PyResult<Bound<'py, PyAny>> {
    Ok((false, PyList::new(p, c)?).into_pyobject(p)?.into_any())
}

#[pymethods]
impl LraCore {
    #[new]
    fn new(p: Python<'_>, eager: bool) -> PyResult<LraCore> {
        let fr = p.import("fractions")?.getattr("Fraction")?;
        let frac = fr.getattr_opt("_from_coprime_ints")?.unwrap_or(fr).unbind();
        let mut t = Theory::new();
        t.eager = eager;
        Ok(LraCore { t, frac, calls: 0 })
    }

    fn registered(&self, literal: u32) -> bool {
        self.t.atoms.contains_key(&literal) || self.t.ground.contains_key(&literal) || self.t.ints.contains_key(&literal)
    }

    /// `_lin`'s variables and nothing else: what a payload leaves behind when its constant then raises.
    fn touch(&mut self, ids: Vec<u32>) {
        self.t.touch(&ids);
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
        self.calls += 1;
        let payload = Payload::Plain { neg: negated as u32, strict, eq, constant: rat_of(constant)?, terms: pairs_of(terms)? };
        self.t.register_atom(literal, &payload);
        Ok(())
    }

    fn register_integral(&mut self, literal: u32, offset: &Bound<'_, PyAny>, terms: &Bound<'_, PyList>) -> PyResult<()> {
        self.calls += 1;
        let payload = Payload::Integral { offset: rat_of(offset)?, terms: pairs_of(terms)? };
        self.t.register_atom(literal, &payload);
        Ok(())
    }

    fn assert_lit<'py>(&mut self, p: Python<'py>, literal: i32) -> PyResult<Option<Bound<'py, PyAny>>> {
        self.calls += 1;
        self.t.assert_lit(literal).map(|c| conflict(p, c)).transpose()
    }

    fn check<'py>(&mut self, p: Python<'py>, budget: i64, terms: &Bound<'py, PyList>) -> PyResult<Bound<'py, PyAny>> {
        self.calls += 1;
        match self.t.check(budget) {
            CheckResult::Conflict(c) => conflict(p, c),
            CheckResult::Sat(m) => {
                let d = PyDict::new(p);
                for (id, q) in &m {
                    d.set_item(terms.get_item(*id as usize)?, self.frac(p, q)?)?;
                }
                Ok((true, d).into_pyobject(p)?.into_any())
            }
        }
    }

    fn propagate<'py>(&mut self, p: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        self.calls += 1;
        let out = PyList::empty(p);
        for (lit, why) in self.t.propagate() {
            out.append((lit, PyList::new(p, why)?))?;
        }
        Ok(out)
    }

    fn push_level(&mut self) {
        self.calls += 1;
        self.t.push_level();
    }

    fn pop_level(&mut self) -> PyResult<()> {
        self.calls += 1;
        if self.t.lims.is_empty() {
            return Err(PyIndexError::new_err("pop from empty list"));
        }
        self.t.pop_level();
        Ok(())
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
        d.set_item("gave_up", 0)?;
        d.set_item("exhausted", s.exhausted)?;
        Ok(d)
    }

    /// The whole state, with term ids for terms: `lra_backend._state` builds LRATheory's fields from it. Every order
    /// here is defined (variable order, registration order, or sorted); no hash map is iterated for its own order.
    fn dump<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let t = &self.t;
        let d = PyDict::new(p);
        d.set_item("key", PyList::new(p, &t.key)?)?;
        let bounds = |xs: &[Option<(Rat, Rat)>]| -> PyResult<Bound<'py, PyList>> {
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
        d.set_item("vq", self.rats(p, &t.vq)?)?;
        d.set_item("vd", self.rats(p, &t.vd)?)?;
        let rows = PyList::empty(p);
        for (b, r) in t.rows.iter().enumerate() {
            if let Some(r) = r {
                rows.append((b, self.pairs(p, &r.0)?))?;
            }
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
                atoms.append((*lit, *v, kind_text(*kind), self.frac(p, c)?))?;
            } else if let Some((v, m, k)) = t.ints.get(lit) {
                ints.append((*lit, *v, self.frac(p, m)?, self.frac(p, k)?))?;
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
            diseqs.append((*v, self.frac(p, c)?, *l))?;
        }
        d.set_item("diseqs", diseqs)?;
        let int_lits = PyList::empty(p);
        for (v, m, k, l) in &t.int_lits {
            int_lits.append((*v, self.frac(p, m)?, self.frac(p, k)?, *l))?;
        }
        d.set_item("int_lits", int_lits)?;
        d.set_item("lims", PyList::new(p, &t.lims)?)?;
        d.set_item("dirty", PyList::new(p, t.dirty.set.iter().copied())?)?;
        d.set_item("pending_ground", PyList::new(p, &t.pending_ground)?)?;
        let mut slacks: Vec<_> = t.slack_of.iter().collect();
        slacks.sort_by_key(|e| *e.1); // a new slack is the newest variable: this is insertion order
        let sl = PyList::empty(p);
        for (form, v) in slacks {
            sl.append((self.pairs(p, form)?, *v))?;
        }
        d.set_item("slack_of", sl)?;
        let mut forms: Vec<_> = t.forms.iter().collect();
        forms.sort_by(|a, b| a.0.cmp(b.0)); // only ever looked up: any defined order will do
        let fl = PyList::empty(p);
        for (key, (v, c)) in forms {
            fl.append((self.pairs(p, key)?, *v, self.frac(p, c)?))?;
        }
        d.set_item("forms", fl)?;
        d.set_item("exhausted", t.exhausted)?;
        d.set_item("branched_rational", t.branched_rational)?;
        d.set_item("stats", self.stats(p)?)?;
        Ok(d)
    }
}
