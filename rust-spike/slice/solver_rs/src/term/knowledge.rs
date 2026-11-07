//! Runtime knowledge, component 6 (`PORT-INVENTORY.md` section 10). So far the atoms family: the unit patterns of
//! `templates/atoms.py`, with the parts of `_common.py` (`units`, `Pattern` on unit shapes, `_unsubsumed`) and of
//! `rules.py` (`cnf_of`, `expand_clause`, `closure_mask`, `unit_propagate`) they run.
//!
//! `Rules` is offline data, read once and never written. A pattern is a function of its facts alone: nothing here is
//! kept between calls, and no hash order is read (`HashMap`s are looked up by name, never iterated).
use super::offline::{Json, OfflineData};
use std::collections::HashMap;

/// A signed 1-based literal over the basis, as in `rules.py`.
type Lit = i32;
/// Basis index and sign, a literal of `expand_clause`'s output.
type BLit = (usize, bool);

const EVEN: u64 = 0x5555_5555_5555_5555;

#[inline]
fn lit_bit(l: Lit) -> u32 {
    if l > 0 {
        2 * (l as u32 - 1)
    } else {
        2 * ((-l) as u32 - 1) + 1
    }
}

fn lits_mask(ls: impl IntoIterator<Item = Lit>) -> u64 {
    ls.into_iter().fold(0, |m, l| m | 1u64 << lit_bit(l))
}

#[inline]
fn signed(i: usize, pos: bool) -> Lit {
    if pos {
        i as Lit + 1
    } else {
        -(i as Lit + 1)
    }
}

/// `rules.py`'s output and `_CONST_BASIS`, from the offline file.
pub struct Rules {
    pub basis: Vec<String>,
    cnf_pos: HashMap<String, Vec<Vec<Lit>>>,
    cnf_neg: HashMap<String, Vec<Vec<Lit>>>,
    masks: Vec<u64>,
    rule_free: u64,
    vocab: Vec<String>,
    pub const_basis: Vec<String>,
}

fn strs(j: Option<&Json>, what: &str) -> Result<Vec<String>, String> {
    j.and_then(Json::as_list)
        .ok_or_else(|| format!("offline: no {what}"))?
        .iter()
        .map(|s| s.as_str().map(str::to_string).ok_or_else(|| format!("offline: {what}: not a string")))
        .collect()
}

fn int_list(j: &Json, what: &str) -> Result<Vec<i64>, String> {
    j.as_list()
        .ok_or_else(|| format!("offline: {what}: not a list"))?
        .iter()
        .map(|x| x.as_int().ok_or_else(|| format!("offline: {what}: not an int")))
        .collect()
}

fn clauses(j: &Json, what: &str) -> Result<Vec<Vec<Lit>>, String> {
    j.as_list()
        .ok_or_else(|| format!("offline: {what}: not a list"))?
        .iter()
        .map(|c| Ok(int_list(c, what)?.into_iter().map(|l| l as Lit).collect()))
        .collect()
}

fn cnf_table(j: Option<&Json>, what: &str) -> Result<HashMap<String, Vec<Vec<Lit>>>, String> {
    match j {
        Some(Json::Obj(items)) => items.iter().map(|(k, v)| Ok((k.clone(), clauses(v, what)?))).collect(),
        _ => Err(format!("offline: no {what}")),
    }
}

/// `{"$set": [...]}`, as `gen_offline_data.canon` writes a set.
fn set_items<'a>(j: Option<&'a Json>, what: &str) -> Result<&'a [Json], String> {
    j.and_then(|s| s.get("$set"))
        .and_then(Json::as_list)
        .ok_or_else(|| format!("offline: no set {what}"))
}

impl Rules {
    pub fn load(data: &OfflineData) -> Result<Rules, String> {
        let rules = data.body.get("rules").ok_or("offline: no rules")?;
        let common = data.body.get("common").ok_or("offline: no common")?;
        let basis = strs(rules.get("BASIS"), "BASIS")?;
        let npred = rules.get("NPRED").and_then(Json::as_int).ok_or("offline: no NPRED")?;
        if npred as usize != basis.len() || basis.len() > 32 {
            return Err(format!("offline: {npred} predicates over {} basis names", basis.len()));
        }
        let inst = clauses(rules.get("RULE_INSTANTIATED").ok_or("offline: no RULE_INSTANTIATED")?, "rule")?;
        let masks = inst.iter().map(|c| lits_mask(c.iter().copied())).collect();
        let mut rule_free = 0u64;
        for x in set_items(rules.get("RULE_FREE"), "RULE_FREE")? {
            rule_free |= 1u64 << x.as_int().ok_or("offline: RULE_FREE: not an int")?;
        }
        let vocab = set_items(common.get("VOCAB"), "VOCAB")?
            .iter()
            .map(|s| s.as_str().map(str::to_string).ok_or_else(|| "offline: VOCAB: not a string".to_string()))
            .collect::<Result<Vec<_>, _>>()?;
        Ok(Rules {
            basis,
            cnf_pos: cnf_table(rules.get("_CNF_POS"), "_CNF_POS")?,
            cnf_neg: cnf_table(rules.get("_CNF_NEG"), "_CNF_NEG")?,
            masks,
            rule_free,
            vocab,
            const_basis: strs(common.get("_CONST_BASIS"), "_CONST_BASIS")?,
        })
    }

    pub fn in_vocab(&self, pred: &str) -> bool {
        self.vocab.iter().any(|v| v == pred)
    }

    /// `closure_mask`: the unit-propagation fixpoint of the literal mask `a`, or None on a conflict.
    fn closure(&self, mut a: u64) -> Option<u64> {
        let mut sw = ((a & EVEN) << 1) | ((a >> 1) & EVEN);
        if a & sw != 0 {
            return None;
        }
        let mut changed = true;
        while changed {
            changed = false;
            for &m in &self.masks {
                if a & m != 0 {
                    continue;
                }
                let free = m & !sw;
                if free == 0 {
                    return None;
                }
                if free & (free - 1) == 0 {
                    a |= free;
                    sw |= if free & EVEN != 0 { free << 1 } else { free >> 1 };
                    changed = true;
                }
            }
        }
        Some(a)
    }

    /// `expand_clause` of one literal `(0, pred, pos)`: the clauses of its CNF, tautologies dropped, duplicates merged.
    fn expand(&self, pred: &str, pos: bool) -> Result<Vec<Vec<BLit>>, String> {
        let table = if pos { &self.cnf_pos } else { &self.cnf_neg };
        let cnf = table.get(pred).ok_or_else(|| format!("unknown predicate {pred}"))?;
        let mut res: Vec<Vec<BLit>> = Vec::with_capacity(cnf.len());
        let mut seen: Vec<Vec<BLit>> = Vec::with_capacity(cnf.len());
        for cl in cnf {
            let mut c: Vec<BLit> = Vec::with_capacity(cl.len());
            for &l in cl {
                let b = ((l.unsigned_abs() - 1) as usize, l > 0);
                if !c.contains(&b) {
                    c.push(b);
                }
            }
            if c.iter().any(|&(i, p)| c.contains(&(i, !p))) {
                continue;
            }
            let mut key = c.clone();
            key.sort_unstable();
            if seen.contains(&key) {
                continue;
            }
            seen.push(key);
            res.push(c);
        }
        Ok(res)
    }

    /// `_common.units`, then `Pattern.__init__`, over `(pred, value)` facts in the order given.
    pub fn units(&self, facts: &[(&str, bool)]) -> Result<UnitPattern, String> {
        let mut lits: Vec<Lit> = Vec::with_capacity(self.basis.len());
        let mut rest: Vec<Vec<BLit>> = Vec::new();
        for &(pred, value) in facts {
            for c in self.expand(pred, value)? {
                if c.len() == 1 {
                    lits.push(signed(c[0].0, c[0].1));
                } else {
                    rest.push(c);
                }
            }
        }
        let mut closed = self.closure(lits_mask(lits.iter().copied()));
        if let Some(m) = closed {
            lits = self.sorted_lits(m);
        }
        if !rest.is_empty() {
            let mut units = lits_mask(lits.iter().copied());
            loop {
                let mut keep = Vec::with_capacity(rest.len());
                let mut new: Vec<Lit> = Vec::new();
                for cs in &rest {
                    let cl: Vec<BLit> = cs
                        .iter()
                        .copied()
                        .filter(|&(i, p)| units & 1u64 << lit_bit(signed(i, !p)) == 0)
                        .collect();
                    if cl.iter().any(|&(i, p)| units & 1u64 << lit_bit(signed(i, p)) != 0) {
                        continue;
                    }
                    if cl.len() == 1 && closed.is_some() {
                        new.push(signed(cl[0].0, cl[0].1));
                    } else {
                        keep.push(cl);
                    }
                }
                rest = keep;
                if new.is_empty() {
                    break;
                }
                closed = self.closure(units | lits_mask(new));
                match closed {
                    None => break,
                    Some(m) => {
                        lits = self.sorted_lits(m);
                        units = m;
                    }
                }
            }
        }
        let mut rules: Vec<Vec<BLit>> =
            lits.iter().map(|&l| vec![((l.unsigned_abs() - 1) as usize, l > 0)]).collect();
        rules.extend(rest);
        let complete = closed.is_some_and(|m| {
            let mut decided = self.rule_free;
            for i in 0..self.basis.len() {
                if m & (3u64 << (2 * i)) != 0 {
                    decided |= 1u64 << i;
                }
            }
            decided.count_ones() as usize == self.basis.len()
        });
        let clauses = unsubsumed(&rules);
        Ok(UnitPattern { rules, clauses, complete })
    }

    /// `sorted(mask_lits(m), key=abs)`. Never both signs of a variable: `m` is a closure.
    fn sorted_lits(&self, m: u64) -> Vec<Lit> {
        let mut out = Vec::with_capacity(self.basis.len());
        for i in 0..self.basis.len() {
            if m & (1u64 << (2 * i)) != 0 {
                out.push(signed(i, true));
            } else if m & (1u64 << (2 * i + 1)) != 0 {
                out.push(signed(i, false));
            }
        }
        out
    }
}

/// `_unsubsumed` of a unit pattern's rules: `(basis index, neg)` clauses without duplicates and without those a shorter
/// one subsumes, shortest first, each sorted. Python's masks and index are a speed-up of this same subset test.
fn unsubsumed(rules: &[Vec<BLit>]) -> Vec<Vec<(usize, bool)>> {
    let mut distinct: Vec<Vec<(usize, bool)>> = Vec::with_capacity(rules.len());
    for r in rules {
        // A rule here is `() -> cs`, so a clause literal's `neg` is `not pos`.
        let mut c: Vec<(usize, bool)> = r.iter().map(|&(i, pos)| (i, !pos)).collect();
        c.sort_unstable();
        c.dedup();
        if c.iter().any(|&(i, n)| c.contains(&(i, !n))) {
            continue;
        }
        if !distinct.contains(&c) {
            distinct.push(c);
        }
    }
    distinct.sort_by_key(Vec::len); // stable, as Python's `sorted(..., key=len)`
    let mut out: Vec<Vec<(usize, bool)>> = Vec::with_capacity(distinct.len());
    for c in distinct {
        if !out.iter().any(|d| d.iter().all(|l| c.contains(l))) {
            out.push(c);
        }
    }
    out
}

/// A unit `Pattern`: node slot 0, one object, no child slots and nothing wide.
pub struct UnitPattern {
    /// Each `((), ((0, basis[i], pos), ...))`, in `units`' order.
    pub rules: Vec<Vec<BLit>>,
    /// `(i, neg)` literals, all in slot 0.
    pub clauses: Vec<Vec<(usize, bool)>>,
    pub complete: bool,
}
