//! `Session`'s variable and clause surface and `VarTable`, over a session's own node ids (component 5, step 5a). Python's
//! `Session` shell (`session_live.py`), `Relations` and the templates call this through `SessionCore`. Each object becomes a
//! node id in `nids`, a Python dict, so two objects share an id exactly when Python's own `base` and `custom` dicts would
//! have joined them. No borrow is held across a callback: `node` runs templates, and they come back in.
use std::cell::{Cell, RefCell};
use std::collections::HashMap;
use std::rc::Rc;

use pyo3::exceptions::{PyException, PyKeyError, PyRecursionError, PyTypeError, PyValueError};
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyList, PySet, PyTuple};

use crate::compile::{self, block_lits, Cx, Def, Kind, Need, F, R};
use crate::formula_py::PyP;

const NAMES: [&str; 18] = [
    "py:var", "py:dvar", "py:node", "py:compile", "py:literal", "py:table", "rs:visit", "rs:add_clause", "rs:ensure_vars",
    "rs:def_implications", "rs:neg_shared", "join", "rs:emit_callback", "refuse:depth", "refuse:convert", "refuse:object", "second:visit", "custom:own",
];
const VAR: usize = 0;
const DVAR: usize = 1;
const NODE: usize = 2;
const COMPILE: usize = 3;
const LITERAL: usize = 4;
const TABLE: usize = 5;
const VISIT: usize = 6;
const ADD_CLAUSE: usize = 7;
const ENSURE: usize = 8;
const IMPL: usize = 9;
const NEG: usize = 10;
const JOIN: usize = 11;
const EMIT_CB: usize = 12;
const REFUSE_DEPTH: usize = 13;
const REFUSE_CONVERT: usize = 14;
const REFUSE_OBJECT: usize = 15;
const SECOND_VISIT: usize = 16;
const CUSTOM_OWN: usize = 17;

/// Deeper formulas compile on Python, over this same table. Python's own limit depends on the caller's stack, so it isn't
/// reproduced: its deepest shape is `Implies`, 3 frames a level (first failure at depth 330 from a bare stack, limit 1000), so
/// 64 is below what Python reaches with up to about 800 frames already on the stack.
const FORMULA_DEPTH: u32 = 64;

thread_local! {
    static COUNTS: [Cell<u64>; 18] = const { [const { Cell::new(0) }; 18] };
}

fn tick(i: usize) {
    COUNTS.with(|c| c[i].set(c[i].get() + 1));
}

/// Crossings of the boundary so far, by kind. `join` isn't a crossing: objects of different classes that a dict joined.
#[pyfunction]
fn session_counts<'py>(p: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
    let d = PyDict::new(p);
    COUNTS.with(|c| {
        for (i, n) in NAMES.iter().enumerate() {
            d.set_item(*n, c[i].get())?;
        }
        Ok::<_, PyErr>(())
    })?;
    Ok(d)
}

/// What `rules.py` says, read once at install. `impls` is a memo of a pure function of constants.
#[pyclass(unsendable)]
pub struct SessionRules {
    data: Rc<RulesData>,
}

struct RulesData {
    basis: Vec<Py<PyAny>>,
    index: HashMap<String, u32>,
    kinds: Vec<Kind>,
    names: Vec<Py<PyAny>>,
    classes: Vec<Py<PyAny>>,
    def_implications: Py<PyAny>,
    impls: RefCell<HashMap<(Def, Def), Rc<Vec<(i32, i32)>>>>,
}

#[pymethods]
impl SessionRules {
    /// `classes`: `P`, `And`, `Or`, `Not`, `Implies`, `Equivalent`, `Exclusive`, `ITE`, `_Lit`.
    #[new]
    fn new(basis: Bound<'_, PyAny>, def_lits: Bound<'_, PyDict>, classes: Vec<Py<PyAny>>, def_implications: Py<PyAny>) -> PyResult<Self> {
        let (mut index, mut kinds, mut names, mut b) = (HashMap::new(), vec![], vec![], vec![]);
        for (i, x) in basis.try_iter()?.enumerate() {
            let x = x?;
            index.insert(x.extract::<String>()?, i as u32);
            kinds.push(Kind::Basis(i as u32));
            names.push(x.clone().unbind());
            b.push(x.unbind());
        }
        for (k, v) in def_lits.iter() {
            let (op, ls): (String, Vec<i32>) = v.extract()?;
            index.insert(k.extract::<String>()?, kinds.len() as u32);
            kinds.push(Kind::Derived(Rc::new((op == "&", ls))));
            names.push(k.unbind());
        }
        Ok(SessionRules { data: Rc::new(RulesData { basis: b, index, kinds, names, classes, def_implications, impls: RefCell::new(HashMap::new()) }) })
    }
}

#[derive(Clone, Copy)]
enum Slot {
    Aux,
    Block(u32, i32),
    Custom(u32, u32),
}

/// `VarTable`, plus `Session.base` and the memos of `var` and `dvar`.
struct St {
    base_of: Vec<i32>,
    base: Vec<i32>,
    slots: Vec<Slot>,
    new_nodes: Vec<u32>,
    custom: HashMap<(u32, u32), i32>,
    new_custom: Vec<(u32, u32)>,
    naux: u32,
    true_var: Option<i32>,
    defvars: HashMap<(u32, u32), i32>,
    dv: HashMap<(Def, u32), (i32, i32, bool)>,
    dv_node: HashMap<u32, Vec<(Def, i32)>>,
}

impl St {
    fn node_base(&mut self, nid: u32) -> i32 {
        let n = nid as usize;
        if self.base_of.len() <= n {
            self.base_of.resize(n + 1, 0);
        }
        if self.base_of[n] != 0 {
            return self.base_of[n];
        }
        let b = self.slots.len() as i32;
        self.base_of[n] = b;
        self.slots.extend(std::iter::repeat_n(Slot::Block(nid, b), NPRED.with(Cell::get)));
        self.new_nodes.push(nid);
        b
    }

    fn aux(&mut self) -> i32 {
        let v = self.slots.len() as i32;
        self.slots.push(Slot::Aux);
        self.naux += 1;
        v
    }

    fn visited(&self, nid: u32) -> i32 {
        self.base.get(nid as usize).copied().unwrap_or(0)
    }
}

thread_local! {
    static NPRED: Cell<usize> = const { Cell::new(0) };
}

#[pyclass(unsendable, frozen)]
pub struct SessionCore {
    rules: Rc<RulesData>,
    /// A weak reference to the shell: the shell reaches this object and the solver reaches the shell through its theories,
    /// and a strong one here is an edge the collector can't see.
    shell: Py<PyAny>,
    nids: Py<PyDict>,
    /// The object per node id, as Python's slots keep it: the one passed to `node_base`, so it can still change until then.
    objs: RefCell<Vec<Py<PyAny>>>,
    /// Set when a conversion refuses for `second_object`, which `convert` counts.
    refused_object: Cell<bool>,
    bad: RefCell<Vec<Py<PyAny>>>,
    /// Custom predicates: a dict, because Python's table takes any hashable there, joined as a dict joins them.
    custom_ids: Py<PyDict>,
    custom_preds: RefCell<Vec<Py<PyAny>>>,
    /// Each custom atom's own expr: an `Args` and a `Tuple` are `==`, so one node, and the node's object isn't the atom's.
    custom_exprs: RefCell<HashMap<(u32, u32), Py<PyAny>>>,
    st: RefCell<St>,
}

impl SessionCore {
    fn shell<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        self.shell.bind(p).call0()
    }

    /// The id of an object about to reach `node_base`, or passed where Python's table would take it: with no slot yet, this
    /// is the object the slot will hold.
    fn nid_of(&self, x: &Bound<'_, PyAny>) -> PyResult<u32> {
        if let Some(n) = self.known(x)? {
            if self.second_object(x, n) {
                self.objs.borrow_mut()[n as usize] = x.clone().unbind();
            }
            return Ok(n);
        }
        let mut objs = self.objs.borrow_mut();
        let n = objs.len() as u32;
        objs.push(x.clone().unbind());
        self.nids.bind(x.py()).set_item(x, n)?;
        Ok(n)
    }

    /// `nid_of` for an atom's expr. A custom atom takes no slot on Python, so it doesn't choose the object one will hold.
    fn nid_of_atom(&self, p: Python<'_>, pred: u32, x: &Bound<'_, PyAny>) -> PyResult<u32> {
        match (self.kind_of(p, pred), self.known(x)?) {
            (Kind::Custom, Some(n)) => Ok(n),
            _ => self.nid_of(x),
        }
    }

    /// `x` is `==` to the object held for node `n`, isn't that object, and `n` has no slot yet, so which one the slot holds
    /// depends on the order `node_base` is reached. Python keeps the first passed there, and `Pow`'s `same` row reads identity.
    fn second_object(&self, x: &Bound<'_, PyAny>, n: u32) -> bool {
        !self.objs.borrow()[n as usize].bind(x.py()).is(x)
            && self.st.borrow().base_of.get(n as usize).copied().unwrap_or(0) == 0
    }

    /// `nid_of` for an atom in a formula being converted. Conversion walks the formula and compiling may reach its atoms in
    /// another order, and a node with no visit yet may be visited from here, where Python visits the atom's own object. So a
    /// second object for a node with no visit refuses, before anything is emitted, and Python's compiler passes them in its
    /// own order over this same table.
    fn nid_in_formula(&self, x: &Bound<'_, PyAny>) -> PyResult<u32> {
        if let Some(n) = self.known(x)? {
            if !self.objs.borrow()[n as usize].bind(x.py()).is(x) && self.st.borrow().visited(n) == 0 {
                return Err(self.refuse_object());
            }
            return Ok(n);
        }
        self.nid_of(x)
    }

    fn refuse_object(&self) -> PyErr {
        self.refused_object.set(true);
        PyValueError::new_err("a second object for a node with no visit")
    }

    /// A custom atom's own expr reaching a direct entry: Python's `custom` keeps the first atom to reach `table.var`, so with
    /// no variable yet this is the one it would keep, and with one nothing changes.
    fn custom_expr(&self, pred: u32, nid: u32, x: &Bound<'_, PyAny>) {
        if matches!(self.kind_of(x.py(), pred), Kind::Custom) && !self.st.borrow().custom.contains_key(&(pred, nid)) {
            self.custom_exprs.borrow_mut().insert((pred, nid), x.clone().unbind());
        }
    }

    /// The same in a formula being converted, which may reach its atoms in another order: a different expr with no variable
    /// yet refuses, as a second object does.
    fn custom_in_formula(&self, pred: u32, nid: u32, x: &Bound<'_, PyAny>) -> PyResult<()> {
        if !matches!(self.kind_of(x.py(), pred), Kind::Custom) || self.st.borrow().custom.contains_key(&(pred, nid)) {
            return Ok(());
        }
        let mut exprs = self.custom_exprs.borrow_mut();
        match exprs.get(&(pred, nid)) {
            Some(o) if !o.bind(x.py()).is(x) => Err(self.refuse_object()),
            Some(_) => Ok(()),
            None => {
                exprs.insert((pred, nid), x.clone().unbind());
                Ok(())
            }
        }
    }

    fn known(&self, x: &Bound<'_, PyAny>) -> PyResult<Option<u32>> {
        let Some(v) = self.nids.bind(x.py()).get_item(x)? else { return Ok(None) };
        let n: u32 = v.extract()?;
        if !self.objs.borrow()[n as usize].bind(x.py()).get_type().is(x.get_type()) {
            tick(JOIN);
        }
        Ok(Some(n))
    }

    fn pred_id(&self, p: Python<'_>, pred: &Bound<'_, PyAny>) -> PyResult<u32> {
        let r = &self.rules;
        if let Ok(s) = pred.extract::<String>() {
            if let Some(&i) = r.index.get(&s) {
                return Ok(i);
            }
        }
        let ids = self.custom_ids.bind(p);
        if let Some(v) = ids.get_item(pred)? {
            return v.extract();
        }
        let mut c = self.custom_preds.borrow_mut();
        let i = (r.kinds.len() + c.len()) as u32;
        ids.set_item(pred, i)?;
        c.push(pred.clone().unbind());
        Ok(i)
    }

    fn pred_name<'py>(&self, p: Python<'py>, i: u32) -> Bound<'py, PyAny> {
        let r = &self.rules;
        let i = i as usize;
        if i < r.names.len() {
            r.names[i].bind(p).clone()
        } else {
            self.custom_preds.borrow()[i - r.names.len()].bind(p).clone()
        }
    }

    fn kind_of(&self, _p: Python<'_>, i: u32) -> Kind {
        self.rules.kinds.get(i as usize).cloned().unwrap_or(Kind::Custom)
    }

    fn atom_fields<'py>(&self, a: &Bound<'py, PyAny>) -> PyResult<(u32, Bound<'py, PyAny>)> {
        let p = a.py();
        if let Ok(x) = a.cast::<PyP>() {
            let (pred, expr) = x.get().fields();
            return Ok((self.pred_id(p, pred.bind(p))?, expr.bind(p).clone()));
        }
        Ok((self.pred_id(p, &a.getattr(intern!(p, "pred"))?)?, a.getattr(intern!(p, "expr"))?))
    }

    fn to_f(&self, f: &Bound<'_, PyAny>, depth: u32) -> PyResult<R> {
        let p = f.py();
        if depth > FORMULA_DEPTH {
            return Err(PyRecursionError::new_err("formula deeper than Rust compiles"));
        }
        if f.is_instance_of::<PyBool>() {
            return Ok(Rc::new(if f.is_truthy()? { F::True } else { F::False }));
        }
        let c = &self.rules.classes;
        if f.is_instance_of::<PyP>() || f.is_instance(c[0].bind(p))? {
            let (pred, expr) = self.atom_fields(f)?;
            let n = self.nid_in_formula(&expr)?;
            self.custom_in_formula(pred, n, &expr)?;
            return Ok(Rc::new(F::Atom(pred, n)));
        }
        let args = |f: &Bound<'_, PyAny>| -> PyResult<Vec<R>> {
            let a = f.getattr(intern!(p, "args"))?;
            let t = a.cast::<PyTuple>()?;
            t.iter().map(|x| self.to_f(&x, depth + 1)).collect()
        };
        for (i, cls) in c.iter().enumerate().skip(1) {
            if !f.is_instance(cls.bind(p))? {
                continue;
            }
            if i == 8 {
                return Ok(Rc::new(F::Lit(f.getattr(intern!(p, "lit"))?.extract()?)));
            }
            let mut a = args(f)?;
            return Ok(Rc::new(match i {
                1 => F::And(a),
                2 => F::Or(a),
                3 => F::Not(a.remove(0)),
                4 => {
                    let y = a.remove(1);
                    F::Implies(a.remove(0), y)
                }
                5 => F::Equivalent(a),
                6 => F::Exclusive(a),
                _ => {
                    let (z, y) = (a.remove(2), a.remove(1));
                    F::Ite(a.remove(0), y, z)
                }
            }));
        }
        let mut b = self.bad.borrow_mut();
        b.push(f.clone().unbind());
        Ok(Rc::new(F::Bad(b.len() as u32 - 1)))
    }

    /// The formula over ids, or `None` for Python to compile it: too deep, or any error reading it. Nothing has been emitted
    /// yet, so Python's compiler raises what it raises, where it raises it. A BaseException isn't an answer and goes up.
    fn convert(&self, f: &Bound<'_, PyAny>) -> PyResult<Option<R>> {
        let p = f.py();
        match self.to_f(f, 0) {
            Ok(r) => Ok(Some(r)),
            Err(e) if e.is_instance_of::<PyException>(p) => {
                tick(if self.refused_object.take() {
                    REFUSE_OBJECT
                } else if e.is_instance_of::<PyRecursionError>(p) {
                    REFUSE_DEPTH
                } else {
                    REFUSE_CONVERT
                });
                Ok(None)
            }
            Err(e) => Err(e),
        }
    }

    fn emit(&self, p: Python<'_>, clause: &[i32]) -> PyResult<()> {
        tick(ADD_CLAUSE);
        let s = self.shell(p)?.getattr(intern!(p, "solver"))?;
        s.call_method1(intern!(p, "add_clause"), (PyList::new(p, clause)?,))?;
        Ok(())
    }

    fn ensure_vars(&self, p: Python<'_>, v: i32) -> PyResult<()> {
        tick(ENSURE);
        self.shell(p)?.getattr(intern!(p, "solver"))?.call_method1(intern!(p, "ensure_vars"), (v,))?;
        Ok(())
    }

    /// `Session.node` with `demanded=None`. Python visits the object passed, whichever one the slot holds; `passed` is that
    /// object, and `None` is a formula's atom, which conversion has refused unless it's the one in `objs` or already visited.
    fn node_id(&self, p: Python<'_>, nid: u32, passed: Option<&Bound<'_, PyAny>>) -> PyResult<i32> {
        let b = self.st.borrow().visited(nid);
        if b != 0 {
            return Ok(b);
        }
        if let Some(o) = passed {
            if !self.objs.borrow()[nid as usize].bind(p).is(o) {
                tick(SECOND_VISIT);
            }
            return self.visit_id(o, nid, p.None().bind(p));
        }
        let o = self.objs.borrow()[nid as usize].clone_ref(p);
        self.visit_id(o.bind(p), nid, p.None().bind(p))
    }

    fn visit_id(&self, node: &Bound<'_, PyAny>, nid: u32, demanded: &Bound<'_, PyAny>) -> PyResult<i32> {
        let p = node.py();
        let b = {
            let mut st = self.st.borrow_mut();
            let b = st.node_base(nid);
            let n = nid as usize;
            if st.base.len() <= n {
                st.base.resize(n + 1, 0);
            }
            st.base[n] = b;
            st.new_nodes.clear();
            b
        };
        tick(VISIT);
        self.shell(p)?.call_method1(intern!(p, "_core_visit"), (node, b, demanded))?;
        Ok(b)
    }

    fn var_id(&self, p: Python<'_>, pred: u32, nid: u32, passed: &Bound<'_, PyAny>, name: impl FnOnce() -> PyErr) -> PyResult<i32> {
        match self.kind_of(p, pred) {
            Kind::Basis(i) => Ok(self.node_id(p, nid, Some(passed))? + i as i32),
            Kind::Custom => Err(name()),
            Kind::Derived(d) => {
                if d.1.len() > 1 {
                    return self.dvar_raw(p, &d, nid, Some(passed), 3, false);
                }
                if let Some(&v) = self.st.borrow().defvars.get(&(pred, nid)) {
                    return Ok(v);
                }
                let b = self.node_id(p, nid, Some(passed))?;
                let lits = block_lits(b, &d.1);
                let v = {
                    let mut st = self.st.borrow_mut();
                    let v = st.aux();
                    st.defvars.insert((pred, nid), v);
                    v
                };
                self.ensure_vars(p, v)?;
                if d.0 {
                    for &l in &lits {
                        self.emit(p, &[-v, l])?;
                    }
                    let mut c = vec![v];
                    c.extend(lits.iter().map(|l| -l));
                    self.emit(p, &c)
                } else {
                    for &l in &lits {
                        self.emit(p, &[-l, v])?;
                    }
                    let mut c = vec![-v];
                    c.extend_from_slice(&lits);
                    self.emit(p, &c)
                }?;
                Ok(v)
            }
        }
    }

    /// `Session._dvar`. Python reads the memo before visiting and allocates on what it read, so a visit that made the same key
    /// is overwritten; a key that was there is read again after, because the Python holds its list.
    fn dvar_raw(&self, p: Python<'_>, d: &Def, nid: u32, passed: Option<&Bound<'_, PyAny>>, need: i32, link: bool) -> PyResult<i32> {
        let key = (d.clone(), nid);
        let had = self.st.borrow().dv.contains_key(&key);
        let b = self.node_id(p, nid, passed)?;
        if !had {
            let v = {
                let mut st = self.st.borrow_mut();
                let v = st.aux();
                st.dv.insert(key.clone(), (v, 0, false));
                v
            };
            self.ensure_vars(p, v)?;
        }
        let (v, have, linked) = self.st.borrow().dv[&key];
        if link && !linked {
            self.st.borrow_mut().dv.get_mut(&key).expect("just read").2 = true;
            self.link(p, d, nid, v)?;
        }
        let missing = need & !have;
        if missing != 0 {
            let lits = block_lits(b, &d.1);
            if d.0 {
                if missing & 1 != 0 {
                    for &l in &lits {
                        self.emit(p, &[-v, l])?;
                    }
                }
                if missing & 2 != 0 {
                    let mut c = vec![v];
                    c.extend(lits.iter().map(|l| -l));
                    self.emit(p, &c)?;
                }
            } else {
                if missing & 2 != 0 {
                    for &l in &lits {
                        self.emit(p, &[-l, v])?;
                    }
                }
                if missing & 1 != 0 {
                    let mut c = vec![-v];
                    c.extend_from_slice(&lits);
                    self.emit(p, &c)?;
                }
            }
            self.st.borrow_mut().dv.get_mut(&key).expect("just read").1 = have | need;
        }
        Ok(v)
    }

    fn implications(&self, p: Python<'_>, a: &Def, b: &Def) -> PyResult<Rc<Vec<(i32, i32)>>> {
        let r = &self.rules;
        let key = (a.clone(), b.clone());
        if let Some(x) = r.impls.borrow().get(&key) {
            return Ok(x.clone());
        }
        tick(IMPL);
        let t = |d: &Def| -> PyResult<Py<PyTuple>> {
            let ls = PyTuple::new(p, d.1.iter().copied())?;
            Ok(PyTuple::new(p, [(if d.0 { "&" } else { "|" }).into_pyobject(p)?.into_any(), ls.into_any()])?.unbind())
        };
        let got: Vec<(i32, i32)> = r.def_implications.bind(p).call1((t(a)?, t(b)?))?.extract()?;
        let got = Rc::new(got);
        r.impls.borrow_mut().insert(key, got.clone());
        Ok(got)
    }

    /// `Session._link`.
    fn link(&self, p: Python<'_>, d: &Def, nid: u32, v: i32) -> PyResult<()> {
        let others: Vec<(Def, i32)> = {
            let mut st = self.st.borrow_mut();
            let o = st.dv_node.entry(nid).or_default();
            if o.iter().any(|(d2, v2)| *v2 == v && d2 == d) {
                return Ok(());
            }
            o.clone()
        };
        let own = |l: i32| d.1.iter().any(|x| x.abs() == l.abs());
        for (d2, v2) in &others {
            if d.1.len() == 1 && (d2.1.len() == 1 || d.1.iter().all(|x| d2.1.iter().any(|y| y.abs() == x.abs()))) {
                continue;
            }
            if d2.1.len() == 1 && own(d2.1[0]) {
                continue;
            }
            for &(s1, s2) in self.implications(p, d, d2)?.iter() {
                self.emit(p, &[s1 * v, s2 * *v2])?;
            }
        }
        self.st.borrow_mut().dv_node.entry(nid).or_default().push((d.clone(), v));
        Ok(())
    }

    fn table_var(&self, p: Python<'_>, pred: u32, nid: u32) -> PyResult<i32> {
        match self.kind_of(p, pred) {
            Kind::Basis(i) => Ok(self.st.borrow_mut().node_base(nid) + i as i32),
            Kind::Derived(_) => {
                Err(PyValueError::new_err(format!("derived predicate {} has no variable", self.pred_name(p, pred).repr()?)))
            }
            Kind::Custom => {
                let mut st = self.st.borrow_mut();
                if let Some(&v) = st.custom.get(&(pred, nid)) {
                    return Ok(v);
                }
                let v = st.slots.len() as i32;
                st.custom.insert((pred, nid), v);
                st.slots.push(Slot::Custom(pred, nid));
                st.new_custom.push((pred, nid));
                Ok(v)
            }
        }
    }

    fn make_atom<'py>(&self, p: Python<'py>, pred: u32, nid: u32) -> PyResult<Bound<'py, PyAny>> {
        let o = self.objs.borrow()[nid as usize].clone_ref(p);
        self.rules.classes[0].bind(p).call1((self.pred_name(p, pred), o))
    }

    /// `slots[v]` of a custom atom. Every route to its variable records the expr first.
    fn custom_atom<'py>(&self, p: Python<'py>, pred: u32, nid: u32) -> PyResult<Bound<'py, PyAny>> {
        let o = self.custom_exprs.borrow()[&(pred, nid)].clone_ref(p);
        if !self.objs.borrow()[nid as usize].bind(p).is(&o) {
            tick(CUSTOM_OWN);
        }
        self.rules.classes[0].bind(p).call1((self.pred_name(p, pred), o))
    }

    /// `Session.dvar` for a derived atom.
    fn dvar_def(&self, p: Python<'_>, d: &Def, nid: u32, passed: Option<&Bound<'_, PyAny>>, need: Need) -> PyResult<Option<i32>> {
        let need = match need {
            Need::NegUnit | Need::PosUnit => {
                tick(NEG);
                let on = self.shell(p)?.getattr(intern!(p, "_neg_shared"))?.is_truthy()?;
                if !on || d.1.len() < 2 {
                    return Ok(None);
                }
                if need == Need::NegUnit {
                    Need::Neg
                } else {
                    Need::Pos
                }
            }
            n => n,
        };
        if d.1.len() == 1 {
            let b = self.node_id(p, nid, passed)?;
            let v = block_lits(b, &d.1)[0];
            self.link(p, d, nid, v)?;
            return Ok(Some(v));
        }
        let mask = match need {
            Need::Both => 3,
            Need::Pos => 1,
            _ => 2,
        };
        self.dvar_raw(p, d, nid, passed, mask, true).map(Some)
    }
}

struct PyCx<'a, 'py> {
    core: &'a SessionCore,
    p: Python<'py>,
    /// The caller's own `emit`, when it isn't `Session.emit`.
    via: Option<Bound<'py, PyAny>>,
    use_dv: bool,
}

impl Cx for PyCx<'_, '_> {
    type E = PyErr;

    fn kind(&self, pred: u32) -> Kind {
        self.core.kind_of(self.p, pred)
    }

    fn node_base(&mut self, nid: u32) -> i32 {
        self.core.st.borrow_mut().node_base(nid)
    }

    fn var(&mut self, pred: u32, nid: u32) -> PyResult<i32> {
        self.core.table_var(self.p, pred, nid)
    }

    fn aux(&mut self) -> i32 {
        self.core.st.borrow_mut().aux()
    }

    fn true_var(&self) -> Option<i32> {
        self.core.st.borrow().true_var
    }

    fn set_true_var(&mut self, v: i32) {
        self.core.st.borrow_mut().true_var = Some(v);
    }

    fn emit(&mut self, clause: Vec<i32>) -> PyResult<()> {
        if let Some(via) = &self.via {
            tick(EMIT_CB);
            via.call1((PyList::new(self.p, &clause)?,))?;
            return Ok(());
        }
        self.core.emit(self.p, &clause)
    }

    fn has_dv(&self) -> bool {
        self.use_dv
    }

    fn dv(&mut self, d: &Def, nid: u32, need: Need) -> PyResult<Option<i32>> {
        self.core.dvar_def(self.p, d, nid, None, need)
    }

    fn dv_basis(&mut self, pred: u32, nid: u32) -> PyResult<i32> {
        let v = self.core.table_var(self.p, pred, nid)?;
        if let Kind::Basis(i) = self.core.kind_of(self.p, pred) {
            self.core.link(self.p, &Rc::new((true, vec![i as i32 + 1])), nid, v)?;
        }
        Ok(v)
    }

    fn bad(&mut self, i: u32, literal: bool) -> PyErr {
        let what = if literal { "cannot make a literal from" } else { "cannot compile" };
        let shown = match self.core.bad.borrow().get(i as usize) {
            Some(o) => o.bind(self.p).repr().map(|r| r.to_string()).unwrap_or_default(),
            None => "_Lit".to_string(),
        };
        PyTypeError::new_err(format!("{what} {shown}"))
    }
}

#[pymethods]
impl SessionCore {
    #[new]
    fn new(p: Python<'_>, rules: PyRef<'_, SessionRules>, shell: Py<PyAny>) -> PyResult<Self> {
        NPRED.with(|n| n.set(rules.data.basis.len()));
        Ok(SessionCore {
            rules: rules.data.clone(),
            shell,
            nids: PyDict::new(p).unbind(),
            objs: RefCell::new(vec![]),
            refused_object: Cell::new(false),
            bad: RefCell::new(vec![]),
            custom_ids: PyDict::new(p).unbind(),
            custom_preds: RefCell::new(vec![]),
            custom_exprs: RefCell::new(HashMap::new()),
            st: RefCell::new(St {
                base_of: vec![],
                base: vec![],
                slots: vec![Slot::Aux],
                new_nodes: vec![],
                custom: HashMap::new(),
                new_custom: vec![],
                naux: 0,
                true_var: None,
                defvars: HashMap::new(),
                dv: HashMap::new(),
                dv_node: HashMap::new(),
            }),
        })
    }

    fn var(&self, pred: &Bound<'_, PyAny>, node: &Bound<'_, PyAny>) -> PyResult<i32> {
        tick(VAR);
        let p = pred.py();
        let (i, n) = (self.pred_id(p, pred)?, self.nid_of(node)?);
        self.var_id(p, i, n, node, || PyKeyError::new_err(pred.clone().unbind()))
    }

    #[pyo3(signature = (dn, need="both"))]
    fn dvar(&self, dn: &Bound<'_, PyAny>, need: &str) -> PyResult<Option<i32>> {
        tick(DVAR);
        let p = dn.py();
        if need == "basis" {
            let (i, e) = self.atom_fields(dn)?;
            let n = self.nid_of_atom(p, i, &e)?;
            self.custom_expr(i, n, &e);
            let mut cx = PyCx { core: self, p, via: None, use_dv: true };
            return cx.dv_basis(i, n).map(Some);
        }
        let (d, node): (Bound<'_, PyAny>, Bound<'_, PyAny>) = dn.extract()?;
        let (op, ls): (String, Vec<i32>) = d.extract()?;
        let need = match need {
            "pos" => Need::Pos,
            "neg" => Need::Neg,
            "posunit" => Need::PosUnit,
            "negunit" => Need::NegUnit,
            _ => Need::Both,
        };
        self.dvar_def(p, &Rc::new((op == "&", ls)), self.nid_of(&node)?, Some(&node), need)
    }

    /// `_dvar` as Python's `var` and tests call it.
    #[pyo3(signature = (d, node, need, link=false))]
    fn dvar_raw_py(&self, d: &Bound<'_, PyAny>, node: &Bound<'_, PyAny>, need: i32, link: bool) -> PyResult<i32> {
        tick(DVAR);
        let (op, ls): (String, Vec<i32>) = d.extract()?;
        self.dvar_raw(d.py(), &Rc::new((op == "&", ls)), self.nid_of(node)?, Some(node), need, link)
    }

    fn base_get(&self, node: &Bound<'_, PyAny>) -> PyResult<Option<i32>> {
        tick(NODE);
        Ok(self.known(node)?.map(|n| self.st.borrow().visited(n)).filter(|&b| b != 0))
    }

    /// `Session.node`'s path for a node not visited yet.
    fn visit(&self, node: &Bound<'_, PyAny>, demanded: &Bound<'_, PyAny>) -> PyResult<i32> {
        tick(NODE);
        let n = self.nid_of(node)?;
        self.visit_id(node, n, demanded)
    }

    /// `compile_formula`; false if Python has to compile it. `via`: the caller's `emit`, when it isn't `Session.emit`.
    #[pyo3(signature = (f, via, use_dv))]
    fn compile(&self, f: &Bound<'_, PyAny>, via: Option<Bound<'_, PyAny>>, use_dv: bool) -> PyResult<bool> {
        tick(COMPILE);
        let Some(r) = self.convert(f)? else { return Ok(false) };
        compile::compile(&r, &mut PyCx { core: self, p: f.py(), via, use_dv })?;
        Ok(true)
    }

    /// `formula_literal`; `None` if Python has to compile it.
    #[pyo3(signature = (f, via, use_dv))]
    fn literal(&self, f: &Bound<'_, PyAny>, via: Option<Bound<'_, PyAny>>, use_dv: bool) -> PyResult<Option<i32>> {
        tick(LITERAL);
        let Some(r) = self.convert(f)? else { return Ok(None) };
        compile::literal(&r, &mut PyCx { core: self, p: f.py(), via, use_dv }).map(Some)
    }

    // ---- `VarTable`'s surface, for the shell's view

    fn table_var_py(&self, a: &Bound<'_, PyAny>) -> PyResult<i32> {
        tick(TABLE);
        let (i, e) = self.atom_fields(a)?;
        let n = self.nid_of_atom(a.py(), i, &e)?;
        self.custom_expr(i, n, &e);
        self.table_var(a.py(), i, n)
    }

    fn aux(&self) -> i32 {
        tick(TABLE);
        self.st.borrow_mut().aux()
    }

    fn node_base(&self, node: &Bound<'_, PyAny>) -> PyResult<i32> {
        tick(TABLE);
        let n = self.nid_of(node)?;
        Ok(self.st.borrow_mut().node_base(n))
    }

    fn base_of_get(&self, node: &Bound<'_, PyAny>) -> PyResult<Option<i32>> {
        tick(TABLE);
        Ok(self.known(node)?.and_then(|n| self.st.borrow().base_of.get(n as usize).copied()).filter(|&b| b != 0))
    }

    fn custom_get(&self, a: &Bound<'_, PyAny>) -> PyResult<Option<i32>> {
        tick(TABLE);
        let (i, e) = self.atom_fields(a)?;
        let Some(n) = self.known(&e)? else { return Ok(None) };
        Ok(self.st.borrow().custom.get(&(i, n)).copied())
    }

    fn n_vars(&self) -> usize {
        tick(TABLE);
        self.st.borrow().slots.len() - 1
    }

    fn n_base(&self) -> usize {
        tick(TABLE);
        self.st.borrow().base.iter().filter(|&&b| b != 0).count()
    }

    fn naux(&self) -> u32 {
        self.st.borrow().naux
    }

    fn set_true_var(&self, v: i32) {
        tick(TABLE);
        self.st.borrow_mut().true_var = Some(v);
    }

    fn true_var(&self) -> Option<i32> {
        self.st.borrow().true_var
    }

    /// `slots[v]`: None, the custom atom, or `(node, base)`.
    fn slot<'py>(&self, p: Python<'py>, v: usize) -> PyResult<Bound<'py, PyAny>> {
        tick(TABLE);
        let s = self.st.borrow().slots[v];
        match s {
            Slot::Aux => Ok(p.None().into_bound(p)),
            Slot::Custom(i, n) => self.custom_atom(p, i, n),
            Slot::Block(n, b) => {
                let o = self.objs.borrow()[n as usize].clone_ref(p);
                Ok(PyTuple::new(p, [o.into_bound(p), b.into_pyobject(p)?.into_any()])?.into_any())
            }
        }
    }

    /// `atom(v)`.
    fn atom<'py>(&self, p: Python<'py>, v: usize) -> PyResult<Bound<'py, PyAny>> {
        let s = self.st.borrow().slots[v];
        match s {
            Slot::Aux => Ok(p.None().into_bound(p)),
            Slot::Custom(i, n) => self.custom_atom(p, i, n),
            Slot::Block(n, b) => self.make_atom(p, v as u32 - b as u32, n),
        }
    }

    fn new_nodes<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        tick(TABLE);
        let objs = self.objs.borrow();
        let st = self.st.borrow();
        PyList::new(p, st.new_nodes.iter().map(|&n| objs[n as usize].clone_ref(p)))
    }

    fn clear_new_nodes(&self) {
        tick(TABLE);
        self.st.borrow_mut().new_nodes.clear();
    }

    fn new_custom<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        tick(TABLE);
        let got = self.st.borrow().new_custom.clone();
        let mut out = Vec::with_capacity(got.len());
        for (i, n) in got {
            out.push(self.custom_atom(p, i, n)?);
        }
        PyList::new(p, out)
    }

    fn clear_new_custom(&self) {
        tick(TABLE);
        self.st.borrow_mut().new_custom.clear();
    }

    fn has_new_custom(&self) -> bool {
        tick(TABLE);
        !self.st.borrow().new_custom.is_empty()
    }
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<SessionRules>()?;
    m.add_class::<SessionCore>()?;
    m.add_function(wrap_pyfunction!(session_counts, m)?)
}
