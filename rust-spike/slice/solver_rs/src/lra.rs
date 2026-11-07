//! A port of satassume/theories/lra/lra.py, with constants: numbers are `Num`, and any step that can raise in Python
//! returns `R` at the same point, after the same writes, since the state comparison reads a session that gave up.
//! Same pivoting, same branch order, same budget. lra/port keeps the frozen rational copy for the replay binary.
//!
//! What must keep Python's order, and how:
//! - Row dicts: insertion order decides conflict literal order and later rows, so `Row` is an ordered Vec.
//! - `_rows`' outer order: `_simplex` walks it and skips only `b > leave`, so with constants it decides which comparison
//!   runs and so whether one raises. `row_order` keeps it.
//! - `_dirty`: `LRATheory.propagate` walks it in ascending order (`sorted`), so a `BTreeSet`. No hash order anywhere:
//!   the `Map`s below are only looked up, and the dump uses `reg_order`, `row_order` and `forms_order`.
//! - `_cols`: sets. A raise during `_update` or `_pivot` comes before any write, so their order changes no state.
use crate::constfield::{refresh_limits, CfErr, Num};
use crate::lra_cert::{certify, limits, rational_values, within, CertAtoms};
use num_bigint::BigInt;
use pyo3::exceptions::PyException;
use pyo3::prelude::*;
use crate::rat::Rat;
use std::collections::HashMap;

#[cfg(not(feature = "fxhash"))]
pub type Map<K, V> = HashMap<K, V>;
#[cfg(feature = "fxhash")]
pub type Map<K, V> = HashMap<K, V, std::hash::BuildHasherDefault<Fx>>;

#[cfg(feature = "fxhash")]
#[derive(Default)]
pub struct Fx(u64);
#[cfg(feature = "fxhash")]
impl std::hash::Hasher for Fx {
    fn write(&mut self, bytes: &[u8]) {
        for b in bytes {
            self.write_u64(*b as u64);
        }
    }
    #[inline]
    fn write_u64(&mut self, x: u64) {
        self.0 = (self.0.rotate_left(5) ^ x).wrapping_mul(0x517cc1b727220a95);
    }
    #[inline]
    fn write_u32(&mut self, x: u32) {
        self.write_u64(x as u64);
    }
    #[inline]
    fn write_i64(&mut self, x: i64) {
        self.write_u64(x as u64);
    }
    #[inline]
    fn write_usize(&mut self, x: usize) {
        self.write_u64(x as u64);
    }
    #[inline]
    fn finish(&self) -> u64 {
        self.0
    }
}

#[cfg(feature = "mutants")]
pub fn mutant(n: u32) -> bool {
    use std::sync::OnceLock;
    static M: OnceLock<u32> = OnceLock::new();
    *M.get_or_init(|| std::env::var("LRA_MUT").ok().and_then(|s| s.parse().ok()).unwrap_or(0)) == n
}
#[cfg(not(feature = "mutants"))]
#[inline(always)]
pub fn mutant(_n: u32) -> bool {
    false
}

pub const BRANCH_BUDGET: i64 = 16;

/// A fallible step: `Undecided` and `TooLarge` make the theory give up at the hook, anything else goes up as in Python.
pub type R<T> = Result<T, CfErr>;

#[derive(Clone, Copy, PartialEq, Eq, Debug, Hash)]
pub enum Kind {
    Le,
    Lt,
    Ge,
    Gt,
    Eq,
    Ne,
}
use Kind::*;

fn neg_kind(k: Kind) -> Kind {
    match k {
        Le => Gt,
        Lt => Ge,
        Ge => Lt,
        Gt => Le,
        Eq => Ne,
        Ne => Eq,
    }
}

fn flip_kind(k: Kind) -> Kind {
    match k {
        Le => Ge,
        Lt => Gt,
        Ge => Le,
        Gt => Lt,
        Eq => Eq,
        Ne => Ne,
    }
}

pub type Bound = (Num, Num);

// Python's comparisons of numbers and of tuples. `a > b` is `b < a` and `a >= b` is `b <= a`: `_cmp` takes the sign of
// the difference. A tuple comparison finds the first position that isn't `is`/`==` and compares only there; formal
// equality answers True without evaluating, which also covers the `is` shortcut.
fn gt(a: &Num, b: &Num) -> R<bool> {
    b.lt(a)
}
fn ge(a: &Num, b: &Num) -> R<bool> {
    b.le(a)
}
fn t_eq(a0: &Num, a1: &Num, b0: &Num, b1: &Num) -> R<bool> {
    Ok(a0.py_eq(b0)? && a1.py_eq(b1)?)
}
fn t_lt(a0: &Num, a1: &Num, b0: &Num, b1: &Num) -> R<bool> {
    if !a0.py_eq(b0)? {
        return a0.lt(b0);
    }
    if !a1.py_eq(b1)? {
        return a1.lt(b1);
    }
    Ok(false)
}
fn t_le(a0: &Num, a1: &Num, b0: &Num, b1: &Num) -> R<bool> {
    if !a0.py_eq(b0)? {
        return a0.le(b0);
    }
    if !a1.py_eq(b1)? {
        return a1.le(b1);
    }
    Ok(true)
}
fn t_gt(a0: &Num, a1: &Num, b0: &Num, b1: &Num) -> R<bool> {
    t_lt(b0, b1, a0, a1)
}
fn t_ge(a0: &Num, a1: &Num, b0: &Num, b1: &Num) -> R<bool> {
    t_le(b0, b1, a0, a1)
}
/// `b == (c, _ZERO)` for an optional bound: None is never equal.
fn opt_eq0(b: &Option<Bound>, c: &Num) -> R<bool> {
    match b {
        None => Ok(false),
        Some(x) => t_eq(&x.0, &x.1, c, &Num::zero()),
    }
}

/// A dict in insertion order: deleting closes the gap, a new key goes last.
#[derive(Default, Clone)]
pub struct Row(pub Vec<(u32, Num)>);

impl Row {
    #[inline]
    fn pos(&self, k: u32) -> Option<usize> {
        self.0.iter().position(|e| e.0 == k)
    }
    #[inline]
    fn get(&self, k: u32) -> Option<&Num> {
        self.0.iter().find(|e| e.0 == k).map(|e| &e.1)
    }
}

/// `_dirty`. `first_added` exists only for the planted bug that walks it in the order of first addition.
#[derive(Default)]
pub struct Dirty {
    pub(crate) set: std::collections::BTreeSet<u32>,
    #[cfg(feature = "mutants")]
    first_added: Vec<u32>,
}

impl Dirty {
    pub fn is_empty(&self) -> bool {
        self.set.is_empty()
    }
    #[inline]
    pub fn add(&mut self, key: u32) {
        #[cfg(feature = "mutants")]
        if !self.set.contains(&key) {
            self.first_added.push(key);
        }
        self.set.insert(key);
    }
}

pub enum Payload {
    Plain { neg: u32, strict: bool, eq: bool, constant: Num, terms: Vec<(u32, Num)> },
    Integral { offset: Num, terms: Vec<(u32, Num)> },
}

pub enum CheckResult {
    Conflict(Vec<i32>),
    Sat(Vec<(u32, Num)>), // the model: term id, value, in variable order
}

pub(crate) enum Trail {
    Lo(u32, Option<Bound>, i32),
    Up(u32, Option<Bound>, i32),
    Asg(u32),
    Dis,
    Int,
}

#[derive(Default, Clone, Copy)]
pub struct Stats {
    pub pivots: u64,
    pub checks: u64,
    pub conflicts: u64,
    pub propagations: u64,
    pub branches: u64,
    pub gave_up: u64,
    pub exhausted: u64,
}

#[cfg(feature = "prof")]
pub mod prof {
    use std::sync::atomic::{AtomicU64, Ordering::Relaxed};
    pub static MAX_ROW: AtomicU64 = AtomicU64::new(0);
    pub static MAX_COL: AtomicU64 = AtomicU64::new(0);
    pub static MAX_VARS: AtomicU64 = AtomicU64::new(0);
    pub static SIMPLEX: AtomicU64 = AtomicU64::new(0);
    pub fn sizes(row: usize, col: usize, vars: usize) {
        MAX_ROW.fetch_max(row as u64, Relaxed);
        MAX_COL.fetch_max(col as u64, Relaxed);
        MAX_VARS.fetch_max(vars as u64, Relaxed);
    }
    pub fn simplex() {
        SIMPLEX.fetch_add(1, Relaxed);
    }
}

fn dedupe(lits: Vec<i32>) -> Vec<i32> {
    let mut out: Vec<i32> = Vec::with_capacity(lits.len());
    for l in lits {
        if l != 0 && !out.contains(&l) {
            out.push(l);
        }
    }
    out
}

/// `_floor(q, d)`. An Element is `math.floor(q)`, with `d` unused; `d` itself can be an Element.
fn floor_d(q: &Num, d: &Num) -> R<Rat> {
    match q {
        Num::Q(r) if r.is_int() => Ok(if d.lt(&Num::zero())? { r.sub(&Rat::ONE) } else { r.clone() }),
        Num::Q(r) => Ok(r.floor()),
        e => e.floor(),
    }
}

/// `_ceil(q, d)`.
fn ceil_d(q: &Num, d: &Num) -> R<Rat> {
    match q {
        Num::Q(r) if r.is_int() => Ok(if gt(d, &Num::zero())? { r.add(&Rat::ONE) } else { r.clone() }),
        Num::Q(r) => Ok(r.ceil()),
        e => e.ceil(),
    }
}

fn is_one_zero(m: &Num, k: &Num) -> bool {
    // `m is _ONE and k is _ZERO`: `_register_integral` and the disequality split make exactly the rationals 1 and 0 so
    matches!((m, k), (Num::Q(a), Num::Q(b)) if *a == Rat::ONE && b.is_zero())
}

/// `_cagg` and `_cert`: the aggregates the certificate keeps between calls, and its memo per `values`. The memo's
/// `except Exception` is the caller's, `Theory::certificate`.
pub struct CertMemo {
    agg: CertAtoms,
    memo: Vec<(Option<(Rat, BigInt)>, CertKey, (bool, Option<Rat>))>,
}
type CertKey = (usize, usize, usize, usize, [i64; 6]);

/// `_int_verdict`: (truth, the literals of the bounds), or None.
pub type Verdict = Option<(bool, [i32; 2])>;

pub struct Theory {
    pub exhausted: bool,
    /// `self.eager`: run the simplex inside `assert_lit` of a bound.
    pub eager: bool,
    /// `self.branched_rational`.
    pub branched_rational: bool,
    /// `self.gave_up`: every hook is a no-op from here on.
    pub gave_up: bool,
    /// `self._fields`: a payload had a constant, even one that later cancelled.
    pub fields: bool,
    /// Every registered literal in order: the insertion order of `_atoms`, `_ints`, `_ground` and `_ints_on`, which the
    /// maps don't keep. Only the dump reads it.
    pub(crate) reg_order: Vec<u32>,
    pub stats: Stats,
    pub(crate) key: Vec<i64>, // term id, -1 for a slack
    pub(crate) var_of: Map<u32, u32>,
    pub(crate) slack_of: Map<Vec<(u32, Num)>, u32>,
    /// `_slack_of`'s keys in insertion order: the certificate walks them.
    pub(crate) slack_forms: Vec<Vec<(u32, Num)>>,
    pub(crate) forms: Map<Vec<(u32, Num)>, (u32, Num)>,
    /// `_forms`' keys in insertion order, for the dump.
    pub(crate) forms_order: Vec<Vec<(u32, Num)>>,
    pub(crate) lo: Vec<Option<Bound>>,
    pub(crate) up: Vec<Option<Bound>>,
    pub(crate) lo_r: Vec<i32>,
    pub(crate) up_r: Vec<i32>,
    pub(crate) vq: Vec<Num>,
    pub(crate) vd: Vec<Num>,
    pub(crate) rows: Vec<Option<Row>>,
    /// `_rows`' keys in dict order. `_simplex` walks them in this order and only skips `b > leave`, so with constants
    /// this order decides which comparison runs, and so whether one raises.
    pub(crate) row_order: Vec<u32>,
    pub(crate) cols: Vec<Vec<u32>>,
    pub(crate) atoms: Map<u32, (u32, Kind, Num)>,
    pub(crate) ground: Map<u32, bool>,
    pub(crate) atoms_on: Vec<Vec<u32>>,
    pub(crate) assigned: Map<u32, bool>,
    pub(crate) diseqs: Vec<(u32, Num, i32)>,
    pub(crate) ints: Map<u32, (u32, Num, Num)>,
    pub(crate) ints_on: Map<u32, Vec<u32>>,
    pub(crate) int_lits: Vec<(u32, Num, Num, i32)>,
    /// `_int_memo`: only with constants, and only when both bounds have literals.
    pub(crate) int_memo: Map<(u32, Num, Num, i32, i32), Verdict>,
    pub(crate) trail: Vec<Trail>,
    pub(crate) lims: Vec<usize>,
    pub(crate) dirty: Dirty,
    pub(crate) pending_ground: Vec<u32>,
    pub(crate) cert: CertMemo,
}

impl Theory {
    pub fn new() -> Theory {
        Theory {
            exhausted: false,
            eager: true,
            branched_rational: false,
            gave_up: false,
            fields: false,
            reg_order: vec![],
            stats: Stats::default(),
            key: vec![],
            var_of: Map::default(),
            slack_of: Map::default(),
            slack_forms: vec![],
            forms: Map::default(),
            forms_order: vec![],
            lo: vec![],
            up: vec![],
            lo_r: vec![],
            up_r: vec![],
            vq: vec![],
            vd: vec![],
            rows: vec![],
            row_order: vec![],
            cols: vec![],
            atoms: Map::default(),
            ground: Map::default(),
            atoms_on: vec![],
            assigned: Map::default(),
            diseqs: vec![],
            ints: Map::default(),
            ints_on: Map::default(),
            int_lits: vec![],
            int_memo: Map::default(),
            trail: vec![],
            lims: vec![],
            dirty: Dirty::default(),
            pending_ground: vec![],
            cert: CertMemo { agg: CertAtoms::new(), memo: vec![] },
        }
    }

    pub fn nvars(&self) -> usize {
        self.key.len()
    }
    pub fn nrows(&self) -> usize {
        self.row_order.len()
    }

    fn new_var(&mut self, key: i64) -> u32 {
        let v = self.key.len() as u32;
        self.key.push(key);
        self.lo.push(None);
        self.up.push(None);
        self.lo_r.push(0);
        self.up_r.push(0);
        self.vq.push(Num::zero());
        self.vd.push(Num::zero());
        self.rows.push(None);
        self.cols.push(vec![]);
        self.atoms_on.push(vec![]);
        if key >= 0 {
            self.var_of.insert(key as u32, v);
        }
        v
    }

    /// `_give_up`.
    pub fn give_up(&mut self) {
        self.gave_up = true;
        self.stats.gave_up += 1;
    }

    /// Python's `except Undecided` at a hook: give up and answer `dflt`; anything else goes up.
    fn hook<T>(&mut self, r: R<T>, dflt: T) -> R<T> {
        match r {
            Err(e) if e.is_undecided() => {
                self.give_up();
                Ok(dflt)
            }
            x => x,
        }
    }

    fn term_var(&mut self, key: u32) -> u32 {
        match self.var_of.get(&key) {
            Some(v) => *v,
            None => self.new_var(key as i64),
        }
    }

    fn slack(&mut self, form: Vec<(u32, Num)>) -> R<u32> {
        if let Some(s) = self.slack_of.get(&form) {
            return Ok(*s);
        }
        let mut row: Vec<(u32, Num)> = vec![];
        fn plus(row: &mut Vec<(u32, Num)>, k: u32, x: Num) -> R<()> {
            match row.iter().position(|e| e.0 == k) {
                Some(p) => row[p].1 = row[p].1.add(&x)?,
                None => row.push((k, Num::zero().add(&x)?)),
            }
            Ok(())
        }
        for (v, c) in &form {
            match &self.rows[*v as usize] {
                None => plus(&mut row, *v, c.clone())?,
                Some(r) => {
                    for (k, a) in &r.0 {
                        plus(&mut row, *k, c.mul(a)?)?;
                    }
                }
            }
        }
        row.retain(|e| !e.1.formally_zero());
        let (mut vq, mut vd) = (Num::zero(), Num::zero());
        for (k, a) in &row {
            vq = vq.add(&a.mul(&self.vq[*k as usize])?)?;
            vd = vd.add(&a.mul(&self.vd[*k as usize])?)?;
        }
        let s = self.new_var(-1); // arithmetic done: commit
        self.slack_forms.push(form.clone());
        self.slack_of.insert(form, s);
        for (k, _) in &row {
            self.cols[*k as usize].push(s);
        }
        self.vq[s as usize] = vq;
        self.vd[s as usize] = vd;
        self.rows[s as usize] = Some(Row(row));
        self.row_order.push(s);
        Ok(s)
    }

    /// `_lin`: repeated terms summed, every term gets a variable, formal zeros dropped.
    pub(crate) fn lin(&mut self, terms: &[(u32, Num)]) -> R<Vec<(u32, Num)>> {
        let mut lin: Vec<(u32, Num)> = Vec::with_capacity(terms.len());
        for (t, c) in terms {
            match lin.iter().position(|e| e.0 == *t) {
                Some(p) => lin[p].1 = lin[p].1.add(c)?,
                None => lin.push((*t, c.clone())),
            }
        }
        for (t, _) in &lin {
            self.term_var(*t);
        }
        lin.retain(|e| !e.1.formally_zero());
        Ok(lin)
    }

    /// What a payload leaves when its number then raises: `_lin` had run. False if `_lin` itself gave up.
    pub fn touch(&mut self, terms: &[(u32, Num)]) -> R<bool> {
        let r = self.lin(terms).map(|_| true);
        self.hook(r, false)
    }

    fn var_of_form(&mut self, lin: &[(u32, Num)]) -> R<(u32, Num)> {
        let mut key: Vec<(u32, Num)> = lin.to_vec();
        key.sort_by_key(|e| e.0); // a frozenset of (term, coefficient): the same pairs, the same key
        if let Some(r) = self.forms.get(&key) {
            return Ok(r.clone());
        }
        let mut vs: Vec<(u32, Num)> = lin.iter().map(|(t, c)| (self.term_var(*t), c.clone())).collect();
        vs.sort_by_key(|e| e.0);
        let r = if vs.len() == 1 {
            vs[0].clone()
        } else {
            let c = vs[0].1.clone();
            let mut form: Vec<(u32, Num)> = Vec::with_capacity(vs.len());
            for (w, a) in &vs {
                form.push((*w, a.div(&c)?));
            }
            (self.slack(form)?, c)
        };
        self.forms.insert(key.clone(), r.clone());
        self.forms_order.push(key);
        Ok(r)
    }

    pub fn register_atom(&mut self, literal: u32, payload: &Payload) -> R<()> {
        let r = self.register_inner(literal, payload);
        self.hook(r, ())
    }

    fn register_inner(&mut self, literal: u32, payload: &Payload) -> R<()> {
        self.reg_order.push(literal);
        match payload {
            Payload::Integral { offset, terms } => self.register_integral(literal, offset, terms),
            Payload::Plain { neg, strict, eq, constant, terms } => {
                let lin = self.lin(terms)?;
                let k = constant;
                if matches!(k, Num::E(_)) {
                    self.fields = true; // lra.py:662, before anything below can raise
                }
                let mut kind = if *eq {
                    Eq
                } else if *strict {
                    Lt
                } else {
                    Le
                };
                if neg % 2 == 1 {
                    kind = neg_kind(kind);
                }
                if lin.is_empty() {
                    // Python builds the whole dict of six before indexing it: every one of these can raise.
                    let z = Num::zero();
                    let e = z.py_eq(k)?;
                    let ne = !z.py_eq(k)?;
                    let lt = z.lt(k)?;
                    let le = z.le(k)?;
                    let g = gt(&z, k)?;
                    let gq = ge(&z, k)?;
                    let truth = match kind {
                        Eq => e,
                        Ne => ne,
                        Lt => lt,
                        Le => le,
                        Gt => g,
                        Ge => gq,
                    };
                    self.ground.insert(literal, truth);
                    self.pending_ground.push(literal);
                    return Ok(());
                }
                let (v, c) = self.var_of_form(&lin)?;
                let bound = k.div(&c)?;
                if c.lt(&Num::zero())? {
                    kind = flip_kind(kind);
                }
                self.atoms.insert(literal, (v, kind, bound));
                self.atoms_on[v as usize].push(literal);
                self.dirty.add(v);
                Ok(())
            }
        }
    }

    fn register_integral(&mut self, literal: u32, offset: &Num, terms: &[(u32, Num)]) -> R<()> {
        let lin = self.lin(terms)?;
        if matches!(offset, Num::E(_)) {
            self.fields = true; // lra.py:722
        }
        if lin.is_empty() {
            let truth = offset.is_integer()?;
            self.ground.insert(literal, truth);
            self.pending_ground.push(literal);
            return Ok(());
        }
        let (v, m) = self.var_of_form(&lin)?;
        // Only an optimisation: an offset whose floor is undecidable stays as it is.
        let k = match offset.floor().and_then(|f| offset.sub(&Num::Q(f))) {
            Ok(k) => k,
            Err(e) if e.is_undecided() => offset.clone(),
            Err(e) => return Err(e),
        };
        self.ints.insert(literal, (v, m, k));
        self.ints_on.entry(v).or_default().push(literal);
        self.dirty.add(v);
        Ok(())
    }

    pub fn push_level(&mut self) {
        self.lims.push(self.trail.len());
    }

    pub fn pop_level(&mut self) {
        let n = self.lims.pop().unwrap();
        while self.trail.len() > n {
            match self.trail.pop().unwrap() {
                Trail::Lo(v, b, r) => {
                    self.lo[v as usize] = b;
                    self.lo_r[v as usize] = r;
                }
                Trail::Up(v, b, r) => {
                    self.up[v as usize] = b;
                    self.up_r[v as usize] = r;
                }
                Trail::Asg(a) => {
                    self.assigned.remove(&a);
                }
                Trail::Dis => {
                    self.diseqs.pop();
                }
                Trail::Int => {
                    self.int_lits.pop();
                }
            }
        }
    }

    /// None, or the conflict.
    pub fn assert_lit(&mut self, literal: i32) -> R<Option<Vec<i32>>> {
        if self.gave_up {
            return Ok(None);
        }
        let r = self.assert_inner(literal);
        self.hook(r, None)
    }

    fn assert_inner(&mut self, literal: i32) -> R<Option<Vec<i32>>> {
        let a = literal.unsigned_abs();
        let Some((v, kind, c)) = self.atoms.get(&a).cloned() else {
            if let Some(it) = self.ints.get(&a).cloned() {
                return self.assert_integral(literal, it);
            }
            let Some(truth) = self.ground.get(&a).copied() else {
                return Ok(None);
            };
            self.assigned.insert(a, literal > 0);
            self.trail.push(Trail::Asg(a));
            if truth != (literal > 0) {
                self.stats.conflicts += 1;
                return Ok(Some(vec![-literal]));
            }
            return Ok(None);
        };
        self.assigned.insert(a, literal > 0);
        self.trail.push(Trail::Asg(a));
        let kind = if literal < 0 { neg_kind(kind) } else { kind };
        let mut conflict = self.assert_kind(v, kind, &c, literal)?;
        if conflict.is_none() && !self.int_lits.is_empty() && self.ints_on.contains_key(&v) {
            conflict = self.int_bounds(v)?;
        }
        if conflict.is_none() && self.eager && kind != Ne {
            conflict = self.simplex()?;
        }
        if conflict.is_some() {
            self.stats.conflicts += 1;
        }
        Ok(conflict)
    }

    fn assert_kind(&mut self, v: u32, kind: Kind, c: &Num, lit: i32) -> R<Option<Vec<i32>>> {
        match kind {
            Le => self.set_upper(v, (c.clone(), Num::zero()), lit),
            Lt => self.set_upper(v, (c.clone(), Num::Q(Rat::MINUS_ONE)), lit),
            Ge => self.set_lower(v, (c.clone(), Num::zero()), lit),
            Gt => self.set_lower(v, (c.clone(), Num::one()), lit),
            Eq => match self.set_upper(v, (c.clone(), Num::zero()), lit)? {
                Some(x) if !x.is_empty() => Ok(Some(x)), // Python's `or`: an empty list is false
                _ => self.set_lower(v, (c.clone(), Num::zero()), lit),
            },
            Ne => {
                self.diseqs.push((v, c.clone(), lit));
                self.trail.push(Trail::Dis);
                let vi = v as usize;
                if let (Some(lo), Some(up)) = (&self.lo[vi], &self.up[vi]) {
                    // `lo == up == (c, _ZERO)`
                    if t_eq(&lo.0, &lo.1, &up.0, &up.1)? && t_eq(&up.0, &up.1, c, &Num::zero())? {
                        return Ok(Some(dedupe(vec![-lit, -self.lo_r[vi], -self.up_r[vi]])));
                    }
                }
                Ok(None)
            }
        }
    }

    fn set_upper(&mut self, v: u32, b: Bound, lit: i32) -> R<Option<Vec<i32>>> {
        let vi = v as usize;
        if let Some(up) = &self.up[vi] {
            if t_le(&up.0, &up.1, &b.0, &b.1)? {
                return Ok(None);
            }
        }
        if let Some(lo) = &self.lo[vi] {
            if t_lt(&b.0, &b.1, &lo.0, &lo.1)? {
                return Ok(Some(dedupe(vec![-lit, -self.lo_r[vi]])));
            }
        }
        let old = self.up[vi].replace(b.clone());
        self.trail.push(Trail::Up(v, old, self.up_r[vi]));
        self.up_r[vi] = lit;
        self.dirty.add(v);
        if self.rows[vi].is_none() && t_gt(&self.vq[vi], &self.vd[vi], &b.0, &b.1)? {
            self.update(v, &b)?;
        }
        Ok(None)
    }

    fn set_lower(&mut self, v: u32, b: Bound, lit: i32) -> R<Option<Vec<i32>>> {
        let vi = v as usize;
        if let Some(lo) = &self.lo[vi] {
            if t_ge(&lo.0, &lo.1, &b.0, &b.1)? {
                return Ok(None);
            }
        }
        if let Some(up) = &self.up[vi] {
            if t_gt(&b.0, &b.1, &up.0, &up.1)? {
                return Ok(Some(dedupe(vec![-lit, -self.up_r[vi]])));
            }
        }
        let old = self.lo[vi].replace(b.clone());
        self.trail.push(Trail::Lo(v, old, self.lo_r[vi]));
        self.lo_r[vi] = lit;
        self.dirty.add(v);
        if self.rows[vi].is_none() && t_lt(&self.vq[vi], &self.vd[vi], &b.0, &b.1)? {
            self.update(v, &b)?;
        }
        Ok(None)
    }

    /// Computed first, then written: a raise leaves the values as they were.
    fn update(&mut self, v: u32, b: &Bound) -> R<()> {
        let vi = v as usize;
        let dq = b.0.sub(&self.vq[vi])?;
        let dd = b.1.sub(&self.vd[vi])?;
        let mut new = Vec::with_capacity(self.cols[vi].len());
        for &r in &self.cols[vi] {
            let ri = r as usize;
            let a = self.rows[ri].as_ref().unwrap().get(v).unwrap();
            let nq = self.vq[ri].add(&a.mul(&dq)?)?;
            let nd = self.vd[ri].add(&a.mul(&dd)?)?;
            new.push((ri, nq, nd));
        }
        for (ri, nq, nd) in new {
            self.vq[ri] = nq;
            self.vd[ri] = nd;
        }
        self.vq[vi] = b.0.clone();
        self.vd[vi] = b.1.clone();
        Ok(())
    }

    fn assert_integral(&mut self, literal: i32, it: (u32, Num, Num)) -> R<Option<Vec<i32>>> {
        let a = literal.unsigned_abs();
        self.assigned.insert(a, literal > 0);
        self.trail.push(Trail::Asg(a));
        let (v, m, k) = it;
        // Appended before the verdict, which can raise.
        self.int_lits.push((v, m.clone(), k.clone(), literal));
        self.trail.push(Trail::Int);
        if let Some((truth, why)) = self.int_verdict(v, &m, &k)? {
            if truth != (literal > 0) {
                self.stats.conflicts += 1;
                let mut x = vec![-literal];
                x.extend(why.iter().map(|l| -l));
                return Ok(Some(dedupe(x)));
            }
        }
        Ok(None)
    }

    fn int_verdict(&mut self, v: u32, m: &Num, k: &Num) -> R<Verdict> {
        let vi = v as usize;
        if self.lo[vi].is_none() || self.up[vi].is_none() {
            return Ok(None);
        }
        if self.fields {
            let (lr, ur) = (self.lo_r[vi], self.up_r[vi]);
            if lr != 0 && ur != 0 {
                let key = (v, m.clone(), k.clone(), lr, ur);
                if let Some(r) = self.int_memo.get(&key) {
                    return Ok(*r);
                }
                let r = self.int_verdict_bounds(vi, m, k)?;
                self.int_memo.insert(key, r);
                return Ok(r);
            }
        }
        self.int_verdict_bounds(vi, m, k)
    }

    fn int_verdict_bounds(&self, vi: usize, m: &Num, k: &Num) -> R<Verdict> {
        let (lo, up) = (self.lo[vi].as_ref().unwrap(), self.up[vi].as_ref().unwrap());
        let why = [self.lo_r[vi], self.up_r[vi]];
        let (a, b) = if is_one_zero(m, k) {
            (lo.clone(), up.clone())
        } else {
            let a = (m.mul(&lo.0)?.add(k)?, m.mul(&lo.1)?);
            let b = (m.mul(&up.0)?.add(k)?, m.mul(&up.1)?);
            if m.lt(&Num::zero())? {
                (b, a)
            } else {
                (a, b)
            }
        };
        if t_eq(&lo.0, &lo.1, &up.0, &up.1)? {
            return Ok(Some((a.0.is_integer()?, why))); // pinned: d == 0 here
        }
        let c = ceil_d(&a.0, &a.1)?;
        if c > floor_d(&b.0, &b.1)? {
            return Ok(Some((false, why)));
        }
        Ok(None)
    }

    fn int_bounds(&mut self, v: u32) -> R<Option<Vec<i32>>> {
        for i in 0..self.int_lits.len() {
            if self.int_lits[i].0 == v {
                let (_, m, k, lit) = self.int_lits[i].clone();
                if let Some((truth, why)) = self.int_verdict(v, &m, &k)? {
                    if truth != (lit > 0) {
                        let mut x = vec![-lit];
                        x.extend(why.iter().map(|l| -l));
                        return Ok(Some(dedupe(x)));
                    }
                }
            }
        }
        Ok(None)
    }

    fn branch(&mut self, budget: &mut i64) -> R<Option<Vec<i32>>> {
        // cases: (kind, n) twice; (v, m, k, lit) of the split
        let mut split: Option<(u32, Num, Num, i32, [(Kind, Num); 2])> = None;
        let fields = self.fields;
        let mut y: Option<Option<Rat>> = None; // the certificate's, once needed
        let mut skipped = false;
        for i in 0..self.int_lits.len() {
            let (v, m, k, lit) = self.int_lits[i].clone();
            let vi = v as usize;
            let (nq, nd) = if is_one_zero(&m, &k) {
                (self.vq[vi].clone(), self.vd[vi].clone())
            } else {
                (m.mul(&self.vq[vi])?.add(&k)?, m.mul(&self.vd[vi])?)
            };
            let integral = !nd.nonzero()? && nq.is_integer()?;
            if lit > 0 && !integral {
                if fields && self.cert_skips(&mut y, vi)? {
                    skipped = true;
                    continue;
                }
                let f = Num::Q(floor_d(&nq, &nd)?);
                let f1 = f.add(&Num::one())?;
                split = Some((v, m, k, lit, [(Le, f), (Ge, f1)]));
                break;
            }
            if lit < 0 && integral {
                if fields && self.cert_skips(&mut y, vi)? {
                    skipped = true;
                    continue;
                }
                let down = !opt_eq0(&self.lo[vi], &self.vq[vi])?;
                let cases = if down == gt(&m, &Num::zero())? {
                    [(Lt, nq.clone()), (Gt, nq)]
                } else {
                    [(Gt, nq.clone()), (Lt, nq)]
                };
                split = Some((v, m, k, lit, cases));
                break;
            }
        }
        if split.is_none() {
            if skipped {
                self.exhausted = true;
                self.stats.exhausted += 1;
                return Ok(None);
            }
            for (v, c, lit) in &self.diseqs {
                let vi = *v as usize;
                if self.vq[vi].py_eq(c)? && !self.vd[vi].nonzero()? {
                    let down = !opt_eq0(&self.lo[vi], c)?;
                    let cases = if down { [(Lt, c.clone()), (Gt, c.clone())] } else { [(Gt, c.clone()), (Lt, c.clone())] };
                    split = Some((*v, Num::one(), Num::zero(), *lit, cases));
                    break;
                }
            }
        }
        let Some((v, m, k, lit, cases)) = split else {
            return Ok(None);
        };
        let limit = if mutant(2) { 1 } else { 0 };
        if *budget <= limit {
            self.exhausted = true;
            self.stats.exhausted += 1;
            return Ok(None);
        }
        *budget -= 1;
        self.stats.branches += 1;
        if !fields {
            self.branched_rational = true;
        }
        let mut expl = vec![-lit];
        for (kind, n) in cases.iter() {
            let kind = if m.lt(&Num::zero())? { flip_kind(*kind) } else { *kind };
            self.push_level();
            let bound = n.sub(&k)?.div(&m)?;
            let mut r = self.assert_kind(v, kind, &bound, 0)?;
            if r.is_none() {
                r = self.simplex()?;
                if r.is_none() {
                    r = self.branch(budget)?;
                }
            }
            self.pop_level();
            match r {
                None => return Ok(None),
                Some(x) => expl.extend(x),
            }
        }
        Ok(Some(dedupe(expl)))
    }

    /// `_certificate` (lra.py:448): `(certified, Y)`, memoized per registered atom count and per `values`. Any failure
    /// of the certificate is `(False, None)`, as Python's `except Exception` makes it.
    pub fn certificate(&mut self, values: Option<&(Rat, BigInt)>) -> R<(bool, Option<Rat>)> {
        refresh_limits()?;
        let key: CertKey = (self.atoms.len(), self.ints.len(), self.slack_of.len(), self.key.len(), limits());
        if let Some((_, k, r)) = self.cert.memo.iter().find(|(v, _, _)| v.as_ref() == values) {
            if *k == key {
                return Ok(r.clone());
            }
        }
        // `except Exception`: a BaseException still goes up.
        let r = match self.certify(values) {
            Ok(r) => r,
            Err(CfErr::Py(e)) if !Python::attach(|py| e.is_instance_of::<PyException>(py)) => return Err(CfErr::Py(e)),
            Err(_) => (false, None),
        };
        match self.cert.memo.iter_mut().find(|(v, _, _)| v.as_ref() == values) {
            Some(e) => {
                e.1 = key;
                e.2 = r.clone();
            }
            None => self.cert.memo.push((values.cloned(), key, r.clone())),
        }
        Ok(r)
    }

    /// `_certify`: registration order for atoms and ints, slack order for the forms, as Python's dicts give them.
    fn certify(&mut self, values: Option<&(Rat, BigInt)>) -> R<(bool, Option<Rat>)> {
        let atoms: Vec<(bool, &Num)> = self
            .reg_order
            .iter()
            .filter_map(|l| self.atoms.get(l))
            .map(|(_, kind, b)| (matches!(kind, Eq | Ne), b))
            .collect();
        let ints: Vec<(&Num, &Num)> =
            self.reg_order.iter().filter_map(|l| self.ints.get(l)).map(|(_, m, k)| (m, k)).collect();
        let forms: Vec<&[(u32, Num)]> = self.slack_forms.iter().map(|f| f.as_slice()).collect();
        let nt = self.key.len() - self.row_order.len();
        certify(&mut self.cert.agg, atoms.into_iter(), ints.into_iter(), forms.into_iter(), nt, values)
    }

    /// `_int_memo`'s entries, for the dump. The state text sorts them by repr, so their order is not read here.
    pub(crate) fn int_memo_order(&self) -> Vec<((u32, Num, Num, i32, i32), Verdict)> {
        self.int_memo.iter().map(|(k, v)| (k.clone(), v.clone())).collect()
    }

    /// `certified`.
    pub fn certified(&mut self) -> R<bool> {
        Ok(self.certificate(None)?.0)
    }

    /// `certified_with`.
    pub fn certified_with(&mut self, values: &(Rat, BigInt)) -> R<bool> {
        Ok(self.certificate(Some(values))?.0)
    }

    /// `rational_values`: `(top, den)` of the nonbasic variables, if all are rational.
    pub fn rational_values(&self) -> Option<(Rat, BigInt)> {
        rational_values((0..self.vq.len()).filter(|&v| self.rows[v].is_none()).map(|v| &self.vq[v]))
    }

    /// `Y is not None and not _within_cert(vq[v], Y)`, reading the certificate once per `_branch`.
    fn cert_skips(&mut self, y: &mut Option<Option<Rat>>, vi: usize) -> R<bool> {
        if y.is_none() {
            *y = Some(self.certificate(None)?.1);
        }
        match y.as_ref().unwrap() {
            None => Ok(false),
            Some(b) => Ok(!within(&self.vq[vi], b)?),
        }
    }

    fn simplex(&mut self) -> R<Option<Vec<i32>>> {
        #[cfg(feature = "prof")]
        prof::simplex();
        loop {
            let (mut leave, mut below) = (-1i64, false);
            for &b in &self.row_order {
                let bl = b as i64;
                // Bland's rule. Planted bug 1: the largest violating basic variable.
                if leave != -1 && (if mutant(1) { bl < leave } else { bl > leave }) {
                    continue;
                }
                let bi = b as usize;
                if let Some(l) = &self.lo[bi] {
                    if t_lt(&self.vq[bi], &self.vd[bi], &l.0, &l.1)? {
                        (leave, below) = (bl, true);
                        continue;
                    }
                }
                if let Some(u) = &self.up[bi] {
                    if t_gt(&self.vq[bi], &self.vd[bi], &u.0, &u.1)? {
                        (leave, below) = (bl, false);
                    }
                }
            }
            if leave == -1 {
                return Ok(None);
            }
            let b = leave as u32;
            let row = self.rows[b as usize].as_ref().unwrap();
            let mut enter: i64 = -1;
            for (j, a) in &row.0 {
                let jl = *j as i64;
                if enter != -1 && (if mutant(9) { jl < enter } else { jl > enter }) {
                    continue;
                }
                let ji = *j as usize;
                let inc = gt(a, &Num::zero())? == below; // need x_j to increase?
                let ok = if inc {
                    match &self.up[ji] {
                        None => true,
                        Some(u) => t_lt(&self.vq[ji], &self.vd[ji], &u.0, &u.1)?,
                    }
                } else {
                    match &self.lo[ji] {
                        None => true,
                        Some(l) => t_gt(&self.vq[ji], &self.vd[ji], &l.0, &l.1)?,
                    }
                };
                if ok {
                    enter = jl;
                }
            }
            if enter == -1 {
                let mut expl = Vec::with_capacity(row.0.len() + 1);
                let bi = b as usize;
                expl.push(-(if below { self.lo_r[bi] } else { self.up_r[bi] }));
                for (j, a) in &row.0 {
                    let ji = *j as usize;
                    let pos = gt(a, &Num::zero())?;
                    expl.push(-(if pos == below { self.up_r[ji] } else { self.lo_r[ji] }));
                }
                return Ok(Some(dedupe(expl)));
            }
            let target = if below {
                self.lo[b as usize].clone().unwrap()
            } else {
                self.up[b as usize].clone().unwrap()
            };
            self.pivot_and_update(b, enter as u32, &target)?;
        }
    }

    fn pivot_and_update(&mut self, b: u32, j: u32, target: &Bound) -> R<()> {
        let (bi, ji) = (b as usize, j as usize);
        let a = self.rows[bi].as_ref().unwrap().get(j).unwrap().clone();
        let tq = target.0.sub(&self.vq[bi])?.div(&a)?;
        let td = target.1.sub(&self.vd[bi])?.div(&a)?;
        let mut new = Vec::with_capacity(self.cols[ji].len() + 1);
        for &k in &self.cols[ji] {
            if k != b {
                let ki = k as usize;
                let ak = self.rows[ki].as_ref().unwrap().get(j).unwrap();
                let nq = self.vq[ki].add(&ak.mul(&tq)?)?;
                let nd = self.vd[ki].add(&ak.mul(&td)?)?;
                new.push((ki, nq, nd));
            }
        }
        new.push((ji, self.vq[ji].add(&tq)?, self.vd[ji].add(&td)?));
        self.pivot(b, j)?; // may raise before writing
        self.vq[bi] = target.0.clone();
        self.vd[bi] = target.1.clone();
        for (k, q, d) in new {
            self.vq[k] = q;
            self.vd[k] = d;
        }
        Ok(())
    }

    #[inline]
    fn col_discard(&mut self, k: u32, r: u32) {
        let c = &mut self.cols[k as usize];
        if let Some(p) = c.iter().position(|x| *x == r) {
            c.swap_remove(p);
        }
    }

    /// `_pivot`: all arithmetic before any write, so a raise leaves the tableau whole. The pivot count is already up.
    fn pivot(&mut self, b: u32, j: u32) -> R<()> {
        self.stats.pivots += 1;
        let (bi, ji) = (b as usize, j as usize);
        let row = self.rows[bi].as_ref().unwrap();
        #[cfg(feature = "prof")]
        prof::sizes(row.0.len(), self.cols[ji].len(), self.key.len());
        let a = row.get(j).unwrap();
        let inv = if mutant(3) { a.clone() } else { Num::one().div(a)? };
        let mut newrow: Vec<(u32, Num)> = Vec::with_capacity(row.0.len());
        newrow.push((b, inv.clone()));
        for (k, c) in &row.0 {
            if *k != j {
                newrow.push((*k, c.neg().mul(&inv)?));
            }
        }
        if mutant(4) {
            newrow[1..].reverse(); // new row in reverse order
        }
        let mut cj = self.cols[ji].clone();
        if mutant(8) {
            cj.reverse(); // column order: expected to change nothing
        }
        let mut updates: Vec<(u32, Vec<(u32, Num)>)> = Vec::with_capacity(cj.len());
        for &r in &cj {
            if r == b {
                continue;
            }
            let rr = self.rows[r as usize].as_ref().unwrap();
            let f = rr.get(j).unwrap();
            let mut new = Vec::with_capacity(newrow.len());
            for (k, c) in &newrow {
                let fc = f.mul(c)?;
                new.push((*k, match rr.get(*k) {
                    Some(old) => old.add(&fc)?,
                    None => Num::zero().add(&fc)?,
                }));
            }
            updates.push((r, new));
        }
        // commit
        let row = self.rows[bi].take().unwrap();
        self.row_order.retain(|x| *x != b);
        for (k, _) in &row.0 {
            if *k != j {
                self.col_discard(*k, b);
            }
        }
        for (r, new) in updates {
            let ri = r as usize;
            let mut rr = self.rows[ri].take().unwrap();
            let p = rr.pos(j).unwrap();
            rr.0.remove(p);
            for (k, nv) in new {
                let at = rr.pos(k);
                if !nv.formally_zero() {
                    match at {
                        Some(p) => rr.0[p].1 = nv,
                        None => {
                            self.cols[k as usize].push(r);
                            rr.0.push((k, nv));
                        }
                    }
                } else if let Some(p) = at {
                    rr.0.remove(p);
                    self.col_discard(k, r);
                }
            }
            self.rows[ri] = Some(rr);
        }
        self.cols[ji] = vec![];
        for (k, _) in &newrow {
            self.cols[*k as usize].push(j);
        }
        self.rows[ji] = Some(Row(newrow));
        self.row_order.push(j);
        Ok(())
    }

    fn concrete(&self) -> R<Vec<Num>> {
        let mut delta = Num::one();
        let n = self.vq.len();
        for v in 0..n {
            let (q, d) = (&self.vq[v], &self.vd[v]);
            if let Some(l) = &self.lo[v] {
                if gt(&l.1, d)? && gt(q, &l.0)? {
                    let x = q.sub(&l.0)?.div(&l.1.sub(d)?)?;
                    if x.lt(&delta)? {
                        delta = x;
                    }
                }
            }
            if let Some(u) = &self.up[v] {
                if u.1.lt(d)? && q.lt(&u.0)? {
                    let x = u.0.sub(q)?.div(&d.sub(&u.1)?)?;
                    if x.lt(&delta)? {
                        delta = x;
                    }
                }
            }
        }
        let mut out = Vec::with_capacity(n);
        for v in 0..n {
            out.push(self.vq[v].add(&delta.mul(&self.vd[v])?)?);
        }
        Ok(out)
    }

    fn model(&self, point: Vec<Num>) -> Vec<(u32, Num)> {
        point
            .into_iter()
            .enumerate()
            .filter(|(v, _)| self.key[*v] >= 0)
            .map(|(v, q)| (self.key[v] as u32, q))
            .collect()
    }

    fn off_all(&self, p: &[Num]) -> R<bool> {
        for (v, c, _) in &self.diseqs {
            if p[*v as usize].py_eq(c)? {
                return Ok(false);
            }
        }
        Ok(true)
    }

    /// `budget` is `BRANCH_BUDGET`, read by the caller per check since Python's is a patchable module global. None: gave up.
    pub fn check(&mut self, branch_budget: i64) -> R<Option<CheckResult>> {
        if self.gave_up {
            return Ok(None);
        }
        let r = self.check_inner(branch_budget).map(Some);
        self.hook(r, None)
    }

    fn check_inner(&mut self, branch_budget: i64) -> R<CheckResult> {
        self.stats.checks += 1;
        let mut conflict = self.simplex()?;
        if conflict.is_none() && !self.int_lits.is_empty() {
            let mut budget = branch_budget;
            conflict = self.branch(&mut budget)?;
        }
        if let Some(c) = conflict {
            self.stats.conflicts += 1;
            return Ok(CheckResult::Conflict(c));
        }
        let p0 = self.concrete()?;
        if self.off_all(&p0)? {
            return Ok(CheckResult::Sat(self.model(p0)));
        }
        let mut points = vec![p0];
        for idx in 0..self.diseqs.len() {
            let (v, c, lit) = self.diseqs[idx].clone();
            let mut off = false;
            for p in &points {
                if !p[v as usize].py_eq(&c)? {
                    off = true;
                    break;
                }
            }
            if off {
                continue;
            }
            let mut expl: Vec<i32> = vec![];
            let mut found = None;
            for kind in [Lt, Gt] {
                self.push_level();
                let mut r = self.assert_kind(v, kind, &c, 0)?;
                if r.is_none() {
                    r = self.simplex()?;
                }
                if r.is_none() {
                    found = Some(self.concrete()?);
                }
                self.pop_level();
                if found.is_some() {
                    break;
                }
                expl.extend(r.unwrap());
            }
            match found {
                None => {
                    self.stats.conflicts += 1;
                    let mut x = vec![-lit];
                    x.extend(expl);
                    return Ok(CheckResult::Conflict(dedupe(x)));
                }
                Some(p) => points.push(p),
            }
        }
        let n = points.len();
        let mut t: i64 = 1;
        loop {
            let tr = Num::Q(Rat::S(t, 1));
            let mut w = Vec::with_capacity(n);
            let mut x = Num::one();
            for _ in 0..n {
                w.push(x.clone());
                x = x.mul(&tr)?;
            }
            let mut total = Num::zero();
            for wi in &w {
                total = total.add(wi)?;
            }
            let nv = points[0].len();
            let mut p = Vec::with_capacity(nv);
            for v in 0..nv {
                let mut s = Num::zero();
                for (wi, pt) in w.iter().zip(points.iter()) {
                    s = s.add(&wi.mul(&pt[v])?)?;
                }
                p.push(s.div(&total)?);
            }
            if self.off_all(&p)? {
                return Ok(CheckResult::Sat(self.model(p)));
            }
            t += 1;
        }
    }

    pub fn propagate(&mut self) -> R<Vec<(i32, Vec<i32>)>> {
        if self.gave_up {
            return Ok(vec![]);
        }
        let r = self.propagate_inner();
        self.hook(r, vec![])
    }

    fn propagate_inner(&mut self) -> R<Vec<(i32, Vec<i32>)>> {
        let mut out: Vec<(i32, Vec<i32>)> = vec![];
        if !self.pending_ground.is_empty() {
            for a in std::mem::take(&mut self.pending_ground) {
                if !self.assigned.contains_key(&a) {
                    let lit = if self.ground[&a] { a as i32 } else { -(a as i32) };
                    out.push((lit, vec![lit]));
                }
            }
        }
        if self.dirty.is_empty() {
            return Ok(out);
        }
        #[cfg(feature = "mutants")]
        let order: Vec<u32> = if mutant(6) {
            self.dirty.set.iter().rev().copied().collect() // descending, instead of ascending
        } else if mutant(7) {
            self.dirty.first_added.clone() // the order of first addition, instead of ascending
        } else {
            self.dirty.set.iter().copied().collect()
        };
        #[cfg(not(feature = "mutants"))]
        let order: Vec<u32> = self.dirty.set.iter().copied().collect();
        for v in order {
            let vi = v as usize;
            if self.lo[vi].is_none() && self.up[vi].is_none() {
                continue;
            }
            for &a in &self.atoms_on[vi] {
                if self.assigned.contains_key(&a) {
                    continue;
                }
                let (_, kind, c) = &self.atoms[&a];
                // Optional: an implication it can't decide is skipped, never guessed.
                let val = match self.implied(vi, *kind, c) {
                    Ok(x) => x,
                    Err(e) if e.is_undecided() => continue,
                    Err(e) => return Err(e),
                };
                if let Some((val, why, n)) = val {
                    let lit = if val { a as i32 } else { -(a as i32) };
                    let mut x = vec![lit];
                    x.extend(why[..n].iter().map(|r| -r));
                    out.push((lit, dedupe(x)));
                }
            }
            if let Some(list) = self.ints_on.get(&v).cloned() {
                for a in list {
                    if self.assigned.contains_key(&a) {
                        continue;
                    }
                    let (w, m, k) = self.ints[&a].clone();
                    let val = match self.int_verdict(w, &m, &k) {
                        Ok(x) => x,
                        Err(e) if e.is_undecided() => continue,
                        Err(e) => return Err(e),
                    };
                    if let Some((val, why)) = val {
                        let lit = if val { a as i32 } else { -(a as i32) };
                        let mut x = vec![lit];
                        x.extend(why.iter().map(|r| -r));
                        out.push((lit, dedupe(x)));
                    }
                }
            }
        }
        self.dirty = Dirty::default();
        self.stats.propagations += out.len() as u64;
        Ok(out)
    }

    /// `_implied`: every comparison Python makes, in its order, since each can raise.
    fn implied(&self, vi: usize, kind: Kind, c: &Num) -> R<Option<(bool, [i32; 2], usize)>> {
        let (l, u) = (self.lo[vi].as_ref(), self.up[vi].as_ref());
        let z = Num::zero();
        let (lr, ur) = (self.lo_r[vi], self.up_r[vi]);
        let l_gt = || -> R<bool> { l.map_or(Ok(false), |b| t_gt(&b.0, &b.1, c, &z)) };
        let l_ge = || -> R<bool> { l.map_or(Ok(false), |b| t_ge(&b.0, &b.1, c, &z)) };
        let u_lt = || -> R<bool> { u.map_or(Ok(false), |b| t_lt(&b.0, &b.1, c, &z)) };
        let u_le = || -> R<bool> { u.map_or(Ok(false), |b| t_le(&b.0, &b.1, c, &z)) };
        match kind {
            Ne | Eq => {
                let r = if l_gt()? {
                    (false, [lr, 0], 1)
                } else if u_lt()? {
                    (false, [ur, 0], 1)
                } else if opt_eq0(&self.lo[vi], c)? && opt_eq0(&self.up[vi], c)? {
                    (true, [lr, ur], 2)
                } else {
                    return Ok(None);
                };
                Ok(Some(if kind == Ne { (!r.0, r.1, r.2) } else { r }))
            }
            Le | Lt | Ge | Gt => {
                let (t, f) = match kind {
                    Le => (u_le()?, l_gt()?),
                    Lt => (u_lt()?, l_ge()?),
                    Ge => (l_ge()?, u_lt()?),
                    _ => (l_gt()?, u_le()?),
                };
                let is_lt = matches!(kind, Le | Lt);
                Ok(if t {
                    Some((true, [if is_lt { ur } else { lr }, 0], 1))
                } else if f {
                    Some((false, [if is_lt { lr } else { ur }, 0], 1))
                } else {
                    None
                })
            }
        }
    }
}
