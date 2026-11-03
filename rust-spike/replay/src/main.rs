//! replay WORKLOAD TRACEDIR MODE: replay a recorded trace through the Rust port. Modes as in replay_py.py:
//! check (CRC per call, counters per query), timed, empty (dispatch only), tape (the tape walk alone).
mod block;
mod map;
mod solver;

use block::Closure;
use solver::{Solver, Tape, R};
use std::collections::HashMap;
use std::hint::black_box;
use std::rc::Rc;
use std::time::Instant;

const MAGIC: u32 = 0x5352_5431;

type Lits = &'static [u32];

enum Op {
    Query(u32),
    New(u32),
    Drop(u32),
    Attach { sid: u32, tid: u32 },
    RegAtom { sid: u32, tid: u32, var: i32, mention: bool },
    EnsureVars { sid: u32, v: u32 },
    AddClause { sid: u32, lits: Lits },
    AddInternal { sid: u32, mentions: Option<Box<[(u32, u128)]>>, clauses: Box<[Lits]> },
    SetRuleBlock { sid: u32, block: u32, nvars: i32 },
    RegisterBlock { sid: u32, base: i32, mask: u128 },
    Mention { sid: u32, lits: Lits },
    Propagate { sid: u32 },
    Value { sid: u32, lit: i32 },
    Implied { sid: u32, hold: i32, lits: Lits },
    Release { sid: u32, k: u32 },
    SetInert { sid: u32, v: u32 },
    Solve { sid: u32, lits: Lits },
    Consistent { sid: u32, hold: i32, lits: Lits },
    Entails { sid: u32, lit: i32, hold: i32, lits: Lits },
    EntailsAll { sid: u32, hold: i32, lits: Lits, asm: Lits },
    Theories { sid: u32 },
}

struct Trace {
    ops: Vec<Op>,
    blocks: HashMap<u32, Vec<Vec<u32>>>,
    attach: Vec<(bool, bool)>,
    tapes: Vec<Lits>,
}

fn load_words(path: &str) -> &'static [u32] {
    let b = std::fs::read(path).unwrap_or_else(|e| panic!("{path}: {e}"));
    let w: Vec<u32> = b.chunks_exact(4).map(|c| u32::from_le_bytes(c.try_into().unwrap())).collect();
    Box::leak(w.into_boxed_slice())
}

fn mask(w: &[u32], i: usize) -> u128 {
    (0..4).fold(0u128, |m, k| m | ((w[i + k] as u128) << (32 * k)))
}

fn lits(w: Lits, i: &mut usize) -> Lits {
    let n = w[*i] as usize;
    let r = &w[*i + 1..*i + 1 + n];
    *i += 1 + n;
    r
}

fn decode(path: &str) -> Trace {
    let w = load_words(path);
    assert_eq!(w[0], MAGIC, "bad magic");
    let (n_api, n_th) = (w[1] as usize, w[2] as usize);
    let end = 3 + n_api;
    let mut tapes = Vec::with_capacity(n_th);
    let mut t = end;
    for _ in 0..n_th {
        let n = w[t] as usize;
        tapes.push(&w[t + 1..t + 1 + n]);
        t += 1 + n;
    }
    assert_eq!(t, w.len(), "trailing words");
    let mut ops = Vec::new();
    let mut blocks = HashMap::new();
    let mut attach = vec![(false, false); n_th];
    let mut i = 3;
    while i < end {
        let op = w[i];
        i += 1;
        match op {
            1 => {
                ops.push(Op::Query(w[i]));
                i += 1;
            }
            2 => {
                ops.push(Op::New(w[i]));
                i += 1;
            }
            3 => {
                ops.push(Op::Drop(w[i]));
                i += 1;
            }
            40 => {
                let (id, nc) = (w[i], w[i + 1] as usize);
                i += 2;
                let mut cls = Vec::with_capacity(nc);
                for _ in 0..nc {
                    cls.push(lits(w, &mut i).to_vec());
                }
                blocks.insert(id, cls);
            }
            _ => {
                let sid = w[i];
                i += 1;
                ops.push(match op {
                    10 => {
                        let tid = w[i];
                        attach[tid as usize] = (w[i + 1] != 0, w[i + 2] != 0);
                        i += 3;
                        Op::Attach { sid, tid }
                    }
                    11 => {
                        let o = Op::RegAtom { sid, tid: w[i], var: w[i + 1] as i32, mention: w[i + 2] != 0 };
                        i += 3;
                        o
                    }
                    12 => {
                        i += 1;
                        Op::EnsureVars { sid, v: w[i - 1] }
                    }
                    14 => Op::AddClause { sid, lits: lits(w, &mut i) },
                    16 => {
                        let (has, nm) = (w[i] != 0, w[i + 1] as usize);
                        i += 2;
                        let mut ms = Vec::with_capacity(nm);
                        for _ in 0..nm {
                            ms.push((w[i], mask(w, i + 1)));
                            i += 5;
                        }
                        let nc = w[i] as usize;
                        i += 1;
                        let mut cls = Vec::with_capacity(nc);
                        for _ in 0..nc {
                            cls.push(lits(w, &mut i));
                        }
                        Op::AddInternal {
                            sid,
                            mentions: if has { Some(ms.into_boxed_slice()) } else { None },
                            clauses: cls.into_boxed_slice(),
                        }
                    }
                    18 => {
                        i += 2;
                        Op::SetRuleBlock { sid, block: w[i - 2], nvars: w[i - 1] as i32 }
                    }
                    19 => {
                        i += 5;
                        Op::RegisterBlock { sid, base: w[i - 5] as i32, mask: mask(w, i - 4) }
                    }
                    21 => Op::Mention { sid, lits: lits(w, &mut i) },
                    22 => Op::Propagate { sid },
                    23 => {
                        i += 1;
                        Op::Value { sid, lit: w[i - 1] as i32 }
                    }
                    25 => {
                        let hold = w[i] as i32;
                        i += 1;
                        Op::Implied { sid, hold, lits: lits(w, &mut i) }
                    }
                    26 => {
                        i += 1;
                        Op::Release { sid, k: w[i - 1] }
                    }
                    27 => {
                        i += 1;
                        Op::SetInert { sid, v: w[i - 1] }
                    }
                    28 => Op::Solve { sid, lits: lits(w, &mut i) },
                    29 => {
                        let hold = w[i] as i32;
                        i += 1;
                        Op::Consistent { sid, hold, lits: lits(w, &mut i) }
                    }
                    30 => {
                        let (lit, hold) = (w[i] as i32, w[i + 1] as i32);
                        i += 2;
                        Op::Entails { sid, lit, hold, lits: lits(w, &mut i) }
                    }
                    31 => {
                        let hold = w[i] as i32;
                        i += 1;
                        let l = lits(w, &mut i);
                        let a = lits(w, &mut i);
                        Op::EntailsAll { sid, hold, lits: l, asm: a }
                    }
                    32 => Op::Theories { sid },
                    _ => panic!("op {op} at {i}"),
                });
            }
        }
    }
    assert_eq!(i, end, "api overran");
    Trace { ops, blocks, attach, tapes }
}

fn crc_table() -> [u32; 256] {
    let mut t = [0u32; 256];
    for (i, e) in t.iter_mut().enumerate() {
        let mut c = i as u32;
        for _ in 0..8 {
            c = if c & 1 != 0 { 0xEDB8_8320 ^ (c >> 1) } else { c >> 1 };
        }
        *e = c;
    }
    t
}

struct Crc {
    t: [u32; 256],
    c: u32,
}

impl Crc {
    fn word(&mut self, x: i32) {
        for b in x.to_le_bytes() {
            self.c = self.t[((self.c ^ b as u32) & 0xFF) as usize] ^ (self.c >> 8);
        }
    }
    fn of(&mut self, xs: &[i32]) -> u32 {
        self.c = 0xFFFF_FFFF;
        for &x in xs {
            self.word(x);
        }
        self.c ^ 0xFFFF_FFFF
    }
}

/// A public call's result in the normal form of common_trace.norm.
enum Out {
    None,
    Bool(bool),
    Count(usize),
    List(Option<Vec<i32>>),
    Tri(Option<bool>),
}

const EXC: i32 = -3;

struct Machine {
    solvers: Vec<Option<Solver>>,
    tables: HashMap<(u32, i32), Rc<Closure>>,
    tapes: Vec<Option<Tape>>,
    blocks: HashMap<u32, Vec<Vec<u32>>>,
}

impl Machine {
    fn new(tr: &Trace, nsolvers: usize) -> Machine {
        let tapes = tr
            .tapes
            .iter()
            .enumerate()
            .map(|(i, &w)| {
                let (has_prop, has_dec) = tr.attach[i];
                Some(Tape { w, pos: 0, tid: i as u32, has_prop, has_dec })
            })
            .collect();
        Machine {
            solvers: (0..nsolvers).map(|_| None).collect(),
            tables: HashMap::new(),
            tapes,
            blocks: tr.blocks.clone(),
        }
    }

    /// One public call. Query, New and Drop don't come here.
    #[inline]
    fn call(&mut self, op: &Op) -> (u32, R<Out>) {
        fn s(v: &mut [Option<Solver>], sid: u32) -> &mut Solver {
            v[sid as usize].as_mut().unwrap()
        }
        let v = &mut self.solvers;
        match op {
            Op::Attach { sid, tid } => {
                let t = self.tapes[*tid as usize].take().unwrap();
                s(v, *sid).attach_theory(t);
                (*sid, Ok(Out::None))
            }
            Op::RegAtom { sid, tid, var, mention } => (*sid, s(v, *sid).register_atom(*tid, *var, *mention).map(Out::Bool)),
            Op::EnsureVars { sid, v: x } => {
                s(v, *sid).ensure_vars(*x as usize);
                (*sid, Ok(Out::None))
            }
            Op::AddClause { sid, lits } => (*sid, s(v, *sid).add_clause(lits).map(Out::Bool)),
            Op::AddInternal { sid, mentions, clauses } => {
                (*sid, s(v, *sid).add_internal(clauses, mentions.as_deref()).map(Out::Bool))
            }
            Op::SetRuleBlock { sid, block, nvars } => {
                let blocks = &self.blocks;
                let t = self
                    .tables
                    .entry((*block, *nvars))
                    .or_insert_with(|| Rc::new(Closure::new(blocks[block].clone(), *nvars)));
                (*sid, s(v, *sid).set_rule_block(t).map(|_| Out::None))
            }
            Op::RegisterBlock { sid, base, mask } => (*sid, s(v, *sid).register_block(*base, *mask).map(Out::Bool)),
            Op::Mention { sid, lits } => (*sid, s(v, *sid).mention(lits).map(|_| Out::None)),
            Op::Propagate { sid } => (*sid, Ok(Out::Bool(s(v, *sid).propagate()))),
            Op::Value { sid, lit } => (*sid, Ok(Out::Tri(s(v, *sid).value(*lit)))),
            Op::Implied { sid, hold, lits } => (*sid, s(v, *sid).implied(lits, *hold).map(Out::List)),
            Op::Release { sid, k } => {
                s(v, *sid).release(*k as usize);
                (*sid, Ok(Out::None))
            }
            Op::SetInert { sid, v: x } => (*sid, s(v, *sid).set_inert(*x as usize).map(|_| Out::None)),
            Op::Solve { sid, lits } => (*sid, s(v, *sid).solve(lits).map(Out::Bool)),
            Op::Consistent { sid, hold, lits } => (*sid, s(v, *sid).consistent(lits, *hold).map(Out::Bool)),
            Op::Entails { sid, lit, hold, lits } => (*sid, s(v, *sid).entails(*lit, lits, *hold).map(Out::Tri)),
            Op::EntailsAll { sid, hold, lits, asm } => (*sid, s(v, *sid).entails_all(lits, asm, *hold).map(Out::Tri)),
            Op::Theories { sid } => (*sid, Ok(Out::Count(s(v, *sid).theories_count()))),
            Op::Query(_) | Op::New(_) | Op::Drop(_) => unreachable!(),
        }
    }
}

fn norm_crc(c: &mut Crc, r: &R<Out>) -> u32 {
    match r {
        Err(_) => c.of(&[EXC]),
        Ok(Out::None) | Ok(Out::Tri(None)) | Ok(Out::List(None)) => c.of(&[-2]),
        Ok(Out::Bool(b)) | Ok(Out::Tri(Some(b))) => c.of(&[*b as i32]),
        Ok(Out::Count(n)) => c.of(&[*n as i32]),
        Ok(Out::List(Some(l))) => {
            c.c = 0xFFFF_FFFF;
            c.word(l.len() as i32);
            for &x in l {
                c.word(x);
            }
            c.c ^ 0xFFFF_FFFF
        }
    }
}

const NCOUNT: usize = 10;

fn counters(s: &Solver) -> [u64; NCOUNT] {
    let n = &s.n;
    [
        n.decisions, n.conflicts, n.props, n.learned, n.restarts, n.reductions, n.ring_hits, n.tdecisions, n.pushes, n.pops,
    ]
}

fn run_check(wl: &str, dir: &str, tr: &Trace, nsolvers: usize, perq_rec: &[Vec<u64>]) {
    let res = load_words(&format!("{dir}/{wl}.res"));
    let mut m = Machine::new(tr, nsolvers);
    let mut crc = Crc { t: crc_table(), c: 0 };
    let mut last = vec![[0u64; NCOUNT]; nsolvers];
    let mut total = [0u64; NCOUNT];
    let mut calls = 0usize;
    let mut q: i64 = -1;
    let mut out: Vec<Vec<u64>> = Vec::with_capacity(perq_rec.len());
    let mut close = |q: i64, total: &[u64; NCOUNT], calls: usize| {
        let mut cur = total.to_vec();
        cur.push(calls as u64);
        if cur != perq_rec[q as usize] {
            panic!("query {q}: counters differ: replay {cur:?}, recorded {:?}", perq_rec[q as usize]);
        }
        out.push(cur);
    };
    let check_tape = |s: &Solver| {
        for t in &s.theories {
            assert_eq!(t.pos, t.w.len(), "theory {}: tape not used up", t.tid);
        }
    };
    for op in &tr.ops {
        match op {
            Op::Query(x) => {
                if q >= 0 {
                    close(q, &total, calls);
                }
                q = *x as i64;
            }
            Op::New(s) => m.solvers[*s as usize] = Some(Solver::new()),
            Op::Drop(s) => {
                if let Some(so) = m.solvers[*s as usize].take() {
                    check_tape(&so);
                }
            }
            _ => {
                let (sid, r) = m.call(op);
                let h = norm_crc(&mut crc, &r);
                if h != res[calls] {
                    panic!("call {calls}, query {q}: result crc differs");
                }
                calls += 1;
                let cur = counters(m.solvers[sid as usize].as_ref().unwrap());
                for i in 0..NCOUNT {
                    total[i] += cur[i] - last[sid as usize][i];
                }
                last[sid as usize] = cur;
            }
        }
    }
    close(q, &total, calls);
    assert_eq!(calls, res.len(), "short replay");
    assert_eq!(q as usize + 1, perq_rec.len(), "short replay");
    for so in m.solvers.iter().flatten() {
        check_tape(so);
    }
    println!(
        "{{\"impl\": \"rs\", \"mode\": \"check\", \"wl\": \"{wl}\", \"ok\": true, \"counters\": {:?}, \"calls\": {calls}}}",
        total
    );
    let text = format!("{out:?}");
    std::fs::write(format!("{dir}/{wl}.perq-rs.json"), text).unwrap();
}

fn run_timed(wl: &str, tr: &Trace, nsolvers: usize, none_q: &[bool]) {
    let mut m = Machine::new(tr, nsolvers);
    let mut stamps: Vec<Instant> = Vec::with_capacity(none_q.len());
    let t0 = Instant::now();
    for op in &tr.ops {
        match op {
            Op::Query(_) => stamps.push(Instant::now()),
            Op::New(s) => m.solvers[*s as usize] = Some(Solver::new()),
            Op::Drop(s) => m.solvers[*s as usize] = None,
            _ => {
                let r = m.call(op);
                black_box(&r);
            }
        }
    }
    let t1 = Instant::now();
    let (mut tn, mut td) = (0.0, 0.0);
    for (q, st) in stamps.iter().enumerate() {
        let e = if q + 1 < stamps.len() { stamps[q + 1] } else { t1 };
        let d = e.duration_since(*st).as_secs_f64();
        if none_q[q] {
            tn += d;
        } else {
            td += d;
        }
    }
    println!(
        "{{\"impl\": \"rs\", \"mode\": \"timed\", \"wl\": \"{wl}\", \"T\": {}, \"T_none\": {tn}, \"T_def\": {td}}}",
        t1.duration_since(t0).as_secs_f64()
    );
}

#[cfg(feature = "prof")]
fn run_byop(wl: &str, tr: &Trace, nsolvers: usize) {
    let mut m = Machine::new(tr, nsolvers);
    let mut by: HashMap<&'static str, (f64, u64)> = HashMap::new();
    let t0 = Instant::now();
    for op in &tr.ops {
        let name = match op {
            Op::Query(_) => continue,
            Op::New(_) => "new",
            Op::Drop(_) => "drop",
            Op::Attach { .. } => "attach_theory",
            Op::RegAtom { .. } => "register_atom",
            Op::EnsureVars { .. } => "ensure_vars",
            Op::AddClause { .. } => "add_clause",
            Op::AddInternal { .. } => "add_internal",
            Op::SetRuleBlock { .. } => "set_rule_block",
            Op::RegisterBlock { .. } => "register_block",
            Op::Mention { .. } => "mention",
            Op::Propagate { .. } => "propagate",
            Op::Value { .. } => "value",
            Op::Implied { .. } => "implied",
            Op::Release { .. } => "release",
            Op::SetInert { .. } => "set_inert",
            Op::Solve { .. } => "solve",
            Op::Consistent { .. } => "consistent",
            Op::Entails { .. } => "entails",
            Op::EntailsAll { .. } => "entails_all",
            Op::Theories { .. } => "theories",
        };
        let t = Instant::now();
        match op {
            Op::New(s) => m.solvers[*s as usize] = Some(Solver::new()),
            Op::Drop(s) => m.solvers[*s as usize] = None,
            _ => {
                let r = m.call(op);
                black_box(&r);
            }
        }
        let e = by.entry(name).or_default();
        e.0 += t.elapsed().as_secs_f64();
        e.1 += 1;
    }
    let total = t0.elapsed().as_secs_f64();
    let prop = solver::PROP_NS.load(std::sync::atomic::Ordering::Relaxed) as f64 / 1e9;
    let items: Vec<String> = by.iter().map(|(k, v)| format!("\"{k}\": [{}, {}]", v.0, v.1)).collect();
    println!(
        "{{\"impl\": \"rs\", \"mode\": \"byop\", \"wl\": \"{wl}\", \"T\": {total}, \"T_prop\": {prop}, \"by\": {{{}}}}}",
        items.join(", ")
    );
}

fn run_empty(wl: &str, tr: &Trace) {
    let t0 = Instant::now();
    for op in &tr.ops {
        black_box(op);
    }
    println!(
        "{{\"impl\": \"rs\", \"mode\": \"empty\", \"wl\": \"{wl}\", \"T\": {}}}",
        t0.elapsed().as_secs_f64()
    );
}

fn run_tape(wl: &str, tr: &Trace) {
    let mut ts: Vec<Tape> = tr
        .tapes
        .iter()
        .enumerate()
        .map(|(i, &w)| Tape { w, pos: 0, tid: i as u32, has_prop: true, has_dec: true })
        .collect();
    let mut n = 0u64;
    let t0 = Instant::now();
    for t in &mut ts {
        while t.pos < t.w.len() {
            n += 1;
            match t.w[t.pos] {
                1 => {
                    let x = t.w[t.pos + 1] as i32;
                    black_box(t.assert_lit(x));
                }
                2 => {
                    black_box(t.propagate());
                }
                3 => {
                    black_box(t.check());
                }
                _ => {
                    black_box(t.decide());
                }
            }
        }
    }
    println!(
        "{{\"impl\": \"rs\", \"mode\": \"tape\", \"wl\": \"{wl}\", \"calls\": {n}, \"T_tape\": {}, \"T_plain\": 0.0}}",
        t0.elapsed().as_secs_f64()
    );
}

/// `solvers`, `answers` and `perq` of the meta file, with no JSON crate: a small reader for these three fields.
struct Meta {
    solvers: usize,
    none_q: Vec<bool>,
    perq: Vec<Vec<u64>>,
}

fn find_list(s: &str, key: &str) -> usize {
    let k = format!("\"{key}\": ");
    s.find(&k).unwrap_or_else(|| panic!("meta: no {key}")) + k.len()
}

fn read_meta(path: &str) -> Meta {
    let s = std::fs::read_to_string(path).unwrap();
    let at = find_list(&s, "solvers");
    let solvers: usize = s[at..].split(|c: char| !c.is_ascii_digit()).next().unwrap().parse().unwrap();
    // answers: a flat list of null, true, false or strings
    let at = find_list(&s, "answers") + 1;
    let end = at + s[at..].find(']').unwrap();
    let none_q: Vec<bool> = s[at..end].split(", ").map(|x| x.trim() == "null").collect();
    // perq: [[...], [...]]
    let at = find_list(&s, "perq") + 1;
    let mut perq = Vec::new();
    let mut rest = &s[at..];
    while rest.starts_with('[') {
        let e = rest.find(']').unwrap();
        perq.push(rest[1..e].split(", ").map(|x| x.parse().unwrap()).collect());
        rest = rest[e + 1..].trim_start_matches(", ");
    }
    assert_eq!(perq.len(), none_q.len(), "meta: perq and answers differ in length");
    Meta { solvers, none_q, perq }
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let (wl, dir, mode) = (a[1].as_str(), a[2].as_str(), a[3].as_str());
    let tr = decode(&format!("{dir}/{wl}.trace"));
    let meta = read_meta(&format!("{dir}/{wl}.meta.json"));
    match mode {
        "check" => run_check(wl, dir, &tr, meta.solvers, &meta.perq),
        "timed" => run_timed(wl, &tr, meta.solvers, &meta.none_q),
        "empty" => run_empty(wl, &tr),
        "tape" => run_tape(wl, &tr),
        #[cfg(feature = "prof")]
        "byop" => run_byop(wl, &tr, meta.solvers),
        _ => panic!("mode {mode}"),
    }
}
