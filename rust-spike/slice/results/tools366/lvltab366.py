"""lvltab366.py OUT.jsonl... (sa-port-366): one line per pass from lvl366.py's OUT.lvl.jsonl joined by position with
diff359.py's OUT.jsonl: queries, conversions, the walkers' level calls, calls that raised, queries holding a raise
(want 0), queries whose conversion first filled domain._UNDEFINED_KEYS, kept conversions by reason, conversions whose
`raised` list is non-empty, and whether the two files' conversion counts agree."""
import collections, json, sys
for path in sys.argv[1:]:
    rows = [json.loads(x) for x in open(path)]
    lv = [json.loads(x) for x in open(path[:-6] + ".lvl.jsonl")]
    tot, lv = lv[-1], lv[:-1]
    qs = [r for r in rows if "q" in r]
    i = qraise = qinit = craised = 0
    kept = collections.Counter()
    for r in qs:
        part = lv[i:i + len(r["cv"])]
        i += len(r["cv"])
        qraise += any(x[1] for x in part)
        qinit += any(x[2] for x in part)
        for c in r["cv"]:
            if c[0] == "kept":
                kept[c[1]] += 1
            elif c[2]:
                craised += 1
    name = path.rsplit("/", 1)[-1][:-6]
    print(name, "present", tot["present"], "queries", len(qs), "conversions", tot["conversions"], "joined", i == len(lv),
          "level-calls", tot["calls"], "outside-a-conversion", tot["outside"], "calls-raised", tot["raised"],
          "queries-with-a-raise", qraise, "queries-filling-UNDEFINED_KEYS", qinit, "conv-raised-nonempty", craised,
          "kept", dict(sorted(kept.items())), "plant", tot["plant"], "digest", rows[-1].get("digest"))
