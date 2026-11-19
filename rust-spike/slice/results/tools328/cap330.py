"""cap330.py COST_DIR S1_DIR (sa-port-330, issue 323): the witness check's cap, derived from the points tried per call.
No new timing: COST_DIR is sa-port-329's pinned per-call run (cost.jsonl: seconds per call at cap 32 and with no cap, 3
rounds, median taken per call; why.jsonl: per call the reason and the points tried), S1_DIR is sa-port-328's S1 lease
(time.jsonl: off, cap 32, no cap; median of 12 rounds).

Per call the uncapped run gives T, the points it tries with no cap, and whether it ends certified. Under a cap c the
call tries min(c, T) points and is certified iff it is certified uncapped with T <= c (the order of the points does not
depend on the cap). Its cost under c is a straight line through what was measured:
  T = 0            the measured time (no point is tried under any cap)
  T > 32           fixed + per-point from the two measured arms (32 points and T points)
  0 < T <= 32      both arms measured the same call; fixed is the median fixed part of the T > 32 calls, at most the time
The engine time a certified query saves is not measured per query: S1 gives the sum, gross(32) = (off - on32) + cost(32),
shared equally among the calls certified at 32; the calls certified only above 32 share gross(none) - gross(32).
So the rows for 32 and none reproduce S1; the other rows are this model, not measurements."""
import json, statistics as st, sys
cost_dir, s1_dir = sys.argv[1:3]
CAPS = (1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 64, 128, 0)
s1 = {}
for l in open(s1_dir + "/time.jsonl"):
    r = json.loads(l)
    s1.setdefault((r["wl"], r["arm"]), []).append(r["s"])
s1 = {k: st.median(v) for k, v in s1.items()}
calls, why = {}, {}
for l in open(cost_dir + "/cost.jsonl"):
    r = json.loads(l)
    for q, s, cert, tried in r["calls"]:
        calls.setdefault((r["wl"], r["arm"]), {}).setdefault(q, []).append((s, cert, tried))
for l in open(cost_dir + "/why.jsonl"):
    r = json.loads(l)
    why[(r["wl"], r["arm"])] = {w[0]: (w[1], w[2]) for w in r["why"]}
for wl in ("dev", "fuzz"):
    for mode in ("py", "rust"):
        c32, c0 = calls[(wl, mode + "-on32")], calls[(wl, mode + "-on0")]
        w0 = why[(wl, mode + "-on0")]
        assert set(c32) == set(c0) == set(w0)
        rows = []
        for q in c0:
            t0, t32 = st.median(x[0] for x in c0[q]), st.median(x[0] for x in c32[q])
            cert = c0[q][0][1]
            T = c0[q][0][2] if cert else w0[q][1]
            rows.append((T, cert, t0, t32))
        fixed = [max(0.0, t32 - 32 * (t0 - t32) / (T - 32)) for T, cert, t0, t32 in rows if T > 32]
        fmed = st.median(fixed) if fixed else 0.0

        def cost(row, c):
            T, cert, t0, t32 = row
            if T == 0:
                return (t0 + t32) / 2
            if T <= 32:
                t = (t0 + t32) / 2
                f = min(fmed, t)
                return t if (c == 0 or c >= T) else f + (t - f) * c / T
            p = (t0 - t32) / (T - 32)
            f = max(0.0, t32 - 32 * p)
            if c == 0 or c >= T:
                return t0
            return t32 + p * (c - 32) if c > 32 else f + (t32 - f) * c / 32

        off, on32, on0 = (s1[(wl, mode + a)] for a in ("-off", "-on32", "-on0"))
        n32 = sum(1 for r in rows if r[1] and r[0] <= 32)
        nall = sum(1 for r in rows if r[1])
        k32, k0 = sum(cost(r, 32) for r in rows), sum(cost(r, 0) for r in rows)
        g32, g0 = (off - on32) + k32, (off - on0) + k0
        print(f"== {wl} {mode}: {len(rows)} calls; S1 off {off*1e3:.1f} ms, cap 32 {on32*1e3:.1f}, none {on0*1e3:.1f}; "
              f"gross engine time saved at 32: {g32*1e3:.1f} ms over {n32} certified ({g32/n32*1e6:.0f} us each); "
              f"the {nall-n32} certified only above 32: {(g0-g32)*1e3:.1f} ms"
              + (f" ({(g0-g32)/(nall-n32)*1e6:.0f} us each)" if nall > n32 else "") + f"; median fixed part {fmed*1e6:.0f} us")
        print("cap certified cost_ms cost_certified_ms cost_fall_ms saved_ms net_ms net_%_of_off")
        for c in CAPS:
            n = sum(1 for r in rows if r[1] and (c == 0 or r[0] <= c))
            kc = sum(cost(r, c) for r in rows if r[1] and (c == 0 or r[0] <= c))
            kf = sum(cost(r, c) for r in rows if not (r[1] and (c == 0 or r[0] <= c)))
            saved = g32 * n / n32 if n <= n32 else g32 + (g0 - g32) * (n - n32) / (nall - n32)
            net = kc + kf - saved
            print(f"{c or 'none':>4} {n:5d} {1e3*(kc+kf):8.1f} {1e3*kc:8.1f} {1e3*kf:8.1f} {1e3*saved:8.1f} {1e3*net:+8.1f} {100*net/off:+6.1f}")
        # what the fall-through calls are, by the points they try uncapped
        fall = [r for r in rows if not (r[1] and r[0] <= 32)]
        b = {}
        for T, cert, t0, t32 in fall:
            k = "0" if T == 0 else "1-8" if T <= 8 else "9-32" if T <= 32 else "33+ certified later" if cert else "33+ never"
            x = b.setdefault(k, [0, 0.0]); x[0] += 1; x[1] += t32
        print("fall-through at cap 32 by uncapped points:", {k: (v[0], round(v[1] * 1e3, 1)) for k, v in sorted(b.items())})
