"""sum320.py [--compact] NAME=FILE.cnt ... (sa-port-321): sums the count build's lines (count320.patch, SA320_COUNT) per workload.
The last line per (pid, ser) is one solver's total; solvers are summed. Prints markdown tables: what was built against
what was read, per kind of read (visited by propagation, reason or conflict, proof) and per phase of the read
(0 the query, 1 inside build_context, 2 inside its complete check, any). Built-but-unread is an upper bound in
hindsight, not a saving. --compact prints the report's shorter tables, the workloads side by side."""
import sys

KIND = ["visited", "reason", "proof"]
ORG = ["the query (phase 0)", "build_context (phase 1)", "its complete check (phase 2)", "learnt", "other (theory, explanations)"]
PH = ["the query (phase 0)", "build_context (phase 1)", "its complete check (phase 2)"]
RK = ["user eq atom", "queued atom interpreted", "top entry", "pending link"]


def parse(line):
    d = {}
    for kv in line.split()[1:]:
        k, v = kv.split("=", 1)
        if ";" in v:
            d[k] = [[int(x) for x in r.split(",")] for r in v.split(";")]
        elif "," in v:
            d[k] = [int(x) for x in v.split(",")]
        else:
            d[k] = int(v) if v.lstrip("-").isdigit() else v
    return d


def load(path):
    rows, rk, nlines = {}, {}, 0
    for line in open(path):
        if line.startswith("S "):
            d = parse(line)
            nlines += 1
            rows[(d["pid"], d["ser"])] = d
            rk[d["pid"]] = d["rk"]      # rows made is a process-wide counter: the last line per pid has the total
    return list(rows.values()), [sum(r[i] for r in rk.values()) for i in range(4)], nlines


def pct(a, b):
    return "%d (%.1f%%)" % (a, 100.0 * a / b) if b else "%d" % a


def marks_row(name, built, m, noreason=False):
    # m: 12 columns, kind*3+phase then 9+kind. noreason: the patch has no reason mark for this kind of fact (units)
    cells = [pct(m[k * 3 + ph], built) for ph in (0, 2) for k in range(3)] + [pct(m[9 + k], built) for k in range(3)]
    if noreason:
        for i in (1, 4, 7):
            cells[i] = "n/m"
    return "| %s | %d | %s | %d |" % (name, built, " | ".join(cells), built - m[9])


HEAD = ("| %s | built | query: visited | query: reason | query: proof | check: visited | check: reason | check: proof [p] "
        "| any phase: visited | any: reason | any: proof | never visited |\n|---|" + "---:|" * 11)


def compact(args):
    """The report's tables: every workload side by side, the query (phase 0) first, against build_context's clauses."""
    W = []
    for arg in args:
        name, path = arg.split("=", 1)
        S, rk, _ = load(path)
        W.append((name, S, rk))
    T = lambda S, key, i=None, j=None: sum((n[key] if i is None else n[key][i] if j is None else n[key][i][j]) for n in S)
    names = [w[0] for w in W]
    sl = lambda xs: " / ".join("%d" % x for x in xs)
    print("| built, per workload | " + " | ".join(names) + " |\n|---|" + "---:|" * len(W))
    rows = [("solvers (born in build_context / in the query)", lambda S, rk: sl([sum(1 for n in S if n["born"] == 1), sum(1 for n in S if n["born"] == 0)])),
            ("variables: build_context / its check / the query", lambda S, rk: sl([T(S, "vb", i) for i in (1, 2, 0)])),
            ("clauses: build_context / its check / the query", lambda S, rk: sl([T(S, "nb", i) for i in (1, 2, 0)])),
            ("clauses: learnt / other (theory, explanations)", lambda S, rk: sl([T(S, "nb", i) for i in (3, 4)])),
            ("unit clauses: build_context / its check / the query", lambda S, rk: sl([T(S, "ub", i) for i in (1, 2, 0)])),
            ("rule blocks: build_context / its check / the query", lambda S, rk: sl([T(S, "bb", i) for i in (1, 2, 0)])),
            ("relation rows made: user eq / queued atom / top entry / pending link", lambda S, rk: sl(rk)),
            ("relation rows that emitted something, same kinds", lambda S, rk: sl([T(S, "re", k) for k in range(4)]))]
    for label, f in rows:
        print("| %s | %s |" % (label, " | ".join(f(S, rk) for _, S, rk in W)))
    print()
    for name, S, rk in W:
        facts = [("build_context's clauses", T(S, "nb", 1), [T(S, "cm", 1, j) for j in range(12)], False),
                 ("build_context's variables", T(S, "vb", 1), [T(S, "vm", 1, j) for j in range(12)], False),
                 ("the check's own clauses", T(S, "nb", 2), [T(S, "cm", 2, j) for j in range(12)], False),
                 ("the query's own clauses", T(S, "nb", 0), [T(S, "cm", 0, j) for j in range(12)], False),
                 ("rule blocks, all phases", sum(T(S, "bb", i) for i in range(3)), [T(S, "bm", j) for j in range(12)], False),
                 ("relation rows that emitted, all kinds", sum(T(S, "re", k) for k in range(4)), [sum(T(S, "rm", k, j) for k in range(4)) for j in range(12)], False),
                 ("of them, pending links", T(S, "re", 3), [T(S, "rm", 3, j) for j in range(12)], False)]
        print("**%s**, read by the query (phase 0), by the complete check (phase 2) and in any phase:\n" % name)
        print("| %s | built | query: visited | query: reason | query: proof | check: visited | check: reason | check: proof [p] | any: visited | any: reason | any: proof | never visited |" % name)
        print("|---|" + "---:|" * 11)
        for label, built, m, nr in facts:
            print(marks_row(label, built, m, nr))
        print()


def main():
    if sys.argv[1] == "--compact":
        return compact(sys.argv[2:])
    for arg in sys.argv[1:]:
        name, path = arg.split("=", 1)
        S, rk, nlines = load(path)
        tot = lambda key, i=None, j=None: sum((n[key] if i is None else n[key][i] if j is None else n[key][i][j]) for n in S)
        vec = lambda key, i: [tot(key, i, j) for j in range(12)]
        born = [sum(1 for n in S if n["born"] == b) for b in range(3)]
        ec = [tot("ec", i) for i in range(6)]
        nosolve = sum(1 for n in S if n["born"] == 1 and n["ec"][0] == 0)
        print("### %s\n" % name)
        print("Solvers %d (born in the query %d, in build_context %d, in its check %d), from %d count lines. Entries: "
              "solve_int %d, assume %d, propagate %d, entails by a live trail %d, by a trail that is not live %d, root "
              "conflicts %d. Context solvers that never reached solve_int: %d.\n" % (len(S), born[0], born[1], born[2], nlines, *ec, nosolve))
        print(HEAD % "clauses, by where they were added")
        for o in (1, 2, 0, 3, 4):
            print(marks_row(ORG[o], tot("nb", o), vec("cm", o)))
        print()
        print(HEAD % "variables, by the phase that made them")
        for o in (1, 2, 0):
            print(marks_row(PH[o], tot("vb", o), vec("vm", o)))
        print()
        print(HEAD % "unit clauses, by the phase that added them")
        for o in (1, 2, 0):
            print(marks_row(PH[o], tot("ub", o), vec("um", o), noreason=True))
        print()
        bb = [tot("bb", i) for i in range(3)]
        print(HEAD % "rule blocks (marks are not split by the phase that built them)")
        print(marks_row("all (built in phase 0/1/2: %d/%d/%d)" % tuple(bb), sum(bb), [tot("bm", j) for j in range(12)]))
        print()
        print(HEAD.replace("| built |", "| made | emitted |").replace("---:|" * 11, "---:|" * 12) % "relation rows, by kind (read = any clause, variable, unit or atom it emitted is marked)")
        for k in range(4):
            e, m = tot("re", k), vec("rm", k)
            cells = [pct(m[kk * 3 + ph], e) for ph in (0, 2) for kk in range(3)] + [pct(m[9 + kk], e) for kk in range(3)]
            print("| %s | %d | %d | %s | %d |" % (RK[k], rk[k], e, " | ".join(cells), e - m[9]))
        e = sum(tot("re", k) for k in range(4))
        m = [sum(tot("rm", k, j) for k in range(4)) for j in range(12)]
        cells = [pct(m[kk * 3 + ph], e) for ph in (0, 2) for kk in range(3)] + [pct(m[9 + kk], e) for kk in range(3)]
        print("| all kinds | %d | %d | %s | %d |" % (sum(rk), e, " | ".join(cells), e - m[9]))
        print()
        # the headline line: build_context's clauses against the query and the check
        b, c = tot("nb", 1), vec("cm", 1)
        q, qc = tot("nb", 0), vec("cm", 0)
        print("The query itself added %d clauses, %d variables, %d units and %d rule blocks; it visited %s of its own clauses, "
              "reason %s, proof %s. Learnt clauses: %d.\n" % (q, tot("vb", 0), tot("ub", 0), bb[0], pct(qc[0], q), pct(qc[3], q), pct(qc[6], q), tot("nb", 3)))
        print("Totals, %s: build_context added %d clauses (+%d in its check), %d variables, %d units, %d rule blocks; %d relation "
              "rows made, %d emitted. The query visited %s of build_context's clauses, used %s as a reason and %s in a proof; "
              "the complete check visited %s, reason %s, proof %s [p].\n"
              % (name, b, tot("nb", 2), tot("vb", 1), tot("ub", 1), bb[1], sum(rk), e,
                 pct(c[0], b), pct(c[3], b), pct(c[6], b), pct(c[2], b), pct(c[5], b), pct(c[8], b)))


main()
