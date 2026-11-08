"""A workload for the LRA certificate's pi reading (adapters step, part C2), as `live.py cert`.

Built from the code reached, not from any eval set: `LRATheory._branch` (lra.py :930-960) skips an integer split when
the variable's value exceeds the certificate's `Y`, and `Y = (nonbasic + 1) * had * (X + 1) * 2**16` with `X` the
largest atom bound's `_magnitude` of its `pi_laurent` (lra_cert.py :145-158; on Rust lra_cert.rs `laurent`, which calls
constfield.rs `pi_laurent_elem`). Dev and fuzz bound integers only by small constants, so `Y` is far above every value
they split at, and a wrong Laurent reading (e.g. the `cf-laurent-rational` plant: pi terms dropped) moves no answer there.

Here an integer variable sits above a pi bound with a large pi coefficient and a small rational part. Where one
variable is bounded alone, `assert_lit`'s rounded integer bounds decide it with no split, so `Y` isn't read; with the
two-term form `t + y` the infeasible side needs a split at a value of about `c * pi`. With the right reading `Y` is above
it; with the pi terms dropped `X` is the rational part, `Y` falls below `c * pi` for `c = 10**8`, the split counts as
running out and the answer is None where Python's is True (queries 53 and 59, measured on e12e622 with the plant: 2
answers and 34 compared states differ, Rust without it MATCHes). The other coefficients are controls.

`python cert_wl.py` prints each query's answer on the default backend.
"""
from sympy import Q, Rational, Symbol, pi, symbols

x, y = symbols("x y")
n = Symbol("n", integer=True)
H = Rational(1, 2)


def queries():
    out = [(Q.zero(x), Q.ge(x, -pi / 2))]             # test_term_live.py's CERT query
    for c in (10, 1000, 10**5, 10**6, 10**8):
        for t, base in ((x, Q.integer(x)), (n, True)):
            lo = Q.ge(t, c * pi) & base
            out += [(Q.ge(t, c * pi + H), lo),         # no integer in [c pi, c pi + 1/2): True
                    (Q.gt(t, c * pi + H), lo),
                    (Q.lt(t, c * pi + H), lo),         # False
                    (Q.le(t, -c * pi - H), Q.le(t, -c * pi) & base),   # the negative side: True
                    (Q.ge(t + y, c * pi + H), lo & Q.ge(y, 0)),       # a two-term form
                    (Q.ge(t, c * pi + 1), lo)]          # not definite: an integer may sit there (None either way)
    return out


if __name__ == "__main__":
    from sympy import ask
    for i, (p, a) in enumerate(queries()):
        print(i, p, "|", a, "->", ask(p, a))
