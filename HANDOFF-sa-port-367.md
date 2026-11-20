# HANDOFF sa-port-367: computed-against-read audit (issue 323), measurement only

Branch audit/reads (clone /home/tilo/dev/sa-port-7, worktree ~/sa-rust-ids-work/sa-port-367/wt), from rust-slice
966268c. No source change; only rust-spike/slice/results/tools367/ and results/reads-audit.md are committed.

## What exists

- **Profile, both paths, 966268c**: orion ~/sa-rust-ids-work/sa-port-367/s1/p1 (time/time.jsonl, run/, ana-WL-py.json,
  ana-WL-rust.json), from pareto1 under one quiet lease (lease-p1.log; end marker gop1-end.txt). Launcher
  tools367/goprof367.sh 966268c p1 -> onlease367p.sh -> pys367.sh (arms `default`: no SLICE_ switch; `rust-nat`).
  x86-64 .so 8b8041d3fe6223c2 (sa-port-359's build of 00535462, crate equal to 966268c's, checked by goprof367.sh).
  `run/WL-py-mods.json` (mods367.py): the slice modules loaded and run on the default path.
- **Counts, both paths**: orion ~/sa-rust-ids-work/sa-port-367/cntR/WL-{default,rust-nat}.json (the cells the tables
  use: default with every satassume module, rust-nat with the seven marked files only) and cntB/WL-{default,rust-nat}.json
  (every module on both paths; its rust-nat dev and fuzz cells change the answers and are NOT used) (cnt367.py through
  gocnt367.sh; orion .so 4d8921d9c510e99f built from 966268c; end marker cntB/all-end.txt). File list: filelist.txt
  (every satassume module and every slice module that is not a test file).
- **Tables**: `python3 tools367/tab367.py ~/sa-rust-ids-work/sa-port-367/s1/p1 ~/sa-rust-ids-work/sa-port-367/cntR
  default|rust-nat` -> tools367/tab-default.txt, tab-rust-nat.txt.

## file:line map of the counters (tools367/cnt367.py)

- :131 `on_start` (PY_START): calls per code object, call site = nearest Python frame's (code, lasti).
- :143 `on_return` (PY_RETURN) with :119 `next_is_pop`: returned value dropped at the call site.
- :157 `Field`, the counting data descriptor: :169 `__get__` (reads, kinds use/mut/aug, epochs_read), :209 `__set__`
  (writes, trivial, epochs, writers).
- :245 `attr_kinds` and :290 `read_kind`: the kind of a read from the reader's source position (ast).
- :304 `class_fields` (which fields a class stores, by ast), :338 `install_fields` (descriptors put on the classes).
- :395 the counted loop (ON[0] True only inside it).
- :447 the plants: per file a planted function called twice (2 calls, 1 dropped); per field one planted LOAD_ATTR read
  and one operator.attrgetter read (each +1 read, both `use`); a planted class for the read kinds. `plant.failed`
  must be empty in every WL-PATH.line.

## Limits of the counters (say them in every report)

- Entries of a dict, list or set held in a field are not counted one by one: a column that is filled and of which only
  some entries are read shows as `read`. The readers' lines are listed, so it can be read off by hand.
- A value returned to Rust and stored in a Rust table is `read` here (the call's value is taken); whether Rust reads
  it is a crate question. Known cases, not re-measured: the formula skeleton (removed by sa-port-363/365), the
  per-term construction level (sa-port-364, removal queued as sa-port-366).
- A returned tuple of which the caller uses only some items shows as `read`.
- Module-level memo dicts are not wrapped (a Rust reader holds the dict object); memo misses and lookups are the calls
  of the compute function and of its caller.

## Left to do

See the end of results/reads-audit.md ("What is not done").
