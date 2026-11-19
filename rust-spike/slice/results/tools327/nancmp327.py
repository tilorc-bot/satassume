"""nancmp327.py PROF.json... (sa-port-327): from prof292.py's pooled inclusive counts, the rows of the _may_be_nan step:
Python's templates/__init__.py frames, the native may_be_nan, and term_row (their caller), as samples and share of the
in-loop samples, with the pooled wall per sample turned into ms (share x median run wall)."""
import json, re, statistics as st, sys
ROWS = [("py templates/__init__.py (file)", re.compile(r"^pyfile:knowledge/templates/__init__\.py$")),
        ("py _may_be_nan", re.compile(r"^py:knowledge/templates/__init__\.py:_may_be_nan$")),
        ("rs may_be_nan (any)", re.compile(r"^rs:.*may_be_nan")),
        ("rs Walk::term_row (entry)", re.compile(r"^rs:<term::walk::Walk>::__pymethod_term_row__$")),
        ("py convert.py:rust_walk.<lambda>", re.compile(r"^py:.*convert\.py:rust_walk\.<locals>\.<lambda>$|^py:convert\.py:rust_walk\.<lambda>$")),
        ("py term_live.py:_convert", re.compile(r"^py:.*term_live\.py:_convert$"))]
for f in sys.argv[1:]:
    d = json.load(open(f)); N = d["N"]; w = st.median(r[2] for r in d["runs"])
    print(f"{f}: in-loop samples {N}, runs {len(d['runs'])}" + (f", median wall {w:.3f} s" if w else ""))
    for name, p in ROWS:
        ks = [k for k in d["incl"] if p.search(k)]
        n = max((d["incl"][k] for k in ks), default=0) if name.startswith("rs may") else sum(d["incl"][k] for k in ks)
        print(f"   {name:34} {n:6} = {100*n/N:5.2f}%" + (f" = {1000*w*n/N:6.1f} ms" if w else "") + (f"   [{'; '.join(k + ' ' + str(d['incl'][k]) for k in ks)[:160]}]" if name.startswith("rs may") else ""))
