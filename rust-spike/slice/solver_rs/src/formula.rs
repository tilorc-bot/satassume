//! The formula step (issue 323): a Python Formula (`satassume/sat/formula.py`, input) converted ONCE into Rust nodes, as
//! `convert.py` converts terms. After `convert`, nothing here reads the Python object again: the tree, each atom
//! occurrence's `pred` and `expr`, and `atoms_of`'s result are held by the node.
//!
//! What is read, once, at the boundary: `isinstance` against the nine classes (in `to_f`'s order: `bool`, `P`, then `And`,
//! `Or`, `Not`, `Implies`, `Equivalent`, `Exclusive`, `ITE`, `_Lit`), `.args`, `_Lit.lit`, an atom's `.pred`/`.expr`, and one
//! dict lookup per atom occurrence (`P`'s hash and `==`, as `atoms_of`'s `seen` set runs them: `fm:atom_intern`).
//!
//! Refused, so the caller keeps Python's path (counted, nothing half-built is returned):
//! - deeper than `DEPTH` (`fm:refuse:depth`): the same limit as session.rs's `FORMULA_DEPTH`, so a node exists exactly when
//!   `to_f` would have converted the object;
//! - an instance of `Formula` that is none of the classes, or one whose `.args` hasn't its class's arity
//!   (`fm:refuse:class`): Python's `atoms_of` walks such an object's args and `to_f` doesn't;
//! - any `Exception` from a read (`fm:refuse:read`). A BaseException goes up.
//!
//! An object that is no formula at all stays in the tree as `Bad`, as in compile.rs: Python raises `TypeError` when
//! compilation reaches it and `atoms_of` skips it.
//!
//! Not wired into the session yet: the per-session cache of nodes belongs in `SessionCore`, which waits for state part 2
//! (iii). Counters 630-639, plants 601-606 (the formula step's ranges).
use crate::formula_py::PyP;
use pyo3::exceptions::{PyException, PyValueError};
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyList, PyTuple};
use std::cell::Cell;
use std::rc::Rc;

/// Deeper formulas compile on Python, over this same table. Python's own limit depends on the caller's stack, so it isn't
/// reproduced: its deepest shape is `Implies`, 3 frames a level (first failure at depth 330 from a bare stack, limit 1000), so
/// 64 is below what Python reaches with up to about 800 frames already on the stack.
pub(crate) const DEPTH: u32 = 64;

pub(crate) enum N {
    True,
    False,
    /// An atom occurrence: the index into `FNode::occ`.
    Atom(u32),
    Not(Rc<N>),
    And(Vec<Rc<N>>),
    Or(Vec<Rc<N>>),
    Implies(Rc<N>, Rc<N>),
    Equivalent(Vec<Rc<N>>),
    Exclusive(Vec<Rc<N>>),
    Ite(Rc<N>, Rc<N>, Rc<N>),
    Lit(i32),
    /// Not a formula: the index into `FNode::bad`.
    Bad(u32),
}

/// One occurrence of an atom. `to_f` reads each occurrence's own `expr` object (a second object for a node refuses), so the
/// occurrence keeps its own, not its first-seen equal's.
pub(crate) struct Occ {
    pub obj: Py<PyAny>,
    pub pred: Py<PyAny>,
    pub expr: Py<PyAny>,
    /// Index into `atoms`: the first-seen atom this one is `==` to.
    pub atom: u32,
}

const NAMES: [&str; 15] = [
    "fm:convert",       // 630: conversions run
    "fm:nodes",         // 631: nodes built
    "fm:atom_occ",      // 632: atom occurrences read (`.pred`, `.expr`)
    "fm:atom_intern",   // 633: `seen` lookups (P's hash and ==): input-origin keys
    "fm:refuse:depth",  // 634
    "fm:refuse:class",  // 635
    "fm:refuse:read",   // 636
    "fm:atoms",         // 637: `atoms_of` answered from a node
    "fm:plant_fired",   // 638
    "fm:bad",           // 639: non-formula objects kept as `Bad`
    "fm:cache_hit",     // 640: a session's node cache answered (no walk of the object)
    "fm:to_f",          // 641: a node walked into ids for the compiler
    "fm:atoms_py",      // 642: Python's `atoms_of` called for a refused formula
    "fm:atoms_node",    // 643: an engine `atoms_of` site answered from the session's node
    "fm:nosession",     // 644: an engine `atoms_of` site with no session at hand: converted there, kept by nothing
];
const CONVERT: usize = 0;
const NODES: usize = 1;
const ATOM_OCC: usize = 2;
const ATOM_INTERN: usize = 3;
const REFUSE_DEPTH: usize = 4;
const REFUSE_CLASS: usize = 5;
const REFUSE_READ: usize = 6;
const ATOMS: usize = 7;
const PLANT_FIRED: usize = 8;
const BAD: usize = 9;
pub(crate) const CACHE_HIT: usize = 10;
pub(crate) const TO_F: usize = 11;
pub(crate) const ATOMS_PY: usize = 12;
pub(crate) const ATOMS_NODE: usize = 13;
const NOSESSION: usize = 14;

/// Plants 601-606, each the control of one comparison in test_formula_nodes.py.
const PLANTS: [&str; 6] = [
    "fm-atoms-drop-last",  // 601: `atoms` without its last atom
    "fm-atoms-no-dedupe",  // 602: every occurrence its own atom
    "fm-args-reverse",     // 603: `And`/`Or` arguments reversed
    "fm-implies-swap",     // 604: `Implies(a, b)` read as `Implies(b, a)`
    "fm-ite-swap",         // 605: `ITE(c, a, b)` read as `ITE(c, b, a)`
    "fm-not-drop",         // 606: `Not(a)` read as `a`
];

thread_local! {
    static COUNTS: [Cell<u64>; 15] = const { [const { Cell::new(0) }; 15] };
    /// The nine classes for a site with no session: `SessionRules`' list (session_live.py `_core_rules`), read once.
    static CLASSES: std::cell::RefCell<Option<Rc<Vec<Py<PyAny>>>>> = const { std::cell::RefCell::new(None) };
    /// 0: none; else 1 + the index into `PLANTS`.
    static PLANT: Cell<u8> = const { Cell::new(0) };
}

pub(crate) fn tick(i: usize) {
    COUNTS.with(|c| c[i].set(c[i].get() + 1));
}

fn planted(i: u8) -> bool {
    let on = PLANT.with(|c| c.get()) == i + 1;
    if on {
        tick(PLANT_FIRED);
        // the bar's channel: its plants phase reads `rel:plant_fired` from the session report
        crate::session::tick(crate::session::REL_PLANT);
    }
    on
}

enum Stop {
    Refuse(usize),
    Py(PyErr),
}

impl From<PyErr> for Stop {
    fn from(e: PyErr) -> Self {
        Stop::Py(e)
    }
}

struct Walk<'a, 'py> {
    p: Python<'py>,
    classes: &'a [Py<PyAny>],
    occ: Vec<Occ>,
    firsts: Vec<Bound<'py, PyAny>>,
    seen: Bound<'py, PyDict>,
    bad: Vec<Py<PyAny>>,
    nodes: u32,
}

impl<'py> Walk<'_, 'py> {
    fn atom(&mut self, f: &Bound<'py, PyAny>, bare: bool) -> Result<N, Stop> {
        let p = self.p;
        let (pred, expr) = match f.cast::<PyP>() {
            Ok(x) => {
                let (a, b) = x.get().fields();
                (a.clone_ref(p), b.clone_ref(p))
            }
            Err(_) => (f.getattr(intern!(p, "pred"))?.unbind(), f.getattr(intern!(p, "expr"))?.unbind()),
        };
        tick(ATOM_OCC);
        // `atoms_of(P)` is `(P,)` with no hash; inside a formula, the `seen` set's lookup.
        let atom = if bare || planted(1) {
            self.firsts.push(f.clone());
            self.firsts.len() - 1
        } else {
            tick(ATOM_INTERN);
            match self.seen.get_item(f)? {
                Some(i) => i.extract()?,
                None => {
                    self.seen.set_item(f, self.firsts.len())?;
                    self.firsts.push(f.clone());
                    self.firsts.len() - 1
                }
            }
        };
        self.occ.push(Occ { obj: f.clone().unbind(), pred, expr, atom: atom as u32 });
        Ok(N::Atom(self.occ.len() as u32 - 1))
    }

    fn walk(&mut self, f: &Bound<'py, PyAny>, depth: u32) -> Result<Rc<N>, Stop> {
        let p = self.p;
        if depth > DEPTH {
            return Err(Stop::Refuse(REFUSE_DEPTH));
        }
        self.nodes += 1;
        if f.is_instance_of::<PyBool>() {
            return Ok(Rc::new(if f.is_truthy()? { N::True } else { N::False }));
        }
        if f.is_instance_of::<PyP>() || f.is_instance(self.classes[0].bind(p))? {
            return Ok(Rc::new(self.atom(f, depth == 0)?));
        }
        for i in 1..self.classes.len() {
            if !f.is_instance(self.classes[i].bind(p))? {
                continue;
            }
            if i == 8 {
                return Ok(Rc::new(N::Lit(f.getattr(intern!(p, "lit"))?.extract()?)));
            }
            let args = f.getattr(intern!(p, "args"))?.cast_into::<PyTuple>().map_err(PyErr::from)?;
            let arity = match i {
                3 => Some(1),
                4 => Some(2),
                7 => Some(3),
                _ => None,
            };
            if arity.is_some_and(|n| n != args.len()) {
                return Err(Stop::Refuse(REFUSE_CLASS));
            }
            let mut a = Vec::with_capacity(args.len());
            for x in args.iter() {
                a.push(self.walk(&x, depth + 1)?);
            }
            return Ok(Rc::new(match i {
                1 | 2 => {
                    if a.len() > 1 && planted(2) {
                        a.reverse();
                    }
                    if i == 1 { N::And(a) } else { N::Or(a) }
                }
                3 => {
                    if planted(5) {
                        return Ok(a.remove(0));
                    }
                    N::Not(a.remove(0))
                }
                4 => {
                    let y = a.remove(1);
                    let x = a.remove(0);
                    if planted(3) { N::Implies(y, x) } else { N::Implies(x, y) }
                }
                5 => N::Equivalent(a),
                6 => N::Exclusive(a),
                _ => {
                    let (z, y) = (a.remove(2), a.remove(1));
                    let c = a.remove(0);
                    if planted(4) { N::Ite(c, z, y) } else { N::Ite(c, y, z) }
                }
            }));
        }
        if f.is_instance(&p.import(intern!(p, "satassume.sat.formula"))?.getattr(intern!(p, "Formula"))?)? {
            return Err(Stop::Refuse(REFUSE_CLASS));
        }
        tick(BAD);
        self.bad.push(f.clone().unbind());
        Ok(Rc::new(N::Bad(self.bad.len() as u32 - 1)))
    }
}

/// A converted Formula. Opaque to Python but for what the tests compare.
#[pyclass(name = "FormulaNode", module = "sa_solver", unsendable)]
pub struct FNode {
    root: Rc<N>,
    occ: Vec<Occ>,
    atoms: Py<PyTuple>,
    bad: Vec<Py<PyAny>>,
    source: Py<PyAny>,
    nodes: u32,
}

impl FNode {
    /// Every object the node holds, for the collector (the session's cache keeps nodes alive).
    pub(crate) fn visit(&self, visit: &pyo3::PyVisit<'_>) -> Result<(), pyo3::PyTraverseError> {
        visit.call(&self.source)?;
        visit.call(&self.atoms)?;
        for o in &self.occ {
            visit.call(&o.obj)?;
            visit.call(&o.pred)?;
            visit.call(&o.expr)?;
        }
        for b in &self.bad {
            visit.call(b)?;
        }
        Ok(())
    }

    pub(crate) fn root(&self) -> &Rc<N> {
        &self.root
    }

    pub(crate) fn occ(&self, i: u32) -> &Occ {
        &self.occ[i as usize]
    }

    pub(crate) fn bad(&self, i: u32) -> &Py<PyAny> {
        &self.bad[i as usize]
    }

    /// `atoms_of(f)`: the first-seen atoms, the objects Python's walk returns, in its order.
    pub(crate) fn atoms_of<'py>(&self, p: Python<'py>) -> Bound<'py, PyTuple> {
        tick(ATOMS);
        self.atoms.bind(p).clone()
    }

    fn shape_of<'py>(&self, p: Python<'py>, n: &N) -> PyResult<Bound<'py, PyAny>> {
        let tagged = |tag: &str, kids: Vec<&Rc<N>>| -> PyResult<Bound<'py, PyAny>> {
            let mut v = vec![tag.into_pyobject(p)?.into_any()];
            for k in kids {
                v.push(self.shape_of(p, k)?);
            }
            Ok(PyTuple::new(p, v)?.into_any())
        };
        match n {
            N::True => Ok(PyBool::new(p, true).to_owned().into_any()),
            N::False => Ok(PyBool::new(p, false).to_owned().into_any()),
            N::Atom(k) => {
                let o = &self.occ[*k as usize];
                Ok(PyTuple::new(p, [intern!(p, "atom").clone().into_any(), o.pred.bind(p).clone(), o.expr.bind(p).clone()])?.into_any())
            }
            N::Not(a) => tagged("not", vec![a]),
            N::And(a) => tagged("and", a.iter().collect()),
            N::Or(a) => tagged("or", a.iter().collect()),
            N::Implies(a, b) => tagged("implies", vec![a, b]),
            N::Equivalent(a) => tagged("equivalent", a.iter().collect()),
            N::Exclusive(a) => tagged("exclusive", a.iter().collect()),
            N::Ite(c, a, b) => tagged("ite", vec![c, a, b]),
            N::Lit(l) => Ok(PyTuple::new(p, [intern!(p, "lit").clone().into_any(), l.into_pyobject(p)?.into_any()])?.into_any()),
            N::Bad(i) => Ok(PyTuple::new(p, [intern!(p, "bad").clone().into_any(), self.bad[*i as usize].bind(p).clone()])?.into_any()),
        }
    }
}

#[pymethods]
impl FNode {
    /// `atoms_of` of the converted formula.
    #[getter]
    fn atoms<'py>(&self, p: Python<'py>) -> Bound<'py, PyTuple> {
        self.atoms_of(p)
    }

    /// The object converted. Held so its identity can key a cache; never read again.
    #[getter]
    fn source<'py>(&self, p: Python<'py>) -> Bound<'py, PyAny> {
        self.source.bind(p).clone()
    }

    #[getter]
    fn nodes(&self) -> u32 {
        self.nodes
    }

    /// The tree as nested tuples headed by a tag, for tests: `('and', ...)`, `('atom', pred, expr)`, `('lit', n)`,
    /// `('bad', obj)`, `True`, `False`.
    fn shape<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        self.shape_of(p, &self.root)
    }

    /// Each atom occurrence in walk order: `(the occurrence's own object, its index into atoms)`.
    fn occurrences<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        let l = PyList::empty(p);
        for o in &self.occ {
            l.append((o.obj.bind(p), o.atom))?;
        }
        Ok(l)
    }
}

/// Why a conversion refused; each is counted where it is decided.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub(crate) enum Refused {
    Depth,
    Class,
    Read,
}

/// The node of `f`, or `None` where it is refused (see the module's head). `classes`: `SessionRules`' nine.
pub(crate) fn convert(f: &Bound<'_, PyAny>, classes: &[Py<PyAny>]) -> PyResult<Option<FNode>> {
    Ok(convert_or(f, classes)?.ok())
}

/// `convert`, saying why it refused.
pub(crate) fn convert_or(f: &Bound<'_, PyAny>, classes: &[Py<PyAny>]) -> PyResult<Result<FNode, Refused>> {
    let p = f.py();
    if classes.len() != 9 {
        return Err(PyValueError::new_err("formula: nine classes expected"));
    }
    tick(CONVERT);
    let mut w = Walk { p, classes, occ: Vec::new(), firsts: Vec::new(), seen: PyDict::new(p), bad: Vec::new(), nodes: 0 };
    let root = match w.walk(f, 0) {
        Ok(r) => r,
        Err(Stop::Refuse(c)) => {
            tick(c);
            return Ok(Err(if c == REFUSE_DEPTH { Refused::Depth } else { Refused::Class }));
        }
        Err(Stop::Py(e)) if e.is_instance_of::<PyException>(p) => {
            tick(REFUSE_READ);
            return Ok(Err(Refused::Read));
        }
        Err(Stop::Py(e)) => return Err(e),
    };
    COUNTS.with(|c| c[NODES].set(c[NODES].get() + u64::from(w.nodes)));
    let mut firsts = w.firsts;
    if !firsts.is_empty() && planted(0) {
        firsts.pop();
    }
    Ok(Ok(FNode { root, occ: w.occ, atoms: PyTuple::new(p, firsts)?.unbind(), bad: w.bad, source: f.clone().unbind(), nodes: w.nodes }))
}

fn classes(p: Python<'_>) -> PyResult<Rc<Vec<Py<PyAny>>>> {
    if let Some(c) = CLASSES.with(|c| c.borrow().clone()) {
        return Ok(c);
    }
    let fm = p.import(intern!(p, "satassume.sat.formula"))?;
    let mut v = Vec::with_capacity(9);
    for n in ["P", "And", "Or", "Not", "Implies", "Equivalent", "Exclusive", "ITE"] {
        v.push(fm.getattr(n)?.unbind());
    }
    v.push(p.import(intern!(p, "satassume.knowledge.compile"))?.getattr(intern!(p, "_Lit"))?.unbind());
    let c = Rc::new(v);
    CLASSES.with(|x| *x.borrow_mut() = Some(c.clone()));
    Ok(c)
}

/// Python's own `atoms_of`, for a formula the conversion refuses (`fm:atoms_py`).
pub(crate) fn atoms_py<'py>(f: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyTuple>> {
    let p = f.py();
    tick(ATOMS_PY);
    let a = p.import(intern!(p, "satassume.sat.formula"))?.getattr(intern!(p, "atoms_of"))?.call1((f,))?;
    Ok(a.cast_into::<PyTuple>()?)
}

/// `atoms_of(f)` where no session is at hand (`theory_scope`, the cones): one walk of the object here, and the node is
/// dropped. Counted (`fm:nosession`): a formula the session also converts is read twice until the entry hands nodes down.
pub(crate) fn atoms_nosession<'py>(f: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyTuple>> {
    let p = f.py();
    tick(NOSESSION);
    match convert_or(f, &classes(p)?)? {
        Ok(n) => Ok(n.atoms_of(p)),
        Err(_) => atoms_py(f),
    }
}

#[pyfunction]
fn formula_convert(f: &Bound<'_, PyAny>, classes: Vec<Py<PyAny>>) -> PyResult<Option<FNode>> {
    convert(f, &classes)
}

/// The step's counters into `d` (`formula_counts()`, and the session report's `counts`).
pub(crate) fn counts_into(d: &Bound<'_, PyDict>) -> PyResult<()> {
    COUNTS.with(|c| {
        for (i, n) in NAMES.iter().enumerate() {
            d.set_item(*n, c[i].get())?;
        }
        Ok(())
    })
}

#[pyfunction]
fn formula_counts<'py>(p: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
    let d = PyDict::new(p);
    counts_into(&d)?;
    Ok(d)
}

/// Sets the planted bug by name, or none.
#[pyfunction]
#[pyo3(signature = (name=None))]
fn formula_plant(name: Option<&str>) -> PyResult<()> {
    let i = match name {
        None => 0,
        Some(n) => 1 + PLANTS.iter().position(|x| *x == n).ok_or_else(|| PyValueError::new_err(format!("formula: no plant {n}")))? as u8,
    };
    PLANT.with(|c| c.set(i));
    Ok(())
}

#[pyfunction]
fn formula_plants() -> Vec<&'static str> {
    PLANTS.to_vec()
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // The bar's channel (bar.sh's plants phase): SLICE_SESSION_PLANT=fm-..., read once as the module loads.
    if let Ok(n) = std::env::var("SLICE_SESSION_PLANT") {
        if let Some(i) = PLANTS.iter().position(|x| *x == n) {
            PLANT.with(|c| c.set(1 + i as u8));
        }
    }
    m.add_class::<FNode>()?;
    m.add_function(wrap_pyfunction!(formula_convert, m)?)?;
    m.add_function(wrap_pyfunction!(formula_counts, m)?)?;
    m.add_function(wrap_pyfunction!(formula_plant, m)?)?;
    m.add_function(wrap_pyfunction!(formula_plants, m)?)?;
    Ok(())
}
