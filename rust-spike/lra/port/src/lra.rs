//! A port of satassume/theories/lra/lra.py at 9bafaa5, rational sessions only: no constfield, so no giving up and no
//! certificate. Written from the Python, same pivoting, same branch order, same budget.
//!
//! What must keep Python's order, and how:
//! - Row dicts: insertion order decides conflict literal order and later rows, so `Row` is an ordered Vec.
//! - `_dirty`: a set of ints whose iteration order decides propagate's order, so `PySet` reproduces CPython's table.
//! - `_cols`: sets whose order changes nothing (each row's update is independent), so they are plain Vecs.
//! - `for b in rows`: only the minimum violating basic variable matters, so a scan in variable order is the same.
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

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
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

pub type Bound = (Rat, Rat);

#[inline]
fn tuple_lt(q: &Rat, d: &Rat, b: &Bound) -> bool {
    match q.cmp(&b.0) {
        std::cmp::Ordering::Less => true,
        std::cmp::Ordering::Greater => false,
        std::cmp::Ordering::Equal => *d < b.1,
    }
}

#[inline]
fn tuple_gt(q: &Rat, d: &Rat, b: &Bound) -> bool {
    match q.cmp(&b.0) {
        std::cmp::Ordering::Greater => true,
        std::cmp::Ordering::Less => false,
        std::cmp::Ordering::Equal => *d > b.1,
    }
}

/// A dict in insertion order: deleting closes the gap, a new key goes last.
#[derive(Default, Clone)]
pub struct Row(pub Vec<(u32, Rat)>);

impl Row {
    #[inline]
    fn pos(&self, k: u32) -> Option<usize> {
        self.0.iter().position(|e| e.0 == k)
    }
    #[inline]
    fn get(&self, k: u32) -> Option<&Rat> {
        self.0.iter().find(|e| e.0 == k).map(|e| &e.1)
    }
}

/// CPython 3.12's set of small non-negative ints, for its iteration order. Only add and iterate: `_dirty` never
/// discards. hash(x) == x. See set_add_entry and set_table_resize in Objects/setobject.c.
pub struct PySet {
    table: Vec<i64>, // -1 empty
    mask: usize,
    fill: usize,
    #[cfg(feature = "mutants")]
    first_added: Vec<u32>,
}

const LINEAR_PROBES: usize = 9;

impl PySet {
    pub fn new() -> PySet {
        PySet {
            table: vec![-1; 8],
            mask: 7,
            fill: 0,
            #[cfg(feature = "mutants")]
            first_added: Vec::new(),
        }
    }
    #[inline]
    pub fn is_empty(&self) -> bool {
        self.fill == 0
    }
    pub fn add(&mut self, key: u32) {
        #[cfg(feature = "mutants")]
        if !self.first_added.contains(&key) {
            self.first_added.push(key);
        }
        let hash = key as usize;
        let key = key as i64;
        let mask = self.mask;
        let mut i = hash & mask;
        let mut perturb = hash;
        loop {
            let probes = if i + LINEAR_PROBES <= mask { LINEAR_PROBES } else { 0 };
            for j in 0..=probes {
                let e = self.table[i + j];
                if e == -1 {
                    self.table[i + j] = key;
                    self.fill += 1;
                    if self.fill * 5 >= mask * 3 {
                        self.resize();
                    }
                    return;
                }
                if e == key {
                    return;
                }
            }
            perturb >>= 5;
            i = (i.wrapping_mul(5).wrapping_add(1).wrapping_add(perturb)) & mask;
        }
    }
    fn resize(&mut self) {
        let minused = if self.fill > 50000 { self.fill * 2 } else { self.fill * 4 };
        let mut newsize = 8;
        while newsize <= minused {
            newsize <<= 1;
        }
        let old = std::mem::replace(&mut self.table, vec![-1; newsize]);
        self.mask = newsize - 1;
        let mask = self.mask;
        for &key in old.iter().filter(|&&k| k != -1) {
            let hash = key as usize;
            let mut i = hash & mask;
            let mut perturb = hash;
            'find: loop {
                if self.table[i] == -1 {
                    self.table[i] = key;
                    break 'find;
                }
                if i + LINEAR_PROBES <= mask {
                    for j in 1..=LINEAR_PROBES {
                        if self.table[i + j] == -1 {
                            self.table[i + j] = key;
                            break 'find;
                        }
                    }
                }
                perturb >>= 5;
                i = (i.wrapping_mul(5).wrapping_add(1).wrapping_add(perturb)) & mask;
            }
        }
    }
    pub fn iter(&self) -> impl Iterator<Item = u32> + '_ {
        self.table.iter().filter(|&&k| k != -1).map(|&k| k as u32)
    }
}

pub enum Payload {
    Plain { neg: u32, strict: bool, eq: bool, constant: Rat, terms: Vec<(u32, Rat)> },
    Integral { offset: Rat, terms: Vec<(u32, Rat)> },
}

pub enum CheckResult {
    Conflict(Vec<i32>),
    Sat(Vec<(u32, Rat)>), // the model: term id, value, in variable order
}

enum Trail {
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

/// ``_floor(q, d)`` and ``_ceil(q, d)``.
fn floor_d(q: &Rat, d: &Rat) -> Rat {
    if q.is_int() {
        if d.is_neg() {
            q.sub(&Rat::ONE)
        } else {
            q.clone()
        }
    } else {
        q.floor()
    }
}

fn ceil_d(q: &Rat, d: &Rat) -> Rat {
    if q.is_int() {
        if d.is_pos() {
            q.add(&Rat::ONE)
        } else {
            q.clone()
        }
    } else {
        q.ceil()
    }
}

pub struct Theory {
    pub exhausted: bool,
    pub stats: Stats,
    key: Vec<i64>, // term id, -1 for a slack
    var_of: Map<u32, u32>,
    slack_of: Map<Vec<(u32, Rat)>, u32>,
    forms: Map<Vec<(u32, Rat)>, (u32, Rat)>,
    lo: Vec<Option<Bound>>,
    up: Vec<Option<Bound>>,
    lo_r: Vec<i32>,
    up_r: Vec<i32>,
    vq: Vec<Rat>,
    vd: Vec<Rat>,
    rows: Vec<Option<Row>>,
    nrows: usize,
    cols: Vec<Vec<u32>>,
    atoms: Map<u32, (u32, Kind, Rat)>,
    ground: Map<u32, bool>,
    atoms_on: Vec<Vec<u32>>,
    assigned: Map<u32, bool>,
    diseqs: Vec<(u32, Rat, i32)>,
    ints: Map<u32, (u32, Rat, Rat)>,
    ints_on: Map<u32, Vec<u32>>,
    int_lits: Vec<(u32, Rat, Rat, i32)>,
    trail: Vec<Trail>,
    lims: Vec<usize>,
    dirty: PySet,
    pending_ground: Vec<u32>,
}

impl Theory {
    pub fn new() -> Theory {
        Theory {
            exhausted: false,
            stats: Stats::default(),
            key: vec![],
            var_of: Map::default(),
            slack_of: Map::default(),
            forms: Map::default(),
            lo: vec![],
            up: vec![],
            lo_r: vec![],
            up_r: vec![],
            vq: vec![],
            vd: vec![],
            rows: vec![],
            nrows: 0,
            cols: vec![],
            atoms: Map::default(),
            ground: Map::default(),
            atoms_on: vec![],
            assigned: Map::default(),
            diseqs: vec![],
            ints: Map::default(),
            ints_on: Map::default(),
            int_lits: vec![],
            trail: vec![],
            lims: vec![],
            dirty: PySet::new(),
            pending_ground: vec![],
        }
    }

    pub fn nvars(&self) -> usize {
        self.key.len()
    }
    pub fn nrows(&self) -> usize {
        self.nrows
    }

    fn new_var(&mut self, key: i64) -> u32 {
        let v = self.key.len() as u32;
        self.key.push(key);
        self.lo.push(None);
        self.up.push(None);
        self.lo_r.push(0);
        self.up_r.push(0);
        self.vq.push(Rat::ZERO);
        self.vd.push(Rat::ZERO);
        self.rows.push(None);
        self.cols.push(vec![]);
        self.atoms_on.push(vec![]);
        if key >= 0 {
            self.var_of.insert(key as u32, v);
        }
        v
    }

    fn term_var(&mut self, key: u32) -> u32 {
        match self.var_of.get(&key) {
            Some(v) => *v,
            None => self.new_var(key as i64),
        }
    }

    fn slack(&mut self, form: Vec<(u32, Rat)>) -> u32 {
        if let Some(s) = self.slack_of.get(&form) {
            return *s;
        }
        let mut row: Vec<(u32, Rat)> = vec![];
        fn plus(row: &mut Vec<(u32, Rat)>, k: u32, x: Rat) {
            match row.iter().position(|e| e.0 == k) {
                Some(p) => row[p].1 = row[p].1.add(&x),
                None => row.push((k, x)),
            }
        }
        for (v, c) in &form {
            match &self.rows[*v as usize] {
                None => plus(&mut row, *v, c.clone()),
                Some(r) => {
                    for (k, a) in &r.0 {
                        plus(&mut row, *k, c.mul(a));
                    }
                }
            }
        }
        row.retain(|e| !e.1.is_zero());
        let (mut vq, mut vd) = (Rat::ZERO, Rat::ZERO);
        for (k, a) in &row {
            vq = vq.add(&a.mul(&self.vq[*k as usize]));
            vd = vd.add(&a.mul(&self.vd[*k as usize]));
        }
        let s = self.new_var(-1);
        self.slack_of.insert(form, s);
        for (k, _) in &row {
            self.cols[*k as usize].push(s);
        }
        self.vq[s as usize] = vq;
        self.vd[s as usize] = vd;
        self.rows[s as usize] = Some(Row(row));
        self.nrows += 1;
        s
    }

    fn lin(&mut self, terms: &[(u32, Rat)]) -> Vec<(u32, Rat)> {
        let mut lin: Vec<(u32, Rat)> = Vec::with_capacity(terms.len());
        for (t, c) in terms {
            match lin.iter().position(|e| e.0 == *t) {
                Some(p) => lin[p].1 = lin[p].1.add(c),
                None => lin.push((*t, c.clone())),
            }
        }
        for (t, _) in &lin {
            self.term_var(*t);
        }
        lin.retain(|e| !e.1.is_zero());
        lin
    }

    fn var_of_form(&mut self, lin: &[(u32, Rat)]) -> (u32, Rat) {
        let mut key: Vec<(u32, Rat)> = lin.to_vec();
        key.sort_by_key(|e| e.0); // a frozenset of (term, coefficient): the same pairs, the same key
        if let Some(r) = self.forms.get(&key) {
            return r.clone();
        }
        let mut vs: Vec<(u32, Rat)> = lin.iter().map(|(t, c)| (self.term_var(*t), c.clone())).collect();
        vs.sort_by_key(|e| e.0);
        let r = if vs.len() == 1 {
            vs[0].clone()
        } else {
            let c = vs[0].1.clone();
            let form: Vec<(u32, Rat)> = vs.iter().map(|(w, a)| (*w, a.div(&c))).collect();
            (self.slack(form), c)
        };
        self.forms.insert(key, r.clone());
        r
    }

    pub fn register_atom(&mut self, literal: u32, payload: &Payload) {
        match payload {
            Payload::Integral { offset, terms } => self.register_integral(literal, offset, terms),
            Payload::Plain { neg, strict, eq, constant, terms } => {
                let lin = self.lin(terms);
                let k = constant;
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
                    let truth = match kind {
                        Eq => k.is_zero(),
                        Ne => !k.is_zero(),
                        Lt => k.is_pos(),
                        Le => !k.is_neg(),
                        Gt => k.is_neg(),
                        Ge => !k.is_pos(),
                    };
                    self.ground.insert(literal, truth);
                    self.pending_ground.push(literal);
                    return;
                }
                let (v, c) = self.var_of_form(&lin);
                let bound = k.div(&c);
                if c.is_neg() {
                    kind = flip_kind(kind);
                }
                self.atoms.insert(literal, (v, kind, bound));
                self.atoms_on[v as usize].push(literal);
                self.dirty.add(v);
            }
        }
    }

    fn register_integral(&mut self, literal: u32, offset: &Rat, terms: &[(u32, Rat)]) {
        let lin = self.lin(terms);
        if lin.is_empty() {
            self.ground.insert(literal, offset.is_int());
            self.pending_ground.push(literal);
            return;
        }
        let (v, m) = self.var_of_form(&lin);
        let k = offset.sub(&offset.floor());
        self.ints.insert(literal, (v, m, k));
        self.ints_on.entry(v).or_default().push(literal);
        self.dirty.add(v);
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
    pub fn assert_lit(&mut self, literal: i32) -> Option<Vec<i32>> {
        let a = literal.unsigned_abs();
        let Some((v, kind, c)) = self.atoms.get(&a).cloned() else {
            if let Some(it) = self.ints.get(&a).cloned() {
                return self.assert_integral(literal, it);
            }
            let truth = *self.ground.get(&a)?;
            self.assigned.insert(a, literal > 0);
            self.trail.push(Trail::Asg(a));
            if truth != (literal > 0) {
                self.stats.conflicts += 1;
                return Some(vec![-literal]);
            }
            return None;
        };
        self.assigned.insert(a, literal > 0);
        self.trail.push(Trail::Asg(a));
        let kind = if literal < 0 { neg_kind(kind) } else { kind };
        let mut conflict = self.assert_kind(v, kind, &c, literal);
        if conflict.is_none() && !self.int_lits.is_empty() && self.ints_on.contains_key(&v) {
            conflict = self.int_bounds(v);
        }
        if conflict.is_none() && kind != Ne {
            conflict = self.simplex();
        }
        if conflict.is_some() {
            self.stats.conflicts += 1;
        }
        conflict
    }

    fn assert_kind(&mut self, v: u32, kind: Kind, c: &Rat, lit: i32) -> Option<Vec<i32>> {
        match kind {
            Le => self.set_upper(v, (c.clone(), Rat::ZERO), lit),
            Lt => self.set_upper(v, (c.clone(), Rat::MINUS_ONE), lit),
            Ge => self.set_lower(v, (c.clone(), Rat::ZERO), lit),
            Gt => self.set_lower(v, (c.clone(), Rat::ONE), lit),
            Eq => match self.set_upper(v, (c.clone(), Rat::ZERO), lit) {
                Some(x) if !x.is_empty() => Some(x), // Python's `or`: an empty list is false
                _ => self.set_lower(v, (c.clone(), Rat::ZERO), lit),
            },
            Ne => {
                self.diseqs.push((v, c.clone(), lit));
                self.trail.push(Trail::Dis);
                let vi = v as usize;
                if let (Some(lo), Some(up)) = (&self.lo[vi], &self.up[vi]) {
                    if lo == up && lo.0 == *c && lo.1.is_zero() {
                        return Some(dedupe(vec![-lit, -self.lo_r[vi], -self.up_r[vi]]));
                    }
                }
                None
            }
        }
    }

    fn set_upper(&mut self, v: u32, b: Bound, lit: i32) -> Option<Vec<i32>> {
        let vi = v as usize;
        if let Some(up) = &self.up[vi] {
            if *up <= b {
                return None;
            }
        }
        if let Some(lo) = &self.lo[vi] {
            if b < *lo {
                return Some(dedupe(vec![-lit, -self.lo_r[vi]]));
            }
        }
        let old = self.up[vi].replace(b.clone());
        self.trail.push(Trail::Up(v, old, self.up_r[vi]));
        self.up_r[vi] = lit;
        self.dirty.add(v);
        if self.rows[vi].is_none() && tuple_gt(&self.vq[vi], &self.vd[vi], &b) {
            self.update(v, &b);
        }
        None
    }

    fn set_lower(&mut self, v: u32, b: Bound, lit: i32) -> Option<Vec<i32>> {
        let vi = v as usize;
        if let Some(lo) = &self.lo[vi] {
            if *lo >= b {
                return None;
            }
        }
        if let Some(up) = &self.up[vi] {
            if b > *up {
                return Some(dedupe(vec![-lit, -self.up_r[vi]]));
            }
        }
        let old = self.lo[vi].replace(b.clone());
        self.trail.push(Trail::Lo(v, old, self.lo_r[vi]));
        self.lo_r[vi] = lit;
        self.dirty.add(v);
        if self.rows[vi].is_none() && tuple_lt(&self.vq[vi], &self.vd[vi], &b) {
            self.update(v, &b);
        }
        None
    }

    fn update(&mut self, v: u32, b: &Bound) {
        let vi = v as usize;
        let dq = b.0.sub(&self.vq[vi]);
        let dd = b.1.sub(&self.vd[vi]);
        for idx in 0..self.cols[vi].len() {
            let r = self.cols[vi][idx] as usize;
            let a = self.rows[r].as_ref().unwrap().get(v).unwrap();
            let nq = self.vq[r].add(&a.mul(&dq));
            let nd = self.vd[r].add(&a.mul(&dd));
            self.vq[r] = nq;
            self.vd[r] = nd;
        }
        self.vq[vi] = b.0.clone();
        self.vd[vi] = b.1.clone();
    }

    fn assert_integral(&mut self, literal: i32, it: (u32, Rat, Rat)) -> Option<Vec<i32>> {
        let a = literal.unsigned_abs();
        self.assigned.insert(a, literal > 0);
        self.trail.push(Trail::Asg(a));
        let (v, m, k) = it;
        let r = self.int_verdict(v, &m, &k);
        self.int_lits.push((v, m, k, literal));
        self.trail.push(Trail::Int);
        if let Some((truth, why)) = r {
            if truth != (literal > 0) {
                self.stats.conflicts += 1;
                let mut x = vec![-literal];
                x.extend(why.iter().map(|l| -l));
                return Some(dedupe(x));
            }
        }
        None
    }

    fn int_verdict(&self, v: u32, m: &Rat, k: &Rat) -> Option<(bool, [i32; 2])> {
        let vi = v as usize;
        let (lo, up) = (self.lo[vi].as_ref()?, self.up[vi].as_ref()?);
        let why = [self.lo_r[vi], self.up_r[vi]];
        let pinned = lo == up;
        if *m == Rat::ONE && k.is_zero() {
            if pinned {
                return Some((lo.0.is_int(), why));
            }
            return if ceil_d(&lo.0, &lo.1) > floor_d(&up.0, &up.1) { Some((false, why)) } else { None };
        }
        let mut a = (m.mul(&lo.0).add(k), m.mul(&lo.1));
        let mut b = (m.mul(&up.0).add(k), m.mul(&up.1));
        if m.is_neg() {
            std::mem::swap(&mut a, &mut b);
        }
        if pinned {
            return Some((a.0.is_int(), why));
        }
        if ceil_d(&a.0, &a.1) > floor_d(&b.0, &b.1) {
            return Some((false, why));
        }
        None
    }

    fn int_bounds(&self, v: u32) -> Option<Vec<i32>> {
        for (w, m, k, lit) in &self.int_lits {
            if *w == v {
                if let Some((truth, why)) = self.int_verdict(v, m, k) {
                    if truth != (*lit > 0) {
                        let mut x = vec![-*lit];
                        x.extend(why.iter().map(|l| -l));
                        return Some(dedupe(x));
                    }
                }
            }
        }
        None
    }

    fn branch(&mut self, budget: &mut i64) -> Option<Vec<i32>> {
        // cases: (kind, n) twice; (v, m, k, lit) of the split
        let mut split: Option<(u32, Rat, Rat, i32, [(Kind, Rat); 2])> = None;
        for (v, m, k, lit) in &self.int_lits {
            let vi = *v as usize;
            let (nq, nd) = if *m == Rat::ONE && k.is_zero() {
                (self.vq[vi].clone(), self.vd[vi].clone())
            } else {
                (m.mul(&self.vq[vi]).add(k), m.mul(&self.vd[vi]))
            };
            let integral = nd.is_zero() && nq.is_int();
            if *lit > 0 && !integral {
                let f = floor_d(&nq, &nd);
                let f1 = f.add(&Rat::ONE);
                split = Some((*v, m.clone(), k.clone(), *lit, [(Le, f), (Ge, f1)]));
                break;
            }
            if *lit < 0 && integral {
                let at_lo = matches!(&self.lo[vi], Some(b) if b.0 == self.vq[vi] && b.1.is_zero());
                let down = !at_lo;
                let cases = if down == m.is_pos() {
                    [(Lt, nq.clone()), (Gt, nq)]
                } else {
                    [(Gt, nq.clone()), (Lt, nq)]
                };
                split = Some((*v, m.clone(), k.clone(), *lit, cases));
                break;
            }
        }
        if split.is_none() {
            for (v, c, lit) in &self.diseqs {
                let vi = *v as usize;
                if self.vq[vi] == *c && self.vd[vi].is_zero() {
                    let at_lo = matches!(&self.lo[vi], Some(b) if b.0 == *c && b.1.is_zero());
                    let cases = if !at_lo { [(Lt, c.clone()), (Gt, c.clone())] } else { [(Gt, c.clone()), (Lt, c.clone())] };
                    split = Some((*v, Rat::ONE, Rat::ZERO, *lit, cases));
                    break;
                }
            }
        }
        let (v, m, k, lit, cases) = split?;
        let limit = if mutant(2) { 1 } else { 0 };
        if *budget <= limit {
            self.exhausted = true;
            self.stats.exhausted += 1;
            return None;
        }
        *budget -= 1;
        self.stats.branches += 1;
        let mut expl = vec![-lit];
        for (kind, n) in cases.iter() {
            let kind = if m.is_neg() { flip_kind(*kind) } else { *kind };
            self.push_level();
            let bound = n.sub(&k).div(&m);
            let mut r = self.assert_kind(v, kind, &bound, 0);
            if r.is_none() {
                r = self.simplex();
                if r.is_none() {
                    r = self.branch(budget);
                }
            }
            self.pop_level();
            match r {
                None => return None,
                Some(x) => expl.extend(x),
            }
        }
        Some(dedupe(expl))
    }

    fn simplex(&mut self) -> Option<Vec<i32>> {
        #[cfg(feature = "prof")]
        prof::simplex();
        loop {
            let mut leave: Option<(u32, bool)> = None;
            let n = self.rows.len();
            if mutant(1) {
                // Pivot order: the largest violating basic variable, not Bland's smallest.
                for b in (0..n).rev() {
                    if self.rows[b].is_none() {
                        continue;
                    }
                    if let Some(l) = &self.lo[b] {
                        if tuple_lt(&self.vq[b], &self.vd[b], l) {
                            leave = Some((b as u32, true));
                            break;
                        }
                    }
                    if let Some(u) = &self.up[b] {
                        if tuple_gt(&self.vq[b], &self.vd[b], u) {
                            leave = Some((b as u32, false));
                            break;
                        }
                    }
                }
            } else {
                for b in 0..n {
                    if self.rows[b].is_none() {
                        continue;
                    }
                    if let Some(l) = &self.lo[b] {
                        if tuple_lt(&self.vq[b], &self.vd[b], l) {
                            leave = Some((b as u32, true));
                            break;
                        }
                    }
                    if let Some(u) = &self.up[b] {
                        if tuple_gt(&self.vq[b], &self.vd[b], u) {
                            leave = Some((b as u32, false));
                            break;
                        }
                    }
                }
            }
            let (b, below) = leave?;
            let row = self.rows[b as usize].as_ref().unwrap();
            let mut enter: i64 = -1;
            for (j, a) in &row.0 {
                let ji = *j as usize;
                let inc = a.is_pos() == below;
                let ok = if inc {
                    match &self.up[ji] {
                        None => true,
                        Some(u) => tuple_lt(&self.vq[ji], &self.vd[ji], u),
                    }
                } else {
                    match &self.lo[ji] {
                        None => true,
                        Some(l) => tuple_gt(&self.vq[ji], &self.vd[ji], l),
                    }
                };
                if ok && (enter == -1 || (if mutant(9) { (*j as i64) > enter } else { (*j as i64) < enter })) {
                    enter = *j as i64;
                }
            }
            if enter == -1 {
                let mut expl = Vec::with_capacity(row.0.len() + 1);
                if below {
                    expl.push(-self.lo_r[b as usize]);
                    for (j, a) in &row.0 {
                        let ji = *j as usize;
                        expl.push(-(if a.is_pos() { self.up_r[ji] } else { self.lo_r[ji] }));
                    }
                } else {
                    expl.push(-self.up_r[b as usize]);
                    for (j, a) in &row.0 {
                        let ji = *j as usize;
                        expl.push(-(if a.is_pos() { self.lo_r[ji] } else { self.up_r[ji] }));
                    }
                }
                return Some(dedupe(expl));
            }
            let target = if below {
                self.lo[b as usize].clone().unwrap()
            } else {
                self.up[b as usize].clone().unwrap()
            };
            self.pivot_and_update(b, enter as u32, &target);
        }
    }

    fn pivot_and_update(&mut self, b: u32, j: u32, target: &Bound) {
        let (bi, ji) = (b as usize, j as usize);
        let a = self.rows[bi].as_ref().unwrap().get(j).unwrap().clone();
        let tq = target.0.sub(&self.vq[bi]).div(&a);
        let td = target.1.sub(&self.vd[bi]).div(&a);
        self.vq[bi] = target.0.clone();
        self.vd[bi] = target.1.clone();
        self.vq[ji] = self.vq[ji].add(&tq);
        self.vd[ji] = self.vd[ji].add(&td);
        for idx in 0..self.cols[ji].len() {
            let k = self.cols[ji][idx];
            if k != b {
                let ki = k as usize;
                let ak = self.rows[ki].as_ref().unwrap().get(j).unwrap();
                let nq = self.vq[ki].add(&ak.mul(&tq));
                let nd = self.vd[ki].add(&ak.mul(&td));
                self.vq[ki] = nq;
                self.vd[ki] = nd;
            }
        }
        self.pivot(b, j);
    }

    #[inline]
    fn col_discard(&mut self, k: u32, r: u32) {
        let c = &mut self.cols[k as usize];
        if let Some(p) = c.iter().position(|x| *x == r) {
            c.swap_remove(p);
        }
    }

    fn pivot(&mut self, b: u32, j: u32) {
        self.stats.pivots += 1;
        let (bi, ji) = (b as usize, j as usize);
        let row = self.rows[bi].take().unwrap();
        #[cfg(feature = "prof")]
        prof::sizes(row.0.len(), self.cols[ji].len(), self.key.len());
        let a = row.get(j).unwrap();
        let inv = if mutant(3) { a.clone() } else { a.inv() };
        let mut newrow: Vec<(u32, Rat)> = Vec::with_capacity(row.0.len());
        newrow.push((b, inv.clone()));
        for (k, c) in &row.0 {
            if *k != j {
                self.col_discard(*k, b);
                newrow.push((*k, c.neg().mul(&inv)));
            }
        }
        if mutant(4) {
            newrow[1..].reverse(); // new row in reverse order
        }
        self.col_discard(j, b);
        let mut cj = std::mem::take(&mut self.cols[ji]);
        if mutant(8) {
            cj.reverse(); // column order: expected to change nothing
        }
        for r in cj {
            let ri = r as usize;
            let mut rr = self.rows[ri].take().unwrap();
            let p = rr.pos(j).unwrap();
            let f = rr.0.remove(p).1;
            for (k, c) in &newrow {
                let fc = f.mul(c);
                match rr.pos(*k) {
                    Some(p) => {
                        let nv = rr.0[p].1.add(&fc);
                        if nv.is_zero() {
                            rr.0.remove(p);
                            self.col_discard(*k, r);
                        } else {
                            rr.0[p].1 = nv;
                        }
                    }
                    None => {
                        if !fc.is_zero() {
                            self.cols[*k as usize].push(r);
                            rr.0.push((*k, fc));
                        }
                    }
                }
            }
            self.rows[ri] = Some(rr);
        }
        for (k, _) in &newrow {
            self.cols[*k as usize].push(j);
        }
        self.rows[ji] = Some(Row(newrow));
    }

    fn concrete(&self) -> Vec<Rat> {
        let mut delta = Rat::ONE;
        let n = self.vq.len();
        for v in 0..n {
            let (q, d) = (&self.vq[v], &self.vd[v]);
            if let Some(l) = &self.lo[v] {
                if l.1 > *d && *q > l.0 {
                    let x = q.sub(&l.0).div(&l.1.sub(d));
                    if x < delta {
                        delta = x;
                    }
                }
            }
            if let Some(u) = &self.up[v] {
                if u.1 < *d && *q < u.0 {
                    let x = u.0.sub(q).div(&d.sub(&u.1));
                    if x < delta {
                        delta = x;
                    }
                }
            }
        }
        (0..n).map(|v| self.vq[v].add(&delta.mul(&self.vd[v]))).collect()
    }

    fn model(&self, point: Vec<Rat>) -> Vec<(u32, Rat)> {
        point
            .into_iter()
            .enumerate()
            .filter(|(v, _)| self.key[*v] >= 0)
            .map(|(v, q)| (self.key[v] as u32, q))
            .collect()
    }

    pub fn check(&mut self) -> CheckResult {
        self.stats.checks += 1;
        let mut conflict = self.simplex();
        if conflict.is_none() && !self.int_lits.is_empty() {
            let mut budget = BRANCH_BUDGET;
            conflict = self.branch(&mut budget);
        }
        if let Some(c) = conflict {
            self.stats.conflicts += 1;
            return CheckResult::Conflict(c);
        }
        let p0 = self.concrete();
        if self.diseqs.iter().all(|(v, c, _)| p0[*v as usize] != *c) {
            return CheckResult::Sat(self.model(p0));
        }
        let mut points = vec![p0];
        for idx in 0..self.diseqs.len() {
            let (v, c, lit) = self.diseqs[idx].clone();
            if points.iter().any(|p| p[v as usize] != c) {
                continue;
            }
            let mut expl: Vec<i32> = vec![];
            let mut found = None;
            for kind in [Lt, Gt] {
                self.push_level();
                let mut r = self.assert_kind(v, kind, &c, 0);
                if r.is_none() {
                    r = self.simplex();
                }
                if r.is_none() {
                    found = Some(self.concrete());
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
                    return CheckResult::Conflict(dedupe(x));
                }
                Some(p) => points.push(p),
            }
        }
        let n = points.len();
        let mut t: i64 = 1;
        loop {
            let tr = Rat::S(t, 1);
            let mut w = Vec::with_capacity(n);
            let mut x = Rat::ONE;
            for _ in 0..n {
                w.push(x.clone());
                x = x.mul(&tr);
            }
            let mut total = Rat::ZERO;
            for wi in &w {
                total = total.add(wi);
            }
            let nv = points[0].len();
            let mut p = Vec::with_capacity(nv);
            for v in 0..nv {
                let mut s = Rat::ZERO;
                for (wi, pt) in w.iter().zip(points.iter()) {
                    s = s.add(&wi.mul(&pt[v]));
                }
                p.push(s.div(&total));
            }
            if self.diseqs.iter().all(|(v, c, _)| p[*v as usize] != *c) {
                return CheckResult::Sat(self.model(p));
            }
            t += 1;
        }
    }

    pub fn propagate(&mut self) -> Vec<(i32, Vec<i32>)> {
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
            return out;
        }
        let dirty = std::mem::replace(&mut self.dirty, PySet::new());
        #[cfg(feature = "mutants")]
        let order: Vec<u32> = {
            let mut xs: Vec<u32> = dirty.iter().collect();
            if mutant(6) {
                xs.sort(); // ascending variable, instead of CPython's table
            } else if mutant(7) {
                xs = dirty.first_added.clone(); // the order they were first added, instead of CPython's table
            }
            xs
        };
        #[cfg(not(feature = "mutants"))]
        let order = dirty.iter();
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
                if let Some((val, why, n)) = self.implied(v, *kind, c) {
                    let lit = if val { a as i32 } else { -(a as i32) };
                    let mut x = vec![lit];
                    x.extend(why[..n].iter().map(|r| -r));
                    out.push((lit, dedupe(x)));
                }
            }
            if let Some(list) = self.ints_on.get(&v) {
                for &a in list {
                    if self.assigned.contains_key(&a) {
                        continue;
                    }
                    let (w, m, k) = &self.ints[&a];
                    if let Some((val, why)) = self.int_verdict(*w, m, k) {
                        let lit = if val { a as i32 } else { -(a as i32) };
                        let mut x = vec![lit];
                        x.extend(why.iter().map(|r| -r));
                        out.push((lit, dedupe(x)));
                    }
                }
            }
        }
        self.stats.propagations += out.len() as u64;
        out
    }

    fn implied(&self, v: u32, kind: Kind, c: &Rat) -> Option<(bool, [i32; 2], usize)> {
        let vi = v as usize;
        let (l, u) = (self.lo[vi].as_ref(), self.up[vi].as_ref());
        // cmp of a bound with (c, 0)
        let lcmp = l.map(|b| b.0.cmp(c).then(b.1.cmp(&Rat::ZERO)));
        let ucmp = u.map(|b| b.0.cmp(c).then(b.1.cmp(&Rat::ZERO)));
        use std::cmp::Ordering::*;
        let (lr, ur) = (self.lo_r[vi], self.up_r[vi]);
        match kind {
            Ne | Eq => {
                let r = if lcmp == Some(Greater) {
                    (false, [lr, 0], 1)
                } else if ucmp == Some(Less) {
                    (false, [ur, 0], 1)
                } else if lcmp == Some(Equal) && ucmp == Some(Equal) {
                    (true, [lr, ur], 2)
                } else {
                    return None;
                };
                Some(if kind == Ne { (!r.0, r.1, r.2) } else { r })
            }
            Le | Lt | Ge | Gt => {
                let (t, f) = match kind {
                    Le => (matches!(ucmp, Some(Less | Equal)), lcmp == Some(Greater)),
                    Lt => (ucmp == Some(Less), matches!(lcmp, Some(Greater | Equal))),
                    Ge => (matches!(lcmp, Some(Greater | Equal)), ucmp == Some(Less)),
                    _ => (lcmp == Some(Greater), matches!(ucmp, Some(Less | Equal))),
                };
                let is_lt = matches!(kind, Le | Lt);
                if t {
                    Some((true, [if is_lt { ur } else { lr }, 0], 1))
                } else if f {
                    Some((false, [if is_lt { lr } else { ur }, 0], 1))
                } else {
                    None
                }
            }
        }
    }
}
