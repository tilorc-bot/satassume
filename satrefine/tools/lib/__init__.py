"""Offline: what satrefine's tools share (``satrefine.tools`` is never imported by refine).

* :mod:`.select`: the handler package and ``ask`` backend a tool runs under (and
  the re-exec that makes a tool's own ``--handlers``/``--backend`` take effect
  under ``python -m``);
* :mod:`.assumptions`: the predicate vocabulary with numeric definitions,
  samplers of values that satisfy it, and the relation deciders;
* :mod:`.grammar`: the random expression grammars and the per-case streams
  (scalar and extended family) of the fuzzer and the differential;
* :mod:`.points`: sample points that satisfy a case's assumptions, with edge
  and branch-cut points and infinities;
* :mod:`.numeric`: numeric values, comparison, and SymPy's conventions at
  infinity;
* :mod:`.matrices`: the matrix family (generation, explicit sample matrices,
  values, comparison, per-row coverage);
* :mod:`.battery`: the ``battery_v3`` battery: loading and classifying a case;
* :mod:`.sizes`: code lines and rows (the scoreboard's size lines);
* :mod:`.workers`: subprocess workers, per-case alarms, a forked task pool,
  the ``srepr`` round trip of worker results.
"""
