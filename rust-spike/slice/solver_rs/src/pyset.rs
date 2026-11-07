//! CPython 3.12's set of small non-negative ints, for its iteration order: add, `|` and iterate.
//!
//! `TransferTheory.decide` does `for p in preds`, and the first predicate that qualifies picks the variable, so the
//! order reaches the search. For ints `hash(x) == x`, so the order doesn't depend on the hash seed. It's a function of
//! the values and of how the set was built, and `{8, 0}` and `{0, 8}` iterate differently. See `set_add_entry`,
//! `set_insert_clean`, `set_table_resize` and `set_merge` in Objects/setobject.c. There are no discards, so no dummies.
//! `transfer_fuzz.py` checks this against real sets. Another CPython could change it; this is what 3.12 does.

const LINEAR_PROBES: usize = 9;
const PERTURB_SHIFT: u32 = 5;
const EMPTY: i64 = -1;

#[derive(Clone, Debug)]
pub struct PySetOrder {
    table: Vec<i64>,
    mask: usize,
    used: usize,
}

impl PySetOrder {
    pub fn new() -> PySetOrder {
        PySetOrder { table: vec![EMPTY; 8], mask: 7, used: 0 }
    }

    /// `set.add`.
    pub fn add(&mut self, key: u32) {
        let hash = key as usize;
        let key = key as i64;
        let mask = self.mask;
        let mut i = hash & mask;
        let mut perturb = hash;
        loop {
            let probes = if i + LINEAR_PROBES <= mask { LINEAR_PROBES } else { 0 };
            for j in 0..=probes {
                let e = self.table[i + j];
                if e == EMPTY {
                    self.table[i + j] = key;
                    self.used += 1;
                    if self.used * 5 >= mask * 3 {
                        let minused = if self.used > 50000 { self.used * 2 } else { self.used * 4 };
                        self.resize(minused);
                    }
                    return;
                }
                if e == key {
                    return;
                }
            }
            perturb >>= PERTURB_SHIFT;
            i = i.wrapping_mul(5).wrapping_add(1).wrapping_add(perturb) & mask;
        }
    }

    /// `set_insert_clean`: `key` is known to be absent and there's room.
    fn insert_clean(table: &mut [i64], mask: usize, key: i64) {
        let hash = key as usize;
        let mut i = hash & mask;
        let mut perturb = hash;
        loop {
            if table[i] == EMPTY {
                table[i] = key;
                return;
            }
            if i + LINEAR_PROBES <= mask {
                for j in 1..=LINEAR_PROBES {
                    if table[i + j] == EMPTY {
                        table[i + j] = key;
                        return;
                    }
                }
            }
            perturb >>= PERTURB_SHIFT;
            i = i.wrapping_mul(5).wrapping_add(1).wrapping_add(perturb) & mask;
        }
    }

    /// `set_table_resize`. A size-8 table stays as it is: with no dummies CPython returns at once.
    fn resize(&mut self, minused: usize) {
        let mut newsize = 8;
        while newsize <= minused {
            newsize <<= 1;
        }
        if newsize == 8 && self.mask == 7 {
            return;
        }
        let mut new = vec![EMPTY; newsize];
        for &k in self.table.iter().filter(|&&k| k != EMPTY) {
            Self::insert_clean(&mut new, newsize - 1, k);
        }
        self.table = new;
        self.mask = newsize - 1;
    }

    /// `set_merge`, the bulk insert behind both the copy and the update of `a | b`.
    fn merge(&mut self, other: &PySetOrder) {
        if other.used == 0 {
            return;
        }
        if (self.used + other.used) * 5 >= self.mask * 3 {
            self.resize((self.used + other.used) * 2);
        }
        if self.used == 0 {
            if self.mask == other.mask {
                self.table.copy_from_slice(&other.table);
            } else {
                for &k in other.table.iter().filter(|&&k| k != EMPTY) {
                    Self::insert_clean(&mut self.table, self.mask, k);
                }
            }
            self.used = other.used;
            return;
        }
        for &k in other.table.iter().filter(|&&k| k != EMPTY) {
            self.add(k as u32);
        }
    }

    /// `self | other`, a new set: `set_or` copies `self` by a merge into an empty set, then merges `other`.
    pub fn union(&self, other: &PySetOrder) -> PySetOrder {
        let mut r = PySetOrder::new();
        r.merge(self);
        r.merge(other);
        r
    }

    /// In `for p in s` order.
    pub fn iter(&self) -> impl Iterator<Item = u32> + '_ {
        self.table.iter().filter(|&&k| k != EMPTY).map(|&k| k as u32)
    }

    pub fn from_single(key: u32) -> PySetOrder {
        let mut s = PySetOrder::new();
        s.add(key);
        s
    }
}
