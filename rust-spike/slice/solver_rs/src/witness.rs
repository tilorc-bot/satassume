//! The witness check on the query's native term ids (sa-port-351, issue 323): `satassume/witness.py`'s per-call compile,
//! point search and exact evaluation, behind SLICE_WITNESS_RUST=1 (witness_live.py). Python's witness.py stays the
//! default and the reference; every function here names the one it mirrors, and tests/test_witness_native.py compares
//! the two per query.
//!
//! What is read of Python, once, at the boundary (the planner's choice B, formula.rs's precedent): the `P` formula that
//! `to_formula` made (`type(f) is` the nine classes witness.py compares with, `.args`, an atom's `.pred`/`.expr`), and one
//! lookup per atom side in the query's `ids` (SymPy's hash and `==`, `wn:lookup`), with the found row's object compared by
//! type so a Python `int` or `bool` side that is `==` to an Integer is not taken for one. Below that everything runs
//! on the table's rows: `Kind` is the exact class `_term` tests, a rational's p and q are its content, and a symbol's own
//! assumptions are `TermTable::symbol_facts` (`assumptions0`, the table's one memoized read per symbol).
//!
//! Sent to Python's witness.py, whole query, counted (never half an answer): a side that is not in `ids`
//! (`wn:fallback:miss`), a side whose row holds an object of another type (`wn:fallback:type`), and a formula object of
//! another class, an ITE without three arguments, a predicate name that is no `str`, a `Rational` subclass, a read that
//! raised, a nesting deeper than `DEPTH` (`wn:fallback:shape`). The first of {undecided, fallback} in walk order decides,
//! as the first `_Undecided` does in Python: everything before it was mapped, so Python saw the same.
//!
//! Exact arithmetic only: `Rat` over BigInt, Q[pi] as coefficient vectors, the 50-digit enclosure as rational bounds.
//! No float anywhere. Nothing is kept across queries: a `WitnessQuery` lives for one call of `witnesses`, and the
//! only statics are the enclosure's powers (constants of the module), the counters and the plant.
//! Counters 706-712 here (713 `wn:fallback:off` is witness_live.py's); plants 760, 761, 763 here (762 in witness_live.py).
use crate::term::py::PyTermTable;
use crate::term::rat::Rat;
use crate::term::table::{flag, Kind, TermTable};
use crate::term::TermId;
use num_bigint::BigInt;
use num_traits::{One, Signed, ToPrimitive, Zero};
use pyo3::exceptions::{PyException, PyValueError};
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyString, PyTuple};
use std::cell::Cell;
use std::collections::{BTreeSet, HashMap};
use std::rc::Rc;
use std::sync::OnceLock;

const MAX_EXP: i64 = 64;
const MAX_BITS: u64 = 4096;
const MAX_PRIME: u64 = 1_000_000;
const MAX_DEG: usize = 16;
/// Formulas and terms nested deeper go to Python, whose own limit is the interpreter's.
const DEPTH: u32 = 200;

const NAMES: [&str; 7] = [
    "wn:compile",        // 706: native compiles run
    "wn:lookup",         // 707: boundary reads: lookups of an atom side in the query's `ids`
    "wn:search",         // 708: native searches run (a compiled query past the Python guards)
    "wn:found",          // 709: searches that gave two points
    "wn:fallback:miss",  // 710: to Python: a side that is not in `ids`
    "wn:fallback:type",  // 711: to Python: a side `==` to a row's object of another type
    "wn:fallback:shape", // 712: to Python: a formula class, arity, name, Rational subclass, read or depth not mirrored
];
const COMPILE: usize = 0;
const LOOKUP: usize = 1;
const SEARCH: usize = 2;
const FOUND: usize = 3;
const F_MISS: usize = 4;
const F_TYPE: usize = 5;
const F_SHAPE: usize = 6;

/// Plants (SLICE_WITNESS_RUST_PLANT; 762 `wn-skip-patched` sits in witness_live.py).
const PLANTS: [&str; 3] = [
    "wn-integer-half", // 760: the native table says 1/2 is an integer
    "wn-work-one",     // 761: the native work count trips one evaluation early (`>=` for `>`)
    "wn-int-side",     // 763: a side's row is taken without comparing the object's type
];
const P_HALF: u8 = 0;
const P_WORK: u8 = 1;
const P_SIDE: u8 = 2;

thread_local! {
    static COUNTS: [Cell<u64>; 7] = const { [const { Cell::new(0) }; 7] };
    /// 0: none; else 1 + the index into `PLANTS`.
    static PLANT: Cell<u8> = const { Cell::new(0) };
}

fn tick(i: usize) {
    COUNTS.with(|c| c[i].set(c[i].get() + 1));
}

fn planted(i: u8) -> bool {
    let on = PLANT.with(|c| c.get()) == i + 1;
    if on {
        // the bar's channel: its plants phase reads `rel:plant_fired` from the session report
        crate::session::tick(crate::session::REL_PLANT);
    }
    on
}

/// witness.py `_Undecided`: no exact value, for a term or atom as such or at one point.
struct Und;
type E<T> = Result<T, Und>;

/// A value of Q[pi]: a rational, or `c[0] + c[1]*pi + ...` with at least two coefficients and the last not 0
/// (witness.py `_PiPoly`; by transcendence the vector is the value's only representation, so `==` reads it).
#[derive(Clone, PartialEq, Eq)]
enum Val {
    Q(Rat),
    Pi(Vec<Rat>),
}

/// witness.py `_poly`.
fn poly(mut c: Vec<Rat>) -> Val {
    while c.len() > 1 && c[c.len() - 1].is_zero() {
        c.pop();
    }
    if c.len() == 1 { Val::Q(c.pop().unwrap()) } else { Val::Pi(c) }
}

/// `_PiPoly.__add__`, and a rational sum.
fn add(a: &Val, b: &Val) -> Val {
    match (a, b) {
        (Val::Q(x), Val::Q(y)) => Val::Q(x.add(y)),
        (Val::Pi(c), Val::Q(o)) | (Val::Q(o), Val::Pi(c)) => {
            let mut c = c.clone();
            c[0] = c[0].add(o);
            Val::Pi(c)
        }
        (Val::Pi(x), Val::Pi(y)) => {
            let (x, y) = if x.len() < y.len() { (y, x) } else { (x, y) };
            let mut out = x.clone();
            for (o, v) in out.iter_mut().zip(y.iter()) {
                *o = o.add(v);
            }
            poly(out)
        }
    }
}

fn neg(a: &Val) -> Val {
    match a {
        Val::Q(x) => Val::Q(x.neg()),
        Val::Pi(c) => Val::Pi(c.iter().map(Rat::neg).collect()),
    }
}

fn sub(a: &Val, b: &Val) -> Val {
    add(a, &neg(b))
}

/// `_PiPoly.__mul__`, and a rational product.
fn mul(a: &Val, b: &Val) -> E<Val> {
    Ok(match (a, b) {
        (Val::Q(x), Val::Q(y)) => Val::Q(x.mul(y)),
        (Val::Pi(c), Val::Q(o)) | (Val::Q(o), Val::Pi(c)) => poly(c.iter().map(|x| x.mul(o)).collect()),
        (Val::Pi(x), Val::Pi(y)) => {
            if x.len() + y.len() - 2 > MAX_DEG {
                return Err(Und);
            }
            let mut out = vec![Rat::int(0); x.len() + y.len() - 1];
            for (i, p) in x.iter().enumerate() {
                for (j, q) in y.iter().enumerate() {
                    out[i + j] = out[i + j].add(&p.mul(q));
                }
            }
            poly(out)
        }
    })
}

/// `_term`'s `power` and `_pi_power`: an integer power of a rational; of a non-rational value, a power by n >= 0.
fn power(b: &Val, n: &Val) -> E<Val> {
    let n = match n {
        Val::Q(n) if n.is_int() => &n.n,
        _ => return Err(Und),
    };
    match b {
        Val::Pi(c) => {
            if n.is_negative() || *n > BigInt::from(MAX_EXP) {
                return Err(Und);
            }
            let n = n.to_u64().ok_or(Und)?;
            // `_PiPoly.__pow__`; the second term is `len(c).bit_length()`
            let bits = c.iter().map(Rat::bits).max().unwrap_or(0) + (usize::BITS - c.len().leading_zeros()) as u64;
            if (c.len() as u64 - 1) * n > MAX_DEG as u64 || bits * n > MAX_BITS {
                return Err(Und);
            }
            let mut r = Val::Q(Rat::int(1));
            for _ in 0..n {
                r = mul(&r, b)?;
            }
            Ok(r)
        }
        Val::Q(b) => {
            if n.abs() > BigInt::from(MAX_EXP) || (b.is_zero() && !n.is_positive()) {
                return Err(Und);
            }
            let n = n.to_i32().ok_or(Und)?;
            if b.bits() * n.unsigned_abs() as u64 > MAX_BITS {
                return Err(Und);
            }
            Ok(Val::Q(b.pow(n)))
        }
    }
}

/// The powers 0..=MAX_DEG of the enclosure's two bounds: witness.py `_LO`, `_HI`, from the same 50 digits.
fn enclosure() -> &'static (Vec<Rat>, Vec<Rat>) {
    static E: OnceLock<(Vec<Rat>, Vec<Rat>)> = OnceLock::new();
    E.get_or_init(|| {
        let n: BigInt = "314159265358979323846264338327950288419716939937510".parse().unwrap();
        let d: BigInt = num_traits::Pow::pow(BigInt::from(10), 50u32);
        let (lo, hi) = (Rat::new(n.clone(), d.clone()), Rat::new(n + 1, d));
        let pows = |b: &Rat| (0..=MAX_DEG as i32).map(|k| b.pow(k)).collect::<Vec<_>>();
        (pows(&lo), pows(&hi))
    })
}

/// witness.py `_sign` at a non-rational value: 1 or -1, or undecided where the enclosure does not separate it from 0.
fn pi_sign(c: &[Rat]) -> E<i32> {
    let (lo, hi) = enclosure();
    let (mut low, mut up) = (c[0].clone(), c[0].clone());
    for k in 1..c.len() {
        let x = &c[k];
        match x.sign() {
            1 => {
                low = low.add(&x.mul(&lo[k]));
                up = up.add(&x.mul(&hi[k]));
            }
            -1 => {
                low = low.add(&x.mul(&hi[k]));
                up = up.add(&x.mul(&lo[k]));
            }
            _ => {}
        }
    }
    if low.sign() > 0 {
        Ok(1)
    } else if up.sign() < 0 {
        Ok(-1)
    } else {
        Err(Und)
    }
}

fn sign(v: &Val) -> E<i32> {
    match v {
        Val::Q(x) => Ok(x.sign()),
        Val::Pi(c) => pi_sign(c),
    }
}

/// rules.BASIS, in its order.
#[derive(Clone, Copy, PartialEq, Eq)]
enum B {
    Algebraic, Complex, Composite, Even, ExtNeg, ExtPos, ExtReal, Finite, Imaginary, Integer, Polar, Prime, Rational,
    Zero,
}

const BASIS: [(&str, B); 14] = [
    ("algebraic", B::Algebraic), ("complex", B::Complex), ("composite", B::Composite), ("even", B::Even),
    ("extended_negative", B::ExtNeg), ("extended_positive", B::ExtPos), ("extended_real", B::ExtReal),
    ("finite", B::Finite), ("imaginary", B::Imaginary), ("integer", B::Integer), ("polar", B::Polar),
    ("prime", B::Prime), ("rational", B::Rational), ("zero", B::Zero),
];

/// witness.py `TWO_WAY`'s predicates with their definitions (rules.DEFINITIONS), as (basis predicate, wanted value):
/// all conjunctions. test_witness_native.py compares this table with rules.DEFINITIONS.
const DEFS: [(&str, &[(B, bool)]); 16] = [
    ("real", &[(B::ExtReal, true), (B::Finite, true)]),
    ("infinite", &[(B::Finite, false)]),
    ("positive", &[(B::ExtPos, true), (B::Finite, true)]),
    ("negative", &[(B::ExtNeg, true), (B::Finite, true)]),
    ("nonnegative", &[(B::ExtReal, true), (B::Finite, true), (B::ExtNeg, false)]),
    ("nonpositive", &[(B::ExtReal, true), (B::Finite, true), (B::ExtPos, false)]),
    ("nonzero", &[(B::ExtReal, true), (B::Finite, true), (B::Zero, false)]),
    ("extended_nonnegative", &[(B::ExtReal, true), (B::ExtNeg, false)]),
    ("extended_nonpositive", &[(B::ExtReal, true), (B::ExtPos, false)]),
    ("extended_nonzero", &[(B::ExtReal, true), (B::Zero, false)]),
    ("positive_infinite", &[(B::ExtPos, true), (B::Finite, false)]),
    ("negative_infinite", &[(B::ExtNeg, true), (B::Finite, false)]),
    ("odd", &[(B::Integer, true), (B::Even, false)]),
    ("irrational", &[(B::ExtReal, true), (B::Finite, true), (B::Rational, false)]),
    ("noninteger", &[(B::ExtReal, true), (B::Integer, false)]),
    ("transcendental", &[(B::Complex, true), (B::Algebraic, false)]),
];

#[derive(Clone, Copy)]
enum Pred {
    Basis(B),
    /// witness.py `ONE_WAY`'s `hermitian` and `commutative`: True at every value of Q[pi].
    Always,
    Def(&'static [(B, bool)]),
}

/// witness.py `_pred` (and `_pi_pred`: the same names are undecided over both tables).
fn pred(name: &str) -> E<Pred> {
    if let Some((_, b)) = BASIS.iter().find(|(n, _)| *n == name) {
        return if *b == B::Polar { Err(Und) } else { Ok(Pred::Basis(*b)) };
    }
    match name {
        "hermitian" | "commutative" => return Ok(Pred::Always),
        "antihermitian" => return Err(Und),
        _ => {}
    }
    DEFS.iter().find(|(n, _)| *n == name).map(|(_, d)| Pred::Def(d)).ok_or(Und)
}

/// witness.py `_is_prime`, for n > 1.
fn is_prime(n: &BigInt) -> E<bool> {
    let n = match n.to_u64() {
        Some(n) if n <= MAX_PRIME => n,
        _ => return Err(Und),
    };
    if n % 2 == 0 {
        return Ok(n == 2);
    }
    let mut d = 3;
    while d * d <= n {
        if n % d == 0 {
            return Ok(false);
        }
        d += 2;
    }
    Ok(true)
}

/// witness.py `_integer`.
fn integer(v: &Rat) -> bool {
    if v.d == BigInt::from(2) && v.n.is_one() && planted(P_HALF) {
        return true;
    }
    v.is_int()
}

/// witness.py `TABLE` at a rational value.
fn basis_q(b: B, v: &Rat) -> E<bool> {
    Ok(match b {
        B::Algebraic | B::Complex | B::ExtReal | B::Finite | B::Rational => true,
        B::Imaginary => false,
        B::Composite => integer(v) && v.n > BigInt::one() && !is_prime(&v.n)?,
        B::Prime => integer(v) && v.n > BigInt::one() && is_prime(&v.n)?,
        // Python's `int(v) % 2 == 0`
        B::Even => integer(v) && num_integer::Integer::is_even(&(&v.n / &v.d)),
        B::ExtNeg => v.sign() < 0,
        B::ExtPos => v.sign() > 0,
        B::Integer => integer(v),
        B::Zero => v.is_zero(),
        B::Polar => return Err(Und),
    })
}

/// witness.py `PI_TABLE` at a value that is not rational.
fn basis_pi(b: B, c: &[Rat]) -> E<bool> {
    Ok(match b {
        B::Complex | B::ExtReal | B::Finite => true,
        B::Algebraic | B::Composite | B::Even | B::Imaginary | B::Integer | B::Prime | B::Rational | B::Zero => false,
        B::ExtNeg => pi_sign(c)? < 0,
        B::ExtPos => pi_sign(c)? > 0,
        B::Polar => return Err(Und),
    })
}

fn basis(b: B, v: &Val) -> E<bool> {
    match v {
        Val::Q(x) => basis_q(b, x),
        Val::Pi(c) => basis_pi(b, c),
    }
}

/// A predicate at a value. A definition is strict, as `all([f(v) == want ...])`: every literal is evaluated.
fn pred_at(p: Pred, v: &Val) -> E<bool> {
    match p {
        Pred::Basis(b) => basis(b, v),
        Pred::Always => Ok(true),
        Pred::Def(lits) => {
            let mut ok = true;
            for (b, want) in lits {
                ok &= basis(*b, v)? == *want;
            }
            Ok(ok)
        }
    }
}

/// A compiled term: witness.py `_term`'s closures.
enum T {
    Sym(usize),
    Const(Rat),
    Add(Vec<T>),
    Mul(Vec<T>),
    Pow(Box<T>, Box<T>),
    Pi,
}

fn eval(t: &T, pt: &[Rat]) -> E<Val> {
    Ok(match t {
        T::Sym(i) => Val::Q(pt[*i].clone()),
        T::Const(c) => Val::Q(c.clone()),
        T::Add(fs) => {
            let mut s = Val::Q(Rat::int(0));
            for f in fs {
                s = add(&s, &eval(f, pt)?);
            }
            s
        }
        T::Mul(fs) => {
            let mut s = Val::Q(Rat::int(1));
            for f in fs {
                s = mul(&s, &eval(f, pt)?)?;
            }
            s
        }
        T::Pow(b, x) => {
            let (b, n) = (eval(b, pt)?, eval(x, pt)?);
            power(&b, &n)?
        }
        T::Pi => Val::Pi(vec![Rat::int(0), Rat::int(1)]),
    })
}

/// A compiled formula: witness.py `_formula`'s closures. Strict: every argument is evaluated.
enum F {
    Const(bool),
    Eq(Rc<T>, Rc<T>),
    Lt(Rc<T>, Rc<T>),
    Pred(Pred, Rc<T>),
    Not(Box<F>),
    And(Vec<F>),
    Or(Vec<F>),
    Implies(Vec<F>),
    Equivalent(Vec<F>),
    Exclusive(Vec<F>),
    Ite(Vec<F>),
}

fn all_of(gs: &[F], pt: &[Rat]) -> E<Vec<bool>> {
    gs.iter().map(|g| holds_f(g, pt)).collect()
}

fn holds_f(f: &F, pt: &[Rat]) -> E<bool> {
    Ok(match f {
        F::Const(b) => *b,
        F::Eq(a, b) => eval(a, pt)? == eval(b, pt)?,
        // `TABLE['lt']` and `PI_TABLE['lt']`: b - a is positive (for two rationals that is a < b)
        F::Lt(a, b) => {
            let (a, b) = (eval(a, pt)?, eval(b, pt)?);
            sign(&sub(&b, &a))? > 0
        }
        F::Pred(p, t) => pred_at(*p, &eval(t, pt)?)?,
        F::Not(g) => !holds_f(g, pt)?,
        F::And(gs) => all_of(gs, pt)?.iter().all(|b| *b),
        F::Or(gs) => all_of(gs, pt)?.iter().any(|b| *b),
        F::Implies(gs) => all_of(gs, pt)? != [true, false],
        F::Equivalent(gs) => {
            let v = all_of(gs, pt)?;
            v.iter().all(|b| *b == v[0])
        }
        F::Exclusive(gs) => all_of(gs, pt)?.iter().filter(|b| **b).count() <= 1,
        F::Ite(gs) => {
            let v = all_of(gs, pt)?;
            if v[0] { v[1] } else { v[2] }
        }
    })
}

/// An atom's function for `_roots`: the difference of a relation's sides, or a predicate's compound term.
enum Probe {
    Diff(Rc<T>, Rc<T>),
    Term(Rc<T>),
}

impl Probe {
    fn at(&self, pt: &[Rat]) -> E<Val> {
        match self {
            Probe::Diff(a, b) => Ok(sub(&eval(a, pt)?, &eval(b, pt)?)),
            Probe::Term(t) => eval(t, pt),
        }
    }
}

enum Stop {
    Und,
    NeedPi,
    Fall(usize),
    Err(PyErr),
}

impl From<Und> for Stop {
    fn from(_: Und) -> Stop {
        Stop::Und
    }
}

/// A read of Python that raised: an `Exception` sends the query to witness.py, which raises it again or doesn't
/// read there; anything else goes up.
fn read<T>(p: Python<'_>, r: PyResult<T>) -> Result<T, Stop> {
    r.map_err(|e| if e.is_instance_of::<PyException>(p) { Stop::Fall(F_SHAPE) } else { Stop::Err(e) })
}

/// witness.py `_Query`, while it is compiled.
struct Cx<'a, 'py> {
    table: &'a TermTable,
    ids: &'a Bound<'py, PyDict>,
    objects: &'a Bound<'py, PyAny>,
    /// P, Not, And, Or, Implies, Equivalent, Exclusive, ITE, Args: witness.py's own globals.
    classes: &'a [Bound<'py, PyAny>],
    pi: bool,
    syms: Vec<TermId>,
    index: HashMap<TermId, usize>,
    consts: Vec<Rat>,
    probes: Vec<(Probe, Vec<usize>, u64)>,
    size: u64,
}

fn rational_kind(k: Kind) -> bool {
    matches!(k, Kind::Integer | Kind::Rational | Kind::Zero | Kind::One | Kind::Half | Kind::NegativeOne)
}

impl<'py> Cx<'_, 'py> {
    /// witness.py `_term` on a row.
    fn term(&mut self, t: TermId, used: &mut BTreeSet<usize>, depth: u32) -> Result<T, Stop> {
        if depth > DEPTH {
            return Err(Stop::Fall(F_SHAPE));
        }
        self.size += 1;
        let class = self.table.class_of(t);
        let kind = class.kind;
        if kind == Kind::Symbol || kind == Kind::Dummy {
            let n = self.syms.len();
            let i = *self.index.entry(t).or_insert(n);
            if i == n {
                self.syms.push(t);
            }
            used.insert(i);
            return Ok(T::Sym(i));
        }
        if rational_kind(kind) {
            let c = self.table.rat(t).ok_or(Stop::Fall(F_SHAPE))?;
            self.consts.push(c.clone());
            return Ok(T::Const(c));
        }
        if class.flags & flag::IS_RATIONAL != 0 {
            // a subclass of Rational: `isinstance(e, Rational)` holds and the row has no p/q to read
            return Err(Stop::Fall(F_SHAPE));
        }
        let args = &self.table.row(t).args;
        match kind {
            Kind::Add | Kind::Mul => {
                let mut fs = Vec::with_capacity(args.len());
                for a in args.iter() {
                    fs.push(self.term(*a, used, depth + 1)?);
                }
                Ok(if kind == Kind::Add { T::Add(fs) } else { T::Mul(fs) })
            }
            Kind::Pow => {
                if args.len() != 2 {
                    return Err(Stop::Fall(F_SHAPE));
                }
                let fb = self.term(args[0], used, depth + 1)?;
                let fx = self.term(args[1], used, depth + 1)?;
                if self.pi && self.table.class_of(args[0]).kind == Kind::Pi {
                    if let Some(x) = self.table.rat(args[1]) {
                        if !x.is_int() || x.n.is_negative() {
                            // 1/pi, sqrt(pi): outside Q[pi] at every point
                            return Err(Stop::Und);
                        }
                    }
                }
                Ok(T::Pow(Box::new(fb), Box::new(fx)))
            }
            Kind::Pi => {
                if !self.pi {
                    return Err(Stop::NeedPi);
                }
                Ok(T::Pi)
            }
            _ => Err(Stop::Und),
        }
    }

    /// An atom side: the boundary lookup, then `_term` on its row.
    fn side(&mut self, e: &Bound<'py, PyAny>, used: &mut BTreeSet<usize>) -> Result<T, Stop> {
        let p = e.py();
        tick(LOOKUP);
        let id = match read(p, self.ids.get_item(e))? {
            None => return Err(Stop::Fall(F_MISS)),
            Some(id) => read(p, id.extract::<u32>())?,
        };
        if !planted(P_SIDE) {
            let o = read(p, self.objects.get_item(id))?;
            if !o.get_type().is(&e.get_type()) {
                return Err(Stop::Fall(F_TYPE));
            }
        }
        self.term(TermId(id), used, 0)
    }

    /// witness.py `_formula`.
    fn formula(&mut self, f: &Bound<'py, PyAny>, depth: u32) -> Result<F, Stop> {
        let p = f.py();
        if f.is(&*PyBool::new(p, true)) {
            return Ok(F::Const(true));
        }
        if f.is(&*PyBool::new(p, false)) {
            return Ok(F::Const(false));
        }
        if depth > DEPTH {
            return Err(Stop::Fall(F_SHAPE));
        }
        let t = f.get_type();
        let c = self.classes;
        if t.is(&c[0]) {
            let name = read(p, f.getattr(intern!(p, "pred")))?;
            let e = read(p, f.getattr(intern!(p, "expr")))?;
            let name = match name.cast_exact::<PyString>() {
                Ok(s) => read(p, s.to_str().map(str::to_owned))?,
                Err(_) => return Err(Stop::Fall(F_SHAPE)),
            };
            let mut used = BTreeSet::new();
            let n0 = self.size;
            let is_args = e.get_type().is(&c[8]);
            if name == "eq" || name == "lt" {
                if !is_args {
                    return Err(Stop::Und);
                }
                let e = read(p, e.cast::<PyTuple>().map_err(PyErr::from))?;
                if e.len() != 2 {
                    return Err(Stop::Und);
                }
                let a = Rc::new(self.side(&read(p, e.get_item(0))?, &mut used)?);
                let b = Rc::new(self.side(&read(p, e.get_item(1))?, &mut used)?);
                self.probes.push((Probe::Diff(a.clone(), b.clone()), used.into_iter().collect(), self.size - n0));
                return Ok(if name == "eq" { F::Eq(a, b) } else { F::Lt(a, b) });
            }
            if is_args {
                return Err(Stop::Und);
            }
            let pr = pred(&name)?;
            let ft = Rc::new(self.side(&e, &mut used)?);
            if !matches!(*ft, T::Sym(_)) {
                self.probes.push((Probe::Term(ft.clone()), used.into_iter().collect(), self.size - n0));
            }
            return Ok(F::Pred(pr, ft));
        }
        let which = match (1..8).find(|i| t.is(&c[*i])) {
            Some(i) => i,
            // another class: Python reads its `.args` first, whatever that gives
            None => return Err(Stop::Fall(F_SHAPE)),
        };
        let args = read(p, f.getattr(intern!(p, "args")))?;
        if which == 1 {
            let g = read(p, args.get_item(0))?;
            return Ok(F::Not(Box::new(self.formula(&g, depth + 1)?)));
        }
        let mut gs = Vec::new();
        for a in read(p, args.try_iter())? {
            gs.push(self.formula(&read(p, a)?, depth + 1)?);
        }
        Ok(match which {
            2 => F::And(gs),
            3 => F::Or(gs),
            4 => F::Implies(gs),
            5 => F::Equivalent(gs),
            6 => F::Exclusive(gs),
            _ => {
                if gs.len() != 3 {
                    return Err(Stop::Fall(F_SHAPE));
                }
                F::Ite(gs)
            }
        })
    }
}

/// One query's compiled form: witness.py `_Query` with the two formulas and the symbols' own assumptions. Lives for one
/// call of `witnesses`.
#[pyclass(unsendable)]
pub struct WitnessQuery {
    syms: Vec<TermId>,
    consts: Vec<Rat>,
    probes: Vec<(Probe, Vec<usize>, u64)>,
    size: u64,
    pi: bool,
    fa: F,
    fp: F,
    /// witness.py `_own` per symbol: every fact of `assumptions0` that is not None.
    owns: Vec<Vec<(Pred, bool)>>,
    work: Cell<u64>,
}

fn own_at(own: &[(Pred, bool)], v: &Rat) -> E<bool> {
    let v = Val::Q(v.clone());
    let mut ok = true;
    for (p, want) in own {
        ok &= pred_at(*p, &v)? == *want;
    }
    Ok(ok)
}

impl WitnessQuery {
    /// witness.py `_Query.spend`.
    fn spend(&self, n: u64, bound: u64) -> bool {
        let w = self.work.get() + n;
        self.work.set(w);
        bound != 0 && (w > bound || (w == bound && planted(P_WORK)))
    }

    /// witness.py `_roots`. The symbols of a probe are visited in index order, Python's in its set's order: each
    /// (symbol, other) pair charges and proposes on its own (`out[i]` is per symbol and every charge of one probe is
    /// the same `cost`), so the roots, their order per symbol and the charge that passes the bound are the same.
    fn roots(&self, n: usize, bound: u64) -> Option<Vec<Vec<Rat>>> {
        let mut out = vec![Vec::new(); n];
        let (zero, one) = (Rat::int(0), Rat::int(1));
        for (d, used, cost) in &self.probes {
            for &i in used {
                for other in [&zero, &one] {
                    let mut pt = vec![other.clone(); n];
                    pt[i] = zero.clone();
                    if self.spend(*cost, bound) {
                        return None;
                    }
                    let Ok(d0) = d.at(&pt) else { continue };
                    pt[i] = one.clone();
                    if self.spend(*cost, bound) {
                        return None;
                    }
                    let Ok(d1) = d.at(&pt) else { continue };
                    if d1 == d0 {
                        continue;
                    }
                    // the secant's root is proposed only if it is rational
                    let (Val::Q(s), Val::Q(d0)) = (sub(&d1, &d0), d0) else { continue };
                    let Some(r) = d0.neg().div(&s) else { continue };
                    pt[i] = r.clone();
                    if self.spend(*cost, bound) {
                        return None;
                    }
                    let Ok(at) = d.at(&pt) else { continue };
                    if at == Val::Q(zero.clone()) && !out[i].contains(&r) {
                        out[i].push(r);
                    }
                }
            }
        }
        Some(out)
    }

    /// witness.py `_pools`.
    fn pools(&self, bound: u64) -> Option<Vec<Vec<Rat>>> {
        let n = self.syms.len();
        let roots = self.roots(n, bound)?;
        let q = |a: i64, b: i64| Rat::new(BigInt::from(a), BigInt::from(b));
        let (one, half) = (Rat::int(1), q(1, 2));
        let mut cs: Vec<Rat> = Vec::new();
        for c in &self.consts {
            if !cs.contains(c) {
                cs.push(c.clone());
            }
        }
        let abs = |c: &Rat| if c.sign() < 0 { c.neg() } else { c.clone() };
        cs.sort_by(|a, b| abs(a).cmp(&abs(b)).then_with(|| a.cmp(b)));
        let mut consts = Vec::new();
        for c in cs.iter().take(8) {
            consts.extend([c.clone(), c.add(&one), c.sub(&one), c.add(&half), c.sub(&half)]);
        }
        let head = [q(0, 1), q(1, 1), q(-1, 1), q(2, 1), q(-2, 1), q(1, 2), q(-1, 2)];
        let tail = [
            q(3, 1), q(-3, 1), q(3, 2), q(-3, 2), q(4, 1), q(-4, 1), q(1, 3), q(-1, 3), q(5, 1), q(-5, 1), q(6, 1),
            q(7, 1), q(9, 1), q(10, 1), q(-10, 1), q(1, 4), q(5, 2), q(-5, 2), q(100, 1), q(-100, 1),
        ];
        let mut pools = Vec::with_capacity(n);
        for i in 0..n {
            let mut rs: Vec<Rat> = roots[i].iter().take(12).cloned().collect();
            rs.sort();
            let mut crit = rs.clone();
            for w in rs.windows(2) {
                crit.push(w[0].add(&w[1]).mul(&half));
            }
            if let (Some(lo), Some(hi)) = (rs.first(), rs.last()) {
                crit.extend([lo.sub(&one), hi.add(&one), lo.sub(&half), hi.add(&half)]);
            }
            let mut pool: Vec<Rat> = Vec::new();
            let mut seen: Vec<Rat> = Vec::new();
            for v in head.iter().chain(crit.iter()).chain(consts.iter()).chain(tail.iter()) {
                if seen.contains(v) {
                    continue;
                }
                seen.push(v.clone());
                // an own assumption without an exact value here: not proposed
                if let Ok(true) = own_at(&self.owns[i], v) {
                    pool.push(v.clone());
                }
            }
            pools.push(pool);
        }
        Some(pools)
    }

    /// witness.py `_holds`.
    fn holds(&self, pt: &[Rat]) -> Option<bool> {
        for (own, v) in self.owns.iter().zip(pt) {
            match own_at(own, v) {
                Ok(true) => {}
                _ => return None,
            }
        }
        match holds_f(&self.fa, pt) {
            Ok(true) => {}
            _ => return None,
        }
        holds_f(&self.fp, pt).ok()
    }

    /// The loop of witness.py `witnesses` over `_by_index_sum`, and the second decision on the two points.
    fn run(&self, cap: u64, limit: u64, bound: u64) -> Option<(Vec<Rat>, Vec<Rat>, u64)> {
        let pools = self.pools(bound)?;
        let sizes: Vec<usize> = pools.iter().map(Vec::len).collect();
        if sizes.contains(&0) {
            return None;
        }
        let cap = if cap == 0 { limit } else { cap };
        let (mut yes, mut no): (Option<Vec<Rat>>, Option<Vec<Rat>>) = (None, None);
        let mut tried = 0u64;
        let mut stopped = false;
        let total: usize = sizes.iter().map(|m| m - 1).sum();
        let mut idx = vec![0usize; sizes.len()];
        for tot in 0..=total {
            // `_compositions(sizes, 0, tot)`: true when the caller is done (found both, or fell through)
            let done = compositions(&sizes, 0, tot, &mut idx, &mut |idx| {
                if tried >= cap || tried >= limit || self.spend(self.size, bound) {
                    stopped = true;
                    return true;
                }
                tried += 1;
                let pt: Vec<Rat> = pools.iter().zip(idx).map(|(pool, i)| pool[*i].clone()).collect();
                match self.holds(&pt) {
                    Some(true) if yes.is_none() => yes = Some(pt),
                    Some(false) if no.is_none() => no = Some(pt),
                    _ => {}
                }
                yes.is_some() && no.is_some()
            });
            if done {
                break;
            }
        }
        if stopped {
            return None;
        }
        let (yes, no) = (yes?, no?);
        // decide again on the two points returned: the search above only proposed them
        if self.holds(&yes) != Some(true) || self.holds(&no) != Some(false) {
            return None;
        }
        Some((yes, no, tried))
    }
}

/// witness.py `_compositions`: every index tuple from position `k` on with the sum `tot`, in its order. True as soon as
/// `f` says stop.
fn compositions(sizes: &[usize], k: usize, tot: usize, idx: &mut Vec<usize>, f: &mut dyn FnMut(&[usize]) -> bool) -> bool {
    let m = sizes[k];
    if k == sizes.len() - 1 {
        if tot < m {
            idx[k] = tot;
            return f(idx);
        }
        return false;
    }
    for i in 0..=tot.min(m - 1) {
        idx[k] = i;
        if compositions(sizes, k + 1, tot - i, idx, f) {
            return true;
        }
    }
    false
}

fn rat_py<'py>(p: Python<'py>, r: &Rat) -> PyResult<Bound<'py, PyAny>> {
    if r.is_int() {
        return Ok(r.n.clone().into_pyobject(p)?.into_any());
    }
    p.import(intern!(p, "fractions"))?.getattr(intern!(p, "Fraction"))?.call1((r.n.clone(), r.d.clone()))
}

#[pymethods]
impl WitnessQuery {
    /// The term ids of the query's symbols, in walk order: witness.py `q.syms`.
    #[getter]
    fn syms(&self) -> Vec<u32> {
        self.syms.iter().map(|t| t.0).collect()
    }

    /// witness.py `q.size`: the term evaluations one point costs.
    #[getter]
    fn size(&self) -> u64 {
        self.size
    }

    /// witness.py `q.work`: the term evaluations charged so far.
    #[getter]
    fn work(&self) -> u64 {
        self.work.get()
    }

    /// witness.py `q.pi`.
    #[getter]
    fn pi(&self) -> bool {
        self.pi
    }

    /// From `_pools` to the second decision: `(point where the proposition is True, point where it is False, points
    /// tried)` as ints and Fractions, or None. `cap`, `limit`, `work`: witness.py's CAP[0], LIMIT and WORK[0] now.
    fn search<'py>(&self, p: Python<'py>, cap: u64, limit: u64, work: u64) -> PyResult<Option<Bound<'py, PyTuple>>> {
        tick(SEARCH);
        let Some((yes, no, tried)) = self.run(cap, limit, work) else { return Ok(None) };
        tick(FOUND);
        let list = |pt: &[Rat]| -> PyResult<Bound<'py, PyAny>> {
            let v = pt.iter().map(|r| rat_py(p, r)).collect::<PyResult<Vec<_>>>()?;
            Ok(pyo3::types::PyList::new(p, v)?.into_any())
        };
        Ok(Some(PyTuple::new(p, [list(&yes)?, list(&no)?, tried.into_pyobject(p)?.into_any()])?))
    }
}

fn compile_once<'py>(
    table: &TermTable, ids: &Bound<'py, PyDict>, objects: &Bound<'py, PyAny>, classes: &[Bound<'py, PyAny>],
    assumptions: &Bound<'py, PyAny>, proposition: &Bound<'py, PyAny>, pi: bool,
) -> Result<WitnessQuery, Stop> {
    let mut cx = Cx {
        table, ids, objects, classes, pi, syms: Vec::new(), index: HashMap::new(), consts: Vec::new(), probes: Vec::new(),
        size: 0,
    };
    let fa = cx.formula(assumptions, 0)?;
    let fp = cx.formula(proposition, 0)?;
    let mut owns = Vec::with_capacity(cx.syms.len());
    for s in &cx.syms {
        // the symbol's `assumptions0`, in dict order: the table's read, memoized for the query
        let facts = table.symbol_facts(*s).map_err(|_| Stop::Fall(F_SHAPE))?;
        let mut own = Vec::new();
        for (name, v) in &facts {
            if let Some(want) = v {
                own.push((pred(name)?, *want));
            }
        }
        owns.push(own);
    }
    Ok(WitnessQuery { syms: cx.syms, consts: cx.consts, probes: cx.probes, size: cx.size, pi, fa, fp, owns, work: Cell::new(0) })
}

/// witness.py `witnesses` from `_Query()` to `if not q.syms`: the query compiled on the table's rows. None: undecided
/// or no symbol, the caller returns None. False: not mirrored, the caller leaves the whole query to witness.py
/// (counted by reason). `classes`: witness.py's P, Not, And, Or, Implies, Equivalent, Exclusive, ITE and Args.
#[pyfunction]
fn witness_compile<'py>(
    table: &Bound<'py, PyTermTable>, ids: &Bound<'py, PyDict>, objects: &Bound<'py, PyAny>,
    assumptions: &Bound<'py, PyAny>, proposition: &Bound<'py, PyAny>, classes: [Bound<'py, PyAny>; 9],
) -> PyResult<Bound<'py, PyAny>> {
    let p = table.py();
    tick(COMPILE);
    let table = table.borrow();
    let table = table.witness_table();
    let mut r = compile_once(table, ids, objects, &classes, assumptions, proposition, false);
    if let Err(Stop::NeedPi) = r {
        // pi outside a function: compile again with values in Q[pi]
        r = compile_once(table, ids, objects, &classes, assumptions, proposition, true);
    }
    match r {
        Ok(q) if q.syms.is_empty() => Ok(p.None().into_bound(p)),
        Ok(q) => Ok(Bound::new(p, q)?.into_any()),
        Err(Stop::Und) | Err(Stop::NeedPi) => Ok(p.None().into_bound(p)),
        Err(Stop::Fall(why)) => {
            tick(why);
            Ok(PyBool::new(p, false).to_owned().into_any())
        }
        Err(Stop::Err(e)) => Err(e),
    }
}

#[pyfunction]
fn witness_counts<'py>(p: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
    let d = PyDict::new(p);
    COUNTS.with(|c| NAMES.iter().zip(c).try_for_each(|(n, v)| d.set_item(n, v.get())))?;
    Ok(d)
}

/// Sets the planted bug by name, or none.
#[pyfunction]
#[pyo3(signature = (name=None))]
fn witness_plant(name: Option<&str>) -> PyResult<()> {
    let i = match name {
        None => 0,
        Some(n) => match PLANTS.iter().position(|x| *x == n) {
            Some(i) => i as u8 + 1,
            None => return Err(PyValueError::new_err(format!("witness_plant: {n}: not a plant"))),
        },
    };
    PLANT.with(|c| c.set(i));
    Ok(())
}

fn coeffs(c: Vec<(BigInt, BigInt)>) -> PyResult<Val> {
    if c.is_empty() || c.iter().any(|(_, d)| d.is_zero()) {
        return Err(PyValueError::new_err("witness_pred: coefficients p/q with q != 0"));
    }
    Ok(poly(c.into_iter().map(|(n, d)| Rat::new(n, d)).collect()))
}

/// For the table's test: predicate `name` at the value of Q[pi] with the coefficients `c` (pairs p, q; one pair is a
/// rational). True or False, or None where witness.py raises `_Undecided` (for the name or at the value).
#[pyfunction]
fn witness_pred(name: &str, c: Vec<(BigInt, BigInt)>) -> PyResult<Option<bool>> {
    let v = coeffs(c)?;
    Ok(pred(name).and_then(|p| pred_at(p, &v)).ok())
}

/// For the table's test: `eq` or `lt` of two values of Q[pi], as `witness_pred`.
#[pyfunction]
fn witness_rel(name: &str, a: Vec<(BigInt, BigInt)>, b: Vec<(BigInt, BigInt)>) -> PyResult<Option<bool>> {
    let (a, b) = (coeffs(a)?, coeffs(b)?);
    match name {
        "eq" => Ok(Some(a == b)),
        "lt" => Ok(sign(&sub(&b, &a)).ok().map(|s| s > 0)),
        _ => Err(PyValueError::new_err("witness_rel: eq or lt")),
    }
}

/// For the table's test: `DEFS` as (name, ((basis predicate, wanted), ...)).
#[pyfunction]
fn witness_definitions() -> Vec<(&'static str, Vec<(&'static str, bool)>)> {
    let name = |b: B| BASIS.iter().find(|(_, x)| *x == b).unwrap().0;
    DEFS.iter().map(|(n, d)| (*n, d.iter().map(|(b, w)| (name(*b), *w)).collect())).collect()
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<WitnessQuery>()?;
    m.add_function(wrap_pyfunction!(witness_compile, m)?)?;
    m.add_function(wrap_pyfunction!(witness_counts, m)?)?;
    m.add_function(wrap_pyfunction!(witness_plant, m)?)?;
    m.add_function(wrap_pyfunction!(witness_pred, m)?)?;
    m.add_function(wrap_pyfunction!(witness_rel, m)?)?;
    m.add_function(wrap_pyfunction!(witness_definitions, m)?)?;
    Ok(())
}
