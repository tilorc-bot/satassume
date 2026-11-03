# HANDOFF sa-bb-1 (10:10Z)

Task: brief in the architect's launch message (REPORT-bb.md: B&B exhaustion table, designs, recommendation).

Scratch: /tmp/claude-1000/-home-tilo-dev-satassume/f1d7341c-bd17-441e-9a56-dcc729cb3820/scratchpad/bb/
- exh_child.py + drive.sh: per-exhaustion dump (out-base/*.jsonl; answers identical to base on fuzz).
- truth.py (z3 in zenv/, offline only): ground truth -> out-base/*.truth.jsonl.
- proto.py: rebuild each dump as a standalone LRATheory; lattice test; derived-integral slacks.
- guard_child.py: static guard on the lra-share switch-ON tree (tree-4f9d931/).

Findings so far:
- Exhaustions per pass: stream 50 (49 queries, 33 distinct problems), battery 48, fuzz 424242 277, ho-fuzz 221.
- ALL are LP-unbounded in some integrality var; 20000 nodes still exhaust (stream 49/50).
  Design (a) (no budget when bounded) covers 0.
- stream: 27 unsat by lattice (negated integrality form in Z-affine span of positive ones,
  pinned vars substituted) = exactly z3 unsat+unknown; 23 feasible (z3 sat), B&B descends
  forever (strict bound on a derived-integral slack a-b>0, DFS '<=' side first).
  Derived-integral slacks branched first: all 23 decided in 2-4 nodes. battery: 24 + 24 same.
- fuzz: lattice 172/277, 159/221; derived-first decides ~17 more; 37/27 remain; pi cases 46/28 skipped.
- Static guard (share only LRA sessions with no integrality atoms): 0 of 612 (stream) / 678 (battery)
  theory hits kept. Useless.
- (b) refuted by argument: learnt lemmas prune assignments whose check would exhaust.
Done: REPORT-bb.md written (10:20Z). No build (no cheap design makes the argument hold).
