//! The rule block's shared tables: a port of `_block_models` and `_BlockClosure`.
//! Masks are over the relative literals of up to 64 variables, so u128. A model *set* has one bit per model:
//! this spike uses u128 and panics past 128 models (the engine's block has 44; Python's limit is 65,536).
use crate::map::Map;
use std::cell::RefCell;
use std::rc::Rc;

pub const EVEN: u128 = 0x5555_5555_5555_5555_5555_5555_5555_5555;

fn comp(bit: u128) -> u128 {
    if bit & EVEN != 0 {
        bit << 1
    } else {
        bit >> 1
    }
}

fn up(occ: &[Vec<u128>], mut a: u128, lit: u128) -> Option<u128> {
    let mut sw = ((a & EVEN) << 1) | ((a >> 1) & EVEN);
    let mut queue = vec![lit];
    while let Some(l) = queue.pop() {
        for &cm in &occ[comp(l).trailing_zeros() as usize] {
            if a & cm != 0 {
                continue;
            }
            let free = cm & !sw;
            if free == 0 {
                return None;
            }
            if free & (free - 1) == 0 {
                a |= free;
                sw |= comp(free);
                queue.push(free);
            }
        }
    }
    Some(a)
}

fn rec(occ: &[Vec<u128>], vbits: &[u128], out: &mut Vec<u128>, a: u128, mut k: usize) {
    while k < vbits.len() {
        let low = vbits[k];
        if a & (low | (low << 1)) == 0 {
            for bit in [low << 1, low] {
                if let Some(b) = up(occ, a | bit, bit) {
                    rec(occ, vbits, out, b, k + 1);
                }
            }
            return;
        }
        k += 1;
    }
    out.push(a);
    assert!(out.len() <= 1 << 16, "rule block has too many models");
}

fn block_models(clauses: &[Vec<u32>], n: usize) -> Vec<u128> {
    let cls: Vec<u128> = clauses.iter().map(|c| c.iter().fold(0u128, |m, &l| m | (1u128 << l))).collect();
    let mut occ: Vec<Vec<u128>> = vec![Vec::new(); 2 * n];
    for &cm in &cls {
        let mut m = cm;
        while m != 0 {
            occ[m.trailing_zeros() as usize].push(cm);
            m &= m - 1;
        }
    }
    let mut order: Vec<usize> = (0..n).collect();
    order.sort_by_key(|&v| std::cmp::Reverse(occ[2 * v].len() + occ[2 * v + 1].len()));
    let vbits: Vec<u128> = order.iter().map(|&v| 1u128 << (2 * v)).collect();
    let mut out = Vec::new();
    rec(&occ, &vbits, &mut out, 0, 0);
    out.sort_unstable();
    out.dedup();
    out
}

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
    pub fn new(clauses: Vec<Vec<u32>>, nvars: i32) -> Closure {
        let top = clauses.iter().flatten().map(|&l| (l >> 1) as usize + 1).max().unwrap_or(0);
        let n = if nvars < 0 { top } else { nvars as usize };
        assert!(n >= top && n >= 1 && n <= 64, "bad rule block size");
        let models = block_models(&clauses, n);
        assert!(models.len() <= 128, "spike: more than 128 models in a rule block");
        let mut msets = vec![0u128; 2 * n];
        for (j, &x) in models.iter().enumerate() {
            for (lit, s) in msets.iter_mut().enumerate() {
                if (x >> lit) & 1 != 0 {
                    *s |= 1u128 << j;
                }
            }
        }
        let all = if models.len() == 128 { u128::MAX } else { (1u128 << models.len()) - 1 };
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
        let x = self.models.iter().copied().find(|&x| x & m == m).expect("rule block: no model contains the set");
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
            assert!(bestk > 0, "rule block explanation: set does not entail the literal");
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
