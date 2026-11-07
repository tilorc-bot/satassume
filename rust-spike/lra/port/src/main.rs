//! main WORKLOAD TRACEDIR MODE: replay the recorded LRATheory calls through the port.
//! timed: one pass, per-class wall time. empty: the same dispatch into empty functions. check: crc32 every result and the
//! state after it against `.lra.res`, print totals (not timed). prof (with the `prof` feature): one pass, then widths and sizes.
//! Everything is decoded before the clock starts, as in replay_lra.py.
mod lra;
mod rat;

use lra::{CheckResult, Payload, Theory};
use rat::Rat;
use std::hint::black_box;
use std::time::Instant;

enum Op {
    Assert(u32, i32),
    Prop(u32),
    Push(u32),
    Pop(u32),
    Check(u32),
    Reg(u32, u32, Payload),
    New(u32),
    Drop(u32),
    Query(u32),
}

fn terms(xs: &[&str], i: usize) -> Vec<(u32, Rat)> {
    let n: usize = xs[i].parse().unwrap();
    (0..n).map(|j| (xs[i + 1 + 2 * j].parse().unwrap(), Rat::parse(xs[i + 2 + 2 * j]))).collect()
}

fn payload(xs: &[&str]) -> Payload {
    if xs[3] == "I" {
        return Payload::Integral { offset: Rat::parse(xs[4]), terms: terms(xs, 5) };
    }
    assert_eq!(xs[3], "P", "payload tag");
    Payload::Plain {
        neg: xs[4].parse().unwrap(),
        strict: xs[5] == "1",
        eq: xs[6] == "1",
        constant: Rat::parse(xs[7]),
        terms: terms(xs, 8),
    }
}

/// The ops, and the largest theory id seen.
fn decode(path: &str) -> (Vec<Op>, usize) {
    let text = std::fs::read_to_string(path).unwrap();
    let mut ops = Vec::new();
    let mut max_t = 0usize;
    for line in text.lines() {
        let xs: Vec<&str> = line.split_ascii_whitespace().collect();
        let t: u32 = xs[1].parse().unwrap();
        let op = match xs[0] {
            "A" => Op::Assert(t, xs[2].parse().unwrap()),
            "G" => Op::Prop(t),
            "U" => Op::Push(t),
            "O" => Op::Pop(t),
            "C" => Op::Check(t),
            "R" => Op::Reg(t, xs[2].parse().unwrap(), payload(&xs)),
            "N" => Op::New(t),
            "D" => Op::Drop(t),
            "Q" => Op::Query(t),
            other => panic!("trace op {other}"),
        };
        if !matches!(op, Op::Query(_)) {
            max_t = max_t.max(t as usize);
        }
        ops.push(op);
    }
    (ops, max_t)
}

/// `meta["cls"]` as class indices (0 none, 1 definite, 2 other), with no JSON crate.
fn read_cls(path: &str) -> Vec<usize> {
    let s = std::fs::read_to_string(path).unwrap();
    let start = s.find("\"cls\": [").expect("meta: no cls") + 8;
    let end = start + s[start..].find(']').unwrap();
    s[start..end]
        .split(',')
        .map(|x| match x.trim().trim_matches('"') {
            "none" => 0,
            "definite" => 1,
            "other" => 2,
            o => panic!("class {o}"),
        })
        .collect()
}

fn crc_table() -> [u32; 256] {
    let mut t = [0u32; 256];
    for (i, e) in t.iter_mut().enumerate() {
        let mut c = i as u32;
        for _ in 0..8 {
            c = if c & 1 != 0 { 0xEDB88320 ^ (c >> 1) } else { c >> 1 };
        }
        *e = c;
    }
    t
}

fn crc32(t: &[u32; 256], s: &str) -> u32 {
    let mut c = !0u32;
    for b in s.bytes() {
        c = t[((c ^ b as u32) & 255) as usize] ^ (c >> 8);
    }
    !c
}

fn lits(xs: &[i32]) -> String {
    xs.iter().map(|x| x.to_string()).collect::<Vec<_>>().join(",")
}

fn check_text(r: &CheckResult) -> String {
    match r {
        CheckResult::Conflict(c) => format!("F{}", lits(c)),
        CheckResult::Sat(m) => {
            format!("T{}", m.iter().map(|(t, q)| format!("{t}={}", q.text())).collect::<Vec<_>>().join(","))
        }
    }
}

fn state_text(th: &Theory) -> String {
    let s = &th.stats;
    format!(
        "|{},{},{},{},{},{},{},{},{}",
        s.pivots,
        s.checks,
        s.conflicts,
        s.propagations,
        s.branches,
        s.exhausted,
        th.exhausted as u8,
        th.nvars(),
        th.nrows()
    )
}

fn run_check(wl: &str, dir: &str, ops: &[Op], max_t: usize) {
    let crcs: Vec<i64> = std::fs::read_to_string(format!("{dir}/{wl}.lra.res"))
        .unwrap()
        .lines()
        .map(|x| x.parse().unwrap())
        .collect();
    assert_eq!(crcs.len(), ops.len(), "res and trace differ in length");
    let table = crc_table();
    let mut ths: Vec<Option<Theory>> = (0..=max_t).map(|_| None).collect();
    let mut totals = lra::Stats::default();
    let mut bad = 0u64;
    let mut first: Option<usize> = None;
    let mut n = 0u64;
    let verbose = std::env::var("LRA_VERBOSE").is_ok();
    let mut add = |s: &lra::Stats| {
        totals.pivots += s.pivots;
        totals.checks += s.checks;
        totals.conflicts += s.conflicts;
        totals.propagations += s.propagations;
        totals.branches += s.branches;
        totals.exhausted += s.exhausted;
    };
    for (k, op) in ops.iter().enumerate() {
        let (t, res) = match op {
            Op::Query(_) => continue,
            Op::New(t) => {
                ths[*t as usize] = Some(Theory::new());
                continue;
            }
            Op::Drop(t) => {
                add(&ths[*t as usize].take().unwrap().stats);
                continue;
            }
            Op::Assert(t, l) => {
                let r = ths[*t as usize].as_mut().unwrap().assert_lit(*l);
                (*t, r.map_or("N".to_string(), |c| format!("F{}", lits(&c))))
            }
            Op::Prop(t) => {
                let r = ths[*t as usize].as_mut().unwrap().propagate();
                let g: Vec<String> = r.iter().map(|(x, why)| format!("{x}:{}", lits(why))).collect();
                (*t, format!("G{}", g.join(";")))
            }
            Op::Push(t) => {
                ths[*t as usize].as_mut().unwrap().push_level();
                (*t, "N".to_string())
            }
            Op::Pop(t) => {
                ths[*t as usize].as_mut().unwrap().pop_level();
                (*t, "N".to_string())
            }
            Op::Check(t) => {
                let r = ths[*t as usize].as_mut().unwrap().check(lra::BRANCH_BUDGET);
                (*t, check_text(&r))
            }
            Op::Reg(t, l, p) => {
                ths[*t as usize].as_mut().unwrap().register_atom(*l, p);
                (*t, "N".to_string())
            }
        };
        n += 1;
        let text = res + &state_text(ths[t as usize].as_ref().unwrap());
        if crc32(&table, &text) as i64 != crcs[k] {
            bad += 1;
            if first.is_none() {
                first = Some(k);
                if verbose {
                    eprintln!("first mismatch at line {} (theory {t}): {text}", k + 1);
                }
            }
        }
    }
    for th in ths.iter().flatten() {
        add(&th.stats);
    }
    let first = first.map_or("null".to_string(), |k| k.to_string());
    println!(
        "{{\"run\": \"rs\", \"mode\": \"check\", \"wl\": \"{wl}\", \"ops\": {n}, \"mismatches\": {bad}, \"first\": {first}, \
         \"totals\": {{\"pivots\": {}, \"checks\": {}, \"conflicts\": {}, \"propagations\": {}, \"branches\": {}, \"exhausted\": {}}}}}",
        totals.pivots, totals.checks, totals.conflicts, totals.propagations, totals.branches, totals.exhausted
    );
}

fn report(run: &str, wl: &str, t: f64, qt: &[f64; 3], ops: usize) {
    println!(
        "{{\"run\": \"{run}\", \"wl\": \"{wl}\", \"T\": {t}, \"classes\": {{\"none\": {}, \"definite\": {}, \"other\": {}}}, \"ops\": {ops}}}",
        qt[0], qt[1], qt[2]
    );
}

fn run_timed(wl: &str, ops: &[Op], max_t: usize, cls: &[usize]) {
    let mut ths: Vec<Option<Theory>> = (0..=max_t).map(|_| None).collect();
    let mut qt = [0f64; 3];
    let start = Instant::now();
    let mut last = start;
    let mut cur: Option<usize> = None;
    for op in ops {
        match op {
            Op::Assert(t, l) => {
                black_box(ths[*t as usize].as_mut().unwrap().assert_lit(*l));
            }
            Op::Prop(t) => {
                black_box(ths[*t as usize].as_mut().unwrap().propagate());
            }
            Op::Push(t) => ths[*t as usize].as_mut().unwrap().push_level(),
            Op::Pop(t) => ths[*t as usize].as_mut().unwrap().pop_level(),
            Op::Check(t) => {
                black_box(ths[*t as usize].as_mut().unwrap().check(lra::BRANCH_BUDGET));
            }
            Op::Reg(t, l, p) => ths[*t as usize].as_mut().unwrap().register_atom(*l, p),
            Op::New(t) => ths[*t as usize] = Some(Theory::new()),
            Op::Drop(t) => ths[*t as usize] = None,
            Op::Query(t) => {
                let now = Instant::now();
                if let Some(c) = cur {
                    qt[c] += (now - last).as_secs_f64();
                }
                last = now;
                cur = Some(cls[*t as usize]);
            }
        }
    }
    let now = Instant::now();
    qt[cur.unwrap()] += (now - last).as_secs_f64();
    let t = (now - start).as_secs_f64();
    black_box(&ths);
    report("rs", wl, t, &qt, ops.len());
}

/// What the timed loop does outside the methods: the same arms, into functions that do nothing and can't be inlined.
struct Nothing;
#[inline(never)]
fn e_new() -> Nothing {
    black_box(Nothing)
}
#[inline(never)]
fn e_assert(th: &mut Nothing, l: i32) -> Option<Vec<i32>> {
    black_box((th, l));
    None
}
#[inline(never)]
fn e_prop(th: &mut Nothing) -> Vec<(i32, Vec<i32>)> {
    black_box(th);
    Vec::new()
}
#[inline(never)]
fn e_push(th: &mut Nothing) {
    black_box(th);
}
#[inline(never)]
fn e_pop(th: &mut Nothing) {
    black_box(th);
}
#[inline(never)]
fn e_check(th: &mut Nothing) -> CheckResult {
    black_box(th);
    CheckResult::Sat(Vec::new())
}
#[inline(never)]
fn e_reg(th: &mut Nothing, l: u32, p: &Payload) {
    black_box((th, l, p));
}

fn run_empty(wl: &str, ops: &[Op], max_t: usize, cls: &[usize]) {
    let mut ths: Vec<Option<Nothing>> = (0..=max_t).map(|_| None).collect();
    let mut qt = [0f64; 3];
    let start = Instant::now();
    let mut last = start;
    let mut cur: Option<usize> = None;
    for op in ops {
        match op {
            Op::Assert(t, l) => {
                black_box(e_assert(ths[*t as usize].as_mut().unwrap(), *l));
            }
            Op::Prop(t) => {
                black_box(e_prop(ths[*t as usize].as_mut().unwrap()));
            }
            Op::Push(t) => e_push(ths[*t as usize].as_mut().unwrap()),
            Op::Pop(t) => e_pop(ths[*t as usize].as_mut().unwrap()),
            Op::Check(t) => {
                black_box(e_check(ths[*t as usize].as_mut().unwrap()));
            }
            Op::Reg(t, l, p) => e_reg(ths[*t as usize].as_mut().unwrap(), *l, p),
            Op::New(t) => ths[*t as usize] = Some(e_new()),
            Op::Drop(t) => ths[*t as usize] = None,
            Op::Query(t) => {
                let now = Instant::now();
                if let Some(c) = cur {
                    qt[c] += (now - last).as_secs_f64();
                }
                last = now;
                cur = Some(cls[*t as usize]);
            }
        }
    }
    let now = Instant::now();
    qt[cur.unwrap()] += (now - last).as_secs_f64();
    let t = (now - start).as_secs_f64();
    black_box(&ths);
    report("rsempty", wl, t, &qt, ops.len());
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let (wl, dir, mode) = (&args[1], &args[2], args[3].as_str());
    let (ops, max_t) = decode(&format!("{dir}/{wl}.lra"));
    let cls = read_cls(&format!("{dir}/{wl}.lra.meta.json"));
    match mode {
        "check" => run_check(wl, dir, &ops, max_t),
        "timed" => run_timed(wl, &ops, max_t, &cls),
        "empty" => run_empty(wl, &ops, max_t, &cls),
        #[cfg(feature = "prof")]
        "prof" => {
            run_timed(wl, &ops, max_t, &cls);
            use std::sync::atomic::Ordering::Relaxed as R;
            println!(
                "{{\"run\": \"rsprof\", \"wl\": \"{wl}\", \"w32\": {}, \"w64\": {}, \"wbig\": {}, \"bigop\": {}, \"maxbits\": {}, \
                 \"max_row\": {}, \"max_col\": {}, \"max_vars\": {}, \"simplex\": {}}}",
                rat::prof::W32.load(R),
                rat::prof::W64.load(R),
                rat::prof::WBIG.load(R),
                rat::prof::BIGOP.load(R),
                rat::prof::MAXBITS.load(R),
                lra::prof::MAX_ROW.load(R),
                lra::prof::MAX_COL.load(R),
                lra::prof::MAX_VARS.load(R),
                lra::prof::SIMPLEX.load(R),
            );
        }
        _ => panic!("mode {mode}"),
    }
}
