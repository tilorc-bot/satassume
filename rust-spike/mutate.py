"""mutate.py TRACEDIR_PARENT, from replay/: break the port in ten ways, one at a time, and see whether check mode notices.
Each source file is restored after its mutation."""
import subprocess,sys,shutil,os
S=sys.argv[1]
M=[("solver.rs","level sort: ascending then reversed (ties flip)","raw.sort_by_key(|&l| std::cmp::Reverse(self.level[(l >> 1) as usize]));","raw.sort_by_key(|&l| self.level[(l >> 1) as usize]); raw.reverse();"),
("block.rs","explain: last best wins, not first","if k > bestk {","if k >= bestk {"),
("solver.rs","_mention: pending blocks in reverse order","for (b, new) in pend {","for (b, new) in pend.into_iter().rev() {"),
("solver.rs","_learn: no var_inc decay","self.var_inc /= VAR_DECAY;",""),
("solver.rs","watch: blocker-style keep (first true checked after search order) - skip reassign of c[1]","if c[0] == fl {\n                    c[0] = c[1];\n                    c[1] = fl;\n                }","if c[0] == fl {\n                    c.swap(0, 1);\n                }\n                if c.len() > 2 && self.val[c[2] as usize] == T { c.swap(1, 2); self.watches[c[1] as usize].push(cr); continue; }"),
("solver.rs","ring: None counts as false in a clause","if x != (if l & 1 == 1 { T } else { F }) {\n                    return true;","if x == (if l & 1 == 1 { F } else { T }) {\n                    return true;"),
("solver.rs","_fill: no growth past mv's end (block past the end)","if mv.len() < lo + n {\n            mv.resize(lo + n, U);\n        }\n        mv[lo..lo + n].copy_from_slice(&vals);","let e = (lo + n).min(mv.len()); mv[lo..e].copy_from_slice(&vals[..e - lo]);"),
("solver.rs","_learn: bump after joining learnts","self.bump_clause(c); // before it joins learnts: a rescale here misses it, as in Python\n            self.learnts.push(c);","self.learnts.push(c);\n            self.bump_clause(c);"),
("solver.rs","_pick_branch: decisions not counted on -1","self.n.decisions += 1;\n                nxt = self.pick_branch();","nxt = self.pick_branch();\n                if nxt >= 0 { self.n.decisions += 1; }"),
("solver.rs","theory unit reason stored as learnt","Reason::Clause(self.new_clause(vec![l], false))","Reason::Clause(self.new_clause(vec![l], true))"),
]
for f,name,a,b in M:
    p="src/"+f; s=open(p).read()
    if a not in s: print("NOMATCH",name); continue
    open(p,"w").write(s.replace(a,b,1))
    r=subprocess.run("cargo build --release 2>&1 | grep -E '^error' ",shell=True,capture_output=True,text=True)
    out=[]
    if r.stdout: out=["BUILD ERROR "+r.stdout[:200]]
    else:
      for wl in ("dev","fuzz"):
        x=subprocess.run(["./target/release/replay",wl,S+"/traces","check"],capture_output=True,text=True)
        m=[l for l in x.stderr.splitlines() if "diverged" in l or "differ" in l or "panicked" in l]
        msg=(x.stderr.split("\n")[1][:70] if x.returncode else "not detected")
        out.append(f"{wl}: {msg}")
    print(name,"|"," | ".join(out),flush=True)
    open(p,"w").write(s)
