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

const NAMES: [&str; 25] = [
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
    "fm:again",         // 647: with `formula_track(True)` only: an object converted that some earlier entry had converted
    "fm:twice:patched", // 648: an object converted again on the other side of a user's replaced `Engine.verdict`, called by name
    "nc:memo_miss",     // 720: entry.rs `noncommutative_term`: domain's `_NONCOMM` memo had no row, so `_noncommutative` was called
    "occ:reach",        // 721: session.rs `reach`: compiling reached a formula atom whose own object isn't the one held for its
                        //      node, which had no visit yet, so the slot or the visit takes that occurrence's object
    "occ:two",          // 722: session.rs `convert`: a formula with a second object for a node with no visit, compiled in Rust
                        //      (it refused before item (1), `refuse:object`, and Python compiled it)
];
/// Counter 720.
pub(crate) const NC_MEMO_MISS: usize = 22;
/// Counter 721.
pub(crate) const OCC_REACH: usize = 23;
/// Counter 722.
pub(crate) const OCC_TWO: usize = 24;
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
const PLANTS: [&str; 17] = [
    "fm-atoms-drop-last",  // 601: `atoms` without its last atom
    "fm-atoms-merge-pred", // 612: the dedupe keyed by the predicate alone, so two atoms with one predicate are one (replaces 602
                           //      `fm-atoms-no-dedupe`, speed-only: every reader of the atoms is idempotent; sa-port-274)
    "fm-args-drop-last",   // 613: `And`/`Or` without their last argument (replaces 603 `fm-args-reverse`, order-only: both are
                           //      commutative; sa-port-274)
    "fm-implies-swap",     // 604: `Implies(a, b)` read as `Implies(b, a)`
    "fm-ite-swap",         // 605: `ITE(c, a, b)` read as `ITE(c, b, a)`
    "fm-not-drop",         // 606: `Not(a)` read as `a`
    "ad-lra-class-is",     // 660: adapters.rs `Reader.id` compares the row's class by identity again (sa-port-235's)
    "class-is",            // 661: `same_class` by identity again, at every site, Rust's and term_live's
    "ad-lra-atom-object",  // 662: a native reader result holds the atom's own object, not the query's first (its row)
    "same-is",             // 663: wiring's 'same' shape and the Pow key's `b == e` by identity again (rows_tpl.rs)
    "fm-hand-no-give",     // 607: `Hand::give` hands nothing over
    "fm-hand-kept",        // 608: an entry's nodes outlive it and answer the next entry (a `Hand` reused across queries)
    "fm-hand-instrument-by-name",  // 609: a registered instrument's `verdict` wrapper is called by name, as a user's patch is
    "fm-hand-patched-direct",   // 610: a user's replaced `Engine.verdict` is passed over: Rust calls its own directly
    "fm-hand-per-entry",   // 622: each outermost entry inside an ask makes its own map again (`formula_ask` shares none)
    "nc-memo-true-false",  // 623: entry.rs `noncommutative_term` reads a memo row of True as False (a wrong answer)
    "occ-walk-first",      // 624: session.rs `reach` does nothing, so a node keeps the object conversion walked to first, not the
                           //      one Python's compiler reaches first (test_occ_object.py)
];

thread_local! {
    static COUNTS: [Cell<u64>; 25] = const { [const { Cell::new(0) }; 25] };
    /// The nine classes for a site with no session: `SessionRules`' list (session_live.py `_core_rules`), read once.
    static CLASSES: std::cell::RefCell<Option<Rc<Vec<Py<PyAny>>>>> = const { std::cell::RefCell::new(None) };
    /// 0: none; else 1 + the index into `PLANTS`.
    static PLANT: Cell<u8> = const { Cell::new(0) };
    /// How many `Hand`s are live on this thread's stack: 0 outside any entry.
    static ENTRIES: Cell<u32> = const { Cell::new(0) };
    /// The objects converted since the outermost entry began, held until it ends, each with the scopes it was converted
    /// in: the first, then any others (`fm:twice` and `fm:twice:patched` only; nothing reads a node here).
    static SEEN: std::cell::RefCell<HashMap<usize, (Py<PyAny>, u32, Vec<u32>)>> = std::cell::RefCell::new(HashMap::new());
    /// The scope conversions run in: 0 is the outermost entry's own, and each by-name call of a user's replaced
    /// `Engine.verdict` (`Patched`) is a new one until it returns.
    static SCOPE: Cell<u32> = const { Cell::new(0) };
    static SCOPES: Cell<u32> = const { Cell::new(0) };
    /// `formula_track(True)`: every object converted since, held so its address stays its own (`fm:again` only; a
    /// measurement a run switches on, nothing reads a node here).
    static TRACK: std::cell::RefCell<Option<HashMap<usize, Py<PyAny>>>> = const { std::cell::RefCell::new(None) };
    /// How many formulas the live `Hand`s hold: 0 outside any entry (`formula_held`).
    static HELD: Cell<usize> = const { Cell::new(0) };
    /// Plant 608's store: the nodes of ended entries.
    static KEPT: std::cell::RefCell<HashMap<usize, Rc<FNode>>> = std::cell::RefCell::new(HashMap::new());
    /// The node map of the top-level ask running on this thread (`formula_ask`), shared by each outermost `Hand` made
    /// inside it, so a later entry of the same ask finds what an earlier one converted. `None` outside any ask.
    static ASK: std::cell::RefCell<Option<Rc<std::cell::RefCell<HashMap<usize, Held>>>>> = const { std::cell::RefCell::new(None) };
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
/// Plant 608: the ruled-out cache, a `Hand` whose nodes survive into the next entry.
const HAND_KEPT: u8 = 11;
/// Plant 622: one node map per entry again, not per ask (`fm:again` within an ask).
const HAND_PER_ENTRY: u8 = 14;
/// Plant 623 (entry.rs `noncommutative_term`).
pub(crate) fn planted_nc_memo() -> bool {
    planted(15)
}
/// Plant 624 (session.rs `reach`).
pub(crate) fn planted_occ_walk_first() -> bool {
    planted(16)
}
const AGAIN: usize = 20;
/// Plant 609 (context.rs `method_of`).
pub(crate) fn plant_instrument_by_name() -> bool {
    planted(12)
}
/// Plant 610 (context.rs `call_from`).
pub(crate) fn plant_patched_direct() -> bool {
    planted(13)
}
const TWICE_PATCHED: usize = 21;
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
        let atom = if bare {
            self.firsts.push(f.clone());
            self.firsts.len() - 1
        } else {
            tick(ATOM_INTERN);
            // plant 612 keys the dedupe too coarsely: by the predicate, so a second atom with it is taken for the first
            let key = if plant_set(1) { pred.bind(p).clone() } else { f.clone() };
            match self.seen.get_item(&key)? {
                Some(i) => {
                    let i: usize = i.extract()?;
                    if plant_set(1) && !self.firsts[i].eq(f)? {
                        planted(1);
                    }
                    i
                }
                None => {
                    self.seen.set_item(&key, self.firsts.len())?;
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
                        a.pop();
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
    if ENTRIES.with(|d| d.get()) > 0 {
        // Again in the scope that converted it: the per-query rule's `fm:twice`. Again in another scope: the two are
        // either side of a replaced `verdict` called by name, where a second `Hand` is allowed (`fm:twice:patched`).
        let scope = SCOPE.with(|c| c.get());
        let again = SEEN.with(|s| match s.borrow_mut().entry(f.as_ptr() as usize) {
            std::collections::hash_map::Entry::Vacant(v) => {
                v.insert((f.clone().unbind(), scope, Vec::new()));
                None
            }
            std::collections::hash_map::Entry::Occupied(mut o) => {
                let (_, first, more) = o.get_mut();
                let same = *first == scope || more.contains(&scope);
                if !same {
                    more.push(scope);
                }
                Some(same)
            }
        });
        match again {
            Some(true) => tick(TWICE),
            Some(false) => tick(TWICE_PATCHED),
            None => {}
        }
    }
    if TRACK.with(|t| t.borrow_mut().as_mut().is_some_and(|m| m.insert(f.as_ptr() as usize, f.clone().unbind()).is_some())) {
        tick(AGAIN);
    }
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

/// Who holds a query's nodes: the entry's `Hand` before a session exists, the session's core after.
pub(crate) trait Nodes {
    /// `atoms_of(f)` from the holder's node of `f`; Python's own where the conversion refuses (`fm:atoms_py`).
    fn atoms<'py>(&self, f: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyTuple>>;
}

/// The nodes an entry holds for the length of its call: each formula it is given (and each one a callback hands it:
/// the extensions' facts, a template's formulas) is converted the first time something needs it and never again. It
/// is an argument, handed down to the scope and cone functions and, by `give`, to each session the entry makes. Found
/// by the object's identity; the node holds the object, and a refusal is kept with the object it refused, so no object
/// is walked twice in one entry. Nothing here outlives the entry's call: the next query starts with none.
pub(crate) struct Hand {
    /// Shared with `ASK` when the entry is an outermost one inside a top-level ask (H2's "one entry call" is then the
    /// ask's: its node map ends with `formula_ask`'s call).
    nodes: Rc<std::cell::RefCell<HashMap<usize, Held>>>,
}

enum Held {
    Node(Rc<FNode>),
    /// The refused object is held: its address is the key.
    Refused(Refused, #[allow(dead_code)] Py<PyAny>),
}

impl Hand {
    /// An entry begins.
    pub(crate) fn enter() -> Hand {
        let outer = ENTRIES.with(|d| { d.set(d.get() + 1); d.get() == 1 });
        // only an outermost entry shares the ask's map: nested ones (`enter_inner`'s `fm:nosession`, a by-name call's
        // `fm:twice:patched`) start their own as before
        let ask = if outer && !planted(HAND_PER_ENTRY) { ASK.with(|a| a.borrow().clone()) } else { None };
        Hand { nodes: ask.unwrap_or_default() }
    }

    /// `enter` for a scope or cone function called from Python. Reached from inside another entry, a by-name call
    /// dropped the caller's nodes on the way (`fm:nosession`).
    pub(crate) fn enter_inner() -> Hand {
        // Behind a user's replaced method the by-name call is the ruled one (`Patched`): what it converts again is
        // `fm:twice:patched`, and `fm:nosession` stays the count of by-name calls of our own.
        if ENTRIES.with(|d| d.get()) > 0 && SCOPE.with(|c| c.get()) == 0 {
            tick(NOSESSION);
        }
        Hand::enter()
    }

    pub(crate) fn node(&self, f: &Bound<'_, PyAny>) -> PyResult<Result<Rc<FNode>, Refused>> {
        let k = f.as_ptr() as usize;
        if let Some(h) = self.nodes.borrow().get(&k) {
            tick(CACHE_HIT);
            return Ok(match h {
                Held::Node(n) => Ok(n.clone()),
                Held::Refused(w, _) => Err(*w),
            });
        }
        if plant_set(HAND_KEPT) {
            if let Some(n) = KEPT.with(|m| m.borrow().get(&k).cloned()) {
                planted(HAND_KEPT);
                self.nodes.borrow_mut().insert(k, Held::Node(n.clone()));
                HELD.with(|h| h.set(h.get() + 1));
                return Ok(Ok(n));
            }
        }
        let r = convert_or(f, &classes(f.py())?)?;
        HELD.with(|h| h.set(h.get() + 1));
        Ok(match r {
            Ok(n) => {
                let n = Rc::new(n);
                self.nodes.borrow_mut().insert(k, Held::Node(n.clone()));
                Ok(n)
            }
            Err(w) => {
                self.nodes.borrow_mut().insert(k, Held::Refused(w, f.clone().unbind()));
                Err(w)
            }
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
            let Held::Node(n) = n else { continue };
            if core.take_node(*k, || Rc::new(n.share(p))) {
                tick(GIVE);
            }
        }
        Ok(())
    }
}

/// A by-name call of an `Engine` method (`verdict`, `_context_session`, `_within_budget`) that is neither session_live's nor a registered instrument's (context.rs
/// `call_from`): the caller's nodes can't go with the objects, so the entry behind the call starts its own `Hand`.
/// What it converts again is counted apart, `fm:twice:patched`, until the call returns.
pub(crate) struct Patched {
    outer: u32,
}

impl Patched {
    pub(crate) fn enter() -> Patched {
        let n = SCOPES.with(|c| { c.set(c.get() + 1); c.get() });
        Patched { outer: SCOPE.with(|c| c.replace(n)) }
    }
}

impl Drop for Patched {
    fn drop(&mut self) {
        SCOPE.with(|c| c.set(self.outer));
    }
}

/// The end of a node map's life (an entry's, or an ask's): what it held is no longer held.
fn release(nodes: HashMap<usize, Held>) {
        if plant_set(HAND_KEPT) {
            // the plant: what the entry held stays, and stays counted as held
            KEPT.with(|m| m.borrow_mut().extend(nodes.into_iter().filter_map(|(k, h)| match h {
                Held::Node(n) => Some((k, n)),
                Held::Refused(..) => { HELD.with(|h| h.set(h.get() - 1)); None }
            })));
        } else {
            HELD.with(|h| h.set(h.get() - nodes.len()));
        }
}

impl Drop for Hand {
    fn drop(&mut self) {
        // the ask's map ends with the ask (`formula_ask`), not with this entry
        if !ASK.with(|a| a.borrow().as_ref().is_some_and(|m| Rc::ptr_eq(m, &self.nodes))) {
            release(std::mem::take(&mut *self.nodes.borrow_mut()));
        }
        if ENTRIES.with(|d| { d.set(d.get() - 1); d.get() }) == 0 {
            let seen = SEEN.with(|s| std::mem::take(&mut *s.borrow_mut()));
            drop(seen);
            SCOPES.with(|c| c.set(0));
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

/// `f(*args)` as one top-level ask (term_live.py `_ask`, the outermost one): every outermost entry inside it shares one
/// node map, so no object is converted twice within an ask (`fm:again` within an ask is 0; across asks it stays
/// information). Doesn't raise `ENTRIES`: a scope or cone function called from Python inside the ask is still an entry
/// of its own, not a by-name call (`fm:nosession`). Nested inside another ask, it is just the call.
#[pyfunction]
#[pyo3(signature = (f, *args))]
fn formula_ask<'py>(f: &Bound<'py, PyAny>, args: &Bound<'py, PyTuple>) -> PyResult<Bound<'py, PyAny>> {
    if ASK.with(|a| a.borrow().is_some()) {
        return f.call1(args);
    }
    struct End;
    impl Drop for End {
        fn drop(&mut self) {
            if let Some(m) = ASK.with(|a| a.borrow_mut().take()) {
                release(std::mem::take(&mut *m.borrow_mut()));
            }
        }
    }
    ASK.with(|a| *a.borrow_mut() = Some(Rc::default()));
    let _end = End;
    f.call1(args)
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
    // plant 608's store goes with the plant; between entries nothing is held again
    drop(KEPT.with(|m| std::mem::take(&mut *m.borrow_mut())));
    if ENTRIES.with(|d| d.get()) == 0 {
        HELD.with(|h| h.set(0));
    }
    Ok(())
}

/// `SEEN`'s rows, `[(object, first scope, the other scopes)]`: the discard's mark and what its check reads (term_live.py
/// `_Mark`, term_discard.py; the gate for sa-port-269 (4)). Empty outside any entry, where a top query's discard happens.
#[pyfunction]
fn formula_seen_rows(p: Python<'_>) -> Vec<(Py<PyAny>, u32, Vec<u32>)> {
    SEEN.with(|s| s.borrow().values().map(|(o, a, m)| (o.clone_ref(p), *a, m.clone())).collect())
}

/// The discard's rollback: `SEEN` holds `rows` again and nothing a refused run converted.
#[pyfunction]
fn formula_seen_restore(rows: Vec<(Py<PyAny>, u32, Vec<u32>)>) {
    let new: HashMap<usize, (Py<PyAny>, u32, Vec<u32>)> = rows.into_iter().map(|(o, a, m)| (o.as_ptr() as usize, (o, a, m))).collect();
    drop(SEEN.with(|s| std::mem::replace(&mut *s.borrow_mut(), new)));
}

/// Plant 608's store by key, for the discard's check: empty unless the plant is set (its only writer is `Hand`'s drop
/// under `plant_set(HAND_KEPT)`).
#[pyfunction]
fn formula_kept_rows() -> Vec<usize> {
    KEPT.with(|m| m.borrow().keys().copied().collect())
}

/// How many formulas the live entries hold: 0 between queries (H2: nothing in a `Hand` survives its entry's call).
#[pyfunction]
fn formula_held() -> usize {
    HELD.with(|h| h.get())
}

/// Switches `fm:again` on or off: on, every converted object is held from then on, so a second conversion of one
/// object in any later entry is counted. Off drops them. A measurement for a run, never on by default.
#[pyfunction]
fn formula_track(on: bool) {
    let old = TRACK.with(|t| t.replace(if on { Some(HashMap::new()) } else { None }));
    drop(old);
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
    m.add_function(wrap_pyfunction!(formula_held, m)?)?;
    m.add_function(wrap_pyfunction!(formula_seen_rows, m)?)?;
    m.add_function(wrap_pyfunction!(formula_seen_restore, m)?)?;
    m.add_function(wrap_pyfunction!(formula_kept_rows, m)?)?;
    m.add_function(wrap_pyfunction!(formula_track, m)?)?;
    m.add_function(wrap_pyfunction!(formula_ask, m)?)?;
    m.add_function(wrap_pyfunction!(class_is_plant, m)?)?;
    Ok(())
}
