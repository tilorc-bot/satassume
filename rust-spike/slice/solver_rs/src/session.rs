//! `Session`'s variable and clause surface and `VarTable`, over a session's own node ids (component 5, step 5a). Python's
//! `Session` shell (`session_live.py`), `Relations` and the templates call this through `SessionCore`. Each object becomes a
//! node id in `nids`, a Python dict, so two objects share an id exactly when Python's own `base` and `custom` dicts would
//! have joined them. No borrow is held across a callback: `node` runs templates, and they come back in.
use std::cell::{Cell, RefCell};
use std::collections::HashMap;
use std::rc::Rc;

use pyo3::exceptions::{PyException, PyKeyError, PyRecursionError, PyTypeError, PyValueError};
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyList, PySet, PyTuple};

use crate::compile::{self, block_lits, Cx, Def, Kind, Need, F, R};
use crate::formula_py::PyP;

const NAMES: [&str; 571] = [
    "py:var", "py:dvar", "py:node", "py:compile", "py:literal", "py:table", "rs:visit", "rs:add_clause", "rs:ensure_vars",
    "rs:def_implications", "rs:neg_shared", "join", "rs:emit_callback", "refuse:depth", "refuse:convert", "refuse:object", "second:visit", "custom:own",
    "link:hit", "link:resolved", "link:none", "link:no_table", "link:second", "link:no_node",
    "rel:closed_extended_real", "rel:order_sides", "rel:order_infinite", "rel:trichotomy", "rel:mention_number", "rel:link_integer",
    "rel:var", "rel:plant_fired",
    "rel:fresh", "rel:interpret", "rel:guard", "rel:bound", "rel:link", "rel:selectors_of", "rel:eq_infinity",
    "link:calls", "link:cross_current", "link:cross_hash", "link:cross_term_id",
    "rel:add_role", "rel:apply_role", "rel:tsource", "rel:tvar", "rel:share_guard", "rel:congruent", "rel:engage_transfer",
    "rel:transfer_terms", "rel:sync_transfer", "rel:xswitch", "rel:congruence_pairs",
    "ses:ensure", "ses:discover", "ses:escalate", "ses:incomplete",
    "ses:want_of", "ses:split", "ses:emit_pattern", "ses:flush", "ses:compile", "ses:compile_pending",
    "ses:compile_patterns", "ses:custom", "ses:visit", "ses:core_visit", "ses:link",
    "ses:query_lit", "ses:prepare_query", "ses:emit", "ses:query_literal", "ses:query_all", "ses:literal_of", "ses:relations", "ses:ensure_atoms", "ses:ensure_twins",
    "rel:init", "rel:enqueue", "rel:note_formula", "rel:process", "rel:link_later", "rel:wants_transfer", "rel:share",
    "rel:cb_note_sides", "rel:cb_eq_links", "rel:cb_atom_selector", "rel:cb_atom_var", "rel:cb_constant_term",
    "rel:adapter", "rel:atom_selector", "rel:atom_var", "rel:note_sides", "rel:eq_links", "rel:cb_termwise",
    "rel:own_term", "rel:constant_term", "rel:number_basis", "rel:sympy_atom", "rel:zero_args", "rel:under_of",
    "rel:zero_twins", "rel:glue_atoms", "rel:guarded_adapters", "rel:terms_of", "rel:link_objects", "rel:closed_units",
    "rel:with_closed_units", "rel:default_specs", "rel:relational_name", "rel:cb_is_many", "rel:cb_sympy_q", "rel:cb_under_apps",
    "rel:cb_zero_twin", "rel:cb_structural_subterms", "rel:cb_relation_atom", "rel:cb_adapter_read", "rel:cb_closed_sign", "rel:cb_units",
    "rel:cb_clause_templates", "rel:py_is_number", "rel:cb_spec_read",
    "scope:new", "scope:linked_terms", "scope:scope_of_atoms", "scope:theory_scope", "scope:custom_pred", "scope:extension_atoms",
    "scope:cb_atoms_of", "scope:cb_affine_pair", "scope:cb_transfer_wanted", "scope:cb_facts_for",
    "ses:init", "ses:assume_formula", "ses:link_set", "ses:assumption_lits", "ses:set_glue", "ses:group_sel", "ses:glue_of",
    "ad:lra_new", "ad:euf_new", "ad:cb_factory", "ad:cb_theory_new", "ad:cb_memoized", "ad:cb_constant_bounds", "ad:cb_parse", "ad:cb_structural", "ad:cb_interned", "ad:lra_register", "ad:euf_register",
    "ad:negated_new", "ad:integral_new", "ad:eqatom_new", "ad:cb_py_payload",
    "cf:pi_laurent",
    "bud:union", "bud:within_budget", "bud:over_budget", "bud:note_budget", "bud:cb_query_cone", "bud:cb_cone_info", "bud:cb_struct",
    "bud:cb_global", "bud:py_fallback",
    "bud:union_cone_none", "bud:union_over", "bud:union_partial", "bud:within_partial", "bud:within_false",
    "cf:elem_new", "cf:elem_py_read", "cf:elem_eq", "cf:elem_hash", "cf:elem_repr", "lra:memo_hit", "lra:memo_miss",
    "cf:elem_sign", "rel:elem_sign",
    "rv:relevant", "rv:split_new", "rv:keys_rel", "rv:keys_miss", "rv:const_free_miss", "rv:vocab_blocks", "rv:part_consistent", "rv:consistent",
    "rv:consistent_caught", "rv:cb_formula", "rv:cb_verdict", "rv:cb_theory_scope", "rv:cb_category", "rv:cb_ext", "rv:cb_memo",
    "rv:py_deep", "rv:br_verdict", "rv:br_glue", "rv:br_parts", "rv:br_unsupported", "rv:sympy_and",
    // 200-229 reserved for the 6g stack (sa-port-172); 230-235 step 5c9a (memos.rs).
    "reserved:200", "reserved:201", "reserved:202", "reserved:203", "reserved:204", "reserved:205", "reserved:206", "reserved:207", "reserved:208", "reserved:209", "reserved:210", "reserved:211", "reserved:212", "reserved:213", "reserved:214", "reserved:215", "reserved:216", "reserved:217", "reserved:218", "reserved:219", "reserved:220", "reserved:221", "reserved:222", "reserved:223", "reserved:224", "reserved:225", "reserved:226", "reserved:227", "reserved:228", "reserved:229",
    "memo:native_clear", "memo:native_items", "memo:restamp", "memo:setting", "memo:setting_prop", "memo:spec_full",
    "reserved:236", "reserved:237", "reserved:238", "reserved:239",
    "pm:neigh", "pm:cb_rules", "pm:full", "pm:key_eq", "pm:key_hash",
    "reserved:245", "reserved:246", "reserved:247", "reserved:248", "reserved:249",
    "em:py_kids", "em:py_qcones", "em:py_glue", "em:py_xbasis", "em:py_splits", "em:slot_set", "em:foreign", "em:full",
    "em:key_eq", "bud:query_cone",
    "fc:py_facts", "fc:py_get", "fc:py_put", "fc:py_sync", "fc:view", "fc:clear", "fc:full", "fc:key_eq", "fc:rollback",
    "fc:new", "fc:py_key",
    "em:py_failed", "em:py_verdict", "em:py_ctxs", "ctx:context_session", "ctx:build_memoized", "ctx:build_context",
    "ctx:verdict", "ctx:complete_check", "ctx:cb_check_version", "ctx:cb_fresh_session", "ctx:cb_helpers", "ctx:py_stats",
    "ctx:caught", "ctx:cb_patched", "ctx:failed_hit", "ctx:verdict_hit", "ctx:fallback",
    // step 5c10c (budget.rs cone rows, engmemo.rs slots 8-9)
    "em:py_cones", "em:py_constructing", "bud:struct", "bud:cone_info", "bud:drop_cones", "bud:cb_templates", "bud:cb_ext",
    "bud:struct_wide", "bud:kids_hit", "bud:cones_hit",
    "bud:py_struct", "bud:py_cone_info", "bud:py_drop_cones",
    "ent:is", "ent:is_many", "ent:decide", "ent:put_result", "ent:is_custom", "ent:ask", "ent:ask_inner", "ent:check_version", "ent:settings_changed", "ent:drop_set_memos", "ent:fresh_session", "ent:cb_noncomm", "ent:cb_gave_up", "ent:cb_scope", "ent:cb_basis", "st:rec_cache_hit", "st:rec_relevant", "st:rec_consistency_check", "st:rec_scope_miss", "st:rec_clear_flag", "st:rec_keep_flag", "st:py_read", "st:slot_set", "st:flag_set", "st:foreign", "st:mark",
    // state step, part 1 (adapters.rs LraQuery): lra_live `_memoized` on the Rust adapter
    "ad:lra_native", "ad:lra_hit", "ad:lra_relation", "ad:lra_term_id_py", "ad:lra_scaffold", "ad:cbm_noquery", "ad:cbm_noid",
    "ad:cbm_check", "ad:cbm_patched", "ad:cbm_off",
    // state step, part 2 (i): `integer_form` of a side that isn't an `Expr` answers None natively (lra_adapter.integer_form :400)
    "ad:lra_not_expr",
    // state step, part 2 (ii): the solver and the transfer engagement held in the core (`Session.solver`/`Session.xfer`,
    // `Relations.xfer`/`xfer_sel`/`_xadapter`), read natively by Rust and through read-only views by Python
    "xf:solver_core", "xf:engage_core", "xf:read_core", "xf:session_view", "xf:rel_view", "xf:record",
    // state step, part 2 (iii): `glue_objects` of a relation atom other than a two-sided `eq`, natively (budget.rs's cone kids)
    "gl:plain",
    // 345-419 reserved (state part 2's numbering runs to 369; 6i(a)'s 370-419 are Common counts)
    "reserved:345", "reserved:346",
    // state step, part 2 (iii)(b): Relations' scalar cursors held in the core (`_xtcur`.. `_xsides_n`)
    "rc:core", "rc:view", "rc:record", "rk:intern:input", "rk:intern:engine", "rk:term", "rk:outlive", "rk:migrate", "rs:core", "rs:view", "rs:record", "rk:dict:hit", "rk:twin", "reserved:360", "reserved:361", "reserved:362", "reserved:363", "reserved:364", "reserved:365", "reserved:366", "reserved:367", "reserved:368", "reserved:369", "reserved:370", "reserved:371", "reserved:372", "reserved:373", "reserved:374", "reserved:375", "reserved:376", "reserved:377", "reserved:378", "reserved:379", "reserved:380", "reserved:381", "reserved:382", "reserved:383", "reserved:384", "reserved:385", "reserved:386", "reserved:387", "reserved:388", "reserved:389", "reserved:390", "reserved:391", "reserved:392", "reserved:393", "reserved:394", "reserved:395", "reserved:396", "reserved:397", "reserved:398", "reserved:399", "reserved:400", "reserved:401", "reserved:402", "reserved:403", "reserved:404", "reserved:405", "reserved:406", "reserved:407", "reserved:408", "reserved:409", "reserved:410", "reserved:411", "reserved:412", "reserved:413", "reserved:414", "reserved:415", "reserved:416", "reserved:417", "reserved:418", "reserved:419",
    // S2 (block.rs rule_tables): the engine's block from the generated tables, another block built in Rust, a failed check
    "rb:generated", "rb:built", "rb:check_error",
    "reserved:423", "reserved:424", "reserved:425", "reserved:426", "reserved:427", "reserved:428", "reserved:429", "reserved:430", "reserved:431", "reserved:432", "reserved:433", "reserved:434", "reserved:435", "reserved:436", "reserved:437", "reserved:438", "reserved:439", "reserved:440", "reserved:441", "reserved:442", "reserved:443", "reserved:444", "reserved:445", "reserved:446", "reserved:447", "reserved:448", "reserved:449", "reserved:450", "reserved:451", "reserved:452", "reserved:453", "reserved:454", "reserved:455", "reserved:456", "reserved:457", "reserved:458", "reserved:459", "reserved:460", "reserved:461", "reserved:462", "reserved:463", "reserved:464", "reserved:465", "reserved:466", "reserved:467", "reserved:468", "reserved:469", "reserved:470", "reserved:471", "reserved:472", "reserved:473", "reserved:474", "reserved:475", "reserved:476", "reserved:477", "reserved:478", "reserved:479", "reserved:480", "reserved:481", "reserved:482", "reserved:483", "reserved:484", "reserved:485", "reserved:486", "reserved:487", "reserved:488", "reserved:489", "reserved:490", "reserved:491", "reserved:492", "reserved:493", "reserved:494", "reserved:495", "reserved:496", "reserved:497", "reserved:498", "reserved:499", "reserved:500", "reserved:501", "reserved:502", "reserved:503", "reserved:504", "reserved:505", "reserved:506", "reserved:507", "reserved:508", "reserved:509", "reserved:510", "reserved:511", "reserved:512", "reserved:513", "reserved:514", "reserved:515", "reserved:516", "reserved:517", "reserved:518", "reserved:519",
    // state step part 2 (iii)(b), rest: Relations' dicts in the core (relkeys.rs RelDictView), 520-522
    "rd:core", "rd:view", "rd:record",
    // state step part 2 (iii)(b), rest: Relations' lists in the core (relkeys.rs RelListView), 523-525
    "rl:core", "rl:view", "rl:record",
    // 526-554 reserved (state part 3's counters start at 550; 550-554 are rows_probe.py's, Python-side)
    "reserved:526", "reserved:527", "reserved:528", "reserved:529", "reserved:530", "reserved:531", "reserved:532", "reserved:533", "reserved:534", "reserved:535", "reserved:536", "reserved:537", "reserved:538", "reserved:539", "reserved:540", "reserved:541", "reserved:542", "reserved:543", "reserved:544", "reserved:545", "reserved:546", "reserved:547", "reserved:548", "reserved:549", "reserved:550", "reserved:551", "reserved:552", "reserved:553", "reserved:554",
    // state part 3 (theory_flags.rs): engine.py _gave_up/_exhausted in Rust, 555-558
    "th:gave_up", "th:exhausted", "th:py_flag", "th:py_helper",
    // state part 3, sub-part 5 (the session/solver boundary): a session with no core read by attribute; `_interpret`/`_link`/
    // `_share_guard`/`_visit` called directly, or by name where a test or SLICE_*=py replaced the method; the session's scalars
    // in the core (native use, Python's view, Python's record method), 559-564
    "sb:attr", "sb:fwd_direct", "sb:fwd_named", "sb:scalar_core", "sb:scalar_view", "sb:scalar_record",
    // ... the session's containers in the core (ses_cont.rs): a native use, Python's view, Python's record method, 565-567
    "sc:core", "sc:view", "sc:record",
    // a session dict's own keys (ses_cont.rs SesDict): Python's `hash()` and `==` on a key, each a call into Python, 568-569
    "sc:key_hash", "sc:key_eq",
    // `core_of` through the `Session.table` property (a Python frame, session_live `_table_get`): a session without `_core`, 570
    "sb:core_prop",
];
const VAR: usize = 0;
const DVAR: usize = 1;
const NODE: usize = 2;
const COMPILE: usize = 3;
const LITERAL: usize = 4;
const TABLE: usize = 5;
const VISIT: usize = 6;
const ADD_CLAUSE: usize = 7;
const ENSURE: usize = 8;
const IMPL: usize = 9;
const NEG: usize = 10;
const JOIN: usize = 11;
const EMIT_CB: usize = 12;
const REFUSE_DEPTH: usize = 13;
const REFUSE_CONVERT: usize = 14;
const REFUSE_OBJECT: usize = 15;
const SECOND_VISIT: usize = 16;
const CUSTOM_OWN: usize = 17;
pub(crate) const LINK_HIT: usize = 18;
pub(crate) const LINK_RESOLVED: usize = 19;
pub(crate) const LINK_NONE: usize = 20;
pub(crate) const LINK_NO_TABLE: usize = 21;
pub(crate) const LINK_SECOND: usize = 22;
pub(crate) const LINK_NO_NODE: usize = 23;
pub(crate) const REL_CLOSED: usize = 24;
pub(crate) const REL_ORDER_SIDES: usize = 25;
pub(crate) const REL_ORDER_INFINITE: usize = 26;
pub(crate) const REL_TRICHOTOMY: usize = 27;
pub(crate) const REL_MENTION: usize = 28;
pub(crate) const REL_LINK_INTEGER: usize = 29;
const REL_VAR: usize = 30;
pub(crate) const REL_PLANT: usize = 31;
pub(crate) const REL_FRESH: usize = 32;
pub(crate) const REL_INTERPRET: usize = 33;
pub(crate) const REL_GUARD: usize = 34;
pub(crate) const REL_BOUND: usize = 35;
pub(crate) const REL_LINK: usize = 36;
pub(crate) const REL_SELECTORS: usize = 37;
pub(crate) const REL_EQ_INFINITY: usize = 38;
pub(crate) const LINK_CALLS: usize = 39;
pub(crate) const LINK_CROSS_CURRENT: usize = 40;
pub(crate) const LINK_CROSS_HASH: usize = 41;
pub(crate) const LINK_CROSS_TERM_ID: usize = 42;
pub(crate) const REL_ADD_ROLE: usize = 43;
pub(crate) const REL_APPLY_ROLE: usize = 44;
pub(crate) const REL_TSOURCE: usize = 45;
pub(crate) const REL_TVAR: usize = 46;
pub(crate) const REL_SHARE_GUARD: usize = 47;
pub(crate) const REL_CONGRUENT: usize = 48;
pub(crate) const REL_ENGAGE: usize = 49;
pub(crate) const REL_TRANSFER_TERMS: usize = 50;
pub(crate) const REL_SYNC_TRANSFER: usize = 51;
pub(crate) const REL_XSWITCH: usize = 52;
pub(crate) const REL_CONGRUENCE_PAIRS: usize = 53;
pub(crate) const SES_ENSURE: usize = 54;
pub(crate) const SES_DISCOVER: usize = 55;
pub(crate) const SES_ESCALATE: usize = 56;
pub(crate) const SES_INCOMPLETE: usize = 57;
pub(crate) const SES_WANT_OF: usize = 58;
pub(crate) const SES_SPLIT: usize = 59;
pub(crate) const SES_EMIT_PATTERN: usize = 60;
pub(crate) const SES_FLUSH: usize = 61;
pub(crate) const SES_COMPILE: usize = 62;
pub(crate) const SES_COMPILE_PENDING: usize = 63;
pub(crate) const SES_COMPILE_PATTERNS: usize = 64;
pub(crate) const SES_CUSTOM: usize = 65;
pub(crate) const SES_VISIT: usize = 66;
pub(crate) const SES_CORE_VISIT: usize = 67;
pub(crate) const SES_LINK: usize = 68;
pub(crate) const SES_QUERY_LIT: usize = 69;
pub(crate) const SES_PREPARE_QUERY: usize = 70;
pub(crate) const SES_EMIT: usize = 71;
pub(crate) const SES_QUERY_LITERAL: usize = 72;
pub(crate) const SES_QUERY_ALL: usize = 73;
pub(crate) const SES_LITERAL_OF: usize = 74;
pub(crate) const SES_RELATIONS: usize = 75;
pub(crate) const SES_ENSURE_ATOMS: usize = 76;
pub(crate) const SES_ENSURE_TWINS: usize = 77;
/// Step 5c4: the rest of `Relations`, and the callbacks it makes to what stays Python.
pub(crate) const REL_INIT: usize = 78;
pub(crate) const REL_ENQUEUE: usize = 79;
pub(crate) const REL_NOTE_FORMULA: usize = 80;
pub(crate) const REL_PROCESS: usize = 81;
pub(crate) const REL_LINK_LATER: usize = 82;
pub(crate) const REL_WANTS_TRANSFER: usize = 83;
pub(crate) const REL_SHARE: usize = 84;
pub(crate) const REL_CB_NOTE_SIDES: usize = 85;
pub(crate) const REL_CB_EQ_LINKS: usize = 86;
pub(crate) const REL_CB_ATOM_SELECTOR: usize = 87;
pub(crate) const REL_CB_ATOM_VAR: usize = 88;
pub(crate) const REL_CB_CONSTANT_TERM: usize = 89;
/// Step 5c5: the five methods 5c4 left, and `_eq_links`' callback to `_termwise`.
pub(crate) const REL_ADAPTER: usize = 90;
pub(crate) const REL_ATOM_SELECTOR: usize = 91;
pub(crate) const REL_ATOM_VAR: usize = 92;
pub(crate) const REL_NOTE_SIDES: usize = 93;
pub(crate) const REL_EQ_LINKS: usize = 94;
pub(crate) const REL_CB_TERMWISE: usize = 95;
/// Step 5c5, second part: relations.py's module functions, and their callbacks to what stays Python.
pub(crate) const REL_OWN_TERM: usize = 96;
pub(crate) const REL_CONSTANT_TERM: usize = 97;
pub(crate) const REL_NUMBER_BASIS: usize = 98;
pub(crate) const REL_SYMPY_ATOM: usize = 99;
pub(crate) const REL_ZERO_ARGS: usize = 100;
pub(crate) const REL_UNDER_OF: usize = 101;
pub(crate) const REL_ZERO_TWINS: usize = 102;
pub(crate) const REL_GLUE_ATOMS: usize = 103;
pub(crate) const REL_GUARDED_ADAPTERS: usize = 104;
pub(crate) const REL_TERMS_OF: usize = 105;
pub(crate) const REL_LINK_OBJECTS: usize = 106;
pub(crate) const REL_CLOSED_UNITS: usize = 107;
pub(crate) const REL_WITH_CLOSED_UNITS: usize = 108;
pub(crate) const REL_DEFAULT_SPECS: usize = 109;
pub(crate) const REL_RELATIONAL_NAME: usize = 110;
pub(crate) const REL_CB_IS_MANY: usize = 111;
pub(crate) const REL_CB_SYMPY_Q: usize = 112;
pub(crate) const REL_CB_UNDER_APPS: usize = 113;
pub(crate) const REL_CB_ZERO_TWIN: usize = 114;
pub(crate) const REL_CB_STRUCTURAL_SUBTERMS: usize = 115;
pub(crate) const REL_CB_RELATION_ATOM: usize = 116;
pub(crate) const REL_CB_ADAPTER_READ: usize = 117;
pub(crate) const REL_CB_CLOSED_SIGN: usize = 118;
pub(crate) const REL_CB_UNITS: usize = 119;
pub(crate) const REL_CB_CLAUSE_TEMPLATES: usize = 120;
pub(crate) const REL_PY_IS_NUMBER: usize = 121;
/// Adapters step: each `AdapterSpec` field read from Rust. Each spec is read once, the first time Rust sees it (`spec_row`).
pub(crate) const REL_CB_SPEC_READ: usize = 122;
/// Step scope's (`scope_core.rs`).
pub(crate) const SCOPE_NEW: usize = 123;
pub(crate) const SCOPE_LINKED_TERMS: usize = 124;
pub(crate) const SCOPE_OF_ATOMS: usize = 125;
pub(crate) const SCOPE_THEORY_SCOPE: usize = 126;
pub(crate) const SCOPE_CUSTOM_PRED: usize = 127;
pub(crate) const SCOPE_EXTENSION_ATOMS: usize = 128;
pub(crate) const SCOPE_CB_ATOMS_OF: usize = 129;
pub(crate) const SCOPE_CB_AFFINE_PAIR: usize = 130;
pub(crate) const SCOPE_CB_TRANSFER_WANTED: usize = 131;
pub(crate) const SCOPE_CB_FACTS_FOR: usize = 132;
/// Step 5c6: the rest of `Session` (`session_glue.rs`).
pub(crate) const SES_INIT: usize = 133;
pub(crate) const SES_ASSUME_FORMULA: usize = 134;
pub(crate) const SES_LINK_SET: usize = 135;
pub(crate) const SES_ASSUMPTION_LITS: usize = 136;
pub(crate) const SES_SET_GLUE: usize = 137;
pub(crate) const SES_GROUP_SEL: usize = 138;
pub(crate) const SES_GLUE_OF: usize = 139;
/// Adapters step, part B (adapters.rs): Rust adapters built, and the callbacks they still make into Python.
pub(crate) const AD_LRA_NEW: usize = 140;
pub(crate) const AD_EUF_NEW: usize = 141;
pub(crate) const AD_CB_FACTORY: usize = 142;
pub(crate) const AD_CB_THEORY_NEW: usize = 143;
pub(crate) const AD_CB_MEMOIZED: usize = 144;
pub(crate) const AD_CB_CONSTANT_BOUNDS: usize = 145;
pub(crate) const AD_CB_PARSE: usize = 146;
pub(crate) const AD_CB_STRUCTURAL: usize = 147;
pub(crate) const AD_CB_INTERNED: usize = 148;
pub(crate) const AD_LRA_REGISTER: usize = 149;
pub(crate) const AD_EUF_REGISTER: usize = 150;
/// Adapters step, part C (payloads.rs): Rust payloads built.
pub(crate) const AD_NEGATED_NEW: usize = 151;
pub(crate) const AD_INTEGRAL_NEW: usize = 152;
pub(crate) const AD_EQATOM_NEW: usize = 153;
/// Part C: a Python payload built for a theory that reads only Python's (Python's own LRATheory/EUFTheory).
pub(crate) const AD_CB_PY_PAYLOAD: usize = 154;
/// Part C2: `pi_laurent` of an Element bound, on Rust (it was a callback, lra_cert.rs:87).
pub(crate) const CF_PI_LAURENT: usize = 155;
/// Step 5c7 part 1: the budget's stateless rows (`budget.rs`), and the cone rows they call back.
pub(crate) const BUD_UNION: usize = 156;
pub(crate) const BUD_WITHIN_BUDGET: usize = 157;
pub(crate) const BUD_OVER_BUDGET: usize = 158;
pub(crate) const BUD_NOTE_BUDGET: usize = 159;
/// Retired by 5c9c (`_query_cone` runs in Rust, `bud:query_cone`); the name stays so counts keep their rows.
#[allow(dead_code)]
pub(crate) const BUD_CB_QUERY_CONE: usize = 160;
pub(crate) const BUD_CB_CONE_INFO: usize = 161;
pub(crate) const BUD_CB_STRUCT: usize = 162;
pub(crate) const BUD_CB_GLOBAL: usize = 163;
pub(crate) const BUD_PY_FALLBACK: usize = 164;
/// `budget.rs` branches, for the budget workload (`budget_wl.py`): `_union`'s over-budget cone, its overflow and its partial
/// overlap; `_within_budget`'s sum over the assumptions' new objects, and its False.
pub(crate) const BUD_UNION_CONE_NONE: usize = 165;
pub(crate) const BUD_UNION_OVER: usize = 166;
pub(crate) const BUD_UNION_PARTIAL: usize = 167;
pub(crate) const BUD_WITHIN_PARTIAL: usize = 168;
pub(crate) const BUD_WITHIN_FALSE: usize = 169;
/// Element._new step: a Rust `Element` pyclass made where `Element._new` built a Python one (constfield.rs `PyElem::of`).
pub(crate) const CF_ELEM_NEW: usize = 170;
/// A read of that pyclass only a Python Element answers (arithmetic, order, an attribute): the named callback.
pub(crate) const CF_ELEM_PY_READ: usize = 171;
/// Its `==`/`!=`/`bool` from Python, answered on Rust.
pub(crate) const CF_ELEM_EQ: usize = 172;
pub(crate) const CF_ELEM_HASH: usize = 173;
pub(crate) const CF_ELEM_REPR: usize = 174;
/// The term table's `lra_*` memo, holding Rust values (term/py.rs `lra_memo`).
pub(crate) const LRA_MEMO_HIT: usize = 175;
pub(crate) const LRA_MEMO_MISS: usize = 176;
/// Python's `constfield.sign` of the pyclass, answered on Rust (`Elem::sign`, as `Element.sign` on the Python backend).
pub(crate) const CF_ELEM_SIGN: usize = 177;
/// `_order_infinite`'s sign of a Rust Element coefficient, read on Rust (relations_core.rs; it was Python's `relations.sign`).
pub(crate) const REL_ELEM_SIGN: usize = 178;
pub(crate) const RV_RELEVANT: usize = 179;
pub(crate) const RV_SPLIT_NEW: usize = 180;
pub(crate) const RV_KEYS_REL: usize = 181;
pub(crate) const RV_KEYS_MISS: usize = 182;
pub(crate) const RV_CONST_FREE_MISS: usize = 183;
pub(crate) const RV_VOCAB_BLOCKS: usize = 184;
pub(crate) const RV_PART_CONSISTENT: usize = 185;
pub(crate) const RV_CONSISTENT: usize = 186;
pub(crate) const RV_CONSISTENT_CAUGHT: usize = 187;
pub(crate) const RV_CB_FORMULA: usize = 188;
pub(crate) const RV_CB_VERDICT: usize = 189;
pub(crate) const RV_CB_THEORY_SCOPE: usize = 190;
pub(crate) const RV_CB_CATEGORY: usize = 191;
pub(crate) const RV_CB_EXT: usize = 192;
pub(crate) const RV_CB_MEMO: usize = 193;
pub(crate) const RV_PY_DEEP: usize = 194;
pub(crate) const RV_BR_VERDICT: usize = 195;
pub(crate) const RV_BR_GLUE: usize = 196;
pub(crate) const RV_BR_PARTS: usize = 197;
pub(crate) const RV_BR_UNSUPPORTED: usize = 198;
pub(crate) const RV_SYMPY_AND: usize = 199;
/// Step 5c9a (memos.rs): a native table's view emptied (`PROCESS.clear()` and the like).
pub(crate) const MEMO_NATIVE_CLEAR: usize = 230;
/// A native table's entries converted for `items()`/`keys()` (tests and the inventory only).
pub(crate) const MEMO_NATIVE_ITEMS: usize = 231;
/// `Table.restamp` of `_KEYS`/`_CONST`, run in Rust (it was a callback into memos.py).
pub(crate) const MEMO_RESTAMP: usize = 232;
/// An `Engine` setting's field read by Rust: the crossing into the Python `Engine` (5c10's container), removed by 5c10.
pub(crate) const MEMO_SETTING: usize = 233;
/// A setting read through its property, on an `Engine` subclass.
pub(crate) const MEMO_SETTING_PROP: usize = 234;
/// A native table emptied at its bound.
pub(crate) const MEMO_FULL: usize = 235;
/// Step 5c9b (procmemo.rs): `neighbourhood` run in Rust.
pub(crate) const PM_NEIGH: usize = 240;
/// `neighbourhood`'s reads of `knowledge.rules` (`RULE_CLAUSES`, `BASIS_OF`), a counted callback.
pub(crate) const PM_CB_RULES: usize = 241;
/// A moved process memo (`_SPLIT`, `_CLOSED`, `_SYMPY_ATOMS`) emptied at its bound.
pub(crate) const PM_FULL: usize = 242;
/// A key's `==` run by a moved memo's lookup (not settled by identity): a callback when the key is a SymPy or Formula object.
pub(crate) const PM_KEY_EQ: usize = 243;
/// A `_CLOSED`/`_SYMPY_ATOMS` lookup hashing its Python key (SymPy's or `P`'s `__hash__`).
pub(crate) const PM_KEY_HASH: usize = 244;
/// Step 5c9c (engmemo.rs): a Python call into an engine memo's methods, per container (a crossing: `_struct`, `_drop_cones`,
/// `_drop_set_memos`, the registry, the tests).
pub(crate) const EM_PY_KIDS: usize = 250;
pub(crate) const EM_PY_QCONES: usize = 251;
pub(crate) const EM_PY_GLUE: usize = 252;
pub(crate) const EM_PY_XBASIS: usize = 253;
pub(crate) const EM_PY_SPLITS: usize = 254;
/// An assignment to one of the five names (`Engine.__init__`, the harness) converted into an `EngineMemo`.
pub(crate) const EM_SLOT_SET: usize = 255;
/// A Rust reader given a container that isn't an `EngineMemo` (ref.py's engine, a test's dict), read through its methods.
pub(crate) const EM_FOREIGN: usize = 256;
/// An engine memo emptied at its bound (`splits` at `maxsize`, `_qcones` at 50,000).
pub(crate) const EM_FULL: usize = 257;
/// A key's `==` run by an engine memo's lookup (not settled by identity).
pub(crate) const EM_KEY_EQ: usize = 258;
/// `_query_cone` run in Rust.
pub(crate) const BUD_QUERY_CONE: usize = 259;
/// Step 5c10a (factcache.rs): Python's calls into a fact cache, each a crossing: `facts` and `put` (`Engine.is_`, `is_many`,
/// `_is_custom`, `_put_result`; 5c10c), `get` (tests, tools), `sync` (`_check_version`; 5c10d).
pub(crate) const FC_PY_FACTS: usize = 260;
pub(crate) const FC_PY_GET: usize = 261;
pub(crate) const FC_PY_PUT: usize = 262;
pub(crate) const FC_PY_SYNC: usize = 263;
/// A read through the store's view (the tests, the registry's sizes and items, memo_check).
pub(crate) const FC_VIEW: usize = 264;
/// A store emptied by `clear` (the registry's clear, `_settings_changed`'s `store.clear()`).
pub(crate) const FC_CLEAR: usize = 265;
/// A store emptied at `maxsize` by a new node's `put`.
pub(crate) const FC_FULL: usize = 266;
/// A node's `==` run by a store lookup (not settled by identity).
pub(crate) const FC_KEY_EQ: usize = 267;
/// `_Mark`'s rollback of a fact cache on a refused query.
pub(crate) const FC_ROLLBACK: usize = 268;
/// A `FactCache` made (every `DictCache(...)` once installed).
pub(crate) const FC_NEW: usize = 269;
/// Python's read or write of a cache's memo key, `_settings` or `_epoch` (`Engine.is_`/`_is_custom` compare `_settings` every
/// query, 5c10c; tests).
pub(crate) const FC_PY_KEY: usize = 270;
/// Step 5c10b (context.rs, engmemo.rs slots 5-7). Python's calls into the `_failed`, `_verdict`, `_context_sessions` views
/// (`_drop_set_memos`, 5c10d; the registry; tests).
pub(crate) const EM_PY_FAILED: usize = 271;
pub(crate) const EM_PY_VERDICT: usize = 272;
pub(crate) const EM_PY_CTXS: usize = 273;
/// The five rows, once per run.
pub(crate) const CTX_CONTEXT_SESSION: usize = 274;
pub(crate) const CTX_BUILD_MEMOIZED: usize = 275;
pub(crate) const CTX_BUILD_CONTEXT: usize = 276;
pub(crate) const CTX_VERDICT: usize = 277;
pub(crate) const CTX_COMPLETE_CHECK: usize = 278;
/// Callbacks into Python, each removed by 5c10d: `_check_version`, `_fresh_session`, the module helpers (`_gave_up`,
/// `_exhausted`, `_noncommutative_atoms`), the `stats["set_checks"]` write.
pub(crate) const CTX_CB_CHECK_VERSION: usize = 279;
pub(crate) const CTX_CB_FRESH_SESSION: usize = 280;
pub(crate) const CTX_CB_HELPERS: usize = 281;
pub(crate) const CTX_PY_STATS: usize = 282;
/// engine.py:1906's handler, now in `build_context`: an Exception from the complete check made into a plain session.
pub(crate) const CTX_CAUGHT: usize = 283;
/// One of the five called by name because a patch replaced session_live's (tests, catch_count).
pub(crate) const CTX_CB_PATCHED: usize = 284;
/// Memo hits and the plain-session fallback (for reach).
pub(crate) const CTX_FAILED_HIT: usize = 285;
pub(crate) const CTX_VERDICT_HIT: usize = 286;
pub(crate) const CTX_FALLBACK: usize = 287;
/// Step 5c10c: a Python call into `_cones`' or `_constructing`'s view (a crossing): `is_`/`is_many` (`_cones.get`,
/// `node in _constructing`, 5c10d), `_Mark.add`/`rollback` (wiring, the state step), the tests and the registry.
pub(crate) const EM_PY_CONES: usize = 288;
pub(crate) const EM_PY_CONSTRUCTING: usize = 289;
/// The cone rows run in Rust (budget.rs): `_struct`, `_cone_info`, `_drop_cones`.
pub(crate) const BUD_STRUCT: usize = 290;
pub(crate) const BUD_CONE_INFO: usize = 291;
pub(crate) const BUD_DROP_CONES: usize = 292;
/// `_struct`'s callbacks: the engine's `clause_templates`/`templates` (knowledge, Python), and the extensions'
/// `facts_for`/`has_node_facts`/`node_facts` (knowledge.extensions, Python).
pub(crate) const BUD_CB_TEMPLATES: usize = 293;
pub(crate) const BUD_CB_EXT: usize = 294;
/// `_struct`'s wide-sum guard (#180 C-WIDEADD) taken; `_kids`/`_cones` hits (for reach).
pub(crate) const BUD_STRUCT_WIDE: usize = 295;
pub(crate) const BUD_KIDS_HIT: usize = 296;
pub(crate) const BUD_CONES_HIT: usize = 297;
/// The cone rows entered from Python (`is_`, `is_many`, `_is_custom`, `_settings_changed`, `_check_version`, the registry, tests),
/// against the totals above, which count Rust's own calls too (`_union`, `_cone_info`'s walk).
pub(crate) const BUD_PY_STRUCT: usize = 298;
pub(crate) const BUD_PY_CONE_INFO: usize = 299;
pub(crate) const BUD_PY_DROP_CONES: usize = 300;

/// Step 5c10d (entry.rs): the query-entry rows run in Rust, one counter per row.
pub(crate) const ENT_IS: usize = 301;
pub(crate) const ENT_IS_MANY: usize = 302;
pub(crate) const ENT_DECIDE: usize = 303;
pub(crate) const ENT_PUT_RESULT: usize = 304;
pub(crate) const ENT_IS_CUSTOM: usize = 305;
pub(crate) const ENT_ASK: usize = 306;
pub(crate) const ENT_ASK_INNER: usize = 307;
pub(crate) const ENT_CHECK_VERSION: usize = 308;
pub(crate) const ENT_SETTINGS_CHANGED: usize = 309;
pub(crate) const ENT_DROP_SET_MEMOS: usize = 310;
pub(crate) const ENT_FRESH_SESSION: usize = 311;
pub(crate) const ENT_CB_NONCOMM: usize = 312;
pub(crate) const ENT_CB_GAVE_UP: usize = 313;
pub(crate) const ENT_CB_SCOPE: usize = 314;
pub(crate) const ENT_CB_BASIS: usize = 315;
pub(crate) const ST_REC_CACHE_HIT: usize = 316;
pub(crate) const ST_REC_RELEVANT: usize = 317;
pub(crate) const ST_REC_CONSISTENCY_CHECK: usize = 318;
pub(crate) const ST_REC_SCOPE_MISS: usize = 319;
pub(crate) const ST_REC_CLEAR_FLAG: usize = 320;
pub(crate) const ST_REC_KEEP_FLAG: usize = 321;
pub(crate) const ST_PY_READ: usize = 322;
pub(crate) const ST_SLOT_SET: usize = 323;
pub(crate) const ST_FLAG_SET: usize = 324;
pub(crate) const ST_FOREIGN: usize = 325;
pub(crate) const ST_MARK: usize = 326;
/// State step, part 1 (adapters.rs): an `interpret`/`order_sides`/`integer_form` the Rust adapter answered on its own query slot.
pub(crate) const AD_LRA_NATIVE: usize = 327;
/// ... of which served from the slot's memo (same object, same query, same flag).
pub(crate) const AD_LRA_HIT: usize = 328;
/// `lra_adapter.relation` called on a slot miss (conversion: it reads predicate heads).
pub(crate) const AD_LRA_RELATION: usize = 329;
/// `term_live.term_id` called for a term that isn't an input row of its own class (derived, a number, or no row).
pub(crate) const AD_LRA_TERM_ID_PY: usize = 330;
/// `term_live.scaffold` called for a derived id in a result (scaffolding, counted again by term_live).
pub(crate) const AD_LRA_SCAFFOLD: usize = 331;
/// `_memoized` still called back, by reason: no query or a kept one (Python's memo serves it).
pub(crate) const AD_CBM_NOQUERY: usize = 332;
/// ... a side with no id: Python reads it (lra_live's on_python, counted `lra:*:no-id` there).
pub(crate) const AD_CBM_NOID: usize = 333;
/// ... SLICE_LRA_CHECK on: lra_live compares with Python's functions.
pub(crate) const AD_CBM_CHECK: usize = 334;
/// ... `_memoized` or the read function isn't the one lra_live installed (a test's patch).
pub(crate) const AD_CBM_PATCHED: usize = 335;
/// ... lra_live not installed (SLICE_LRA_TERM=py, SLICE_TERM=py): Python's functions throughout.
pub(crate) const AD_CBM_OFF: usize = 336;
pub(crate) const AD_LRA_NOT_EXPR: usize = 337;
pub(crate) const XF_SOLVER_CORE: usize = 338;
pub(crate) const XF_ENGAGE_CORE: usize = 339;
pub(crate) const XF_READ_CORE: usize = 340;
pub(crate) const XF_SESSION_VIEW: usize = 341;
pub(crate) const XF_REL_VIEW: usize = 342;
pub(crate) const XF_RECORD: usize = 343;
pub(crate) const GL_PLAIN: usize = 344;
pub(crate) const RC_CORE: usize = 347;
pub(crate) const RC_VIEW: usize = 348;
pub(crate) const RC_RECORD: usize = 349;
/// State step part 2 (iii)(b), RelKeys (planner ~04:50 10 Nov): a key interned with no query-table id, by where it came from.
pub(crate) const RK_INTERN_INPUT: usize = 350;
pub(crate) const RK_INTERN_ENGINE: usize = 351;
/// ... a key that took the query table's term id (no hash).
pub(crate) const RK_TERM: usize = 352;
/// ... a session whose keys met a second query table, or a table after a table-less intern: it outlives its query.
pub(crate) const RK_OUTLIVE: usize = 353;
/// ... each term-id key re-interned by hash when its session turns out to outlive its query.
pub(crate) const RK_MIGRATE: usize = 354;
/// ... the moved sets' native reads and writes, the Python views, the record methods.
pub(crate) const RS_CORE: usize = 355;
pub(crate) const RS_VIEW: usize = 356;
pub(crate) const RS_RECORD: usize = 357;
/// ... a lookup answered by the intern dict (a hash).
pub(crate) const RK_DICT_HIT: usize = 358;
/// RelKeys took the term id of an `==` object of an equal class (relkeys.rs `twin_row`): two equal `Function` classes in one query
pub(crate) const RK_TWIN: usize = 359;
pub(crate) const RD_CORE: usize = 520;
pub(crate) const RD_VIEW: usize = 521;
pub(crate) const RD_RECORD: usize = 522;
pub(crate) const RL_CORE: usize = 523;
pub(crate) const RL_VIEW: usize = 524;
pub(crate) const RL_RECORD: usize = 525;
pub(crate) const RB_GENERATED: usize = 420;
pub(crate) const RB_BUILT: usize = 421;
pub(crate) const RB_CHECK_ERROR: usize = 422;
pub(crate) const TH_GAVE_UP: usize = 555;
pub(crate) const TH_EXHAUSTED: usize = 556;
pub(crate) const TH_PY_FLAG: usize = 557;
pub(crate) const TH_PY_HELPER: usize = 558;
pub(crate) const SB_ATTR: usize = 559;
pub(crate) const SB_FWD_DIRECT: usize = 560;
pub(crate) const SB_FWD_NAMED: usize = 561;
pub(crate) const SB_SCALAR_CORE: usize = 562;
pub(crate) const SB_SCALAR_VIEW: usize = 563;
pub(crate) const SB_SCALAR_RECORD: usize = 564;
pub(crate) const SC_CORE: usize = 565;
pub(crate) const SC_VIEW: usize = 566;
pub(crate) const SC_RECORD: usize = 567;
pub(crate) const SC_KEY_HASH: usize = 568;
pub(crate) const SC_KEY_EQ: usize = 569;
pub(crate) const SB_CORE_PROP: usize = 570;

/// Deeper formulas compile on Python, over this same table. Python's own limit depends on the caller's stack, so it isn't
/// reproduced: its deepest shape is `Implies`, 3 frames a level (first failure at depth 330 from a bare stack, limit 1000), so
/// 64 is below what Python reaches with up to about 800 frames already on the stack.
const FORMULA_DEPTH: u32 = 64;

thread_local! {
    static COUNTS: [Cell<u64>; 571] = const { [const { Cell::new(0) }; 571] };
    /// Each session's serial, for the link's memo: a pointer could alias a dead session's.
    static SERIAL: Cell<u64> = const { Cell::new(0) };
}

pub(crate) fn tick(i: usize) {
    COUNTS.with(|c| c[i].set(c[i].get() + 1));
}

/// Crossings of the boundary so far, by kind. `join` isn't a crossing: objects of different classes that a dict joined.
#[pyfunction]
fn session_counts<'py>(p: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
    let d = PyDict::new(p);
    COUNTS.with(|c| {
        for (i, n) in NAMES.iter().enumerate() {
            if n.starts_with("reserved:") {
                continue;
            }
            d.set_item(*n, c[i].get())?;
        }
        Ok::<_, PyErr>(())
    })?;
    Ok(d)
}

/// What `rules.py` says, read once at install. `impls` is a memo of a pure function of constants.
#[pyclass(unsendable)]
pub struct SessionRules {
    data: Rc<RulesData>,
}

struct RulesData {
    basis: Vec<Py<PyAny>>,
    index: HashMap<String, u32>,
    kinds: Vec<Kind>,
    names: Vec<Py<PyAny>>,
    classes: Vec<Py<PyAny>>,
    def_implications: Py<PyAny>,
    impls: RefCell<HashMap<(Def, Def), Rc<Vec<(i32, i32)>>>>,
}

#[pymethods]
impl SessionRules {
    /// `classes`: `P`, `And`, `Or`, `Not`, `Implies`, `Equivalent`, `Exclusive`, `ITE`, `_Lit`.
    #[new]
    fn new(basis: Bound<'_, PyAny>, def_lits: Bound<'_, PyDict>, classes: Vec<Py<PyAny>>, def_implications: Py<PyAny>) -> PyResult<Self> {
        let (mut index, mut kinds, mut names, mut b) = (HashMap::new(), vec![], vec![], vec![]);
        for (i, x) in basis.try_iter()?.enumerate() {
            let x = x?;
            index.insert(x.extract::<String>()?, i as u32);
            kinds.push(Kind::Basis(i as u32));
            names.push(x.clone().unbind());
            b.push(x.unbind());
        }
        for (k, v) in def_lits.iter() {
            let (op, ls): (String, Vec<i32>) = v.extract()?;
            index.insert(k.extract::<String>()?, kinds.len() as u32);
            kinds.push(Kind::Derived(Rc::new((op == "&", ls))));
            names.push(k.unbind());
        }
        Ok(SessionRules { data: Rc::new(RulesData { basis: b, index, kinds, names, classes, def_implications, impls: RefCell::new(HashMap::new()) }) })
    }
}

#[derive(Clone, Copy)]
enum Slot {
    Aux,
    Block(u32, i32),
    Custom(u32, u32),
}

/// `VarTable`, plus `Session.base` and the memos of `var` and `dvar`.
struct St {
    base_of: Vec<i32>,
    base: Vec<i32>,
    slots: Vec<Slot>,
    new_nodes: Vec<u32>,
    custom: HashMap<(u32, u32), i32>,
    new_custom: Vec<(u32, u32)>,
    naux: u32,
    true_var: Option<i32>,
    defvars: HashMap<(u32, u32), i32>,
    dv: HashMap<(Def, u32), (i32, i32, bool)>,
    dv_node: HashMap<u32, Vec<(Def, i32)>>,
}

impl St {
    fn node_base(&mut self, nid: u32) -> i32 {
        let n = nid as usize;
        if self.base_of.len() <= n {
            self.base_of.resize(n + 1, 0);
        }
        if self.base_of[n] != 0 {
            return self.base_of[n];
        }
        let b = self.slots.len() as i32;
        self.base_of[n] = b;
        self.slots.extend(std::iter::repeat_n(Slot::Block(nid, b), NPRED.with(Cell::get)));
        self.new_nodes.push(nid);
        b
    }

    fn aux(&mut self) -> i32 {
        let v = self.slots.len() as i32;
        self.slots.push(Slot::Aux);
        self.naux += 1;
        v
    }

    fn visited(&self, nid: u32) -> i32 {
        self.base.get(nid as usize).copied().unwrap_or(0)
    }
}

thread_local! {
    static NPRED: Cell<usize> = const { Cell::new(0) };
}

#[pyclass(unsendable, frozen)]
pub struct SessionCore {
    rules: Rc<RulesData>,
    /// A weak reference to the shell: the shell reaches this object and the solver reaches the shell through its theories,
    /// and a strong one here is an edge the collector can't see.
    shell: Py<PyAny>,
    /// Keys the link's memo on the per-query table, which outlives no query but can see several sessions.
    pub(crate) serial: u64,
    nids: Py<PyDict>,
    /// The object per node id, as Python's slots keep it: the one passed to `node_base`, so it can still change until then.
    objs: RefCell<Vec<Py<PyAny>>>,
    /// Set when a conversion refuses for `second_object`, which `convert` counts.
    refused_object: Cell<bool>,
    bad: RefCell<Vec<Py<PyAny>>>,
    /// Custom predicates: a dict, because Python's table takes any hashable there, joined as a dict joins them.
    custom_ids: Py<PyDict>,
    custom_preds: RefCell<Vec<Py<PyAny>>>,
    /// Each custom atom's own expr: an `Args` and a `Tuple` are `==`, so one node, and the node's object isn't the atom's.
    custom_exprs: RefCell<HashMap<(u32, u32), Py<PyAny>>>,
    st: RefCell<St>,
    /// State step, part 2 (ii): `Session.solver`, handed over at `TableView.bind` (`Session.__init__` makes the solver
    /// before the table). Python's attribute stays for its other readers until part 3; the transfer sites read this one.
    solver: RefCell<Option<Py<PyAny>>>,
    /// ... `Session.xfer`: the engaged `Relations`, or None.
    session_xfer: RefCell<Option<Py<PyAny>>>,
    /// ... each `Relations`' `xfer`, `xfer_sel` and `_xadapter` (four independent attributes on Python, so independent here).
    xfer: RefCell<Vec<RelX>>,
    /// State step, part 2 (iii)(b): each `Relations`' scalar cursors (`RC_NAMES`), Rust-native.
    relc: RefCell<Vec<RelC>>,
    /// State step, part 2 (iii)(b), RelKeys: the session's keys for Relations' containers (relkeys.rs).
    pub(crate) relkeys: RefCell<RelKeys>,
    /// ... each `Relations`' sets (`RS_NAMES`), Rust-native.
    pub(crate) rels: RefCell<Vec<RelS>>,
    /// State part 3, sub-part 5: the session's scalars (`SS_NAMES`), Rust-native; `Session.truncated` .. `verdict` are views.
    ses: SesScalars,
    /// ... the session's own containers (ses_cont.rs), Rust-native; `Session.frontier` .. `_groups` are views.
    pub(crate) sc: RefCell<crate::ses_cont::SesCont>,
}

/// State part 3, sub-part 5: `Session`'s scalars, as Python named them: three flags, two ints, then `verdict` (an object:
/// the engine's verdict constant, compared by identity, or None). `Session.__init__`'s values are the defaults.
pub(crate) const SS_NAMES: [&str; 6] = ["truncated", "_link_pending", "_neg_shared", "sel", "n_hold", "verdict"];
pub(crate) const SS_TRUNCATED: usize = 0;
pub(crate) const SS_LINK_PENDING: usize = 1;
pub(crate) const SS_NEG_SHARED: usize = 2;
pub(crate) const SS_SEL: usize = 3;
pub(crate) const SS_N_HOLD: usize = 4;
pub(crate) const SS_VERDICT: usize = 5;

#[derive(Default)]
struct SesScalars {
    flags: [Cell<bool>; 3],
    ints: [Cell<i64>; 2],
    verdict: RefCell<Option<Py<PyAny>>>,
}

/// Sub-part 5's plants (`sb_plant`, SLICE_SESSION_PLANT): 431-436 a scalar read natively as its initial value
/// (`sb-truncated-stale`, `sb-link-pending-stale`, `sb-neg-shared-stale`, `sb-sel-zero`, `sb-hold-zero`, `sb-verdict-none`),
/// 437 `sb-fwd-skip-link` (the direct `_link` not run), 438 `sb-solver-fresh` (`solver_of` gives a new solver),
/// 439-445 `sc-<name>-drop` (ses_cont.rs: a session container's write is a no-op), 446 `sc-key-shared` (ses_cont.rs),
/// 447 `sb-core-unset` (`core_of` doesn't read `_core`: every read goes through the property), 448 `sb-core-stale`
/// (`core_of` gives the first core it saw, whatever the session).
static SB_PLANT: std::sync::atomic::AtomicU16 = std::sync::atomic::AtomicU16::new(0);
const SB_PLANTS: [&str; 18] = ["sb-truncated-stale", "sb-link-pending-stale", "sb-neg-shared-stale", "sb-sel-zero", "sb-hold-zero",
    "sb-verdict-none", "sb-fwd-skip-link", "sb-solver-fresh", "sc-frontier-drop", "sc-pending-drop", "sc-pending_c-drop",
    "sc-demand-drop", "sc-deferred-drop", "sc-literals-drop", "sc-groups-drop", "sc-key-shared", "sb-core-unset", "sb-core-stale"];
const SB_CORE_UNSET: u16 = 447;
const SB_CORE_STALE: u16 = 448;
pub(crate) const SB_FWD_SKIP_LINK: u16 = 437;
const SB_SOLVER_FRESH: u16 = 438;

pub(crate) fn sb_planted(x: u16) -> bool {
    if SB_PLANT.load(std::sync::atomic::Ordering::Relaxed) == x {
        tick(crate::relations_core::plant_counter());
        return true;
    }
    false
}

#[pyfunction]
#[pyo3(signature = (name=None))]
fn sb_plant(name: Option<&str>) -> PyResult<()> {
    let v = match name {
        None => 0,
        Some(n) => match SB_PLANTS.iter().position(|x| *x == n) {
            Some(i) => 431 + i as u16,
            None => return Err(PyValueError::new_err(format!("no such plant: {n}"))),
        },
    };
    SB_PLANT.store(v, std::sync::atomic::Ordering::Relaxed);
    Ok(())
}

/// State part 3, sub-part 5: `s.solver`, from the core. A session with no core (a test's stand-in) is read by attribute, counted.
pub(crate) fn solver_of<'py>(s: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let p = s.py();
    match core_of(s) {
        Ok(c) => {
            let v = c.borrow().solver_direct(p)?;
            if sb_planted(SB_SOLVER_FRESH) { v.get_type().call0() } else { Ok(v) }
        }
        Err(_) => {
            tick(SB_ATTR);
            s.getattr(intern!(p, "solver"))
        }
    }
}

/// ... a flag of `SS_NAMES` (`k` < 3).
pub(crate) fn ses_flag(s: &Bound<'_, PyAny>, k: usize) -> PyResult<bool> {
    match core_of(s) {
        Ok(c) => Ok(c.borrow().flag(k)),
        Err(_) => {
            tick(SB_ATTR);
            s.getattr(SS_NAMES[k])?.is_truthy()
        }
    }
}

pub(crate) fn ses_set_flag(s: &Bound<'_, PyAny>, k: usize, v: bool) -> PyResult<()> {
    match core_of(s) {
        Ok(c) => {
            c.borrow().set_flag(k, v);
            Ok(())
        }
        Err(_) => {
            tick(SB_ATTR);
            s.setattr(SS_NAMES[k], v)
        }
    }
}

/// ... `sel` or `n_hold`.
pub(crate) fn ses_int(s: &Bound<'_, PyAny>, k: usize) -> PyResult<i64> {
    match core_of(s) {
        Ok(c) => Ok(c.borrow().int(k)),
        Err(_) => {
            tick(SB_ATTR);
            s.getattr(SS_NAMES[k])?.extract()
        }
    }
}

pub(crate) fn ses_set_int(s: &Bound<'_, PyAny>, k: usize, v: i64) -> PyResult<()> {
    match core_of(s) {
        Ok(c) => {
            c.borrow().set_int(k, v);
            Ok(())
        }
        Err(_) => {
            tick(SB_ATTR);
            s.setattr(SS_NAMES[k], v)
        }
    }
}

/// ... `verdict`.
pub(crate) fn ses_verdict<'py>(s: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let p = s.py();
    match core_of(s) {
        Ok(c) => Ok(c.borrow().verdict(p)),
        Err(_) => {
            tick(SB_ATTR);
            s.getattr(intern!(p, "verdict"))
        }
    }
}

pub(crate) fn ses_set_verdict(s: &Bound<'_, PyAny>, v: Option<&Bound<'_, PyAny>>) -> PyResult<()> {
    let p = s.py();
    match core_of(s) {
        Ok(c) => {
            c.borrow().set_verdict(v);
            Ok(())
        }
        Err(_) => {
            tick(SB_ATTR);
            s.setattr(intern!(p, "verdict"), v)
        }
    }
}

/// State part 3, sub-part 5: `obj.<name>` as Rust should call it. None when the attribute is still session_live's own frame
/// `wrapper` (which only picks Python's copy for a session with no core, then calls the Rust function): the caller runs that
/// function directly. Otherwise the bound attribute to call: a test's override, or Python's method under SLICE_REL/LOOP=py.
pub(crate) fn named<'py>(obj: &Bound<'py, PyAny>, name: &Bound<'py, pyo3::types::PyString>, cell: &'static pyo3::sync::PyOnceLock<Py<PyAny>>,
                         wrapper: &'static str) -> PyResult<Option<Bound<'py, PyAny>>> {
    let p = obj.py();
    let m = obj.getattr(name)?;
    let w = cell.get_or_try_init(p, || -> PyResult<Py<PyAny>> { Ok(p.import(intern!(p, "session_live"))?.getattr(wrapper)?.unbind()) })?;
    if let Ok(f) = m.getattr(intern!(p, "__func__")) {
        if f.is(w.bind(p)) {
            tick(SB_FWD_DIRECT);
            return Ok(None);
        }
    }
    tick(SB_FWD_NAMED);
    Ok(Some(m))
}

/// RelKeys (planner's ruling, ~04:50 10 Nov): a key is an index into `objs`, which holds a strong ref so `id()` can't be reused.
/// A SymPy term with an id in the query's table takes it (`by_term`, no hash); any other key is interned once by hash (`dict`).
/// `table` is the serial (`PyTermTable::serial`, never the address) of the one query table whose ids `by_term` holds. A session
/// that meets a second table, or a table after it interned a term with none, outlives its query: its `by_term` keys move to
/// `dict` and it stays dict-only. An object with no row of its own class takes the id of the `==` row of an equal class
/// (relkeys.rs `twin_row`), so two equal `Function` classes in one query key as one, as Python's sets and dicts did.
#[derive(Default)]
pub(crate) struct RelKeys {
    pub(crate) objs: Vec<Py<PyAny>>,
    pub(crate) by_term: HashMap<u32, u32>,
    /// the query table's serial (`PyTermTable::serial`), never its address
    pub(crate) table: Option<u64>,
    pub(crate) dict_only: bool,
    pub(crate) dict: Option<Py<PyDict>>,
    /// SymPy terms interned by hash while in table mode (no row); a `by_term` miss checks `dict` only when there are some.
    pub(crate) basic_dict: usize,
    /// a term was interned while no query table was current
    pub(crate) tableless: bool,
}

/// The moved sets of `Relations.__init__`, by index (state step part 2 (iii)(b), rest).
pub(crate) const RS_NAMES: [&str; 9] = ["linked", "_bounded", "_user_eq", "_xpairs", "_aux_eq", "_link_eq", "_xpart", "_xcounted", "_xcand"];
pub(crate) const RS_LINKED: usize = 0;
pub(crate) const RS_BOUNDED: usize = 1;
pub(crate) const RS_USER_EQ: usize = 2;
pub(crate) const RS_XPAIRS: usize = 3;
pub(crate) const RS_AUX_EQ: usize = 4;
pub(crate) const RS_LINK_EQ: usize = 5;
pub(crate) const RS_XPART: usize = 6;
pub(crate) const RS_XCOUNTED: usize = 7;
pub(crate) const RS_XCAND: usize = 8;
/// State step part 2 (iii)(b), rest: `Relations`' dicts held in the core, insertion-ordered (relkeys.rs `OrdMap`, Python
/// dict order: a re-set keeps its place, a delete then set goes last), keyed by RelKeys.
pub(crate) const RD_NAMES: [&str; 15] = ["adapters", "status", "_guards", "_link_lt", "top", "link_sel", "atom_sel", "num_sel",
                                          "_roles", "_info", "_link_of", "_tv", "_tsrc", "_xside", "_xheads"];
pub(crate) const RD_ADAPTERS: usize = 0;
pub(crate) const RD_STATUS: usize = 1;
pub(crate) const RD_GUARDS: usize = 2;
pub(crate) const RD_LINK_LT: usize = 3;
pub(crate) const RD_TOP: usize = 4;
pub(crate) const RD_LINK_SEL: usize = 5;
pub(crate) const RD_ATOM_SEL: usize = 6;
pub(crate) const RD_NUM_SEL: usize = 7;
pub(crate) const RD_ROLES: usize = 8;
pub(crate) const RD_INFO: usize = 9;
pub(crate) const RD_LINK_OF: usize = 10;
pub(crate) const RD_TV: usize = 11;
pub(crate) const RD_TSRC: usize = 12;
pub(crate) const RD_XSIDE: usize = 13;
pub(crate) const RD_XHEADS: usize = 14;
/// State step part 2 (iii)(b), rest: `Relations`' work lists held in the core, `Vec`s of Python objects (atoms, terms,
/// `(node, base)` pairs). `specs` stays Python's list: it's the engine's configuration (the default specs or a user's), read
/// only by iteration and never written after `__init__`.
pub(crate) const RL_NAMES: [&str; 4] = ["queue", "_pending_links", "_xextra", "_xpend"];
pub(crate) const RL_QUEUE: usize = 0;
pub(crate) const RL_PENDING_LINKS: usize = 1;
pub(crate) const RL_XEXTRA: usize = 2;
pub(crate) const RL_XPEND: usize = 3;

/// One `Relations`' sets, as RelKeys keys. Insertion order is kept beside each (`order`) for the test-only snapshot and the
/// views' iteration; no engine code iterates these sets (grep at 022630c).
pub(crate) struct RelS {
    pub(crate) rel: Py<PyAny>,
    pub(crate) s: [std::collections::HashSet<u32>; 9],
    pub(crate) order: [Vec<u32>; 9],
    pub(crate) d: [crate::relkeys::OrdMap; 15],
    pub(crate) l: [Vec<Py<PyAny>>; 4],
}

/// `s.table`, read from the session's `_table_view` (what the `table` property returns), so no Python frame; a session
/// without one is read through `table`.
pub(crate) fn table_of<'py>(s: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let p = s.py();
    if !sb_planted(SB_CORE_UNSET) {
        if let Ok(t) = s.getattr(intern!(p, "_table_view")) {
            return Ok(t);
        }
    }
    tick(SB_CORE_PROP);
    s.getattr(intern!(p, "table"))
}

thread_local! {
    /// Plant 448's stale core.
    static STALE_CORE: RefCell<Option<Py<SessionCore>>> = const { RefCell::new(None) };
}

/// `s.table.core`, read from the session's `_core` (session_live `_table_set` stores it beside the view): a plain instance
/// attribute, so no Python frame. A session without one (no core: ref.py's copy; or a table set before `install()`) is read
/// through `table`, counted `sb:core_prop`.
pub(crate) fn core_of<'py>(s: &Bound<'py, PyAny>) -> PyResult<Bound<'py, SessionCore>> {
    let p = s.py();
    if !sb_planted(SB_CORE_UNSET) {
        if let Ok(c) = s.getattr(intern!(p, "_core")) {
            if let Ok(c) = c.cast_into::<SessionCore>() {
                if sb_planted(SB_CORE_STALE) {
                    return Ok(STALE_CORE.with(|x| x.borrow_mut().get_or_insert_with(|| c.clone().unbind()).bind(p).clone()));
                }
                return Ok(c);
            }
        }
    }
    tick(SB_CORE_PROP);
    Ok(s.getattr(intern!(p, "table"))?.getattr(intern!(p, "core"))?.cast_into::<SessionCore>()?)
}

/// State step, part 2 (ii): `s.xfer`, from the core.
pub(crate) fn session_xfer<'py>(s: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyAny>>> {
    Ok(core_of(s)?.borrow().xfer_session(s.py()))
}

/// One `Relations`' transfer attributes, by `XTH`, `XSEL`, `XAD`; `None` where Python's attribute is None.
pub(crate) struct RelX {
    rel: Py<PyAny>,
    f: [Option<Py<PyAny>>; 3],
}

/// State step, part 2 (iii)(b): one `Relations`' scalar cursors, by index into `RC_NAMES`.
pub(crate) struct RelC {
    rel: Py<PyAny>,
    c: [i64; 7],
}

/// The cursors, as Python named them; `RC_INIT` is `Relations.__init__`'s values.
pub(crate) const RC_NAMES: [&str; 7] = ["_xtcur", "_xhn", "_xhseen", "_xslot", "_xterm", "_xnsides", "_xsides_n"];
pub(crate) const RC_INIT: [i64; 7] = [0, 0, -1, 1, 0, -1, 0];
pub(crate) const XTCUR: usize = 0;
pub(crate) const XHN: usize = 1;
pub(crate) const XHSEEN: usize = 2;
pub(crate) const XSLOT: usize = 3;
pub(crate) const XTERM: usize = 4;
pub(crate) const XNSIDES: usize = 5;
pub(crate) const XSIDES_N: usize = 6;

/// `rel.xfer` (the transfer theory), `rel.xfer_sel`, `rel._xadapter`.
pub(crate) const XTH: usize = 0;
pub(crate) const XSEL: usize = 1;
pub(crate) const XAD: usize = 2;

impl SessionCore {
    /// `s.solver` for the Rust readers that moved off Python's attribute.
    pub(crate) fn solver_direct<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        tick(XF_SOLVER_CORE);
        match &*self.solver.borrow() {
            Some(s) => Ok(s.bind(p).clone()),
            None => Err(PyValueError::new_err("the session core has no solver (TableView.bind gives it)")),
        }
    }

    /// State part 3, sub-part 5: a session flag (`SS_TRUNCATED`, `SS_LINK_PENDING`, `SS_NEG_SHARED`), natively.
    pub(crate) fn flag(&self, k: usize) -> bool {
        tick(SB_SCALAR_CORE);
        if sb_planted(431 + k as u16) {
            return false;
        }
        self.ses.flags[k].get()
    }

    pub(crate) fn set_flag(&self, k: usize, v: bool) {
        tick(SB_SCALAR_CORE);
        self.ses.flags[k].set(v)
    }

    /// ... `SS_SEL` or `SS_N_HOLD`.
    pub(crate) fn int(&self, k: usize) -> i64 {
        tick(SB_SCALAR_CORE);
        if sb_planted(431 + k as u16) {
            return 0;
        }
        self.ses.ints[k - 3].get()
    }

    pub(crate) fn set_int(&self, k: usize, v: i64) {
        tick(SB_SCALAR_CORE);
        self.ses.ints[k - 3].set(v)
    }

    /// ... `verdict`: the engine's constant, or None.
    pub(crate) fn verdict<'py>(&self, p: Python<'py>) -> Bound<'py, PyAny> {
        tick(SB_SCALAR_CORE);
        if sb_planted(436) {
            return p.None().into_bound(p);
        }
        self.ses.verdict.borrow().as_ref().map_or_else(|| p.None().into_bound(p), |v| v.bind(p).clone())
    }

    pub(crate) fn set_verdict(&self, v: Option<&Bound<'_, PyAny>>) {
        tick(SB_SCALAR_CORE);
        *self.ses.verdict.borrow_mut() = v.filter(|v| !v.is_none()).map(|v| v.clone().unbind());
    }

    /// `_engage_transfer`'s four writes (`rel.xfer_sel`, `rel._xadapter`, `rel.xfer`, `s.xfer = rel`).
    pub(crate) fn xfer_engage(&self, rel: &Bound<'_, PyAny>, th: &Bound<'_, PyAny>, ad: &Bound<'_, PyAny>, sel: &Bound<'_, PyAny>) {
        tick(XF_ENGAGE_CORE);
        self.xfer_put(rel, XSEL, Some(sel));
        self.xfer_put(rel, XAD, Some(ad));
        self.xfer_put(rel, XTH, Some(th));
        *self.session_xfer.borrow_mut() = Some(rel.clone().unbind());
    }

    fn xfer_put(&self, rel: &Bound<'_, PyAny>, k: usize, v: Option<&Bound<'_, PyAny>>) {
        let v = v.filter(|v| !v.is_none()).map(|v| v.clone().unbind());
        let mut xs = self.xfer.borrow_mut();
        match xs.iter_mut().find(|x| x.rel.is(rel)) {
            Some(x) => x.f[k] = v,
            None => {
                let mut f = [None, None, None];
                f[k] = v;
                xs.push(RelX { rel: rel.clone().unbind(), f });
            }
        }
    }

    /// State step, part 2 (iii)(b): `Relations.__init__`'s cursor writes (rel_init, or the record method for Python's own).
    pub(crate) fn relc_init(&self, rel: &Bound<'_, PyAny>) {
        tick(RC_CORE);
        let mut v = self.relc.borrow_mut();
        match v.iter_mut().find(|x| x.rel.is(rel)) {
            Some(x) => x.c = RC_INIT,
            None => v.push(RelC { rel: rel.clone().unbind(), c: RC_INIT }),
        }
    }

    /// Cursor `k` of `rel`; `RC_INIT`'s value for a `Relations` the core hasn't seen.
    pub(crate) fn relc_get(&self, rel: &Bound<'_, PyAny>, k: usize) -> i64 {
        tick(RC_CORE);
        let v = self.relc.borrow();
        v.iter().find(|x| x.rel.is(rel)).map_or(RC_INIT[k], |x| x.c[k])
    }

    /// Cursor `k` of `rel` = `val`.
    pub(crate) fn relc_put(&self, rel: &Bound<'_, PyAny>, k: usize, val: i64) {
        tick(RC_CORE);
        if (k == XTERM && crate::relations_core::planted(crate::relations_core::RC_XTERM_STALE))
            || (k == XHSEEN && crate::relations_core::planted(crate::relations_core::RC_HSEEN_STALE))
        {
            return;
        }
        let mut v = self.relc.borrow_mut();
        match v.iter_mut().find(|x| x.rel.is(rel)) {
            Some(x) => x.c[k] = val,
            None => {
                let mut c = RC_INIT;
                c[k] = val;
                v.push(RelC { rel: rel.clone().unbind(), c });
            }
        }
    }

    /// `s.xfer`: the engaged `Relations`, or None.
    pub(crate) fn xfer_session<'py>(&self, p: Python<'py>) -> Option<Bound<'py, PyAny>> {
        tick(XF_READ_CORE);
        if crate::relations_core::planted(crate::relations_core::XF_SESSION_NONE) {
            return None;
        }
        self.session_xfer.borrow().as_ref().map(|x| x.bind(p).clone())
    }

    /// `rel.xfer` (`XTH`), `rel.xfer_sel` (`XSEL`) or `rel._xadapter` (`XAD`); None where Python's attribute is None.
    pub(crate) fn xfer_get<'py>(&self, rel: &Bound<'py, PyAny>, k: usize) -> Option<Bound<'py, PyAny>> {
        tick(XF_READ_CORE);
        let p = rel.py();
        if k == XSEL && crate::relations_core::planted(crate::relations_core::XF_SEL_NONE) {
            return None;
        }
        let xs = self.xfer.borrow();
        let x = if crate::relations_core::planted(crate::relations_core::XF_REL_ANY) { xs.last() } else { xs.iter().find(|x| x.rel.is(rel)) };
        x.and_then(|x| x.f[k].as_ref()).map(|v| v.bind(p).clone())
    }

    /// The same, with Python's None for a missing one.
    pub(crate) fn xfer_obj<'py>(&self, rel: &Bound<'py, PyAny>, k: usize) -> Bound<'py, PyAny> {
        self.xfer_get(rel, k).unwrap_or_else(|| rel.py().None().into_bound(rel.py()))
    }
    fn shell<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        self.shell.bind(p).call0()
    }

    /// The id of an object about to reach `node_base`, or passed where Python's table would take it: with no slot yet, this
    /// is the object the slot will hold.
    fn nid_of(&self, x: &Bound<'_, PyAny>) -> PyResult<u32> {
        if let Some(n) = self.known(x)? {
            if self.second_object(x, n) {
                self.objs.borrow_mut()[n as usize] = x.clone().unbind();
            }
            return Ok(n);
        }
        let mut objs = self.objs.borrow_mut();
        let n = objs.len() as u32;
        objs.push(x.clone().unbind());
        self.nids.bind(x.py()).set_item(x, n)?;
        Ok(n)
    }

    /// `nid_of` for an atom's expr. A custom atom takes no slot on Python, so it doesn't choose the object one will hold.
    fn nid_of_atom(&self, p: Python<'_>, pred: u32, x: &Bound<'_, PyAny>) -> PyResult<u32> {
        match (self.kind_of(p, pred), self.known(x)?) {
            (Kind::Custom, Some(n)) => Ok(n),
            _ => self.nid_of(x),
        }
    }

    /// `x` is `==` to the object held for node `n`, isn't that object, and `n` has no slot yet, so which one the slot holds
    /// depends on the order `node_base` is reached. Python keeps the first passed there, and `Pow`'s `same` row reads identity.
    fn second_object(&self, x: &Bound<'_, PyAny>, n: u32) -> bool {
        !self.objs.borrow()[n as usize].bind(x.py()).is(x)
            && self.st.borrow().base_of.get(n as usize).copied().unwrap_or(0) == 0
    }

    /// `nid_of` for an atom in a formula being converted. Conversion walks the formula and compiling may reach its atoms in
    /// another order, and a node with no visit yet may be visited from here, where Python visits the atom's own object. So a
    /// second object for a node with no visit refuses, before anything is emitted, and Python's compiler passes them in its
    /// own order over this same table.
    fn nid_in_formula(&self, x: &Bound<'_, PyAny>) -> PyResult<u32> {
        if let Some(n) = self.known(x)? {
            if !self.objs.borrow()[n as usize].bind(x.py()).is(x) && self.st.borrow().visited(n) == 0 {
                return Err(self.refuse_object());
            }
            return Ok(n);
        }
        self.nid_of(x)
    }

    fn refuse_object(&self) -> PyErr {
        self.refused_object.set(true);
        PyValueError::new_err("a second object for a node with no visit")
    }

    /// A custom atom's own expr reaching a direct entry: Python's `custom` keeps the first atom to reach `table.var`, so with
    /// no variable yet this is the one it would keep, and with one nothing changes.
    fn custom_expr(&self, pred: u32, nid: u32, x: &Bound<'_, PyAny>) {
        if matches!(self.kind_of(x.py(), pred), Kind::Custom) && !self.st.borrow().custom.contains_key(&(pred, nid)) {
            self.custom_exprs.borrow_mut().insert((pred, nid), x.clone().unbind());
        }
    }

    /// The same in a formula being converted, which may reach its atoms in another order: a different expr with no variable
    /// yet refuses, as a second object does.
    fn custom_in_formula(&self, pred: u32, nid: u32, x: &Bound<'_, PyAny>) -> PyResult<()> {
        if !matches!(self.kind_of(x.py(), pred), Kind::Custom) || self.st.borrow().custom.contains_key(&(pred, nid)) {
            return Ok(());
        }
        let mut exprs = self.custom_exprs.borrow_mut();
        match exprs.get(&(pred, nid)) {
            Some(o) if !o.bind(x.py()).is(x) => Err(self.refuse_object()),
            Some(_) => Ok(()),
            None => {
                exprs.insert((pred, nid), x.clone().unbind());
                Ok(())
            }
        }
    }

    fn known(&self, x: &Bound<'_, PyAny>) -> PyResult<Option<u32>> {
        let Some(v) = self.nids.bind(x.py()).get_item(x)? else { return Ok(None) };
        let n: u32 = v.extract()?;
        let first = self.objs.borrow()[n as usize].clone_ref(x.py());
        if !first.bind(x.py()).get_type().is(x.get_type()) {
            tick(JOIN);
            log_join(self as *const Self as usize, n, first.bind(x.py()), x)?;
        }
        Ok(Some(n))
    }

    /// `x`'s node, for the link: no new node, no `join` tick, and nothing chosen about which object a slot holds.
    pub(crate) fn node_quiet(&self, x: &Bound<'_, PyAny>) -> PyResult<Option<u32>> {
        match self.nids.bind(x.py()).get_item(x)? {
            Some(v) => Ok(Some(v.extract()?)),
            None => Ok(None),
        }
    }

    /// `Session.var` for a method that moved here: what `var` does, past the view Python's `Session` calls.
    pub(crate) fn var_direct(&self, pred: &Bound<'_, PyAny>, node: &Bound<'_, PyAny>) -> PyResult<i32> {
        tick(REL_VAR);
        let p = pred.py();
        let (i, n) = (self.pred_id(p, pred)?, self.nid_of(node)?);
        self.var_id(p, i, n, node, || PyKeyError::new_err(pred.clone().unbind()))
    }

    /// `table.custom.get`, for a method that moved here.
    pub(crate) fn custom_direct(&self, a: &Bound<'_, PyAny>) -> PyResult<Option<i32>> {
        let (i, e) = self.atom_fields(a)?;
        let Some(n) = self.known(&e)? else { return Ok(None) };
        Ok(self.st.borrow().custom.get(&(i, n)).copied())
    }

    /// `node in s.base`, for a method that moved here.
    pub(crate) fn base_contains_direct(&self, node: &Bound<'_, PyAny>) -> PyResult<bool> {
        Ok(self.known(node)?.is_some_and(|n| self.st.borrow().visited(n) != 0))
    }

    /// `len(table.slots)`.
    pub(crate) fn n_slots_direct(&self) -> usize {
        self.st.borrow().slots.len()
    }

    /// `slots[v][0]` when `v` is a block's first variable, and None for anything else.
    pub(crate) fn block_direct<'py>(&self, p: Python<'py>, v: usize) -> Option<Bound<'py, PyAny>> {
        match self.st.borrow().slots[v] {
            Slot::Block(n, b) if b as usize == v => Some(self.objs.borrow()[n as usize].clone_ref(p).into_bound(p)),
            _ => None,
        }
    }

    /// `Session.emit`.
    pub(crate) fn emit_direct(&self, p: Python<'_>, clause: &[i32]) -> PyResult<()> {
        self.emit(p, clause)
    }

    fn pred_id(&self, p: Python<'_>, pred: &Bound<'_, PyAny>) -> PyResult<u32> {
        let r = &self.rules;
        if let Ok(s) = pred.extract::<String>() {
            if let Some(&i) = r.index.get(&s) {
                return Ok(i);
            }
        }
        let ids = self.custom_ids.bind(p);
        if let Some(v) = ids.get_item(pred)? {
            return v.extract();
        }
        let mut c = self.custom_preds.borrow_mut();
        let i = (r.kinds.len() + c.len()) as u32;
        ids.set_item(pred, i)?;
        c.push(pred.clone().unbind());
        Ok(i)
    }

    fn pred_name<'py>(&self, p: Python<'py>, i: u32) -> Bound<'py, PyAny> {
        let r = &self.rules;
        let i = i as usize;
        if i < r.names.len() {
            r.names[i].bind(p).clone()
        } else {
            self.custom_preds.borrow()[i - r.names.len()].bind(p).clone()
        }
    }

    fn kind_of(&self, _p: Python<'_>, i: u32) -> Kind {
        self.rules.kinds.get(i as usize).cloned().unwrap_or(Kind::Custom)
    }

    fn atom_fields<'py>(&self, a: &Bound<'py, PyAny>) -> PyResult<(u32, Bound<'py, PyAny>)> {
        let p = a.py();
        if let Ok(x) = a.cast::<PyP>() {
            let (pred, expr) = x.get().fields();
            return Ok((self.pred_id(p, pred.bind(p))?, expr.bind(p).clone()));
        }
        Ok((self.pred_id(p, &a.getattr(intern!(p, "pred"))?)?, a.getattr(intern!(p, "expr"))?))
    }

    fn to_f(&self, f: &Bound<'_, PyAny>, depth: u32) -> PyResult<R> {
        let p = f.py();
        if depth > FORMULA_DEPTH {
            return Err(PyRecursionError::new_err("formula deeper than Rust compiles"));
        }
        if f.is_instance_of::<PyBool>() {
            return Ok(Rc::new(if f.is_truthy()? { F::True } else { F::False }));
        }
        let c = &self.rules.classes;
        if f.is_instance_of::<PyP>() || f.is_instance(c[0].bind(p))? {
            let (pred, expr) = self.atom_fields(f)?;
            let n = self.nid_in_formula(&expr)?;
            self.custom_in_formula(pred, n, &expr)?;
            return Ok(Rc::new(F::Atom(pred, n)));
        }
        let args = |f: &Bound<'_, PyAny>| -> PyResult<Vec<R>> {
            let a = f.getattr(intern!(p, "args"))?;
            let t = a.cast::<PyTuple>()?;
            t.iter().map(|x| self.to_f(&x, depth + 1)).collect()
        };
        for (i, cls) in c.iter().enumerate().skip(1) {
            if !f.is_instance(cls.bind(p))? {
                continue;
            }
            if i == 8 {
                return Ok(Rc::new(F::Lit(f.getattr(intern!(p, "lit"))?.extract()?)));
            }
            let mut a = args(f)?;
            return Ok(Rc::new(match i {
                1 => F::And(a),
                2 => F::Or(a),
                3 => F::Not(a.remove(0)),
                4 => {
                    let y = a.remove(1);
                    F::Implies(a.remove(0), y)
                }
                5 => F::Equivalent(a),
                6 => F::Exclusive(a),
                _ => {
                    let (z, y) = (a.remove(2), a.remove(1));
                    F::Ite(a.remove(0), y, z)
                }
            }));
        }
        let mut b = self.bad.borrow_mut();
        b.push(f.clone().unbind());
        Ok(Rc::new(F::Bad(b.len() as u32 - 1)))
    }

    /// The formula over ids, or `None` for Python to compile it: too deep, or any error reading it. Nothing has been emitted
    /// yet, so Python's compiler raises what it raises, where it raises it. A BaseException isn't an answer and goes up.
    fn convert(&self, f: &Bound<'_, PyAny>) -> PyResult<Option<R>> {
        let p = f.py();
        match self.to_f(f, 0) {
            Ok(r) => Ok(Some(r)),
            Err(e) if e.is_instance_of::<PyException>(p) => {
                tick(if self.refused_object.take() {
                    REFUSE_OBJECT
                } else if e.is_instance_of::<PyRecursionError>(p) {
                    REFUSE_DEPTH
                } else {
                    REFUSE_CONVERT
                });
                Ok(None)
            }
            Err(e) => Err(e),
        }
    }

    /// `s.table.aux()` and `s.solver.ensure_vars(v)`, for `_fresh`. A plain call, so no `py:table` tick.
    pub(crate) fn aux_direct(&self) -> i32 {
        self.st.borrow_mut().aux()
    }

    pub(crate) fn ensure_vars_direct(&self, p: Python<'_>, v: i32) -> PyResult<()> {
        self.ensure_vars(p, v)
    }

    fn emit(&self, p: Python<'_>, clause: &[i32]) -> PyResult<()> {
        tick(ADD_CLAUSE);
        let s = self.solver_direct(p)?;
        s.call_method1(intern!(p, "add_clause"), (PyList::new(p, clause)?,))?;
        Ok(())
    }

    fn ensure_vars(&self, p: Python<'_>, v: i32) -> PyResult<()> {
        tick(ENSURE);
        self.solver_direct(p)?.call_method1(intern!(p, "ensure_vars"), (v,))?;
        Ok(())
    }

    /// `Session.node` with `demanded=None`. Python visits the object passed, whichever one the slot holds; `passed` is that
    /// object, and `None` is a formula's atom, which conversion has refused unless it's the one in `objs` or already visited.
    fn node_id(&self, p: Python<'_>, nid: u32, passed: Option<&Bound<'_, PyAny>>) -> PyResult<i32> {
        let b = self.st.borrow().visited(nid);
        if b != 0 {
            return Ok(b);
        }
        if let Some(o) = passed {
            if !self.objs.borrow()[nid as usize].bind(p).is(o) {
                tick(SECOND_VISIT);
            }
            return self.visit_id(o, nid, p.None().bind(p));
        }
        let o = self.objs.borrow()[nid as usize].clone_ref(p);
        self.visit_id(o.bind(p), nid, p.None().bind(p))
    }

    fn visit_id(&self, node: &Bound<'_, PyAny>, nid: u32, demanded: &Bound<'_, PyAny>) -> PyResult<i32> {
        let p = node.py();
        let b = {
            let mut st = self.st.borrow_mut();
            let b = st.node_base(nid);
            let n = nid as usize;
            if st.base.len() <= n {
                st.base.resize(n + 1, 0);
            }
            st.base[n] = b;
            st.new_nodes.clear();
            b
        };
        tick(VISIT);
        crate::compile_loop::core_visit(&self.shell(p)?, node, b, demanded)?;
        Ok(b)
    }

    fn var_id(&self, p: Python<'_>, pred: u32, nid: u32, passed: &Bound<'_, PyAny>, name: impl FnOnce() -> PyErr) -> PyResult<i32> {
        match self.kind_of(p, pred) {
            Kind::Basis(i) => Ok(self.node_id(p, nid, Some(passed))? + i as i32),
            Kind::Custom => Err(name()),
            Kind::Derived(d) => {
                if d.1.len() > 1 {
                    return self.dvar_raw(p, &d, nid, Some(passed), 3, false);
                }
                if let Some(&v) = self.st.borrow().defvars.get(&(pred, nid)) {
                    return Ok(v);
                }
                let b = self.node_id(p, nid, Some(passed))?;
                let lits = block_lits(b, &d.1);
                let v = {
                    let mut st = self.st.borrow_mut();
                    let v = st.aux();
                    st.defvars.insert((pred, nid), v);
                    v
                };
                self.ensure_vars(p, v)?;
                if d.0 {
                    for &l in &lits {
                        self.emit(p, &[-v, l])?;
                    }
                    let mut c = vec![v];
                    c.extend(lits.iter().map(|l| -l));
                    self.emit(p, &c)
                } else {
                    for &l in &lits {
                        self.emit(p, &[-l, v])?;
                    }
                    let mut c = vec![-v];
                    c.extend_from_slice(&lits);
                    self.emit(p, &c)
                }?;
                Ok(v)
            }
        }
    }

    /// `Session._dvar`. Python reads the memo before visiting and allocates on what it read, so a visit that made the same key
    /// is overwritten; a key that was there is read again after, because the Python holds its list.
    fn dvar_raw(&self, p: Python<'_>, d: &Def, nid: u32, passed: Option<&Bound<'_, PyAny>>, need: i32, link: bool) -> PyResult<i32> {
        let key = (d.clone(), nid);
        let had = self.st.borrow().dv.contains_key(&key);
        let b = self.node_id(p, nid, passed)?;
        if !had {
            let v = {
                let mut st = self.st.borrow_mut();
                let v = st.aux();
                st.dv.insert(key.clone(), (v, 0, false));
                v
            };
            self.ensure_vars(p, v)?;
        }
        let (v, have, linked) = self.st.borrow().dv[&key];
        if link && !linked {
            self.st.borrow_mut().dv.get_mut(&key).expect("just read").2 = true;
            self.link(p, d, nid, v)?;
        }
        let missing = need & !have;
        if missing != 0 {
            let lits = block_lits(b, &d.1);
            if d.0 {
                if missing & 1 != 0 {
                    for &l in &lits {
                        self.emit(p, &[-v, l])?;
                    }
                }
                if missing & 2 != 0 {
                    let mut c = vec![v];
                    c.extend(lits.iter().map(|l| -l));
                    self.emit(p, &c)?;
                }
            } else {
                if missing & 2 != 0 {
                    for &l in &lits {
                        self.emit(p, &[-l, v])?;
                    }
                }
                if missing & 1 != 0 {
                    let mut c = vec![-v];
                    c.extend_from_slice(&lits);
                    self.emit(p, &c)?;
                }
            }
            self.st.borrow_mut().dv.get_mut(&key).expect("just read").1 = have | need;
        }
        Ok(v)
    }

    fn implications(&self, p: Python<'_>, a: &Def, b: &Def) -> PyResult<Rc<Vec<(i32, i32)>>> {
        let r = &self.rules;
        let key = (a.clone(), b.clone());
        if let Some(x) = r.impls.borrow().get(&key) {
            return Ok(x.clone());
        }
        tick(IMPL);
        let t = |d: &Def| -> PyResult<Py<PyTuple>> {
            let ls = PyTuple::new(p, d.1.iter().copied())?;
            Ok(PyTuple::new(p, [(if d.0 { "&" } else { "|" }).into_pyobject(p)?.into_any(), ls.into_any()])?.unbind())
        };
        let got: Vec<(i32, i32)> = r.def_implications.bind(p).call1((t(a)?, t(b)?))?.extract()?;
        let got = Rc::new(got);
        r.impls.borrow_mut().insert(key, got.clone());
        Ok(got)
    }

    /// `Session._link`.
    fn link(&self, p: Python<'_>, d: &Def, nid: u32, v: i32) -> PyResult<()> {
        tick(SES_LINK);
        let others: Vec<(Def, i32)> = {
            let mut st = self.st.borrow_mut();
            let o = st.dv_node.entry(nid).or_default();
            if o.iter().any(|(d2, v2)| *v2 == v && d2 == d) {
                return Ok(());
            }
            o.clone()
        };
        let own = |l: i32| d.1.iter().any(|x| x.abs() == l.abs());
        for (d2, v2) in &others {
            if d.1.len() == 1 && (d2.1.len() == 1 || d.1.iter().all(|x| d2.1.iter().any(|y| y.abs() == x.abs()))) {
                continue;
            }
            if d2.1.len() == 1 && own(d2.1[0]) {
                continue;
            }
            if crate::relations_core::planted(crate::relations_core::DROP_DV_LINK) {
                continue;
            }
            for &(s1, s2) in self.implications(p, d, d2)?.iter() {
                self.emit(p, &[s1 * v, s2 * *v2])?;
            }
        }
        self.st.borrow_mut().dv_node.entry(nid).or_default().push((d.clone(), v));
        Ok(())
    }

    fn table_var(&self, p: Python<'_>, pred: u32, nid: u32) -> PyResult<i32> {
        match self.kind_of(p, pred) {
            Kind::Basis(i) => Ok(self.st.borrow_mut().node_base(nid) + i as i32),
            Kind::Derived(_) => {
                Err(PyValueError::new_err(format!("derived predicate {} has no variable", self.pred_name(p, pred).repr()?)))
            }
            Kind::Custom => {
                let mut st = self.st.borrow_mut();
                if let Some(&v) = st.custom.get(&(pred, nid)) {
                    return Ok(v);
                }
                let v = st.slots.len() as i32;
                st.custom.insert((pred, nid), v);
                st.slots.push(Slot::Custom(pred, nid));
                st.new_custom.push((pred, nid));
                Ok(v)
            }
        }
    }

    fn make_atom<'py>(&self, p: Python<'py>, pred: u32, nid: u32) -> PyResult<Bound<'py, PyAny>> {
        let o = self.objs.borrow()[nid as usize].clone_ref(p);
        self.rules.classes[0].bind(p).call1((self.pred_name(p, pred), o))
    }

    /// `slots[v]` of a custom atom. Every route to its variable records the expr first.
    fn custom_atom<'py>(&self, p: Python<'py>, pred: u32, nid: u32) -> PyResult<Bound<'py, PyAny>> {
        let o = self.custom_exprs.borrow()[&(pred, nid)].clone_ref(p);
        if !self.objs.borrow()[nid as usize].bind(p).is(&o) {
            tick(CUSTOM_OWN);
        }
        self.rules.classes[0].bind(p).call1((self.pred_name(p, pred), o))
    }

    /// `Session.dvar` for a derived atom.
    fn dvar_def(&self, p: Python<'_>, d: &Def, nid: u32, passed: Option<&Bound<'_, PyAny>>, need: Need) -> PyResult<Option<i32>> {
        let need = match need {
            Need::NegUnit | Need::PosUnit => {
                tick(NEG);
                let on = self.flag(SS_NEG_SHARED);
                if !on || d.1.len() < 2 {
                    return Ok(None);
                }
                if need == Need::NegUnit {
                    Need::Neg
                } else {
                    Need::Pos
                }
            }
            n => n,
        };
        if d.1.len() == 1 {
            let b = self.node_id(p, nid, passed)?;
            let v = block_lits(b, &d.1)[0];
            self.link(p, d, nid, v)?;
            return Ok(Some(v));
        }
        let mask = match need {
            Need::Both => 3,
            Need::Pos => 1,
            _ => 2,
        };
        self.dvar_raw(p, d, nid, passed, mask, true).map(Some)
    }
}

struct PyCx<'a, 'py> {
    core: &'a SessionCore,
    p: Python<'py>,
    /// The caller's own `emit`, when it isn't `Session.emit`.
    via: Option<Bound<'py, PyAny>>,
    use_dv: bool,
}

impl Cx for PyCx<'_, '_> {
    type E = PyErr;

    fn kind(&self, pred: u32) -> Kind {
        self.core.kind_of(self.p, pred)
    }

    fn node_base(&mut self, nid: u32) -> i32 {
        self.core.st.borrow_mut().node_base(nid)
    }

    fn var(&mut self, pred: u32, nid: u32) -> PyResult<i32> {
        self.core.table_var(self.p, pred, nid)
    }

    fn aux(&mut self) -> i32 {
        self.core.st.borrow_mut().aux()
    }

    fn true_var(&self) -> Option<i32> {
        self.core.st.borrow().true_var
    }

    fn set_true_var(&mut self, v: i32) {
        self.core.st.borrow_mut().true_var = Some(v);
    }

    fn emit(&mut self, clause: Vec<i32>) -> PyResult<()> {
        if let Some(via) = &self.via {
            tick(EMIT_CB);
            via.call1((PyList::new(self.p, &clause)?,))?;
            return Ok(());
        }
        self.core.emit(self.p, &clause)
    }

    fn has_dv(&self) -> bool {
        self.use_dv
    }

    fn dv(&mut self, d: &Def, nid: u32, need: Need) -> PyResult<Option<i32>> {
        self.core.dvar_def(self.p, d, nid, None, need)
    }

    fn dv_basis(&mut self, pred: u32, nid: u32) -> PyResult<i32> {
        let v = self.core.table_var(self.p, pred, nid)?;
        if let Kind::Basis(i) = self.core.kind_of(self.p, pred) {
            self.core.link(self.p, &Rc::new((true, vec![i as i32 + 1])), nid, v)?;
        }
        Ok(v)
    }

    fn bad(&mut self, i: u32, literal: bool) -> PyErr {
        let what = if literal { "cannot make a literal from" } else { "cannot compile" };
        let shown = match self.core.bad.borrow().get(i as usize) {
            Some(o) => o.bind(self.p).repr().map(|r| r.to_string()).unwrap_or_default(),
            None => "_Lit".to_string(),
        };
        PyTypeError::new_err(format!("{what} {shown}"))
    }
}

#[pymethods]
impl SessionCore {
    #[new]
    fn new(p: Python<'_>, rules: PyRef<'_, SessionRules>, shell: Py<PyAny>) -> PyResult<Self> {
        NPRED.with(|n| n.set(rules.data.basis.len()));
        Ok(SessionCore {
            rules: rules.data.clone(),
            shell,
            serial: SERIAL.with(|c| {
                c.set(c.get() + 1);
                c.get()
            }),
            nids: PyDict::new(p).unbind(),
            objs: RefCell::new(vec![]),
            refused_object: Cell::new(false),
            bad: RefCell::new(vec![]),
            custom_ids: PyDict::new(p).unbind(),
            custom_preds: RefCell::new(vec![]),
            custom_exprs: RefCell::new(HashMap::new()),
            st: RefCell::new(St {
                base_of: vec![],
                base: vec![],
                slots: vec![Slot::Aux],
                new_nodes: vec![],
                custom: HashMap::new(),
                new_custom: vec![],
                naux: 0,
                true_var: None,
                defvars: HashMap::new(),
                dv: HashMap::new(),
                dv_node: HashMap::new(),
            }),
            solver: RefCell::new(None),
            session_xfer: RefCell::new(None),
            xfer: RefCell::new(vec![]),
            relc: RefCell::new(vec![]),
            relkeys: RefCell::new(RelKeys::default()),
            rels: RefCell::new(vec![]),
            ses: SesScalars::default(),
            sc: RefCell::new(Default::default()),
        })
    }

    /// State step, part 2 (ii): the session's solver, from `TableView.bind`.
    fn set_solver(&self, solver: &Bound<'_, PyAny>) -> PyResult<()> {
        let s = if crate::relations_core::planted(crate::relations_core::XF_SOLVER_FRESH) { solver.get_type().call0()? } else { solver.clone() };
        *self.solver.borrow_mut() = Some(s.unbind());
        Ok(())
    }

    /// The view `Session.xfer`.
    fn xfer_rel<'py>(&self, p: Python<'py>) -> Bound<'py, PyAny> {
        tick(XF_SESSION_VIEW);
        self.xfer_session(p).unwrap_or_else(|| p.None().into_bound(p))
    }

    /// The record method for `Session.xfer = v`: `Session.__init__`'s None, and Python's own `_engage_transfer`
    /// (SLICE_REL=py over this core). Rust's engagement doesn't come through here.
    fn set_xfer_rel(&self, v: &Bound<'_, PyAny>) {
        tick(XF_RECORD);
        *self.session_xfer.borrow_mut() = if v.is_none() { None } else { Some(v.clone().unbind()) };
    }

    /// The views `Relations.xfer` (0), `xfer_sel` (1) and `_xadapter` (2).
    fn xfer_field<'py>(&self, rel: &Bound<'py, PyAny>, k: usize) -> PyResult<Bound<'py, PyAny>> {
        tick(XF_REL_VIEW);
        let p = rel.py();
        if k > XAD {
            return Err(PyValueError::new_err("no such transfer field"));
        }
        if crate::relations_core::planted(crate::relations_core::XF_REL_VIEW_NONE) {
            return Ok(p.None().into_bound(p));
        }
        Ok(self.xfer_obj(rel, k))
    }

    /// The record method for `rel.xfer`/`xfer_sel`/`_xadapter = v`: Python's own `__init__` and `_engage_transfer`
    /// (SLICE_REL=py over this core), and tests that set them to drive a method.
    fn set_xfer_field(&self, rel: &Bound<'_, PyAny>, k: usize, v: &Bound<'_, PyAny>) -> PyResult<()> {
        tick(XF_RECORD);
        if k > XAD {
            return Err(PyValueError::new_err("no such transfer field"));
        }
        self.xfer_put(rel, k, Some(v));
        Ok(())
    }

    /// State part 3, sub-part 5: the views `Session.truncated` .. `verdict` (index into `SS_NAMES`).
    fn ses_field<'py>(&self, p: Python<'py>, k: usize) -> PyResult<Bound<'py, PyAny>> {
        tick(SB_SCALAR_VIEW);
        Ok(match k {
            0..=2 => PyBool::new(p, self.ses.flags[k].get()).to_owned().into_any(),
            3 | 4 => self.ses.ints[k - 3].get().into_pyobject(p)?.into_any(),
            5 => self.ses.verdict.borrow().as_ref().map_or_else(|| p.None().into_bound(p), |v| v.bind(p).clone()),
            _ => return Err(PyValueError::new_err("no such session scalar")),
        })
    }

    /// The record method for `s.truncated` .. `s.verdict = v`: Python's own `Session` methods over this core (SLICE_GLUE=py,
    /// SLICE_DISC=py), `_build_context`'s Python copy, and tests that set one to drive a method.
    fn set_ses_field(&self, k: usize, v: &Bound<'_, PyAny>) -> PyResult<()> {
        tick(SB_SCALAR_RECORD);
        match k {
            0..=2 => self.ses.flags[k].set(v.is_truthy()?),
            3 | 4 => self.ses.ints[k - 3].set(v.extract()?),
            5 => *self.ses.verdict.borrow_mut() = if v.is_none() { None } else { Some(v.clone().unbind()) },
            _ => return Err(PyValueError::new_err("no such session scalar")),
        }
        Ok(())
    }

    /// State part 3, sub-part 5: the view `Session.<SD_NAMES[k]>` (ses_cont.rs `SesDictView`).
    fn sc_dict(slf: &Bound<'_, Self>, k: usize) -> PyResult<crate::ses_cont::SesDictView> {
        tick(SC_VIEW);
        crate::ses_cont::dict_view(slf, k)
    }

    /// ... `Session.frontier` (0), `Session.deferred` (1).
    fn sc_seq(slf: &Bound<'_, Self>, k: usize) -> PyResult<crate::ses_cont::SesSeqView> {
        tick(SC_VIEW);
        crate::ses_cont::seq_view(slf, k)
    }

    /// The record methods behind an assignment to the attribute.
    fn sc_dict_replace(slf: &Bound<'_, Self>, k: usize, d: &Bound<'_, PyAny>) -> PyResult<()> {
        crate::ses_cont::dict_replace(slf, k, d)
    }

    fn sc_seq_replace(slf: &Bound<'_, Self>, k: usize, xs: &Bound<'_, PyAny>) -> PyResult<()> {
        crate::ses_cont::seq_replace(slf, k, xs)
    }

    /// Test-only snapshot export: the session's containers by name (dicts as dicts, sequences as lists).
    fn sc_snapshot<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyDict>> {
        crate::ses_cont::snapshot(slf)
    }

    /// Test-only snapshot export: the session's scalars by name.
    fn ses_snapshot<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let d = PyDict::new(p);
        for (k, n) in SS_NAMES.iter().enumerate() {
            match k {
                0..=2 => d.set_item(n, self.ses.flags[k].get())?,
                3 | 4 => d.set_item(n, self.ses.ints[k - 3].get())?,
                _ => d.set_item(n, self.ses.verdict.borrow().as_ref().map(|v| v.bind(p).clone()))?,
            }
        }
        Ok(d)
    }

    /// State step, part 2 (iii)(b): the views `Relations._xtcur` .. `_xsides_n` (index into `RC_NAMES`).
    fn relc_field(&self, rel: &Bound<'_, PyAny>, k: usize) -> PyResult<i64> {
        tick(RC_VIEW);
        if k >= RC_NAMES.len() {
            return Err(PyValueError::new_err("no such cursor"));
        }
        Ok(self.relc_get(rel, k))
    }

    /// The record method for `rel._xtcur` .. `_xsides_n = v`: Python's own `__init__` and methods (SLICE_REL=py over this
    /// core), and tests that set one to drive a method. `k = None` is `__init__`'s seven writes at once.
    #[pyo3(signature = (rel, k, v))]
    fn set_relc_field(&self, rel: &Bound<'_, PyAny>, k: Option<usize>, v: i64) -> PyResult<()> {
        tick(RC_RECORD);
        match k {
            None => self.relc_init(rel),
            Some(k) if k < RC_NAMES.len() => self.relc_put(rel, k, v),
            Some(_) => return Err(PyValueError::new_err("no such cursor")),
        }
        Ok(())
    }

    /// Test-only snapshot export: every `Relations`' cursors the core holds, as (rel, {name: value}), in first-seen order.
    /// State step part 2 (iii)(b), rest: the view `Relations.<RS_NAMES[k]>` (relkeys.rs `RelSetView`).
    fn rs_field(slf: &Bound<'_, Self>, rel: &Bound<'_, PyAny>, k: usize) -> PyResult<crate::relkeys::RelSetView> {
        tick(RS_VIEW);
        if k >= RS_NAMES.len() {
            return Err(PyValueError::new_err("no such set"));
        }
        Ok(crate::relkeys::rs_view(slf, rel, k))
    }

    /// The record method for `Relations.__init__`'s empty sets (Python's own `__init__` under SLICE_REL=py over this core).
    fn set_rs_init(&self, rel: &Bound<'_, PyAny>) {
        tick(RS_RECORD);
        self.rs_init(rel);
    }

    /// Test-only snapshot export: every `Relations`' moved sets, as (rel, {name: [members in insertion order]}).
    fn rs_snapshot<'py>(&self, p: Python<'py>) -> PyResult<Vec<(Bound<'py, PyAny>, Bound<'py, PyDict>)>> {
        let rels: Vec<Py<PyAny>> = self.rels.borrow().iter().map(|r| r.rel.clone_ref(p)).collect();
        rels.into_iter().map(|r| {
            let r = r.bind(p).clone();
            let d = PyDict::new(p);
            for (k, n) in RS_NAMES.iter().enumerate() {
                d.set_item(n, PyList::new(p, self.rs_items(p, &r, k))?)?;
            }
            Ok((r, d))
        }).collect()
    }

    /// The view `Relations.<RD_NAMES[k]>` (relkeys.rs `RelDictView`).
    fn rd_field(slf: &Bound<'_, Self>, rel: &Bound<'_, PyAny>, k: usize) -> PyResult<crate::relkeys::RelDictView> {
        tick(RD_VIEW);
        if k >= RD_NAMES.len() {
            return Err(PyValueError::new_err("no such dict"));
        }
        Ok(crate::relkeys::rd_view(slf, rel, k))
    }

    /// The record method for `rel.<RD_NAMES[k]> = d` (Python's own `__init__`, `top = {}`): the core's dict becomes `d`.
    fn set_rd(&self, rel: &Bound<'_, PyAny>, k: usize, d: &Bound<'_, PyAny>) -> PyResult<()> {
        tick(RD_RECORD);
        self.rd_clear(rel, k);
        let items = d.call_method0(intern!(d.py(), "items"))?;
        for kv in items.try_iter()? {
            let (key, v): (Bound<'_, PyAny>, Bound<'_, PyAny>) = kv?.extract()?;
            self.rd_set(rel, k, &key, &v)?;
        }
        Ok(())
    }

    /// Test-only snapshot export: every `Relations`' moved dicts, as (rel, {name: [(key, value) in insertion order]}).
    fn rd_snapshot<'py>(&self, p: Python<'py>) -> PyResult<Vec<(Bound<'py, PyAny>, Bound<'py, PyDict>)>> {
        let rels: Vec<Py<PyAny>> = self.rels.borrow().iter().map(|r| r.rel.clone_ref(p)).collect();
        rels.into_iter().map(|r| {
            let r = r.bind(p).clone();
            let d = PyDict::new(p);
            for (k, n) in RD_NAMES.iter().enumerate() {
                let items: Vec<Bound<'py, PyTuple>> = self.rd_items(p, &r, k).into_iter()
                    .map(|(a, b)| PyTuple::new(p, [a, b])).collect::<PyResult<_>>()?;
                d.set_item(n, PyList::new(p, items)?)?;
            }
            Ok((r, d))
        }).collect()
    }

    /// The view `Relations.<RL_NAMES[k]>` (relkeys.rs `RelListView`).
    fn rl_field(slf: &Bound<'_, Self>, rel: &Bound<'_, PyAny>, k: usize) -> PyResult<crate::relkeys::RelListView> {
        tick(RL_VIEW);
        if k >= RL_NAMES.len() {
            return Err(PyValueError::new_err("no such list"));
        }
        Ok(crate::relkeys::rl_view(slf, rel, k))
    }

    /// The record method for `rel.<RL_NAMES[k]> = xs` (Python's own `__init__`): the core's list becomes `xs`.
    fn set_rl(&self, rel: &Bound<'_, PyAny>, k: usize, xs: &Bound<'_, PyAny>) -> PyResult<()> {
        tick(RL_RECORD);
        let v: Vec<Bound<'_, PyAny>> = xs.try_iter()?.collect::<PyResult<_>>()?;
        self.rl_clear(rel, k);
        for x in v {
            self.rl_push(rel, k, &x);
        }
        Ok(())
    }

    /// Test-only snapshot export: every `Relations`' moved lists, as (rel, {name: [item, ...]}).
    fn rl_snapshot<'py>(&self, p: Python<'py>) -> PyResult<Vec<(Bound<'py, PyAny>, Bound<'py, PyDict>)>> {
        let rels: Vec<Py<PyAny>> = self.rels.borrow().iter().map(|r| r.rel.clone_ref(p)).collect();
        rels.into_iter().map(|r| {
            let r = r.bind(p).clone();
            let d = PyDict::new(p);
            for (k, n) in RL_NAMES.iter().enumerate() {
                d.set_item(n, PyList::new(p, self.rl_items(p, &r, k))?)?;
            }
            Ok((r, d))
        }).collect()
    }

    /// RelKeys' size: (keys, by term id, by hash, dict-only).
    fn rk_stats(&self) -> (usize, usize, usize, bool) {
        let k = self.relkeys.borrow();
        (k.objs.len(), k.by_term.len(), k.objs.len() - k.by_term.len(), k.dict_only)
    }

    fn relc_snapshot<'py>(&self, p: Python<'py>) -> PyResult<Vec<(Bound<'py, PyAny>, Bound<'py, PyDict>)>> {
        self.relc.borrow().iter().map(|x| {
            let d = PyDict::new(p);
            for (n, v) in RC_NAMES.iter().zip(x.c) {
                d.set_item(n, v)?;
            }
            Ok((x.rel.bind(p).clone(), d))
        }).collect()
    }

    /// The solver and the transfer records reach back to the shell through the theories.
    fn __traverse__(&self, visit: pyo3::PyVisit<'_>) -> Result<(), pyo3::PyTraverseError> {
        if crate::relations_core::planted(crate::relations_core::XF_TRAVERSE_SKIP) {
            return Ok(());
        }
        if let Ok(s) = self.solver.try_borrow() {
            if let Some(x) = &*s {
                visit.call(x)?;
            }
        }
        if let Ok(x) = self.session_xfer.try_borrow() {
            if let Some(x) = &*x {
                visit.call(x)?;
            }
        }
        if let Ok(v) = self.xfer.try_borrow() {
            for x in v.iter() {
                visit.call(&x.rel)?;
                for f in x.f.iter().flatten() {
                    visit.call(f)?;
                }
            }
        }
        if let Ok(v) = self.relc.try_borrow() {
            for x in v.iter() {
                visit.call(&x.rel)?;
            }
        }
        if let Ok(k) = self.relkeys.try_borrow() {
            for o in k.objs.iter() {
                visit.call(o)?;
            }
            if let Some(d) = &k.dict {
                visit.call(d)?;
            }
        }
        if let Ok(v) = self.rels.try_borrow() {
            for x in v.iter() {
                visit.call(&x.rel)?;
                for m in x.d.iter() {
                    for v in m.values() {
                        visit.call(v)?;
                    }
                }
                for l in x.l.iter() {
                    for v in l {
                        visit.call(v)?;
                    }
                }
            }
        }
        Ok(())
    }

    fn __clear__(&self) {
        if let Ok(mut s) = self.solver.try_borrow_mut() {
            *s = None;
        }
        if let Ok(mut x) = self.session_xfer.try_borrow_mut() {
            *x = None;
        }
        if let Ok(mut v) = self.xfer.try_borrow_mut() {
            v.clear();
        }
        if let Ok(mut v) = self.relc.try_borrow_mut() {
            v.clear();
        }
        if let Ok(mut k) = self.relkeys.try_borrow_mut() {
            *k = RelKeys::default();
        }
        if let Ok(mut v) = self.rels.try_borrow_mut() {
            v.clear();
        }
    }

    fn var(&self, pred: &Bound<'_, PyAny>, node: &Bound<'_, PyAny>) -> PyResult<i32> {
        tick(VAR);
        let p = pred.py();
        let (i, n) = (self.pred_id(p, pred)?, self.nid_of(node)?);
        self.var_id(p, i, n, node, || PyKeyError::new_err(pred.clone().unbind()))
    }

    #[pyo3(signature = (dn, need="both"))]
    fn dvar(&self, dn: &Bound<'_, PyAny>, need: &str) -> PyResult<Option<i32>> {
        tick(DVAR);
        let p = dn.py();
        if need == "basis" {
            let (i, e) = self.atom_fields(dn)?;
            let n = self.nid_of_atom(p, i, &e)?;
            self.custom_expr(i, n, &e);
            let mut cx = PyCx { core: self, p, via: None, use_dv: true };
            return cx.dv_basis(i, n).map(Some);
        }
        let (d, node): (Bound<'_, PyAny>, Bound<'_, PyAny>) = dn.extract()?;
        let (op, ls): (String, Vec<i32>) = d.extract()?;
        let need = match need {
            "pos" => Need::Pos,
            "neg" => Need::Neg,
            "posunit" => Need::PosUnit,
            "negunit" => Need::NegUnit,
            _ => Need::Both,
        };
        self.dvar_def(p, &Rc::new((op == "&", ls)), self.nid_of(&node)?, Some(&node), need)
    }

    /// `Session._link` as a Python caller calls it. The engine's own calls (from `var`, `dvar` and `_dvar`) are Rust's already.
    fn link_py(&self, d: &Bound<'_, PyAny>, node: &Bound<'_, PyAny>, v: i32) -> PyResult<()> {
        let (op, ls): (String, Vec<i32>) = d.extract()?;
        self.link(d.py(), &Rc::new((op == "&", ls)), self.nid_of(node)?, v)
    }

    /// `_dvar` as Python's `var` and tests call it.
    #[pyo3(signature = (d, node, need, link=false))]
    fn dvar_raw_py(&self, d: &Bound<'_, PyAny>, node: &Bound<'_, PyAny>, need: i32, link: bool) -> PyResult<i32> {
        tick(DVAR);
        let (op, ls): (String, Vec<i32>) = d.extract()?;
        self.dvar_raw(d.py(), &Rc::new((op == "&", ls)), self.nid_of(node)?, Some(node), need, link)
    }

    pub(crate) fn base_get(&self, node: &Bound<'_, PyAny>) -> PyResult<Option<i32>> {
        tick(NODE);
        Ok(self.known(node)?.map(|n| self.st.borrow().visited(n)).filter(|&b| b != 0))
    }

    /// `Session.node`'s path for a node not visited yet.
    pub(crate) fn visit(&self, node: &Bound<'_, PyAny>, demanded: &Bound<'_, PyAny>) -> PyResult<i32> {
        tick(NODE);
        let n = self.nid_of(node)?;
        self.visit_id(node, n, demanded)
    }

    /// `compile_formula`; false if Python has to compile it. `via`: the caller's `emit`, when it isn't `Session.emit`.
    #[pyo3(signature = (f, via, use_dv))]
    fn compile(&self, f: &Bound<'_, PyAny>, via: Option<Bound<'_, PyAny>>, use_dv: bool) -> PyResult<bool> {
        tick(COMPILE);
        let Some(r) = self.convert(f)? else { return Ok(false) };
        compile::compile(&r, &mut PyCx { core: self, p: f.py(), via, use_dv })?;
        Ok(true)
    }

    /// `formula_literal`; `None` if Python has to compile it.
    #[pyo3(signature = (f, via, use_dv))]
    fn literal(&self, f: &Bound<'_, PyAny>, via: Option<Bound<'_, PyAny>>, use_dv: bool) -> PyResult<Option<i32>> {
        tick(LITERAL);
        let Some(r) = self.convert(f)? else { return Ok(None) };
        compile::literal(&r, &mut PyCx { core: self, p: f.py(), via, use_dv }).map(Some)
    }

    // ---- `VarTable`'s surface, for the shell's view

    fn table_var_py(&self, a: &Bound<'_, PyAny>) -> PyResult<i32> {
        tick(TABLE);
        let (i, e) = self.atom_fields(a)?;
        let n = self.nid_of_atom(a.py(), i, &e)?;
        self.custom_expr(i, n, &e);
        self.table_var(a.py(), i, n)
    }

    fn aux(&self) -> i32 {
        tick(TABLE);
        self.st.borrow_mut().aux()
    }

    fn node_base(&self, node: &Bound<'_, PyAny>) -> PyResult<i32> {
        tick(TABLE);
        let n = self.nid_of(node)?;
        Ok(self.st.borrow_mut().node_base(n))
    }

    fn base_of_get(&self, node: &Bound<'_, PyAny>) -> PyResult<Option<i32>> {
        tick(TABLE);
        Ok(self.known(node)?.and_then(|n| self.st.borrow().base_of.get(n as usize).copied()).filter(|&b| b != 0))
    }

    fn custom_get(&self, a: &Bound<'_, PyAny>) -> PyResult<Option<i32>> {
        tick(TABLE);
        let (i, e) = self.atom_fields(a)?;
        let Some(n) = self.known(&e)? else { return Ok(None) };
        Ok(self.st.borrow().custom.get(&(i, n)).copied())
    }

    fn n_vars(&self) -> usize {
        tick(TABLE);
        self.st.borrow().slots.len() - 1
    }

    fn n_base(&self) -> usize {
        tick(TABLE);
        self.st.borrow().base.iter().filter(|&&b| b != 0).count()
    }

    fn naux(&self) -> u32 {
        self.st.borrow().naux
    }

    fn set_true_var(&self, v: i32) {
        tick(TABLE);
        self.st.borrow_mut().true_var = Some(v);
    }

    fn true_var(&self) -> Option<i32> {
        self.st.borrow().true_var
    }

    /// `slots[v]`: None, the custom atom, or `(node, base)`.
    fn slot<'py>(&self, p: Python<'py>, v: usize) -> PyResult<Bound<'py, PyAny>> {
        tick(TABLE);
        let s = self.st.borrow().slots[v];
        match s {
            Slot::Aux => Ok(p.None().into_bound(p)),
            Slot::Custom(i, n) => self.custom_atom(p, i, n),
            Slot::Block(n, b) => {
                let o = self.objs.borrow()[n as usize].clone_ref(p);
                Ok(PyTuple::new(p, [o.into_bound(p), b.into_pyobject(p)?.into_any()])?.into_any())
            }
        }
    }

    /// `atom(v)`.
    fn atom<'py>(&self, p: Python<'py>, v: usize) -> PyResult<Bound<'py, PyAny>> {
        let s = self.st.borrow().slots[v];
        match s {
            Slot::Aux => Ok(p.None().into_bound(p)),
            Slot::Custom(i, n) => self.custom_atom(p, i, n),
            Slot::Block(n, b) => self.make_atom(p, v as u32 - b as u32, n),
        }
    }

    fn new_nodes<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        tick(TABLE);
        let objs = self.objs.borrow();
        let st = self.st.borrow();
        PyList::new(p, st.new_nodes.iter().map(|&n| objs[n as usize].clone_ref(p)))
    }

    fn clear_new_nodes(&self) {
        tick(TABLE);
        self.st.borrow_mut().new_nodes.clear();
    }

    fn new_custom<'py>(&self, p: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        tick(TABLE);
        let got = self.st.borrow().new_custom.clone();
        let mut out = Vec::with_capacity(got.len());
        for (i, n) in got {
            out.push(self.custom_atom(p, i, n)?);
        }
        PyList::new(p, out)
    }

    fn clear_new_custom(&self) {
        tick(TABLE);
        self.st.borrow_mut().new_custom.clear();
    }

    fn has_new_custom(&self) -> bool {
        tick(TABLE);
        !self.st.borrow().new_custom.is_empty()
    }
}

thread_local! {
    /// Set only by `join_log.py`, a logging run for 5b's first item. It runs at a `join` and nowhere else.
    static JOIN_HOOK: RefCell<Option<Py<PyAny>>> = const { RefCell::new(None) };
}

fn log_join(session: usize, nid: u32, first: &Bound<'_, PyAny>, second: &Bound<'_, PyAny>) -> PyResult<()> {
    let hook = JOIN_HOOK.with(|h| h.borrow().as_ref().map(|f| f.clone_ref(first.py())));
    if let Some(f) = hook {
        f.bind(first.py()).call1((session, nid, first, second))?;
    }
    Ok(())
}

#[pyfunction]
fn set_join_hook(hook: Option<Py<PyAny>>) {
    JOIN_HOOK.with(|h| *h.borrow_mut() = hook);
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(set_join_hook, m)?)?;
    m.add_class::<SessionRules>()?;
    m.add_class::<SessionCore>()?;
    m.add_function(wrap_pyfunction!(sb_plant, m)?)?;
    m.add_function(wrap_pyfunction!(session_counts, m)?)
}
