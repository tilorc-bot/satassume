"""tab359.py CMP.txt (sa-port-359): gate359.sh's cmp.txt (one cmp359.py line per workload) as a short table: queries,
conversions, kept, reads, raised, rows that differ, the walker counters 740-746 of the SLICE_CONVERT=rust pass, the
counters of the Python walker's pass summed (0: walk.rs did not run there), the walkers' lifetime (w walks, wr weak
references found, a alive after their query, gc alive after the pass and one gc.collect()), and the totals."""
import ast, re, sys
tot = {}
for l in open(sys.argv[1]):
    m = re.match(r"(\S+) queries (\d+)/(\d+) conversions (\d+) kept (\d+) reads (\d+) raised (\d+) differ (\{.*?\}) first (.*?) digest (\S+) (\S+) walk (\S+) so (\S+) cv (\{.*?\}) cv_py (\{.*?\}) term_raised (\S+) life_py (\{.*?\}) life_rust (\{.*?\}) (EQUAL|DIFFER) \| nat (\S+) (\{.*?\}) (\{.*\})", l)
    if not m:
        print('UNPARSED', l[:200])
        continue
    wl, qa, qb, conv, kept, reads, raised, differ, first, da, db, walk, so, cv, cvpy, tr, lp, lr, eq, dn, cvn, ln = m.groups()
    cv, cvpy, lp, lr, cvn, ln, differ = map(ast.literal_eval, (cv, cvpy, lp, lr, cvn, ln, differ))
    print(f"{wl:14} q {qa:>5} conv {conv:>5} kept {kept:>4} reads {reads:>6} raised {raised:>3} diff {sum(differ.values())} {eq} natdig {'=' if dn == db else 'DIFF'} "
          f"entry {cv['cv:entry']} formula {cv['cv:formula']} read {cv['cv:read']} 743 {cv['cv:fallback:depth']} 744 {cv['cv:fallback:name']} 745 {cv['cv:py:own_base']} 746 {cv['cv:patched']} "
          f"| py cv {sum(cvpy.values())} | life py w{lp['walks']} wr{lp['weakrefs']} a{lp['alive']} gc{lp['alive_gc']} rust w{lr['walks']} wr{lr['weakrefs']} a{lr['alive']} gc{lr['alive_gc']} {lr['types']} nat wr{ln['weakrefs']} gc{ln['alive_gc']} so {so}")
    for k in ('cv:entry', 'cv:formula', 'cv:read', 'cv:fallback:depth', 'cv:fallback:name', 'cv:py:own_base', 'cv:patched'):
        tot[k] = tot.get(k, 0) + cv[k]
    for k, v in (('queries', int(qa)), ('conv', int(conv)), ('kept', int(kept)), ('reads', int(reads)), ('raised', int(raised)), ('weakrefs', lr['weakrefs'] + lp['weakrefs'] + ln['weakrefs'])):
        tot[k] = tot.get(k, 0) + v
print(tot)
