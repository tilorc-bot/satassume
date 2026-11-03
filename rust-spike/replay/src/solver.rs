//! A port of `satassume.sat.solver.Solver` for the spike: propagation, search, rule block, ring and held levels.
//! Same algorithm and same order of everything that can change the search; no provenance. Comments mark what
//! differs from the Python in representation, not in behaviour.
use crate::block::{Closure, EVEN};
use std::cell::RefCell;
use std::rc::Rc;

pub const F: u8 = 0;
pub const T: u8 = 1;
pub const U: u8 = 2;

const VAR_DECAY: f64 = 0.95;
const CLA_DECAY: f64 = 0.999;
const RESTART_FIRST: f64 = 100.0;
const RESTART_INC: f64 = 2.0;
const LEARNT_SIZE_INC: f64 = 1.1;
const LEARNT_SIZE_MIN: f64 = 1000.0;
const RING: usize = 2;

#[cfg(feature = "prof")]
pub static PROP_NS: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);

pub struct ValueError;
pub type R<X> = Result<X, ValueError>;

/// One theory's recorded answers; panics on a call it did not record, so any search divergence stops the replay.
pub struct Tape {
    pub w: &'static [u32],
    pub pos: usize,
    pub tid: u32,
    pub has_prop: bool,
    pub has_dec: bool,
}

impl Tape {
    #[inline]
    pub fn assert_lit(&mut self, x: i32) -> Option<&'static [u32]> {
        let (w, p) = (self.w, self.pos);
        if w.get(p) != Some(&1) || w[p + 1] as i32 != x {
            panic!("diverged: assert_lit({x}), theory {}, tape pos {p}", self.tid);
        }
        let n = w[p + 2] as i32;
        if n < 0 {
            self.pos = p + 3;
            None
        } else {
            let e = p + 3 + n as usize;
            self.pos = e;
            Some(&w[p + 3..e])
        }
    }

    /// Returns (index of the first pair, number of pairs) and steps past the whole record: as in Python, where
    /// the theory's list is complete before the solver reads it, stopping early leaves nothing on the tape.
    #[inline]
    pub fn propagate(&mut self) -> (usize, usize) {
        let (w, p) = (self.w, self.pos);
        if w.get(p) != Some(&2) {
            panic!("diverged: propagate, theory {}, tape pos {p}", self.tid);
        }
        let n = w[p + 1] as usize;
        let mut i = p + 2;
        for _ in 0..n {
            i += 2 + w[i + 1] as usize;
        }
        self.pos = i;
        (p + 2, n)
    }

    #[inline]
    pub fn check(&mut self) -> Option<&'static [u32]> {
        let (w, p) = (self.w, self.pos);
        if w.get(p) != Some(&3) {
            panic!("diverged: check, theory {}, tape pos {p}", self.tid);
        }
        let n = w[p + 2] as usize;
        self.pos = p + 3 + n;
        if w[p + 1] == 2 {
            Some(&w[p + 3..p + 3 + n])
        } else {
            None
        }
    }

    #[inline]
    pub fn decide(&mut self) -> Option<u32> {
        let (w, p) = (self.w, self.pos);
        if w.get(p) != Some(&4) {
            panic!("diverged: decide, theory {}, tape pos {p}", self.tid);
        }
        self.pos = p + 2;
        if w[p + 1] == 0 {
            None
        } else {
            Some(w[p + 1])
        }
    }
}

struct Clause {
    lits: Vec<u32>,
    act: f64,
    learnt: bool,
}

#[derive(Clone, Copy)]
enum Reason {
    None,
    Clause(u32),
    Block(u128, u32), // the block's mask when the literal was implied, and its base
}

type Model = Rc<RefCell<Vec<u8>>>;

struct Rec {
    mv: Model,
    ncl: usize,
    rlen: usize,
    nb: usize,
    nt: usize,
    na: u64,
}

pub enum Tr {
    Conflict,
    Live, // the solver's own trail
    Last, // self.last_trail
}

#[derive(Default)]
pub struct Counters {
    pub decisions: u64,
    pub conflicts: u64,
    pub props: u64,
    pub learned: u64,
    pub restarts: u64,
    pub reductions: u64,
    pub ring_hits: u64,
    pub tdecisions: u64,
    pub pushes: u64,
    pub pops: u64,
}

pub struct Solver {
    val: Vec<u8>,
    watches: Vec<Vec<u32>>,
    level: Vec<u32>,
    reason: Vec<Reason>,
    act: Vec<f64>,
    polarity: Vec<u8>,
    hpos: Vec<i32>,
    seen: Vec<u8>,
    heap: Vec<u32>,
    trail: Vec<u32>,
    trail_lim: Vec<u32>,
    qhead: usize,
    db: Vec<Clause>, // every clause; clauses and learnts hold indices. Temporary clauses stay until the solver goes.
    clauses: Vec<u32>,
    learnts: Vec<u32>,
    ok: bool,
    nvars: usize,
    var_inc: f64,
    cla_inc: f64,
    max_learnts: f64,
    assumptions: Vec<u32>,
    witness: Option<Model>,
    stamp: u64,
    acache: Option<(Vec<u32>, u64, usize, Option<Rc<Vec<u32>>>)>,
    last_trail: Rc<Vec<u32>>,
    held: Option<Vec<u32>>,
    conflict: Vec<u32>,
    pub n: Counters,
    scan: usize,
    pub theories: Vec<Tape>,
    tmap: Vec<Vec<u32>>, // per variable, where Python has a dict; nothing iterates it
    thead: usize,
    tprops: Vec<usize>,
    tdecides: Vec<usize>,
    tpending: bool,
    rb_base: Vec<u32>,
    rbc: Option<Rc<Closure>>,
    rb_mask: Vec<u128>,
    rb_ment: Vec<u128>,
    rb_saved: Vec<u64>,
    rb_cl: Vec<u128>,
    rb_undo: Vec<(u32, u128, u128)>,
    rb_ulim: Vec<u32>,
    uid: u64,
    ment: Vec<u8>,
    lazy: Vec<u8>,
    rb_n: usize,
    rb_blocks: usize,
    rb_nclauses: usize,
    rb_bases: Vec<u32>,
    ring: Vec<Rec>,
    n_registered: u64,
    buf: Vec<u32>,
    vals_buf: Vec<u8>,
}

fn common(held: &[u32], lits: &[u32]) -> usize {
    held.iter().zip(lits).take_while(|(a, b)| a == b).count()
}

fn luby(y: f64, mut x: u64) -> f64 {
    let mut size: u64 = 1;
    let mut seq: i32 = 0;
    while size < x + 1 {
        seq += 1;
        size = 2 * size + 1;
    }
    while size - 1 != x {
        size = (size - 1) >> 1;
        seq -= 1;
        x %= size;
    }
    y.powi(seq)
}

#[inline]
fn ext_of(l: u32) -> i32 {
    if l & 1 != 0 {
        -((l >> 1) as i32)
    } else {
        (l >> 1) as i32
    }
}

#[inline]
fn int_of(x: i32) -> u32 {
    if x < 0 {
        2 * (x.unsigned_abs()) + 1
    } else {
        2 * x as u32
    }
}

impl Solver {
    pub fn new() -> Solver {
        Solver {
            val: vec![U, U],
            watches: vec![Vec::new(), Vec::new()],
            level: vec![0],
            reason: vec![Reason::None],
            act: vec![0.0],
            polarity: vec![1],
            hpos: vec![-1],
            seen: vec![0],
            heap: Vec::new(),
            trail: Vec::new(),
            trail_lim: Vec::new(),
            qhead: 0,
            db: Vec::new(),
            clauses: Vec::new(),
            learnts: Vec::new(),
            ok: true,
            nvars: 0,
            var_inc: 1.0,
            cla_inc: 1.0,
            max_learnts: 0.0,
            assumptions: Vec::new(),
            witness: None,
            stamp: 0,
            acache: None,
            last_trail: Rc::new(Vec::new()),
            held: None,
            conflict: Vec::new(),
            n: Counters::default(),
            scan: 0,
            theories: Vec::new(),
            tmap: vec![Vec::new()],
            thead: 0,
            tprops: Vec::new(),
            tdecides: Vec::new(),
            tpending: false,
            rb_base: vec![0],
            rbc: None,
            rb_mask: vec![0],
            rb_ment: vec![0],
            rb_saved: vec![0],
            rb_cl: vec![0],
            rb_undo: Vec::new(),
            rb_ulim: Vec::new(),
            uid: 1,
            ment: vec![0],
            lazy: vec![0],
            rb_n: 0,
            rb_blocks: 0,
            rb_nclauses: 0,
            rb_bases: Vec::new(),
            ring: Vec::new(),
            n_registered: 0,
            buf: Vec::new(),
            vals_buf: Vec::new(),
        }
    }

    fn grow(&mut self, v: usize) {
        let n = self.nvars;
        if v <= n {
            return;
        }
        let k = v - n;
        self.val.resize(self.val.len() + 2 * k, U);
        self.watches.resize_with(self.watches.len() + 2 * k, Vec::new);
        self.level.resize(self.level.len() + k, 0);
        self.reason.resize(self.reason.len() + k, Reason::None);
        self.act.resize(self.act.len() + k, 0.0);
        self.polarity.resize(self.polarity.len() + k, 1);
        self.seen.resize(self.seen.len() + k, 0);
        self.rb_base.resize(self.rb_base.len() + k, 0);
        self.ment.resize(self.ment.len() + k, 0);
        self.lazy.resize(self.lazy.len() + k, 0);
        self.tmap.resize_with(self.tmap.len() + k, Vec::new);
        let start = self.heap.len();
        for i in 0..k {
            self.hpos.push((start + i) as i32);
            self.heap.push((n + 1 + i) as u32);
        }
        self.nvars = v;
    }

    fn internal_lits(&mut self, lits: &[u32]) -> R<Vec<u32>> {
        let mut out = Vec::with_capacity(lits.len());
        let mut maxv = 0usize;
        for &w in lits {
            let x = w as i32;
            if x == 0 {
                return Err(ValueError);
            }
            maxv = maxv.max(x.unsigned_abs() as usize);
            out.push(int_of(x));
        }
        if maxv > self.nvars {
            self.grow(maxv);
        }
        Ok(out)
    }

    fn heap_insert(&mut self, v: usize) {
        if self.hpos[v] >= 0 {
            return;
        }
        self.hpos[v] = self.heap.len() as i32;
        self.heap.push(v as u32);
        self.heap_up(self.heap.len() - 1);
    }

    fn heap_up(&mut self, mut i: usize) {
        let v = self.heap[i];
        let a = self.act[v as usize];
        while i > 0 {
            let p = (i - 1) >> 1;
            let pv = self.heap[p];
            if self.act[pv as usize] >= a {
                break;
            }
            self.heap[i] = pv;
            self.hpos[pv as usize] = i as i32;
            i = p;
        }
        self.heap[i] = v;
        self.hpos[v as usize] = i as i32;
    }

    fn heap_down(&mut self, mut i: usize) {
        let n = self.heap.len();
        let v = self.heap[i];
        let a = self.act[v as usize];
        loop {
            let mut c = 2 * i + 1;
            if c >= n {
                break;
            }
            let r = c + 1;
            if r < n && self.act[self.heap[r] as usize] > self.act[self.heap[c] as usize] {
                c = r;
            }
            let cv = self.heap[c];
            if self.act[cv as usize] <= a {
                break;
            }
            self.heap[i] = cv;
            self.hpos[cv as usize] = i as i32;
            i = c;
        }
        self.heap[i] = v;
        self.hpos[v as usize] = i as i32;
    }

    fn heap_pop(&mut self) -> usize {
        let v = self.heap[0];
        let last = self.heap.pop().unwrap();
        self.hpos[v as usize] = -1;
        if !self.heap.is_empty() {
            self.heap[0] = last;
            self.hpos[last as usize] = 0;
            self.heap_down(0);
        }
        v as usize
    }

    fn bump_var(&mut self, v: usize) {
        let a = self.act[v] + self.var_inc;
        self.act[v] = a;
        if a > 1e100 {
            for u in 1..=self.nvars {
                self.act[u] *= 1e-100;
            }
            self.var_inc *= 1e-100;
        }
        if self.hpos[v] >= 0 {
            self.heap_up(self.hpos[v] as usize);
        }
    }

    fn bump_clause(&mut self, c: u32) {
        let d = &mut self.db[c as usize];
        d.act += self.cla_inc;
        if d.act > 1e20 {
            for i in 0..self.learnts.len() {
                self.db[self.learnts[i] as usize].act *= 1e-20;
            }
            self.cla_inc *= 1e-20;
        }
    }

    fn new_clause(&mut self, lits: Vec<u32>, learnt: bool) -> u32 {
        self.db.push(Clause { lits, act: 0.0, learnt });
        (self.db.len() - 1) as u32
    }

    #[inline]
    fn set_true(&mut self, l: u32, lvl: u32, r: Reason) {
        let v = (l >> 1) as usize;
        self.val[l as usize] = T;
        self.val[(l ^ 1) as usize] = F;
        self.level[v] = lvl;
        self.reason[v] = r;
        self.trail.push(l);
    }

    pub fn add_clause(&mut self, lits: &[u32]) -> R<bool> {
        if !self.ok {
            return Ok(false);
        }
        let out = self.internal_lits(lits)?;
        if out.len() > 1 {
            self.mention_int(&out);
        }
        Ok(self.add_lits(out, true))
    }

    fn add_lits(&mut self, mut raw: Vec<u32>, clean: bool) -> bool {
        if !self.ok {
            return false;
        }
        if !self.trail_lim.is_empty() && self.held.is_none() {
            self.backtrack(0);
        }
        if clean && raw.len() > 1 {
            // Python: a set, then dict.fromkeys. Keeps the first of each literal, in order.
            let mut k = 0;
            for i in 0..raw.len() {
                let l = raw[i];
                if !raw[..k].contains(&l) {
                    raw[k] = l;
                    k += 1;
                }
            }
            raw.truncate(k);
            if raw.iter().any(|&l| raw.contains(&(l ^ 1))) {
                return true;
            }
        }
        let mut out = Vec::with_capacity(raw.len());
        for &l in &raw {
            let vl = self.val[l as usize];
            if vl != U && self.level[(l >> 1) as usize] == 0 {
                if vl == T {
                    return true;
                }
                continue;
            }
            out.push(l);
        }
        self.witness = None;
        self.stamp += 1;
        if out.len() < 2 && !self.trail_lim.is_empty() {
            self.backtrack(0);
        }
        if out.is_empty() {
            self.ok = false;
            return false;
        }
        if out.len() == 1 {
            self.set_true(out[0], 0, Reason::None);
            if self.prop().is_some() {
                self.ok = false;
                return false;
            }
            return true;
        }
        let (a, b) = (out[0], out[1]);
        let c = self.new_clause(out, false);
        self.clauses.push(c);
        if !self.trail_lim.is_empty() {
            self.attach_held(c);
            return true;
        }
        self.watches[a as usize].push(c);
        self.watches[b as usize].push(c);
        true
    }

    fn attach_held(&mut self, cr: u32) {
        let cu = cr as usize;
        let n = self.db[cu].lits.len();
        let mut k = 0;
        for i in 0..n {
            let l = self.db[cu].lits[i];
            if self.val[l as usize] != F {
                self.db[cu].lits[i] = self.db[cu].lits[k];
                self.db[cu].lits[k] = l;
                k += 1;
                if k == 2 {
                    break;
                }
            }
        }
        if k == 1 {
            let mut best = 1;
            for i in 2..n {
                let c = &self.db[cu].lits;
                if self.level[(c[i] >> 1) as usize] > self.level[(c[best] >> 1) as usize] {
                    best = i;
                }
            }
            self.db[cu].lits.swap(1, best);
            let l = self.db[cu].lits[0];
            let l1 = self.db[cu].lits[1];
            let vl = self.val[l as usize];
            if vl == T && self.level[(l >> 1) as usize] > self.level[(l1 >> 1) as usize] {
                k = 0;
            } else if vl == U {
                let dl = self.trail_lim.len() as u32;
                if self.level[(l1 >> 1) as usize] == dl {
                    self.set_true(l, dl, Reason::Clause(cr));
                    self.watches[l as usize].push(cr);
                    self.watches[l1 as usize].push(cr);
                    if self.prop_any().is_some() {
                        self.backtrack(0);
                    }
                    return;
                }
                k = 0;
            }
        }
        if k == 0 {
            self.backtrack(0);
        }
        let (a, b) = (self.db[cu].lits[0], self.db[cu].lits[1]);
        self.watches[a as usize].push(cr);
        self.watches[b as usize].push(cr);
    }

    pub fn ensure_vars(&mut self, v: usize) {
        if v > self.nvars {
            self.grow(v);
        }
    }

    pub fn add_internal(&mut self, clauses: &[&[u32]], mentions: Option<&[(u32, u128)]>) -> R<bool> {
        if !self.ok {
            return Ok(false);
        }
        if !self.trail_lim.is_empty() && self.held.is_none() {
            self.backtrack(0);
        }
        if let Some(m) = mentions {
            self.mention_blocks(m)?;
        } else {
            let mut new: Vec<u32> = Vec::new();
            for lits in clauses {
                for &l in lits.iter() {
                    if self.ment[(l >> 1) as usize] == 0 {
                        new.push(l);
                    }
                }
            }
            if !new.is_empty() {
                self.mention_int(&new);
            }
        }
        for lits in clauses {
            if lits.len() == 1 && !self.trail_lim.is_empty() {
                self.backtrack(0);
            }
            if lits.iter().any(|&l| self.val[l as usize] != U) {
                if !self.add_lits(lits.to_vec(), true) {
                    return Ok(false);
                }
            } else if lits.len() == 1 {
                self.set_true(lits[0], 0, Reason::None);
            } else {
                let c = self.new_clause(lits.to_vec(), false);
                self.clauses.push(c);
                self.watches[lits[0] as usize].push(c);
                self.watches[lits[1] as usize].push(c);
            }
        }
        self.witness = None;
        self.stamp += 1;
        Ok(true)
    }

    pub fn set_rule_block(&mut self, tables: &Rc<Closure>) -> R<()> {
        if let Some(cur) = &self.rbc {
            if cur.clauses == tables.clauses && cur.n == tables.n {
                return Ok(());
            }
            return Err(ValueError);
        }
        self.rb_n = tables.n;
        self.rbc = Some(tables.clone());
        Ok(())
    }

    fn flags_into(&mut self, base: usize, mm: u128) {
        for i in 0..self.rb_n {
            let mt = ((mm >> (2 * i)) & 1) as u8;
            self.lazy[base + i] = 1 - mt;
            self.ment[base + i] = mt;
        }
    }

    pub fn register_block(&mut self, base: i32, mentions: u128) -> R<bool> {
        let rbc = match &self.rbc {
            Some(r) => r.clone(),
            None => return Err(ValueError),
        };
        if base < 1 {
            return Err(ValueError);
        }
        let base = base as usize;
        if !self.ok {
            return Ok(false);
        }
        if !self.trail_lim.is_empty() && self.held.is_none() {
            self.backtrack(0);
        }
        let n = self.rb_n;
        let top = base + n - 1;
        if top > self.nvars {
            self.grow(top);
        }
        if self.rb_base[base..=top].iter().any(|&b| b != 0) {
            return Err(ValueError);
        }
        let lo = 2 * base;
        let assigned = self.val[lo..lo + 2 * n].iter().any(|&x| x != U);
        if assigned
            && !self.trail_lim.is_empty()
            && (base..=top).any(|v| self.val[2 * v] != U && self.level[v] != 0)
        {
            self.backtrack(0);
        }
        self.rb_base[base..=top].fill(base as u32);
        if top + n > self.rb_ment.len() {
            self.rb_room(top + n);
        }
        let mut mm = (mentions | (mentions >> 1)) & EVEN;
        if 2 * n < 128 && mm >> (2 * n) != 0 {
            return Err(ValueError);
        }
        mm |= mm << 1;
        let lo_b = 1.max(base as i64 - n as i64 + 1) as usize;
        let window = lo_b..top + 1;
        if self.rb_ment[window.clone()].iter().any(|&x| x != 0) {
            let full = if 2 * n >= 128 { u128::MAX } else { (1u128 << (2 * n)) - 1 };
            for (k, i) in window.enumerate() {
                let x = self.rb_ment[i];
                if x != 0 {
                    let d = (lo_b + k) as i64 - base as i64;
                    let y = if d >= 0 { x << (2 * d) } else { x >> (-2 * d) };
                    mm |= y & full;
                }
            }
        }
        if self.ment[base..=top].iter().any(|&x| x != 0) {
            for i in 0..n {
                if self.ment[base + i] != 0 {
                    mm |= 3u128 << (2 * i);
                }
            }
        }
        self.rb_ment[base] = mm;
        self.flags_into(base, mm);
        self.rb_mask[base] = 0;
        self.rb_cl[base] = 0;
        self.rb_blocks += 1;
        self.rb_bases.push(base as u32);
        self.rb_nclauses += rbc.clauses.len();
        self.witness = None;
        self.stamp += 1;
        if rbc.models.is_empty() {
            if !self.trail_lim.is_empty() {
                self.backtrack(0);
            }
            self.ok = false;
            return Ok(false);
        }
        if !assigned {
            return Ok(true);
        }
        Ok(self.rb_settle(base, &rbc))
    }

    fn rb_settle(&mut self, base: usize, rbc: &Closure) -> bool {
        let lo = 2 * base;
        let n2 = 2 * self.rb_n;
        let mut m = 0u128;
        for rel in 0..n2 {
            if self.val[lo + rel] == T {
                m |= 1u128 << rel;
            }
        }
        self.rb_mask[base] = m;
        if m == 0 {
            return true;
        }
        let c = rbc.closure(m);
        self.rb_cl[base] = c;
        let mut new = c & !m;
        if c != 0 && new == 0 {
            return true;
        }
        if !self.trail_lim.is_empty() {
            self.backtrack(0);
        }
        if c == 0 {
            self.ok = false;
            return false;
        }
        while new != 0 {
            let l = (lo + new.trailing_zeros() as usize) as u32;
            new &= new - 1;
            if self.val[l as usize] == U {
                self.set_true(l, 0, Reason::None);
            }
        }
        if self.prop().is_some() {
            self.ok = false;
            return false;
        }
        true
    }

    /// `_rb_reason`, into `out`.
    fn rb_reason(&self, v: usize, m: u128, base: u32, out: &mut Vec<u32>) {
        let lo = base << 1;
        let l = if self.val[2 * v] == T { 2 * v as u32 } else { 2 * v as u32 + 1 };
        out.clear();
        out.push(l);
        let e = self.rbc.as_ref().unwrap().explain(m, (l - lo) as i32);
        for &q in e.iter() {
            out.push((q as u32 + lo) ^ 1);
        }
    }

    fn mention_int(&mut self, lits: &[u32]) {
        // Python: a dict, insertion-ordered, and the order reaches _rb_late. A list scanned linearly keeps that.
        let mut pend: Vec<(u32, u128)> = Vec::new();
        for &l in lits {
            let v = (l >> 1) as usize;
            if self.ment[v] == 0 {
                self.ment[v] = 1;
                let b = self.rb_base[v];
                if b != 0 {
                    let bit = 3u128 << (2 * (v - b as usize));
                    match pend.iter_mut().find(|p| p.0 == b) {
                        Some(p) => p.1 |= bit,
                        None => pend.push((b, bit)),
                    }
                }
            }
        }
        for (b, new) in pend {
            let b = b as usize;
            let mm = self.rb_ment[b] | new;
            self.rb_ment[b] = mm;
            self.rb_mentioned(b, new, mm);
        }
    }

    fn rb_room(&mut self, base: usize) {
        let want = base.max(self.nvars) + 1;
        if want > self.rb_ment.len() {
            self.rb_mask.resize(want, 0);
            self.rb_ment.resize(want, 0);
            self.rb_saved.resize(want, 0);
            self.rb_cl.resize(want, 0);
        }
    }

    fn mention_blocks(&mut self, pairs: &[(u32, u128)]) -> R<()> {
        let n = self.rb_n;
        for &(base, mask) in pairs {
            let base = base as usize;
            let mut mask = (mask | (mask >> 1)) & EVEN;
            if mask == 0 {
                continue;
            }
            if 2 * n < 128 && mask >> (2 * n) != 0 {
                return Err(ValueError);
            }
            mask |= mask << 1;
            if base + n > self.rb_ment.len() {
                self.rb_room(base + n);
            }
            let b0 = self.rb_base[base] as usize;
            if b0 != base {
                // the slice is clamped at the end of the list, so a short one counts as touching a block
                let end = (base + n).min(self.rb_base.len());
                if b0 != 0 || self.rb_base[base..end].iter().filter(|&&x| x == 0).count() != n {
                    let mut lits = Vec::new();
                    while mask != 0 {
                        lits.push(2 * base as u32 + mask.trailing_zeros());
                        mask &= mask - 1;
                    }
                    self.mention_int(&lits);
                    continue;
                }
            }
            let old = self.rb_ment[base];
            let new = mask & !old;
            if new == 0 {
                continue;
            }
            let mm = old | new;
            self.rb_ment[base] = mm;
            if b0 == base {
                self.rb_mentioned(base, new, mm);
            }
        }
        Ok(())
    }

    fn rb_mentioned(&mut self, base: usize, new: u128, mm: u128) {
        let n = self.rb_n;
        self.flags_into(base, mm);
        if self.hpos[base..base + n].contains(&-1) {
            for i in 0..n {
                let v = base + i;
                if self.hpos[v] < 0 && self.lazy[v] == 0 {
                    self.heap_insert(v);
                }
            }
        }
        self.stamp += 1;
        if !self.trail_lim.is_empty() {
            let mut imp = self.rb_cl[base] & new;
            if imp != 0 {
                let lo = base << 1;
                let mut unw = 0u128;
                while imp != 0 {
                    let q = imp.trailing_zeros() as usize;
                    imp &= imp - 1;
                    if self.val[q + lo] == U {
                        unw |= 1u128 << q;
                    }
                }
                if unw != 0 {
                    self.rb_late(base, self.rb_mask[base], unw);
                }
            }
        }
    }

    fn rb_late(&mut self, base: usize, m: u128, imp: u128) {
        let dl = self.trail_lim.len() as u32;
        let lo = base << 1;
        let rbc = self.rbc.as_ref().unwrap().clone();
        let mut low = 0u128;
        let mut b = m;
        while b != 0 {
            let q = b.trailing_zeros() as usize;
            b &= b - 1;
            if self.level[(q + lo) >> 1] < dl {
                low |= 1u128 << q;
            }
        }
        if rbc.closure(low) & imp != 0 {
            self.backtrack(0);
            return;
        }
        let mut b = imp;
        while b != 0 {
            let l = (b.trailing_zeros() as usize + lo) as u32;
            b &= b - 1;
            if self.val[l as usize] == U {
                self.set_true(l, dl, Reason::Block(m, base as u32));
            }
        }
        if self.prop_any().is_some() {
            self.backtrack(0);
        }
    }

    pub fn mention(&mut self, lits: &[u32]) -> R<()> {
        let l = self.internal_lits(lits)?;
        self.mention_int(&l);
        Ok(())
    }

    pub fn propagate(&mut self) -> bool {
        if !self.ok {
            return false;
        }
        if self.held.is_some() {
            return true;
        }
        if !self.trail_lim.is_empty() {
            self.backtrack(0);
        }
        if self.prop_any().is_some() {
            self.ok = false;
            return false;
        }
        true
    }

    pub fn value(&self, lit: i32) -> Option<bool> {
        let v = lit.unsigned_abs() as usize;
        if v == 0 || v > self.nvars {
            return None;
        }
        if !self.trail_lim.is_empty() && self.level[v] > 0 {
            return None;
        }
        match self.val[int_of(lit) as usize] {
            T => Some(true),
            F => Some(false),
            _ => None,
        }
    }

    pub fn implied(&mut self, assumptions: &[u32], hold: i32) -> R<Option<Vec<i32>>> {
        let tr = self.assume(assumptions, hold)?;
        let list = |t: &[u32]| t.iter().map(|&l| ext_of(l)).collect::<Vec<i32>>();
        Ok(match tr {
            Tr::Conflict => None,
            Tr::Live => Some(list(&self.trail)),
            Tr::Last => Some(list(&self.last_trail)),
        })
    }

    pub fn release(&mut self, k: usize) {
        if let Some(h) = &self.held {
            if h.len() > k {
                let pre = h[..k].to_vec();
                self.backtrack(k);
                if k != 0 {
                    self.held = Some(pre);
                }
            }
        }
    }

    fn assume(&mut self, assumptions: &[u32], hold: i32) -> R<Tr> {
        let lits = self.internal_lits(assumptions)?;
        self.mention_int(&lits);
        let keep = if hold < 0 { lits.len() } else { (hold as usize).min(lits.len()) };
        let mut start = 0;
        if let Some(h) = &self.held {
            if *h == lits {
                return Ok(Tr::Live);
            }
            start = common(h, &lits);
            if start < h.len() {
                let pre = h[..start].to_vec();
                self.backtrack(start);
                if start != 0 {
                    self.held = Some(pre);
                }
            }
        } else if !self.trail_lim.is_empty() {
            self.backtrack(0);
        }
        if !self.ok {
            return Ok(Tr::Conflict);
        }
        let mut stamp = self.stamp;
        let mut klen = 0;
        if start == 0 {
            if self.prop_any().is_some() {
                self.ok = false;
                return Ok(Tr::Conflict);
            }
            stamp = self.stamp;
            klen = self.trail.len();
            if let Some((kl, ks, kn, t)) = &self.acache {
                if *ks == stamp && *kn == klen && *kl == lits {
                    return Ok(match t {
                        None => Tr::Conflict,
                        Some(t) => {
                            self.last_trail = t.clone();
                            Tr::Last
                        }
                    });
                }
            }
        }
        let trail;
        if self.assume_propagate(&lits[start..]) {
            let t = Rc::new(self.trail.clone());
            self.last_trail = t.clone();
            trail = Some(t);
            if keep != 0 && !self.trail_lim.is_empty() {
                if self.trail_lim.len() > keep {
                    self.backtrack(keep);
                }
                self.held = Some(lits[..keep].to_vec());
            } else {
                self.backtrack(0);
            }
        } else {
            trail = None;
            self.backtrack(0);
        }
        let out = if trail.is_some() { Tr::Last } else { Tr::Conflict };
        if start == 0 && self.ok && self.stamp == stamp {
            self.acache = Some((lits, stamp, klen, trail));
        }
        Ok(out)
    }

    #[inline]
    fn new_level(&mut self) {
        self.trail_lim.push(self.trail.len() as u32);
        self.rb_ulim.push(self.rb_undo.len() as u32);
        self.uid += 1;
        self.n.pushes += self.theories.len() as u64;
    }

    fn assume_propagate(&mut self, lits: &[u32]) -> bool {
        for &l in lits {
            let vl = self.val[l as usize];
            if vl == T {
                self.new_level();
                continue;
            }
            if vl == F {
                return false;
            }
            self.new_level();
            let dl = self.trail_lim.len() as u32;
            self.set_true(l, dl, Reason::None);
            if self.prop_any().is_some() {
                return false;
            }
        }
        true
    }

    #[inline]
    fn prop_any(&mut self) -> Option<u32> {
        if self.theories.is_empty() {
            self.prop()
        } else {
            self.tprop()
        }
    }

    /// `_propagate` and `_propagate_clauses` in one loop: the rule-block part is skipped when no block is set.
    fn prop(&mut self) -> Option<u32> {
        #[cfg(feature = "prof")]
        let t0 = std::time::Instant::now();
        let has_rb = self.rb_n != 0;
        let uid = self.uid;
        let mut qhead = self.qhead;
        let dl = self.trail_lim.len() as u32;
        let mut confl = None;
        let mut nprops = 0;
        while qhead < self.trail.len() {
            let p = self.trail[qhead];
            qhead += 1;
            nprops += 1;
            let pv = (p >> 1) as usize;
            if has_rb {
                let base = self.rb_base[pv] as usize;
                if base != 0 && !matches!(self.reason[pv], Reason::Block(..)) {
                    let bit = 1u128 << (p as usize - (base << 1));
                    let cl = self.rb_cl[base];
                    if cl & bit == 0 {
                        let mut m = self.rb_mask[base];
                        if dl != 0 && self.rb_saved[base] != uid {
                            self.rb_saved[base] = uid;
                            self.rb_undo.push((base as u32, m, cl));
                        }
                        m |= bit;
                        let rbc = self.rbc.as_ref().unwrap();
                        let c = rbc.closure(m);
                        if c == 0 {
                            let lo = (base << 1) as u32;
                            let lits: Vec<u32> = rbc.explain(m, -1).iter().map(|&q| (q as u32 + lo) ^ 1).collect();
                            confl = Some(self.new_clause(lits, false)); // Python: a plain list
                            qhead = self.trail.len();
                            break;
                        }
                        self.rb_mask[base] = m;
                        self.rb_cl[base] = c;
                        let mut new = c & !cl & !bit;
                        if dl != 0 {
                            new &= self.rb_ment[base];
                        }
                        let lo = base << 1;
                        while new != 0 {
                            let l = (new.trailing_zeros() as usize + lo) as u32;
                            new &= new - 1;
                            if self.val[l as usize] == U {
                                self.set_true(l, dl, Reason::Block(m, base as u32));
                            }
                        }
                    }
                }
            }
            let fl = p ^ 1;
            let n = self.watches[fl as usize].len();
            if n == 0 {
                continue;
            }
            // The list leaves its slot while we walk it. No clause can move to it: the new watch is not false.
            let mut ws = std::mem::take(&mut self.watches[fl as usize]);
            let (mut i, mut j) = (0, 0);
            while i < n {
                let cr = ws[i];
                i += 1;
                let c = &mut self.db[cr as usize].lits;
                if c[0] == fl {
                    c[0] = c[1];
                    c[1] = fl;
                }
                let first = c[0];
                let vf = self.val[first as usize];
                if vf == T {
                    ws[j] = cr;
                    j += 1;
                    continue;
                }
                let mut moved = false;
                for k in 2..c.len() {
                    let l = c[k];
                    if self.val[l as usize] != F {
                        c[1] = l;
                        c[k] = fl;
                        self.watches[l as usize].push(cr);
                        moved = true;
                        break;
                    }
                }
                if !moved {
                    ws[j] = cr;
                    j += 1;
                    if vf == F {
                        confl = Some(cr);
                        while i < n {
                            ws[j] = ws[i];
                            j += 1;
                            i += 1;
                        }
                        qhead = self.trail.len();
                    } else {
                        self.set_true(first, dl, Reason::Clause(cr));
                    }
                }
            }
            ws.truncate(j);
            self.watches[fl as usize] = ws;
        }
        self.qhead = qhead;
        self.n.props += nprops;
        #[cfg(feature = "prof")]
        PROP_NS.fetch_add(t0.elapsed().as_nanos() as u64, std::sync::atomic::Ordering::Relaxed);
        confl
    }

    fn backtrack(&mut self, lvl: usize) {
        if self.trail_lim.len() <= lvl {
            return;
        }
        self.held = None;
        let start = self.trail_lim[lvl] as usize;
        for i in (start..self.trail.len()).rev() {
            let l = self.trail[i];
            let v = (l >> 1) as usize;
            self.val[l as usize] = U;
            self.val[(l ^ 1) as usize] = U;
            self.polarity[v] = (l & 1) as u8;
            if self.hpos[v] < 0 {
                self.heap_insert(v);
            }
        }
        let k = self.rb_ulim[lvl] as usize;
        while self.rb_undo.len() > k {
            let (b, m, c) = self.rb_undo.pop().unwrap();
            self.rb_mask[b as usize] = m;
            self.rb_cl[b as usize] = c;
        }
        self.rb_ulim.truncate(lvl);
        self.uid += 1;
        self.trail.truncate(start);
        self.qhead = start;
        if !self.theories.is_empty() {
            if self.thead > start {
                self.thead = start;
            }
            self.n.pops += ((self.trail_lim.len() - lvl) * self.theories.len()) as u64;
        }
        self.trail_lim.truncate(lvl);
    }

    pub fn attach_theory(&mut self, t: Tape) {
        if !self.trail_lim.is_empty() {
            self.backtrack(0);
        }
        let i = self.theories.len();
        if t.has_prop {
            self.tprops.push(i);
        }
        if t.has_dec {
            self.tdecides.push(i);
        }
        self.theories.push(t);
        self.witness = None;
        self.stamp += 1;
    }

    pub fn theories_count(&self) -> usize {
        self.theories.len()
    }

    pub fn register_atom(&mut self, tid: u32, var: i32, mention: bool) -> R<bool> {
        let ti = self.theories.iter().position(|t| t.tid == tid).ok_or(ValueError)?;
        if var <= 0 {
            return Err(ValueError);
        }
        let var = var as usize;
        if var > self.nvars {
            self.grow(var);
        }
        if mention {
            self.mention_int(&[2 * var as u32]);
        }
        if !self.trail_lim.is_empty() {
            self.backtrack(0);
        }
        self.n_registered += 1;
        if self.tmap[var].contains(&(ti as u32)) {
            return Err(ValueError);
        }
        self.tmap[var].push(ti as u32);
        self.witness = None;
        self.stamp += 1;
        self.tpending = true;
        if !self.ok {
            return Ok(false);
        }
        let l = 2 * var as u32;
        let vl = self.val[l as usize];
        if vl != U {
            let tl = if vl == T { l } else { l ^ 1 };
            if self.trail.iter().position(|&x| x == tl).unwrap() < self.thead {
                let x = if vl == T { var as i32 } else { -(var as i32) };
                if let Some(c) = self.theories[ti].assert_lit(x) {
                    self.theory_conflict(c);
                    return Ok(false);
                }
            }
        }
        Ok(true)
    }

    fn tprop(&mut self) -> Option<u32> {
        loop {
            if let Some(c) = self.prop() {
                return Some(c);
            }
            if let Some(c) = self.theory_sync() {
                return Some(c);
            }
            if self.qhead == self.trail.len() {
                return None;
            }
        }
    }

    fn theory_sync(&mut self) -> Option<u32> {
        let mut i = self.thead;
        if i == self.trail.len() && !self.tpending {
            return None;
        }
        self.tpending = false;
        while i < self.trail.len() {
            let l = self.trail[i];
            i += 1;
            let v = (l >> 1) as usize;
            if self.tmap[v].is_empty() {
                continue;
            }
            let x = ext_of(l);
            for k in 0..self.tmap[v].len() {
                let t = self.tmap[v][k] as usize;
                if let Some(c) = self.theories[t].assert_lit(x) {
                    self.thead = i;
                    return Some(self.theory_conflict(c));
                }
            }
        }
        self.thead = i;
        for pi in 0..self.tprops.len() {
            let t = self.tprops[pi];
            let (mut j, n) = self.theories[t].propagate();
            let w = self.theories[t].w;
            for _ in 0..n {
                let x = w[j] as i32;
                let m = w[j + 1] as usize;
                let why = &w[j + 2..j + 2 + m];
                j += 2 + m;
                if let Some(c) = self.theory_imply(x, why) {
                    return Some(c);
                }
            }
        }
        None
    }

    fn theory_clause(&self, lits: &[u32]) -> Vec<u32> {
        let mut out = Vec::with_capacity(lits.len());
        for &w in lits {
            let x = w as i32;
            let v = x.unsigned_abs() as usize;
            if v == 0 || v > self.nvars {
                panic!("theory clause has a bad literal {x}");
            }
            let l = int_of(x);
            if !out.contains(&l) {
                out.push(l);
            }
        }
        out
    }

    fn sort_by_level(&self, raw: &mut [u32]) {
        // stable, like list.sort(key=level, reverse=True): equal levels keep their order
        raw.sort_by_key(|&l| std::cmp::Reverse(self.level[(l >> 1) as usize]));
    }

    fn theory_conflict(&mut self, lits: &[u32]) -> u32 {
        let mut raw = self.theory_clause(lits);
        assert!(!raw.is_empty(), "theory returned an empty conflict clause");
        for &l in &raw {
            assert!(self.val[l as usize] == F, "theory conflict literal {} is not false", ext_of(l));
        }
        self.sort_by_level(&mut raw);
        let ml = self.level[(raw[0] >> 1) as usize] as usize;
        if ml < self.trail_lim.len() {
            self.backtrack(ml);
        }
        if ml == 0 {
            self.ok = false;
            return self.new_clause(raw, false);
        }
        if raw.len() > 1 {
            let (a, b) = (raw[0], raw[1]);
            let c = self.new_clause(raw, true);
            self.stamp += 1;
            self.learnts.push(c);
            self.watches[a as usize].push(c);
            self.watches[b as usize].push(c);
            c
        } else {
            self.new_clause(raw, false)
        }
    }

    fn theory_imply(&mut self, x: i32, lits: &[u32]) -> Option<u32> {
        let mut raw = self.theory_clause(lits);
        let l = int_of(x);
        let at = raw.iter().position(|&q| q == l).expect("theory reason does not contain its literal");
        let vl = self.val[l as usize];
        if vl == T {
            return None;
        }
        if vl == F {
            return Some(self.theory_conflict(lits));
        }
        raw.remove(at);
        for &q in &raw {
            assert!(self.val[q as usize] == F, "theory reason literal {} is not false", ext_of(q));
        }
        let dl = self.trail_lim.len() as u32;
        let reason = if dl == 0 {
            Reason::None
        } else if raw.is_empty() {
            Reason::Clause(self.new_clause(vec![l], false))
        } else {
            self.sort_by_level(&mut raw);
            let r0 = raw[0];
            let mut full = Vec::with_capacity(raw.len() + 1);
            full.push(l);
            full.extend_from_slice(&raw);
            let c = self.new_clause(full, true);
            self.stamp += 1;
            self.learnts.push(c);
            self.watches[l as usize].push(c);
            self.watches[r0 as usize].push(c);
            Reason::Clause(c)
        };
        self.set_true(l, dl, reason);
        None
    }

    fn theory_decide(&mut self) -> i64 {
        for di in 0..self.tdecides.len() {
            let t = self.tdecides[di];
            let x = match self.theories[t].decide() {
                None => continue,
                Some(x) => x,
            };
            let v = x as usize;
            assert!(v > 0 && v <= self.nvars, "theory decision {x} is not a variable");
            assert!(self.val[2 * v] == U, "theory decision {x} is assigned");
            self.n.tdecisions += 1;
            let b = self.rb_base[v] as usize;
            if b != 0 {
                let cl = self.rb_cl[b];
                let q = 2 * (v - b);
                if cl & (1u128 << q) != 0 {
                    return 2 * v as i64;
                }
                if cl & (1u128 << (q + 1)) != 0 {
                    return 2 * v as i64 + 1;
                }
            }
            return 2 * v as i64 + self.polarity[v] as i64;
        }
        -1
    }

    fn theory_check(&mut self) -> Option<u32> {
        for t in 0..self.theories.len() {
            if let Some(c) = self.theories[t].check() {
                return Some(self.theory_conflict(c));
            }
        }
        None
    }

    fn learn(&mut self, confl: u32) -> bool {
        self.n.conflicts += 1;
        self.scan = 0;
        if self.trail_lim.is_empty() {
            self.ok = false;
            return false;
        }
        let (learnt, bt) = self.analyze(confl);
        self.backtrack(bt);
        self.n.learned += 1;
        self.stamp += 1;
        let l0 = learnt[0];
        let reason = if learnt.len() == 1 {
            Reason::None
        } else {
            let l1 = learnt[1];
            let c = self.new_clause(learnt, true);
            self.bump_clause(c); // before it joins learnts: a rescale here misses it, as in Python
            self.learnts.push(c);
            self.watches[l0 as usize].push(c);
            self.watches[l1 as usize].push(c);
            Reason::Clause(c)
        };
        let dl = self.trail_lim.len() as u32;
        self.set_true(l0, dl, reason);
        self.var_inc /= VAR_DECAY;
        self.cla_inc /= CLA_DECAY;
        true
    }

    fn analyze(&mut self, confl: u32) -> (Vec<u32>, usize) {
        let dl = self.trail_lim.len() as u32;
        let mut learnt = vec![0u32];
        let mut toclear: Vec<u32> = Vec::new();
        let mut path = 0i64;
        let mut first = true;
        let mut p;
        let mut index = self.trail.len() as isize - 1;
        let mut buf = std::mem::take(&mut self.buf);
        buf.clear();
        // `buf` holds the current clause; the first is a clause of the database
        let mut cur = Some(confl);
        loop {
            if let Some(c) = cur {
                if self.db[c as usize].learnt {
                    self.bump_clause(c);
                }
                buf.clear();
                buf.extend_from_slice(&self.db[c as usize].lits);
            }
            for &q in &buf[if first { 0 } else { 1 }..] {
                let v = (q >> 1) as usize;
                if self.seen[v] == 0 {
                    let lv = self.level[v];
                    if lv > 0 {
                        self.seen[v] = 1;
                        toclear.push(v as u32);
                        self.bump_var(v);
                        if lv >= dl {
                            path += 1;
                        } else {
                            learnt.push(q);
                        }
                    }
                }
            }
            first = false;
            while self.seen[(self.trail[index as usize] >> 1) as usize] == 0 {
                index -= 1;
            }
            p = self.trail[index as usize];
            index -= 1;
            let pv = (p >> 1) as usize;
            self.seen[pv] = 0;
            path -= 1;
            if path == 0 {
                break;
            }
            match self.reason[pv] {
                Reason::Clause(c) => cur = Some(c),
                Reason::Block(m, b) => {
                    self.rb_reason(pv, m, b, &mut buf);
                    cur = None;
                }
                Reason::None => panic!("analyze: resolving on a decision"),
            }
        }
        learnt[0] = p ^ 1;

        if learnt.len() > 1 {
            let mut j = 1;
            for k in 1..learnt.len() {
                let q = learnt[k];
                let keep = match self.reason[(q >> 1) as usize] {
                    Reason::None => true,
                    Reason::Clause(c) => self.db[c as usize].lits[1..].iter().any(|&l| {
                        let u = (l >> 1) as usize;
                        self.seen[u] == 0 && self.level[u] > 0
                    }),
                    Reason::Block(m, b) => {
                        self.rb_reason((q >> 1) as usize, m, b, &mut buf);
                        buf[1..].iter().any(|&l| {
                            let u = (l >> 1) as usize;
                            self.seen[u] == 0 && self.level[u] > 0
                        })
                    }
                };
                if keep {
                    learnt[j] = q;
                    j += 1;
                }
            }
            learnt.truncate(j);
        }
        for &v in &toclear {
            self.seen[v as usize] = 0;
        }
        self.buf = buf;

        if learnt.len() == 1 {
            return (learnt, 0);
        }
        let mut mi = 1;
        let mut ml = self.level[(learnt[1] >> 1) as usize];
        for k in 2..learnt.len() {
            let lv = self.level[(learnt[k] >> 1) as usize];
            if lv > ml {
                ml = lv;
                mi = k;
            }
        }
        learnt.swap(1, mi);
        (learnt, ml as usize)
    }

    fn analyze_final(&mut self, p: u32) {
        let mut out = vec![p];
        if self.trail_lim.is_empty() {
            self.conflict = out;
            return;
        }
        self.seen[(p >> 1) as usize] = 1;
        let mut buf = std::mem::take(&mut self.buf);
        for i in (self.trail_lim[0] as usize..self.trail.len()).rev() {
            let l = self.trail[i];
            let v = (l >> 1) as usize;
            if self.seen[v] != 0 {
                match self.reason[v] {
                    Reason::None => {
                        if l != p {
                            out.push(l);
                        }
                    }
                    Reason::Clause(c) => {
                        for &q in &self.db[c as usize].lits[1..] {
                            let u = (q >> 1) as usize;
                            if self.level[u] > 0 {
                                self.seen[u] = 1;
                            }
                        }
                    }
                    Reason::Block(m, b) => {
                        self.rb_reason(v, m, b, &mut buf);
                        for &q in &buf[1..] {
                            let u = (q >> 1) as usize;
                            if self.level[u] > 0 {
                                self.seen[u] = 1;
                            }
                        }
                    }
                }
                self.seen[v] = 0;
            }
        }
        self.seen[(p >> 1) as usize] = 0;
        self.buf = buf;
        self.conflict = out;
    }

    fn pick_branch(&mut self) -> i64 {
        let mut v = self.scan;
        if v != 0 {
            let n = self.nvars;
            while v <= n && (self.val[2 * v] != U || self.lazy[v] != 0) {
                v += 1;
            }
            if v > n {
                return -1;
            }
            self.scan = v;
            return 2 * v as i64 + self.polarity[v] as i64;
        }
        while !self.heap.is_empty() {
            let v = self.heap_pop();
            if self.val[2 * v] == U && self.lazy[v] == 0 {
                return 2 * v as i64 + self.polarity[v] as i64;
            }
        }
        -1
    }

    pub fn set_inert(&mut self, v: usize) -> R<()> {
        if v > self.nvars {
            self.grow(v);
        }
        if self.rb_base[v] != 0 {
            return Err(ValueError);
        }
        self.lazy[v] = 1;
        Ok(())
    }

    /// Never fires on these traces (0 reductions), so nothing here tests this path.
    fn reduce_db(&mut self) {
        let mut learnts = std::mem::take(&mut self.learnts);
        let db = &self.db;
        learnts.sort_by(|&a, &b| db[a as usize].act.partial_cmp(&db[b as usize].act).unwrap());
        let half = learnts.len() / 2;
        let mut keep = Vec::with_capacity(learnts.len());
        let mut dead = vec![false; self.db.len()];
        let mut any = false;
        for (i, &c) in learnts.iter().enumerate() {
            let d = &self.db[c as usize];
            let first = d.lits[0];
            let locked = self.val[first as usize] == T
                && matches!(self.reason[(first >> 1) as usize], Reason::Clause(r) if r == c);
            if i < half && d.lits.len() > 2 && !locked {
                dead[c as usize] = true;
                any = true;
            } else {
                keep.push(c);
            }
        }
        if any {
            for l in 2..2 * self.nvars + 2 {
                self.watches[l].retain(|&c| !dead[c as usize]);
            }
        }
        self.learnts = keep;
        self.stamp += 1;
        self.n.reductions += 1;
        self.max_learnts *= LEARNT_SIZE_INC;
    }

    fn search(&mut self, nof_conflicts: i64) -> Option<bool> {
        let mut conflict_c = 0i64;
        loop {
            if let Some(c) = self.prop_any() {
                conflict_c += 1;
                if !self.learn(c) {
                    return Some(false);
                }
                continue;
            }
            if conflict_c >= nof_conflicts {
                self.backtrack(0);
                return None;
            }
            if self.learnts.len() as f64 - self.trail.len() as f64 >= self.max_learnts {
                self.reduce_db();
            }
            let mut dl = self.trail_lim.len();
            let mut nxt: i64 = -1;
            while dl < self.assumptions.len() {
                let p = self.assumptions[dl];
                let vp = self.val[p as usize];
                if vp == T {
                    self.new_level();
                    dl += 1;
                } else if vp == F {
                    self.analyze_final(p);
                    return Some(false);
                } else {
                    nxt = p as i64;
                    break;
                }
            }
            if nxt < 0 {
                self.n.decisions += 1;
                nxt = self.pick_branch();
                if nxt < 0 && !self.tdecides.is_empty() {
                    nxt = self.theory_decide();
                }
                if nxt < 0 {
                    if !self.theories.is_empty() {
                        if let Some(c) = self.theory_check() {
                            conflict_c += 1;
                            if !self.learn(c) {
                                return Some(false);
                            }
                            continue;
                        }
                    }
                    return Some(true);
                }
            }
            self.new_level();
            let dl = self.trail_lim.len() as u32;
            self.set_true(nxt as u32, dl, Reason::None);
        }
    }

    pub fn solve(&mut self, assumptions: &[u32]) -> R<bool> {
        let lits = self.internal_lits(assumptions)?;
        self.mention_int(&lits);
        let keep = match &self.held {
            Some(h) if lits.len() >= h.len() && lits[..h.len()] == h[..] => h.len(),
            _ => 0,
        };
        Ok(self.solve_int(&lits, keep))
    }

    fn solve_int(&mut self, lits: &[u32], keep: usize) -> bool {
        self.conflict.clear();
        if !self.ring.is_empty() && self.ok {
            if let Some(ri) = self.ring_hit(lits) {
                let mv = self.ring[ri].mv.clone();
                let len = mv.borrow().len();
                // `mv + [False] * pad if pad else mv`: any nonzero pad copies, a negative one adds nothing
                self.witness = Some(if self.nvars != len {
                    let mut c = mv.borrow().clone();
                    if self.nvars > len {
                        c.resize(self.nvars, F);
                    }
                    Rc::new(RefCell::new(c))
                } else {
                    mv
                });
                self.n.ring_hits += 1;
                return true;
            }
        }
        let j = match &self.held {
            Some(h) => common(h, lits),
            None => 0,
        };
        if j != 0 {
            if j < self.held.as_ref().unwrap().len() {
                self.backtrack(j);
            }
        } else {
            if !self.trail_lim.is_empty() {
                self.backtrack(0);
            }
            if !self.ok {
                return false;
            }
            if self.prop_any().is_some() {
                self.ok = false;
                return false;
            }
        }
        self.held = None;
        let reductions = self.n.reductions;
        self.scan = 1;
        self.assumptions.clear();
        self.assumptions.extend_from_slice(lits);
        self.max_learnts = self
            .max_learnts
            .max((self.clauses.len() + self.rb_nclauses) as f64 / 3.0)
            .max(LEARNT_SIZE_MIN);
        let mut restarts = 0u64;
        let status = loop {
            let budget = (luby(RESTART_INC, restarts) * RESTART_FIRST) as i64;
            let st = self.search(budget);
            restarts += 1;
            if let Some(s) = st {
                break s;
            }
        };
        self.n.restarts += restarts - 1;
        if status {
            let mv: Vec<u8> = self.val[2..2 * self.nvars + 2].iter().step_by(2).copied().collect();
            let mv = Rc::new(RefCell::new(mv));
            self.witness = Some(mv.clone());
            let rlen = if self.trail_lim.is_empty() { self.trail.len() } else { self.trail_lim[0] as usize };
            self.ring.push(Rec {
                mv,
                ncl: self.clauses.len(),
                rlen,
                nb: self.rb_bases.len(),
                nt: self.theories.len(),
                na: self.n_registered,
            });
            if self.ring.len() > RING {
                self.ring.remove(0);
            }
        }
        if keep != 0 && self.ok && self.trail_lim.len() >= keep && self.n.reductions == reductions {
            self.backtrack(keep);
            self.held = Some(lits[..keep].to_vec());
        } else {
            self.backtrack(0);
        }
        self.assumptions.clear();
        status
    }

    /// `_fill`. The slice assignment can grow `mv` when the block runs past its end.
    fn fill(&self, mv: &mut Vec<u8>, v: usize) -> u8 {
        let b = self.rb_base[v] as usize;
        if b == 0 {
            if self.lazy[v] != 0 {
                mv[v - 1] = F;
                return F;
            }
            return U;
        }
        let n = self.rb_n;
        let lo = b - 1;
        let end = (lo + n).min(mv.len());
        let mut m = 0u128;
        for (i, &x) in mv[lo..end].iter().enumerate() {
            if x != U {
                m |= 1u128 << (2 * i + if x == T { 0 } else { 1 });
            }
        }
        let mut vals = Vec::with_capacity(n);
        self.rbc.as_ref().unwrap().values_of(m, &mut vals);
        if mv.len() < lo + n {
            mv.resize(lo + n, U);
        }
        mv[lo..lo + n].copy_from_slice(&vals);
        mv[v - 1]
    }

    fn ring_hit(&self, lits: &[u32]) -> Option<usize> {
        let root = if self.trail_lim.is_empty() { self.trail.len() } else { self.trail_lim[0] as usize };
        for ri in (0..self.ring.len()).rev() {
            let rec = &self.ring[ri];
            if rec.nt != self.theories.len() || rec.na != self.n_registered {
                continue;
            }
            let mut mv = rec.mv.borrow_mut();
            let n = mv.len();
            // literal true in the model, strictly: `x is not (not l & 1)` breaks on None too
            let holds = |mv: &mut Vec<u8>, l: u32| -> bool {
                let v = (l >> 1) as usize;
                if v > n {
                    return false;
                }
                let mut x = mv[v - 1];
                if x == U {
                    x = self.fill(mv, v);
                }
                x == (if l & 1 == 0 { T } else { F })
            };
            if !lits.iter().all(|&l| holds(&mut mv, l)) {
                continue;
            }
            if !(rec.rlen..root).all(|i| holds(&mut mv, self.trail[i])) {
                continue;
            }
            let mut good = true;
            for i in rec.ncl..self.clauses.len() {
                if !self.clause_ok(&mut mv, n, &self.db[self.clauses[i] as usize].lits) {
                    good = false;
                    break;
                }
            }
            if !good {
                continue;
            }
            if rec.nb == self.rb_bases.len() || self.ring_blocks(&mut mv, &self.rb_bases[rec.nb..]) {
                return Some(ri);
            }
        }
        None
    }

    /// The clause has a literal not false in the model: `x is not (l & 1 == 1)`, so None counts as true here,
    /// and a variable past the model's end counts for nothing.
    fn clause_ok(&self, mv: &mut Vec<u8>, n: usize, c: &[u32]) -> bool {
        for &l in c {
            let v = (l >> 1) as usize;
            if v <= n {
                let mut x = mv[v - 1];
                if x == U {
                    x = self.fill(mv, v);
                }
                if x != (if l & 1 == 1 { T } else { F }) {
                    return true;
                }
            }
        }
        false
    }

    fn ring_blocks(&self, mv: &mut Vec<u8>, bases: &[u32]) -> bool {
        let n = mv.len();
        let rbc = self.rbc.as_ref().unwrap();
        for &b in bases {
            let lo = 2 * b;
            for c in &rbc.clauses {
                let mut ok = false;
                for &q in c {
                    let l = q + lo;
                    let v = (l >> 1) as usize;
                    if v <= n {
                        let mut x = mv[v - 1];
                        if x == U {
                            x = self.fill(mv, v);
                        }
                        if x != (if l & 1 == 1 { T } else { F }) {
                            ok = true;
                            break;
                        }
                    }
                }
                if !ok {
                    return false;
                }
            }
        }
        true
    }

    fn witness_satisfies(&self, assumptions: &[u32]) -> bool {
        let w = match &self.witness {
            None => return false,
            Some(w) => w,
        };
        let mut w = w.borrow_mut();
        let n = w.len();
        for &a in assumptions {
            let a = a as i32;
            let v = a.unsigned_abs() as usize;
            if v <= n {
                let mut b = w[v - 1];
                if b == U {
                    b = self.fill(&mut w, v);
                }
                if b != (if a > 0 { T } else { F }) {
                    return false;
                }
            }
        }
        true
    }

    fn keep_of(hold: i32, n: usize) -> usize {
        if hold < 0 {
            n
        } else {
            (hold as usize).min(n)
        }
    }

    pub fn consistent(&mut self, assumptions: &[u32], hold: i32) -> R<bool> {
        let lits = self.internal_lits(assumptions)?;
        self.mention_int(&lits);
        let k = Self::keep_of(hold, lits.len());
        Ok(self.witness_satisfies(assumptions) || self.solve_int(&lits, k))
    }

    fn in_trail(&self, tr: &Tr, l: u32) -> bool {
        match tr {
            Tr::Live => self.trail.contains(&l),
            Tr::Last => self.last_trail.contains(&l),
            Tr::Conflict => false,
        }
    }

    pub fn entails(&mut self, lit: i32, assumptions: &[u32], hold: i32) -> R<Option<bool>> {
        if lit == 0 {
            return Err(ValueError);
        }
        self.mention(&[lit as u32])?;
        let tr = self.assume(assumptions, hold)?;
        if matches!(tr, Tr::Conflict) {
            return Err(ValueError);
        }
        let v = lit.unsigned_abs() as usize;
        if v > self.nvars {
            self.grow(v);
        }
        let l = int_of(lit);
        let vl = if self.in_trail(&tr, l) {
            Some(true)
        } else if self.in_trail(&tr, l ^ 1) {
            Some(false)
        } else {
            None
        };
        let mut lits = self.internal_lits(assumptions)?;
        let k = Self::keep_of(hold, lits.len());
        if vl.is_some() {
            if self.witness_satisfies(assumptions) || self.solve_int(&lits, k) {
                return Ok(vl);
            }
            return Err(ValueError);
        }
        let n = lits.len();
        lits.push(l ^ 1);
        if !self.solve_int(&lits, k) {
            lits[n] = l;
            if !self.solve_int(&lits, k) {
                return Err(ValueError);
            }
            return Ok(Some(true));
        }
        lits[n] = l;
        if !self.solve_int(&lits, k) {
            return Ok(Some(false));
        }
        Ok(None)
    }

    pub fn entails_all(&mut self, lits: &[u32], assumptions: &[u32], hold: i32) -> R<Option<bool>> {
        if lits.len() == 1 {
            return self.entails(lits[0] as i32, assumptions, hold);
        }
        self.mention(lits)?;
        let tr = self.assume(assumptions, hold)?;
        if matches!(tr, Tr::Conflict) {
            return Err(ValueError);
        }
        let ins = self.internal_lits(lits)?;
        let mut alits = self.internal_lits(assumptions)?;
        let k = Self::keep_of(hold, alits.len());
        let mut vals = std::mem::take(&mut self.vals_buf);
        vals.clear();
        for &l in &ins {
            vals.push(if self.in_trail(&tr, l) {
                T
            } else if self.in_trail(&tr, l ^ 1) {
                F
            } else {
                U
            });
        }
        let all = vals.iter().all(|&x| x == T);
        let res = if vals.contains(&F) || all {
            if self.witness_satisfies(assumptions) || self.solve_int(&alits, k) {
                Ok(Some(all))
            } else {
                Err(ValueError)
            }
        } else {
            let n = alits.len();
            alits.extend_from_slice(&ins);
            if !self.solve_int(&alits, k) {
                alits.truncate(n);
                if !self.solve_int(&alits, k) {
                    Err(ValueError)
                } else {
                    Ok(Some(false))
                }
            } else {
                alits.truncate(n);
                alits.push(0);
                let mut r = Ok(Some(true));
                for (i, &l) in ins.iter().enumerate() {
                    if vals[i] == U {
                        alits[n] = l ^ 1;
                        if self.solve_int(&alits, k) {
                            r = Ok(None);
                            break;
                        }
                    }
                }
                r
            }
        };
        self.vals_buf = vals;
        res
    }
}
