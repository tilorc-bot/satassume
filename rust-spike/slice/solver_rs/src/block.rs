//! The rule block's tables per solver: the closure and explanation parts of `_BlockClosure`.
//! Python's `_rule_tables` still validates the block and enumerates its models, under its existing memo; each Rust
//! solver reads the finished models once and keeps its own memos, so nothing here outlives the solver.
//! Masks are over the relative literals of up to 64 variables, so u128. A model *set* has one bit per model, so u128
//! up to 128 models (the engine's block has 44); past that `closure` scans the models, with the same result.
use crate::map::Map;
use crate::solver::fault;
use std::cell::RefCell;
use std::rc::Rc;

pub const EVEN: u128 = 0x5555_5555_5555_5555_5555_5555_5555_5555;

pub struct Closure {
    pub n: usize,
    pub clauses: Vec<Vec<u32>>,
    pub models: Vec<u128>,
    msets: Vec<u128>,
    all: u128,
    cls: RefCell<Map<u128, u128>>,
    memo: RefCell<Map<u128, u128>>,
    expl: RefCell<Map<(u128, i32), Rc<[u8]>>>,
}

impl Closure {
    pub fn from_models(clauses: Vec<Vec<u32>>, n: usize, models: Vec<u128>) -> Closure {
        let wide = models.len() > 128;
        let mut msets = vec![0u128; 2 * n];
        for (j, &x) in models.iter().enumerate().take(if wide { 0 } else { 128 }) {
            for (lit, s) in msets.iter_mut().enumerate() {
                if (x >> lit) & 1 != 0 {
                    *s |= 1u128 << j;
                }
            }
        }
        let all = if models.len() >= 128 { u128::MAX } else { (1u128 << models.len()) - 1 };
        Closure {
            n,
            clauses,
            models,
            msets,
            all,
            cls: RefCell::new(Map::default()),
            memo: RefCell::new(Map::default()),
            expl: RefCell::new(Map::default()),
        }
    }

    pub fn closure(&self, m: u128) -> u128 {
        if let Some(&r) = self.memo.borrow().get(&m) {
            return r;
        }
        if self.models.len() > 128 {
            let mut acc = u128::MAX;
            let mut any = false;
            for &x in self.models.iter().filter(|&&x| x & m == m) {
                acc &= x;
                any = true;
            }
            let r = if any { acc } else { 0 };
            self.memo.borrow_mut().insert(m, r);
            return r;
        }
        let mut s = self.all;
        let mut b = m;
        while b != 0 && s != 0 {
            s &= self.msets[b.trailing_zeros() as usize];
            b &= b - 1;
        }
        let r = *self.cls.borrow_mut().entry(s).or_insert_with(|| {
            let mut acc = u128::MAX;
            let mut x = s;
            while x != 0 {
                acc &= self.models[x.trailing_zeros() as usize];
                x &= x - 1;
            }
            if s != 0 {
                acc
            } else {
                0
            }
        });
        self.memo.borrow_mut().insert(m, r);
        r
    }

    /// The variable values (T/F) of the first model containing the consistent set `m`.
    pub fn values_of(&self, m: u128, out: &mut Vec<u8>) {
        let x = match self.models.iter().copied().find(|&x| x & m == m) {
            Some(x) => x,
            None => fault("rule block: no model contains the set".to_string()),
        };
        out.clear();
        out.extend((0..self.n).map(|i| ((x >> (2 * i)) & 1) as u8));
    }

    /// Relative literals of `m` that entail `t` (or, with `t < 0`, are inconsistent): greedy, first best wins,
    /// then minimal by deletion. Must match Python exactly: the result feeds conflict analysis.
    pub fn explain(&self, m: u128, t: i32) -> Rc<[u8]> {
        let key = (m, t);
        if let Some(r) = self.expl.borrow().get(&key) {
            return r.clone();
        }
        let bad: Vec<u128> = if t < 0 {
            self.models.clone()
        } else {
            self.models.iter().copied().filter(|&x| (x >> t) & 1 == 0).collect()
        };
        let mut lits: Vec<u32> = Vec::new();
        let mut b = m;
        while b != 0 {
            lits.push(b.trailing_zeros());
            b &= b - 1;
        }
        let mut chosen: Vec<u32> = Vec::new();
        let mut rest = bad.clone();
        while !rest.is_empty() {
            let mut best = 0u32;
            let mut bestk: i64 = -1;
            for &s in &lits {
                let k = rest.iter().filter(|&&x| (x >> s) & 1 == 0).count() as i64;
                if k > bestk {
                    best = s;
                    bestk = k;
                }
            }
            if bestk <= 0 {
                fault("rule block explanation: set does not entail the literal".to_string());
            }
            chosen.push(best);
            rest.retain(|&x| (x >> best) & 1 != 0);
        }
        let mut i = 0;
        while i < chosen.len() && chosen.len() > 1 {
            let mut sub = 0u128;
            for (j, &s) in chosen.iter().enumerate() {
                if j != i {
                    sub |= 1u128 << s;
                }
            }
            if bad.iter().any(|&x| x & sub == sub) {
                i += 1;
            } else {
                chosen.remove(i);
            }
        }
        let r: Rc<[u8]> = chosen.iter().map(|&s| s as u8).collect();
        self.expl.borrow_mut().insert(key, r.clone());
        r
    }
}
