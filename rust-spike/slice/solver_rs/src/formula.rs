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
use std::collections::HashMap;
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

const NAMES: [&str; 20] = [
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
    "fm:nosession",     // 644: a scope or cone function entered by name from inside a Rust entry: no node was handed to it
    "fm:twice",         // 645: an object converted a second time inside one outermost entry
    "fm:give",          // 646: nodes an entry handed to a session
    "cls:eq",           // 670: `same_class`: two class objects with one id in the query's class table
    "cls:differs",      // 671: `same_class`: two class objects, not one class to the query
    "same:eq",          // 672: wiring's 'same' shape or the Pow key met two equal, distinct objects (`==`, not `is`)
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
const PLANTS: [&str; 11] = [
    "fm-atoms-drop-last",  // 601: `atoms` without its last atom
    "fm-atoms-no-dedupe",  // 602: every occurrence its own atom
    "fm-args-reverse",     // 603: `And`/`Or` arguments reversed
    "fm-implies-swap",     // 604: `Implies(a, b)` read as `Implies(b, a)`
    "fm-ite-swap",         // 605: `ITE(c, a, b)` read as `ITE(c, b, a)`
    "fm-not-drop",         // 606: `Not(a)` read as `a`
    "ad-lra-class-is",     // 660: adapters.rs `Reader.id` compares the row's class by identity again (sa-port-235's)
    "class-is",            // 661: `same_class` by identity again, at every site, Rust's and term_live's
    "ad-lra-atom-object",  // 662: a native reader result holds the atom's own object, not the query's first (its row)
    "same-is",             // 663: wiring's 'same' shape and the Pow key's `b == e` by identity again (rows_tpl.rs)
    "fm-hand-no-give",     // 607: `Hand::give` hands nothing over
];

thread_local! {
    static COUNTS: [Cell<u64>; 20] = const { [const { Cell::new(0) }; 20] };
    /// The nine classes for a site with no session: `SessionRules`' list (session_live.py `_core_rules`), read once.
    static CLASSES: std::cell::RefCell<Option<Rc<Vec<Py<PyAny>>>>> = const { std::cell::RefCell::new(None) };
    /// 0: none; else 1 + the index into `PLANTS`.
    static PLANT: Cell<u8> = const { Cell::new(0) };
    /// How many `Hand`s are live on this thread's stack: 0 outside any entry.
    static ENTRIES: Cell<u32> = const { Cell::new(0) };
    /// The objects converted since the outermost entry began, held until it ends (`fm:twice` only; nothing reads a node here).
    static SEEN: std::cell::RefCell<HashMap<usize, Py<PyAny>>> = std::cell::RefCell::new(HashMap::new());
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

const TWICE: usize = 15;
const GIVE: usize = 16;
const CLS_EQ: usize = 17;
const CLS_DIFFERS: usize = 18;
const SAME_EQ: usize = 19;
/// Plant 607: the entry hands no node to the session, which converts the query's formulas again (`fm:twice`).
const HAND_NO_GIVE: u8 = 10;
pub(crate) const AD_LRA_CLASS_IS: u8 = 6;
const CLASS_IS: u8 = 7;
const AD_LRA_ATOM_OBJECT: u8 = 8;
const SAME_IS: u8 = 9;

/// Whether plant `i` is set, not counted: for a plant that fires only where it changes something (`plant_fired`).
fn plant_set(i: u8) -> bool {
    PLANT.with(|c| c.get()) == i + 1
}

/// Plant 662, for adapters.rs: whether it is set (the adapter counts it with `atom_object_fired` where it acts).
pub(crate) fn atom_object_set() -> bool {
    plant_set(AD_LRA_ATOM_OBJECT)
}

pub(crate) fn atom_object_fired() {
    planted(AD_LRA_ATOM_OBJECT);
}

/// wiring.py's 'same' shape and the Pow key's `b == e`, for rows_tpl.rs, once `a` and `b` are known to be two objects
/// and `==`: they are one term (ruling Q1 (b): equality, not identity, so no answer follows which of two equal objects
/// is held). Counted (672); plant 663 answers as identity did.
pub(crate) fn same_eq_met() -> bool {
    tick(SAME_EQ);
    !planted(SAME_IS)
}

/// Plant 660, for adapters.rs.
pub(crate) fn class_is_planted() -> bool {
    planted(AD_LRA_CLASS_IS)
}

/// term_live.py's `same_class`, the same rule: whether `a` and `b` are of one class to query `q` (a term_live `_Query`).
/// The same class object, or two class objects with one id in the query's own class table (`q.classes`, keyed by the
/// classes' hash and `==` when the input was converted). Two `Function('f')` are one class to SymPy and two objects, and
/// which object a process-wide memo hands back follows history (`ad:cbm_noid`). The table is the query's, never the
/// process's; a class the input doesn't hold has no id and is one class only with itself.
pub(crate) fn same_class<'py>(q: &Bound<'py, PyAny>, a: &Bound<'py, PyAny>, b: &Bound<'py, PyAny>) -> PyResult<bool> {
    let (ta, tb) = (a.get_type(), b.get_type());
    if ta.is(&tb) {
        return Ok(true);
    }
    if planted(CLASS_IS) {
        return Ok(false);
    }
    let p = q.py();
    let c = q.getattr(pyo3::intern!(p, "classes"))?;
    let mut same = false;
    if !c.is_none() {
        let get = |t: &Bound<'py, pyo3::types::PyType>| -> PyResult<Option<Bound<'py, PyAny>>> {
            match c.call_method1(pyo3::intern!(p, "get"), (t,)) {
                Ok(i) => Ok(if i.is_none() { None } else { Some(i) }),
                // an unhashable class: no id
                Err(e) if e.is_instance_of::<pyo3::exceptions::PyTypeError>(p) => Ok(None),
                Err(e) => Err(e),
            }
        };
        if let Some(i) = get(&ta)? {
            if let Some(j) = get(&tb)? {
                same = i.eq(j)?;
            }
        }
    }
    tick(if same { CLS_EQ } else { CLS_DIFFERS });
    Ok(same)
}

/// Plant 661 for term_live.py's `same_class` (one plant, both halves): whether it is on, counted as fired.
#[pyfunction]
fn class_is_plant() -> bool {
    planted(CLASS_IS)
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
    /// A node of the same formula with its own references: each holder the collector visits owns what it visits.
    pub(crate) fn share(&self, p: Python<'_>) -> FNode {
        FNode {
            root: self.root.clone(),
            occ: self.occ.iter().map(|o| Occ { obj: o.obj.clone_ref(p), pred: o.pred.clone_ref(p), expr: o.expr.clone_ref(p), atom: o.atom }).collect(),
            atoms: self.atoms.clone_ref(p),
            bad: self.bad.iter().map(|b| b.clone_ref(p)).collect(),
            source: self.source.clone_ref(p),
            nodes: self.nodes,
        }
    }

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
    if ENTRIES.with(|d| d.get()) > 0 && SEEN.with(|s| s.borrow_mut().insert(f.as_ptr() as usize, f.clone().unbind())).is_some() {
        tick(TWICE);
    }
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

/// Who holds a query's nodes: the entry's `Hand` before a session exists, the session's core after.
pub(crate) trait Nodes {
    /// `atoms_of(f)` from the holder's node of `f`; Python's own where the conversion refuses (`fm:atoms_py`).
    fn atoms<'py>(&self, f: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyTuple>>;
}

/// The nodes an entry holds for the length of its call: each formula it is given (and each one a callback hands it:
/// the extensions' facts, a template's formulas) is converted the first time something needs it and never again. It
/// is an argument, handed down to the scope and cone functions and, by `give`, to each session the entry makes. Found
/// by the object's identity; the node holds the object.
pub(crate) struct Hand {
    nodes: std::cell::RefCell<HashMap<usize, Rc<FNode>>>,
}

impl Hand {
    /// An entry begins.
    pub(crate) fn enter() -> Hand {
        ENTRIES.with(|d| d.set(d.get() + 1));
        Hand { nodes: std::cell::RefCell::new(HashMap::new()) }
    }

    /// `enter` for a scope or cone function called from Python. Reached from inside another entry, a by-name call
    /// dropped the caller's nodes on the way (`fm:nosession`).
    pub(crate) fn enter_inner() -> Hand {
        if ENTRIES.with(|d| d.get()) > 0 {
            tick(NOSESSION);
        }
        Hand::enter()
    }

    pub(crate) fn node(&self, f: &Bound<'_, PyAny>) -> PyResult<Result<Rc<FNode>, Refused>> {
        let k = f.as_ptr() as usize;
        if let Some(n) = self.nodes.borrow().get(&k) {
            tick(CACHE_HIT);
            return Ok(Ok(n.clone()));
        }
        Ok(match convert_or(f, &classes(f.py())?)? {
            Ok(n) => {
                let n = Rc::new(n);
                self.nodes.borrow_mut().insert(k, n.clone());
                Ok(n)
            }
            Err(w) => Err(w),
        })
    }

    /// Hands the session `s` a node of its own for each formula held (the same tree, its own references), so the
    /// session converts none of them again. `needed`: formulas the session is about to compile, converted now if
    /// nothing needed them yet.
    pub(crate) fn give(&self, s: &Bound<'_, PyAny>, needed: &[&Bound<'_, PyAny>]) -> PyResult<()> {
        let p = s.py();
        for f in needed {
            if !f.is_none() {
                self.node(f)?.ok();
            }
        }
        if planted(HAND_NO_GIVE) {
            return Ok(());
        }
        let Ok(core) = crate::session::core_of(s) else { return Ok(()) };
        let core = core.borrow();
        for (k, n) in self.nodes.borrow().iter() {
            if core.take_node(*k, || Rc::new(n.share(p))) {
                tick(GIVE);
            }
        }
        Ok(())
    }
}

impl Drop for Hand {
    fn drop(&mut self) {
        if ENTRIES.with(|d| { d.set(d.get() - 1); d.get() }) == 0 {
            let seen = SEEN.with(|s| std::mem::take(&mut *s.borrow_mut()));
            drop(seen);
        }
    }
}

impl Nodes for Hand {
    fn atoms<'py>(&self, f: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyTuple>> {
        match self.node(f)? {
            Ok(n) => Ok(n.atoms_of(f.py())),
            Err(_) => atoms_py(f),
        }
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
    m.add_function(wrap_pyfunction!(class_is_plant, m)?)?;
    Ok(())
}
