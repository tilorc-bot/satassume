//! term_live.py's per-query frames, line for line (issue 323, the term_live step): `current`, `term_id` (with `_int_id`
//! and `same_class`), `_ids`, `_relation_atom`'s `run`, `_guarded`'s wrapper and `_Mark`'s `__init__`/`_note`/`add`.
//! Opt-in (`SLICE_TERM_FRAMES=rust`, term_live.py `use_rust`); Python's functions stay whole, as the reference and the
//! default.
//!
//! **No table of its own.** Every map these functions read or write is the Python one the reference uses, under the same
//! key and with the same lifetime: the query's `ids`/`objects`/`derived`/`rev`/`ints`/`int_ids`/`classes` (one `_Query`,
//! dead with the query), `_local.stack` (the thread's), the `_Mark`'s `tables`/`natives`/`engines`/`facts` (one top-level
//! run) and `COUNTS`. Nothing is kept across queries and nothing is process-wide, with one exception that exists for a
//! plant alone: `stale`, written only under plant 740 `tl-term-stale` (the first query's `derived` map, keyed by the
//! SymPy term, kept for the process), read by term_discard.py as `term.live.STALE` and empty without the plant.
//!
//! Counts go to `COUNTS` under Python's own keys, so every count row reads the same on either path.
//!
//! Plants (`SLICE_TERM_PLANT`, read from `PLANT[0]` by `==` as Python's sites do, so `plant_fired` counts): 740
//! `tl-term-stale` (`term_id`), 741 `tl-ids-reversed` (`_ids`), 742 `tl-current-outer` (`current`), 743 `tl-run-flip`
//! (`run`), 744 `tl-guard-quiet` (the guard), 745 `tl-mark-skip` (`_Mark._note`).

use pyo3::exceptions::{PyAttributeError, PyException, PyTypeError};
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PySet, PyString, PyTuple};
use std::sync::Mutex;

#[pyclass(module = "sa_solver", name = "TermFrames")]
pub struct TermFrames {
    /// The term_live module: `NATIVE_EXTRA`, `_Mark`, `_NO_STAMP` and `CHECK` are read from it at call time.
    module: Py<PyAny>,
    local: Py<PyAny>,
    counts: Py<PyDict>,
    plant: Py<PyAny>,
    basic: Py<PyAny>,
    rational: Py<PyAny>,
    add: Py<PyAny>,
    mul: Py<PyAny>,
    int_sites: Py<PyAny>,
    relations: Py<PyAny>,
    fault_t: Py<PyAny>,
    /// `satassume.state.memos`, `_common` and `constfield`: their tables are read by name at each mark, as Python does.
    memos: Py<PyAny>,
    common: Py<PyAny>,
    constfield: Py<PyAny>,
    /// The builtins `getattr` and `reversed` and `collections.defaultdict`, read once, for `note`.
    getattr: Py<PyAny>,
    reversed: Py<PyAny>,
    defaultdict: Py<PyAny>,
    /// Plant 740's store, and nothing else's: the first query's `derived` map.
    stale: Mutex<Option<Py<PyAny>>>,
}

fn attr_or<'py>(o: &Bound<'py, PyAny>, name: &Bound<'py, PyString>) -> PyResult<Option<Bound<'py, PyAny>>> {
    match o.getattr(name) {
        Ok(v) => Ok(Some(v)),
        Err(e) if e.is_instance_of::<PyAttributeError>(o.py()) => Ok(None),
        Err(e) => Err(e),
    }
}

fn some<'py>(v: Bound<'py, PyAny>) -> Option<Bound<'py, PyAny>> {
    if v.is_none() { None } else { Some(v) }
}

impl TermFrames {
    fn count(&self, py: Python<'_>, key: &str) -> PyResult<()> {
        let c = self.counts.bind(py);
        let n: u64 = match c.get_item(key)? {
            Some(v) => v.extract()?,
            None => 0,
        };
        c.set_item(key, n + 1)
    }

    /// `PLANT[0] == name`, through Python's `==` (a `_Plant` counts the match as `plant_fired`).
    fn planted(&self, py: Python<'_>, name: &str) -> PyResult<bool> {
        let p = self.plant.bind(py).get_item(0)?;
        if p.is_none() {
            return Ok(false);
        }
        p.eq(name)
    }

    /// term_live.py `same_class`, counted in `COUNTS` as there.
    fn same_class<'py>(&self, q: &Bound<'py, PyAny>, a: &Bound<'py, PyAny>, b: &Bound<'py, PyAny>) -> PyResult<bool> {
        let (ta, tb) = (a.get_type(), b.get_type());
        if ta.is(&tb) {
            return Ok(true);
        }
        if crate::formula::class_is_on() {
            return Ok(false);
        }
        let p = q.py();
        let c = q.getattr(intern!(p, "classes"))?;
        let mut same = false;
        if !c.is_none() {
            let r: PyResult<bool> = (|| {
                let i = c.call_method1(intern!(p, "get"), (&ta,))?;
                if i.is_none() {
                    return Ok(false);
                }
                c.call_method1(intern!(p, "get"), (&tb,))?.eq(i)
            })();
            same = match r {
                Ok(s) => s,
                // an unhashable class: no id
                Err(e) if e.is_instance_of::<PyTypeError>(p) => false,
                Err(e) => return Err(e),
            };
        }
        self.count(p, if same { "class:eq" } else { "class:differs" })?;
        Ok(same)
    }

    fn int_id<'py>(&self, q: &Bound<'py, PyAny>, e: &Bound<'py, PyAny>, site: &str) -> PyResult<Bound<'py, PyAny>> {
        let p = q.py();
        self.count(p, &format!("term:int:{site}"))?;
        let table = q.getattr(intern!(p, "table"))?;
        if self.planted(p, "int-as-number")? {
            return table.call_method1(intern!(p, "number"), (e, 1));
        }
        let int_ids = q.getattr(intern!(p, "int_ids"))?;
        if let Some(i) = some(int_ids.call_method1(intern!(p, "get"), (e,))?) {
            return Ok(i);
        }
        let i = table.call_method1(intern!(p, "py_int"), (e,))?;
        int_ids.set_item(e, &i)?;
        q.getattr(intern!(p, "ints"))?.set_item(&i, e)?;
        Ok(i)
    }

    fn term_id_in<'py>(&self, q: &Bound<'py, PyAny>, e: &Bound<'py, PyAny>, site: &str) -> PyResult<Option<Bound<'py, PyAny>>> {
        let p = q.py();
        let is_basic = e.is_instance(self.basic.bind(p))?;
        if is_basic {
            if let Some(i) = some(q.getattr(intern!(p, "ids"))?.call_method1(intern!(p, "get"), (e,))?) {
                // `==` can join classes (Float against Integer), so a row counts only for its own class.
                let o = q.getattr(intern!(p, "objects"))?.get_item(&i)?;
                return Ok(if self.same_class(q, &o, e)? { Some(i) } else { None });
            }
        } else {
            if e.get_type().is(&p.get_type::<pyo3::types::PyInt>()) && self.int_sites.bind(p).contains(site)? {
                return Ok(Some(self.int_id(q, e, site)?));
            }
            let name: String = e.get_type().getattr(intern!(p, "__name__"))?.extract()?;
            self.count(p, &format!("term:unknown:{site}:{name}"))?;
            return Ok(None);
        }
        let derived = q.getattr(intern!(p, "derived"))?;
        if self.planted(p, "tl-term-stale")? {
            // plant 740: a term table that survives its query. The first query's `derived` map is kept, and a later
            // query's term found in it gets that query's id, brought inside this query's table: the stale id that
            // matters names another term's row quietly, it doesn't fall off the end.
            let old = self.stale.lock().unwrap().as_ref().map(|d| d.clone_ref(p));
            match old {
                None => *self.stale.lock().unwrap() = Some(derived.clone().unbind()),
                Some(old) if !old.bind(p).is(&derived) => {
                    if let Some(i) = some(old.bind(p).call_method1(intern!(p, "get"), (e,))?) {
                        let n = q.getattr(intern!(p, "table"))?.len()?.max(1) as u64;
                        let i: u64 = i.extract()?;
                        return Ok(Some((i % n).into_pyobject(p)?.into_any()));
                    }
                }
                _ => {}
            }
        }
        if let Some(i) = some(derived.call_method1(intern!(p, "get"), (e,))?) {
            let o = q.getattr(intern!(p, "rev"))?.get_item(&i)?;
            return Ok(if self.same_class(q, &o, e)? { Some(i) } else { None });
        }
        let cls = e.get_type();
        let table = q.getattr(intern!(p, "table"))?;
        let i = if e.is_instance(self.rational.bind(p))? {
            table.call_method1(intern!(p, "number"), (e.getattr(intern!(p, "p"))?, e.getattr(intern!(p, "q"))?))?
        } else if (cls.is(self.add.bind(p)) || cls.is(self.mul.bind(p)))
            && e.getattr(intern!(p, "is_commutative"))?.is(&pyo3::types::PyBool::new(p, true))
        {
            // every arg is asked before any None stops it, as Python's list is built whole
            let mut args = Vec::new();
            let mut none = false;
            for a in e.getattr(intern!(p, "args"))?.try_iter()? {
                match self.term_id_in(q, &a?, site)? {
                    Some(i) => args.push(i),
                    None => none = true,
                }
            }
            if none {
                return Ok(None);
            }
            let args = PyList::new(p, args)?;
            let i = table.call_method1(if cls.is(self.add.bind(p)) { intern!(p, "raw_add") } else { intern!(p, "raw_mul") }, (args,))?;
            self.count(p, "term:learned")?;
            i
        } else {
            let name: String = cls.getattr(intern!(p, "__name__"))?.extract()?;
            self.count(p, &format!("term:unknown:{site}:{name}"))?;
            return Ok(None);
        };
        if i.ge(table.getattr(intern!(p, "n_input"))?)? {
            derived.set_item(e, &i)?;
            q.getattr(intern!(p, "rev"))?.call_method1(intern!(p, "setdefault"), (&i, e))?;
        }
        Ok(Some(i))
    }

    fn ids_in<'py>(&self, q: &Bound<'py, PyAny>, site: &str, terms: &Bound<'py, PyTuple>) -> PyResult<Option<Bound<'py, PyList>>> {
        let p = q.py();
        let no_query = q.is_none();
        if no_query || !q.getattr(intern!(p, "kept"))?.is_none() {
            self.count(p, &format!("term:no-table:{site}"))?;
            if no_query {
                // Step scope: outside any query, as against inside a kept one.
                self.count(p, &format!("term:no-query:{site}"))?;
            }
            return Ok(None);
        }
        let mut ids = Vec::new();
        let mut none = false;
        for e in terms.iter() {
            match self.term_id_in(q, &e, site)? {
                Some(i) => ids.push(i),
                None => none = true,
            }
        }
        if none {
            self.count(p, &format!("term:py:{site}"))?;
            return Ok(None);
        }
        self.count(p, &format!("term:rust:{site}"))?;
        if ids.len() > 1 && self.planted(p, "tl-ids-reversed")? {
            ids.reverse();      // plant 741: each term gets another's id
        }
        Ok(Some(PyList::new(p, ids)?))
    }

    fn current_in<'py>(&self, p: Python<'py>) -> PyResult<Option<Bound<'py, PyAny>>> {
        let local = self.local.bind(p);
        let s = match attr_or(local, intern!(p, "stack"))? {
            Some(s) => s,
            None => {
                let s = PyList::empty(p).into_any();
                local.setattr(intern!(p, "stack"), &s)?;
                s
            }
        };
        let n = s.len()?;
        if n == 0 {
            return Ok(None);
        }
        if n > 1 && self.planted(p, "tl-current-outer")? {
            return Ok(Some(s.get_item(0)?));    // plant 742: the outermost query's table for a nested query
        }
        Ok(Some(s.get_item(n - 1)?))
    }

    /// `_guarded`'s `except Exception`: counted, and raised again as a `TermFault` from it. A BaseException goes as it is.
    fn guard(&self, p: Python<'_>, site: &str, e: PyErr) -> PyErr {
        if !e.is_instance_of::<PyException>(p) {
            return e;
        }
        match self.planted(p, "tl-guard-quiet") {
            Ok(true) => return e,       // plant 744: the ordinary exception goes on, for a quiet handler to read
            Ok(false) => {}
            Err(e2) => return e2,
        }
        let made = (|| -> PyResult<PyErr> {
            self.count(p, "fault")?;
            let x = e.value(p);
            let name: String = x.get_type().getattr(intern!(p, "__name__"))?.extract()?;
            let new = PyErr::from_value(self.fault_t.bind(p).call1((format!("{site}: {name}: {}", x.str()?),))?);
            new.set_cause(p, Some(e.clone_ref(p)));
            Ok(new)
        })();
        made.unwrap_or_else(|e2| e2)
    }

    fn note(&self, m: &Bound<'_, PyAny>, t: &Bound<'_, PyAny>) -> PyResult<()> {
        let p = m.py();
        let id = t.as_ptr() as usize;
        // Python's `getattr(t, name, default)` itself: the builtin builds no AttributeError on a miss, and a plain dict
        // misses both names (`attr_or` built and dropped one each time).
        let probe = self.getattr.bind(p);
        if probe.call1((t, intern!(p, "native"), false))?.is_truthy()? {
            if t.hasattr(intern!(p, "_nt_mark"))? {
                let mark = t.call_method0(intern!(p, "_nt_mark"))?;
                m.getattr(intern!(p, "natives"))?.set_item(id, (t, mark))?;
            }
            return Ok(());
        }
        if self.planted(p, "tl-mark-skip")? {
            return Ok(());      // plant 745: the table has no mark, so the rollback leaves what the run wrote in it
        }
        let n = t.len()?;
        let stamp = probe.call1((t, intern!(p, "stamp"), self.module.bind(p).getattr(intern!(p, "_NO_STAMP"))?))?;
        let last = if n > 0 {
            match self.reversed.bind(p).call1((t,))?.try_iter()?.next() {
                Some(v) => v?,
                None => p.None().into_bound(p),
            }
        } else {
            p.None().into_bound(p)
        };
        m.getattr(intern!(p, "tables"))?.set_item(id, (t, n, stamp, last))?;
        if t.is_instance(self.defaultdict.bind(p))? && t.getattr(intern!(p, "default_factory"))?.is(&p.get_type::<PyDict>()) {
            for inner in t.call_method0(intern!(p, "values"))?.try_iter()? {
                self.note(m, &inner?)?;
            }
        }
        Ok(())
    }

    fn add_in(&self, m: &Bound<'_, PyAny>, eng: &Bound<'_, PyAny>) -> PyResult<()> {
        let p = m.py();
        let engines = m.getattr(intern!(p, "engines"))?;
        let id = eng.as_ptr() as usize;
        if engines.contains(id)? {
            return Ok(());
        }
        // Rust-owned since 5c10d (entry.rs `EngineStats`): snapshot and restore through its own methods
        let st = eng.getattr(intern!(p, "stats"))?;
        let mark = if st.hasattr(intern!(p, "_st_mark"))? {
            st.call_method0(intern!(p, "_st_mark"))?
        } else {
            (p.get_type::<PyDict>().call1((&st,))?, eng.getattr(intern!(p, "last_budget_limited"))?).into_pyobject(p)?.into_any()
        };
        let constructing = p.get_type::<PySet>().call1((eng.getattr(intern!(p, "_constructing"))?,))?;
        engines.set_item(id, (eng, mark, constructing))?;
        let facts = m.getattr(intern!(p, "facts"))?;
        for name in [intern!(p, "cache"), intern!(p, "custom_cache")] {
            // a Rust-native fact cache (factcache.rs, step 5c10a) marks itself
            let c = eng.getattr(name)?;
            let cid = c.as_ptr() as usize;
            if !facts.contains(cid)? && c.hasattr(intern!(p, "_fc_mark"))? {
                let fm = c.call_method0(intern!(p, "_fc_mark"))?;
                facts.set_item(cid, (&c, fm))?;
            }
        }
        for row in eng.getattr(intern!(p, "memos"))?.call_method0(intern!(p, "items"))?.try_iter()? {
            self.note(m, &row?.get_item(2)?)?;
        }
        Ok(())
    }
}

#[pymethods]
impl TermFrames {
    #[new]
    fn new(module: &Bound<'_, PyAny>) -> PyResult<TermFrames> {
        let g = |n: &str| -> PyResult<Py<PyAny>> { Ok(module.getattr(n)?.unbind()) };
        let builtins = module.py().import("builtins")?;
        Ok(TermFrames {
            module: module.clone().unbind(),
            local: g("_local")?,
            counts: module.getattr("COUNTS")?.cast_into::<PyDict>()?.unbind(),
            plant: g("PLANT")?,
            basic: g("Basic")?,
            rational: g("Rational")?,
            add: g("Add")?,
            mul: g("Mul")?,
            int_sites: g("_INT_SITES")?,
            relations: g("_RELATIONS")?,
            fault_t: g("TermFault")?,
            memos: g("memos")?,
            common: g("_common")?,
            constfield: g("constfield")?,
            getattr: builtins.getattr("getattr")?.unbind(),
            reversed: builtins.getattr("reversed")?.unbind(),
            defaultdict: module.py().import("collections")?.getattr("defaultdict")?.unbind(),
            stale: Mutex::new(None),
        })
    }

    /// term_live.py `current`.
    fn current<'py>(&self, py: Python<'py>) -> PyResult<Option<Bound<'py, PyAny>>> {
        self.current_in(py)
    }

    /// term_live.py `term_id`.
    fn term_id<'py>(&self, q: &Bound<'py, PyAny>, e: &Bound<'py, PyAny>, site: &str) -> PyResult<Option<Bound<'py, PyAny>>> {
        self.term_id_in(q, e, site)
    }

    /// term_live.py `_ids`.
    #[pyo3(signature = (q, site, *terms))]
    fn ids<'py>(&self, q: &Bound<'py, PyAny>, site: &str, terms: &Bound<'py, PyTuple>) -> PyResult<Option<Bound<'py, PyList>>> {
        self.ids_in(q, site, terms)
    }

    /// term_live.py `_guarded`.
    fn guarded(slf: &Bound<'_, Self>, site: String, f: Py<PyAny>) -> Guarded {
        Guarded { frames: slf.clone().unbind(), site, f }
    }

    /// `_relation_atom`'s guarded `run`, over Python's `eq` and `order` branches and its check.
    fn relation_run(slf: &Bound<'_, Self>, py_atom: Py<PyAny>, eq: Py<PyAny>, order: Py<PyAny>, check: Py<PyAny>) -> RelationRun {
        RelationRun { frames: slf.clone().unbind(), py_atom, eq, order, check }
    }

    /// `_Mark(eng)`: the object is Python's `_Mark`, filled here.
    fn mark<'py>(&self, eng: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let p = eng.py();
        let module = self.module.bind(p);
        let mark_t = module.getattr(intern!(p, "_Mark"))?;
        let m = mark_t.call_method1(intern!(p, "__new__"), (&mark_t,))?;
        for name in ["tables", "natives", "engines", "facts"] {
            m.setattr(name, PyDict::new(p))?;
        }
        m.setattr(intern!(p, "cache"), PyList::empty(p))?;
        let cache = self.common.bind(p).getattr(intern!(p, "_CACHE"))?;
        m.setattr(intern!(p, "cache_n"), cache.len()?)?;
        for row in self.memos.bind(p).getattr(intern!(p, "PROCESS"))?.call_method0(intern!(p, "items"))?.try_iter()? {
            let t = row?.get_item(2)?;
            // The pattern cache is not rolled back (ruling R3; term_live.py `_Mark.__init__`).
            if t.is(&self.common.bind(p).getattr(intern!(p, "_CACHE"))?) {
                continue;
            }
            self.note(&m, &t)?;
        }
        let cf = self.constfield.bind(p);
        for name in [intern!(p, "_CONSTANTS"), intern!(p, "_BY_KEY")] {
            self.note(&m, &cf.getattr(name)?)?;
        }
        for t in module.getattr(intern!(p, "NATIVE_EXTRA"))?.try_iter()? {
            self.note(&m, &t?)?;
        }
        self.add_in(&m, eng)?;
        Ok(m)
    }

    /// `_Mark._note`.
    fn mark_note(&self, m: &Bound<'_, PyAny>, t: &Bound<'_, PyAny>) -> PyResult<()> {
        self.note(m, t)
    }

    /// `_Mark.add`.
    fn mark_add(&self, m: &Bound<'_, PyAny>, eng: &Bound<'_, PyAny>) -> PyResult<()> {
        self.add_in(m, eng)
    }

    /// Plant 740's store, for term_discard.py (`term.live.STALE`): the surviving map's terms. Empty without the plant.
    fn stale_rows<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        let old = self.stale.lock().unwrap().as_ref().map(|d| d.clone_ref(py));
        match old {
            Some(d) => PyList::new(py, d.bind(py).try_iter()?.collect::<PyResult<Vec<_>>>()?),
            None => Ok(PyList::empty(py)),
        }
    }

    /// Empties plant 740's store (a test's teardown).
    fn stale_clear(&self) {
        *self.stale.lock().unwrap() = None;
    }
}

/// `_guarded(site, f)`'s wrapper `g`.
#[pyclass(module = "sa_solver")]
pub struct Guarded {
    frames: Py<TermFrames>,
    site: String,
    f: Py<PyAny>,
}

#[pymethods]
impl Guarded {
    #[pyo3(signature = (*args, **kwargs))]
    fn __call__<'py>(&self, py: Python<'py>, args: &Bound<'py, PyTuple>, kwargs: Option<&Bound<'py, PyDict>>) -> PyResult<Bound<'py, PyAny>> {
        self.f.bind(py).call(args, kwargs).map_err(|e| self.frames.bind(py).borrow().guard(py, &self.site, e))
    }

    #[getter]
    fn __wrapped__(&self, py: Python<'_>) -> Py<PyAny> {
        self.f.clone_ref(py)
    }
}

/// `_relation_atom(py)`'s `run`, guarded as `_guarded('relation_atom', run)` is.
#[pyclass(module = "sa_solver")]
pub struct RelationRun {
    frames: Py<TermFrames>,
    py_atom: Py<PyAny>,
    eq: Py<PyAny>,
    order: Py<PyAny>,
    check: Py<PyAny>,
}

impl RelationRun {
    fn run<'py>(&self, f: &TermFrames, name: &Bound<'py, PyAny>, lhs: &Bound<'py, PyAny>, rhs: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyTuple>>> {
        let p = name.py();
        if !f.relations.bind(p).contains(name)? {
            return Ok(None);
        }
        let q = match f.current_in(p)? {
            Some(q) => q,
            None => p.None().into_bound(p),
        };
        let ids = match f.ids_in(&q, "relation_atom", &PyTuple::new(p, [lhs, rhs])?)? {
            Some(ids) => ids,
            None => return Ok(None),
        };
        let name_s: String = name.extract()?;
        let is_eq = name_s == "eq" || name_s == "ne";
        f.count(p, &format!("relation_atom:{name_s}"))?;
        let branch = if is_eq { self.eq.bind(p) } else { self.order.bind(p) };
        // plant 743: an order relation is planned as its mirror (`lt` as `gt`, `le` as `ge`)
        let asked = if !is_eq && f.planted(p, "tl-run-flip")? {
            PyString::new(p, match name_s.as_str() { "lt" => "gt", "gt" => "lt", "le" => "ge", _ => "le" }).into_any()
        } else {
            name.clone()
        };
        let got = branch.call1((&q, asked, lhs, rhs, ids.get_item(0)?, ids.get_item(1)?))?;
        if f.module.bind(p).getattr(intern!(p, "CHECK"))?.get_item(0)?.is_truthy()? {
            self.check.bind(p).call1((self.py_atom.bind(p), name, lhs, rhs, &got))?;
        }
        Ok(Some(PyTuple::new(p, [got])?))
    }
}

#[pymethods]
impl RelationRun {
    fn __call__<'py>(&self, name: &Bound<'py, PyAny>, lhs: &Bound<'py, PyAny>, rhs: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyTuple>>> {
        let p = name.py();
        let f = self.frames.bind(p).borrow();
        self.run(&f, name, lhs, rhs).map_err(|e| f.guard(p, "relation_atom", e))
    }
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<TermFrames>()?;
    m.add_class::<Guarded>()?;
    m.add_class::<RelationRun>()?;
    Ok(())
}
