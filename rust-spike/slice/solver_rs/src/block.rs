//! The rule block's tables per solver: the closure and explanation parts of `_BlockClosure`, and (S2) `_rule_tables`'
//! check and model enumeration.
//! The engine's block (rules.py's RULE_INTERNAL over NPRED) is static, so its models are generated offline from
//! `_rule_tables` (gen_rule_tables.py, rule_tables_gen.rs) and used when the given block has exactly those clauses and
//! that nvars. Any other block (the public `set_rule_block`: tests, fuzzers) is checked and enumerated here, a port of
//! `_rule_tables`' checks and `_block_models`. Python's own `_rule_tables` stays, for the pure-Python path.
//! Each Rust solver builds its Closure from the models and keeps its own memos, so nothing here outlives the solver.
//! Masks are over the relative literals of up to 64 variables, so u128. A model *set* has one bit per model, so u128
//! up to 128 models (the engine's block has 44); past that `closure` scans the models, with the same result.
use crate::map::Map;
use crate::relations_core::{planted, RB_BUILT_MODEL_DROP, RB_CHECK_SKIP, RB_GEN_ANY, RB_GEN_MODEL_FLIP};
use crate::rule_tables_gen as gen;
use crate::session::{tick, RB_BUILT, RB_CHECK_ERROR, RB_GENERATED};
use crate::solver::fault;
use std::cell::RefCell;
use std::rc::Rc;

/// The models' source, for the counters and the tests.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Source {
    Generated,
    Built,
}

/// A failed check: Python's `ValueError` text, or a clause's index whose repr the caller puts into Python's message
/// ("rule block clause {c} is not a clean clause of 2+ literals").
pub enum BlockError {
    Msg(&'static str),
    Clause(usize),
}

/// `_rule_tables`' checks, in its order, then the models: `(clauses, n, models, source)`. Literals come as i64, an int
/// past i64 clamped to its end, which leaves every comparison below with Python's outcome; `nvars` likewise.
pub fn rule_tables(lits: &[Vec<i64>], nvars: Option<i64>) -> Result<(Vec<Vec<u32>>, usize, Vec<u128>, Source), BlockError> {
    let r = check(lits, nvars);
    if r.is_err() {
        tick(RB_CHECK_ERROR);
    }
    let n = r?;
    let clauses: Vec<Vec<u32>> = lits.iter().map(|c| c.iter().map(|&l| l as u32).collect()).collect();
    let generated = n == gen::NVARS
        && (planted(RB_GEN_ANY)
            || (clauses.len() == gen::CLAUSES.len() && clauses.iter().zip(gen::CLAUSES.iter()).all(|(a, b)| a[..] == b[..])));
    if generated {
        tick(RB_GENERATED);
        let mut models = gen::MODELS.to_vec();
        if planted(RB_GEN_MODEL_FLIP) {
            flip_one(&mut models, n);
        }
        return Ok((clauses, n, models, Source::Generated));
    }
    tick(RB_BUILT);
    let mut models = block_models(&clauses, n).ok_or(BlockError::Msg("rule block has too many models"))?;
    if planted(RB_BUILT_MODEL_DROP) {
        models.pop();
    }
    Ok((clauses, n, models, Source::Built))
}

fn check(lits: &[Vec<i64>], nvars: Option<i64>) -> Result<usize, BlockError> {
    // top = max(l >> 1, default=-1) + 1; Python's >> floors, as i64's does
    let top = lits.iter().flatten().map(|&l| l >> 1).max().map_or(0, |m| m + 1);
    let n = nvars.unwrap_or(top);
    if n < top || n < 1 {
        return Err(BlockError::Msg("rule block mentions a variable beyond nvars"));
    }
    if n > 64 {
        return Err(BlockError::Msg("rule blocks have at most 64 variables"));
    }
    if !planted(RB_CHECK_SKIP) {
        for (i, c) in lits.iter().enumerate() {
            let mut vars: Vec<i64> = c.iter().map(|&l| l >> 1).collect();
            vars.sort_unstable();
            vars.dedup();
            if c.len() < 2 || vars.len() != c.len() || c.iter().any(|&l| l < 0) {
                return Err(BlockError::Clause(i));
            }
        }
    }
    Ok(n as usize)
}

/// The plant RB_GEN_MODEL_FLIP: the first model, one variable flipped, where that gives an assignment that isn't a model.
fn flip_one(models: &mut [u128], n: usize) {
    for j in 0..models.len() {
        for v in 0..n {
            let x = models[j] ^ (3u128 << (2 * v));
            if !models.contains(&x) {
                models[j] = x;
                return;
            }
        }
    }
}

fn comp(bit: u128) -> u128 {
    if bit & EVEN != 0 {
        bit << 1
    } else {
        bit >> 1
    }
}

/// `_block_models`' `up`: the unit-propagation closure of `a`, which the literal `lit` (a bit) just joined; None on a
/// conflict. `sw` is `a` with each literal replaced by its complement.
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

/// `_block_models`' `rec`; false once past 65,536 models (Python's "too many models").
fn rec(occ: &[Vec<u128>], vbits: &[u128], out: &mut Vec<u128>, a: u128, mut k: usize) -> bool {
    while k < vbits.len() {
        let low = vbits[k];
        if a & (low | (low << 1)) == 0 {
            for bit in [low << 1, low] {
                if let Some(b) = up(occ, a | bit, bit) {
                    if !rec(occ, vbits, out, b, k + 1) {
                        return false;
                    }
                }
            }
            return true;
        }
        k += 1;
    }
    out.push(a);
    out.len() <= 1 << 16
}

/// `_block_models` for a checked block (clauses of two or more literals over distinct variables, so its root loop
/// over unit and empty clauses has nothing to do): all models, ascending; None past 65,536.
pub fn block_models(clauses: &[Vec<u32>], n: usize) -> Option<Vec<u128>> {
    let cls: Vec<u128> = clauses.iter().map(|c| c.iter().fold(0u128, |m, &l| m | (1u128 << l))).collect();
    let mut occ: Vec<Vec<u128>> = vec![Vec::new(); 2 * n];
    for &cm in &cls {
        let mut m = cm;
        while m != 0 {
            occ[m.trailing_zeros() as usize].push(cm);
            m &= m - 1;
        }
    }
    // Python's sort is stable on -(occurrences), as sort_by_key is on Reverse(occurrences)
    let mut order: Vec<usize> = (0..n).collect();
    order.sort_by_key(|&v| std::cmp::Reverse(occ[2 * v].len() + occ[2 * v + 1].len()));
    let vbits: Vec<u128> = order.iter().map(|&v| 1u128 << (2 * v)).collect();
    let mut out = Vec::new();
    if !rec(&occ, &vbits, &mut out, 0, 0) {
        return None;
    }
    out.sort_unstable();
    out.dedup();
    Some(out)
}

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
