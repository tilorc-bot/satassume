//! Component 5, step 5b: the id-to-term link, and C2a's `Relations` methods over the Rust session.
//!
//! **The link** answers "which of this query's term ids is this object", for a session's node. Nodes live for a session and
//! term ids for a query, and queries nest, so it can't be a column. It resolves the object passed, never the object a node's
//! slot holds, so a join's second object gets its own answer. It creates no node. It reads no row, so rows can fill later than
//! conversion; only positive answers are kept, since a later row could turn None into an id. None is an ordinary answer: that
//! read goes to Python's own function.
//!
//! **The methods** follow `satassume/relations.py` line for line, in its order of effects. What hasn't moved is a callback to
//! `rel`, and module attributes are read at each call because `term_live` and `lra_live` replace them. No table or session
//! borrow is held across a callback, since `Session.ensure` and discovery stay Python and come back in. A callback's exception
//! goes on up unchanged (`Uninterpreted`, the budget's); only this file's own failures become `TermFault`, which no handler on
//! the engine's path can turn into a quiet unknown.
use std::sync::atomic::{AtomicU16, Ordering::Relaxed};
use std::sync::{Arc, RwLock};

use pyo3::exceptions::{PyException, PyKeyError, PyValueError};
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyList, PySet, PyString, PyTuple};

use crate::adapters::{EufAdapter, LraAdapter};
use crate::relkeys::{RDict, RList, RSet};
use crate::session::{self, tick, SessionCore};
use crate::term::py::PyTermTable;

pub(crate) struct Hooks {
    term_live: Py<PyAny>,
    relations: Py<PyAny>,
    euf_adapter: Py<PyAny>,
    /// `session_live._fault(site, text)`: counts it and returns a `TermFault` to raise.
    fault: Py<PyAny>,
}

impl Hooks {
    pub(crate) fn term_live(&self) -> &Py<PyAny> {
        &self.term_live
    }
}

static HOOKS: RwLock<Option<Arc<Hooks>>> = RwLock::new(None);

/// An observer of `_interpret` and `_link` (moved_digest.py's mid-query samples), called as `f(rel, at)` on entry to
/// `rel_interpret` / `rel_link`, before any work, on whichever path reached them (called directly or through
/// session_live's wrapper). It only observes: the digest no longer replaces `Relations._interpret`/`_link`, so Rust keeps
/// its direct path (`sb:fwd_direct`) with the digest on (RULINGS 14, item 4g). Off unless `rel_observe(f)` set it.
static OBSERVING: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);
static OBSERVER: std::sync::Mutex<Option<Py<PyAny>>> = std::sync::Mutex::new(None);

#[pyfunction]
#[pyo3(signature = (f=None))]
fn rel_observe(f: Option<Py<PyAny>>) {
    OBSERVING.store(f.is_some(), Relaxed);
    *OBSERVER.lock().unwrap() = f;
}

fn observe(rel: &Bound<'_, PyAny>, at: &str) -> PyResult<()> {
    if !OBSERVING.load(Relaxed) {
        return Ok(());
    }
    let f = OBSERVER.lock().unwrap().as_ref().map(|f| f.clone_ref(rel.py()));
    if let Some(f) = f {
        f.call1(rel.py(), (rel, at))?;
    }
    Ok(())
}

/// Test plants: 1 `link-none`, every resolve answers None; 2, 3, 4 drop one clause each in `_order_sides`, `_order_infinite`,
/// `_trichotomy`. From 5 on, C2b's: one effect dropped in each moved method, and `fresh-skew` shifts numbering.
static PLANT: AtomicU16 = AtomicU16::new(0);
const LINK_NONE: u16 = 1;
const DROP_SIDES: u16 = 2;
const DROP_INFINITE: u16 = 3;
const DROP_TRICHOTOMY: u16 = 4;
const DROP_INTERPRET: u16 = 5;
const DROP_GUARD: u16 = 6;
const DROP_BOUND: u16 = 7;
const DROP_LINK: u16 = 8;
const DROP_SELECTOR: u16 = 9;
const DROP_EQ_INFINITY: u16 = 10;
const FRESH_NOT_INERT: u16 = 11;
const FRESH_SKEW: u16 = 12;
/// All of `_trichotomy` off, as a test patching Python's method does. `DROP_TRICHOTOMY` keeps its `ensure`s, vars and roles.
const SKIP_TRICHOTOMY: u16 = 13;
/// From here, C2c's: one effect dropped in each moved method.
const DROP_ADD_ROLE: u16 = 14;
const DROP_APPLY_ROLE: u16 = 15;
const DROP_CANDIDACY: u16 = 16;
const DROP_TSOURCE: u16 = 17;
const DROP_TVAR: u16 = 18;
const DROP_TVAR_MC: u16 = 19;
const DROP_ENGAGE: u16 = 20;
const DROP_TERMS: u16 = 21;
const DROP_TERMS_SIDE: u16 = 22;
const DROP_FIXED: u16 = 23;
const DROP_SYNC: u16 = 24;
const DROP_SYNC_POLAR: u16 = 25;
const DROP_XSWITCH: u16 = 26;
const DROP_CONGRUENCE: u16 = 27;
const CONGRUENT_NEVER: u16 = 28;
const SHARE_GUARD_ONE: u16 = 29;
/// From here, 5c1's (`discovery.rs`): one effect dropped in each moved `Session` method.
pub(crate) const DROP_ENSURE_DEMAND: u16 = 30;
pub(crate) const DROP_DISCOVER_FLUSH: u16 = 31;
pub(crate) const DROP_DISCOVER_VISIT: u16 = 32;
pub(crate) const DROP_ESC_PATTERN: u16 = 33;
pub(crate) const DROP_ESC_COMPILE: u16 = 34;
pub(crate) const DROP_ESC_DEFERRED: u16 = 35;
pub(crate) const TRUNCATED_NEVER: u16 = 36;
pub(crate) const INCOMPLETE_NEVER: u16 = 37;
/// From here, 5c2's (`compile_loop.rs`).
pub(crate) const DROP_SPLIT_LATER: u16 = 38;
pub(crate) const DROP_EMIT_MENT: u16 = 39;
pub(crate) const DROP_FLUSH_CUSTOM: u16 = 40;
pub(crate) const DROP_COMPILE_DEMAND: u16 = 41;
pub(crate) const DROP_PEND_COMPILE: u16 = 42;
pub(crate) const WANT_EMPTY: u16 = 43;
pub(crate) const DROP_PAT_DEMAND: u16 = 44;
pub(crate) const DROP_CUSTOM_REL: u16 = 45;
pub(crate) const DROP_CUSTOM_FACTS: u16 = 46;
pub(crate) const DROP_VISIT_ITEMS: u16 = 47;
pub(crate) const DROP_DV_LINK: u16 = 48;
pub(crate) const DROP_PREP_TWINS: u16 = 49;
pub(crate) const DROP_PREP_REL: u16 = 50;
pub(crate) const QUERY_LIT_TUPLE: u16 = 51;
pub(crate) const DROP_QL_MENTION: u16 = 52;
pub(crate) const QL_SKIP_CONSISTENT: u16 = 53;
pub(crate) const DROP_QA_MENTION: u16 = 54;
pub(crate) const DROP_LO_MEMO: u16 = 55;
pub(crate) const DROP_LO_DISCOVER: u16 = 56;
pub(crate) const DROP_REL_PROCESS: u16 = 57;
pub(crate) const DROP_EA_ENSURE: u16 = 58;
pub(crate) const DROP_TWINS_VAR: u16 = 59;
pub(crate) const DROP_EMIT: u16 = 60;
/// From here, 5c4's: one effect dropped in each moved `Relations` method. `skip-share` is the clause off as
/// `test_equality_sharing_is_needed_and_works` turns it off (`_share` and `_trichotomy` both patched away), for its replacement in
/// `test_relations_core.py`; `drop-share` removes sharing alone (the pairs are counted, no interface atom is made).
const DROP_INIT_ENGAGE: u16 = 61;
const DROP_ENQUEUE: u16 = 62;
const DROP_NOTE_TOP: u16 = 63;
const DROP_PROC_EQ_LINKS: u16 = 64;
const DROP_LINK_LATER: u16 = 65;
const WANTS_NEVER: u16 = 66;
const DROP_SHARE: u16 = 67;
const SKIP_SHARE: u16 = 68;
/// `drop-share` with `_trichotomy` off as well, so that sharing is the only route (the re-pointed test's real-specs case). One
/// plant is on at a time, hence one name for both. Test-only, like `skip-share`.
const DROP_SHARE_TRI: u16 = 69;
/// From here, 5c5's: one effect dropped or skewed in each of the five methods 5c4 left.
const ADAPTER_FRESH: u16 = 70;
const SELECTOR_NO_MEMO: u16 = 71;
const ATOM_VAR_SKEW: u16 = 72;
const DROP_NOTE_SIDES: u16 = 73;
const DROP_EQ_LINKS_ZERO: u16 = 74;
/// From here, 5c5's second part: one effect dropped or skewed in each of relations.py's module functions.
const OWN_TERM_FALSE: u16 = 75;
const CONSTANT_TERM_NEVER: u16 = 76;
const BASIS_ALL: u16 = 77;
const SYMPY_ATOM_SWAP: u16 = 78;
const ZERO_ARGS_EMPTY: u16 = 79;
const UNDER_OF_EMPTY: u16 = 80;
const ZERO_TWINS_FIRST: u16 = 81;
const GLUE_NO_TWINS: u16 = 82;
const GUARDED_NONE: u16 = 83;
const TERMS_OF_NO_ORDER: u16 = 84;
const LINK_OBJECTS_BARE: u16 = 85;
const CLOSED_UNITS_NONE: u16 = 86;
const WITH_CLOSED_SKIP: u16 = 87;
const SPECS_NO_EUF: u16 = 88;
const RELNAME_SWAP: u16 = 89;
/// Adapters step, part A: `spec_row` hands back a converted spec with `guarded` flipped on each memo hit.
const SPEC_ROW_FLIP: u16 = 90;
/// From here, step scope's (`scope_core.rs`): one effect dropped in each moved item of scope.py.
pub(crate) const SCOPE_LINKED_EMPTY: u16 = 91;
pub(crate) const LINKED_NO_REL: u16 = 92;
pub(crate) const SCOPE_NO_AFFINE: u16 = 93;
pub(crate) const THEORY_NO_ASSUME: u16 = 94;
pub(crate) const CUSTOM_NEVER: u16 = 95;
pub(crate) const EXT_SHALLOW: u16 = 96;
/// Step 5c6, one per moved `Session` method (`session_glue.rs`).
pub(crate) const INIT_NO_RELATIONS: u16 = 97;
pub(crate) const AF_DROP_RELATIONS: u16 = 98;
pub(crate) const LINK_SET_SKIP: u16 = 99;
pub(crate) const AL_DROP_DELTA: u16 = 100;
pub(crate) const SET_GLUE_NO_EMIT: u16 = 101;
pub(crate) const GROUP_SEL_NO_IMPL: u16 = 102;
pub(crate) const GLUE_OF_PLAIN: u16 = 103;
/// Adapters step, part B (adapters.rs): the Rust LRAAdapter's `register` leaves the atom's terms out of `_shared`.
pub(crate) const AD_LRA_SHARED: u16 = 104;
/// Adapters step, part B: the Rust EUFAdapter's `node_term` interns into `_terms`, so node terms become shared terms.
pub(crate) const AD_EUF_NODE: u16 = 105;
/// Adapters step, part B: `make_adapter` builds the other default adapter (EUF for LRA's spec and back).
const AD_KIND_SWAP: u16 = 106;
/// Adapters step, part B: the Rust EUFAdapter's `shared_terms` leaves out the last term interned.
pub(crate) const AD_EUF_SHARED: u16 = 107;
/// Adapters step, part C (payloads.rs): Rust `Negated` wraps its payload in a second `Negated`, so the negation cancels.
pub(crate) const PAY_NEG_TWICE: u16 = 108;
/// Adapters step, part C: Rust `Integral`'s offset is half a unit off.
pub(crate) const PAY_INT_OFFSET: u16 = 109;
/// Adapters step, part C: Rust `EqAtom` stores the opposite polarity.
pub(crate) const PAY_EQ_FLIP: u16 = 110;
/// Adapters step, part C2 (constfield.rs `pi_laurent_elem`, read by lra_cert.rs): an Element bound reads as its rational
/// part, its pi terms dropped (a wrong value, not None).
pub(crate) const CF_LAURENT_RATIONAL: u16 = 111;
/// Not plants: test_term_live.py's handler tests, at lra.rs's certificate handler, now that no Python is called inside it.
/// `pi_laurent_elem`'s caller raises TermRefuse once (then the plant is off), or ValueError on every call.
pub(crate) const CF_LAURENT_REFUSE: u16 = 112;
pub(crate) const CF_LAURENT_RAISE: u16 = 113;
/// Step 5c7, one per moved budget row (`budget.rs`). 111-113 are adapters C2's (cf-laurent-*).
pub(crate) const UNION_SKIP_OVERLAP: u16 = 114;
pub(crate) const WITHIN_NO_LINK: u16 = 115;
pub(crate) const OVER_BUDGET_NO_FLAG: u16 = 116;
pub(crate) const NOTE_BUDGET_KEEP_FLAG: u16 = 117;
/// Element._new step (term/py.rs `lra_memo`): a memo hit gives one more as a number (rhs, constant, or a side's first
/// coefficient): a wrong value, the entry still there.
pub(crate) const ELEM_MEMO_PLUS1: u16 = 118;
/// Element._new step (constfield.rs `PyElem`): `==` answers the opposite; `hash` is one off; `repr` writes `Element[`;
/// `Num::from_py` of the pyclass reads its negation.
pub(crate) const ELEM_EQ_FLIP: u16 = 119;
pub(crate) const ELEM_HASH_SKEW: u16 = 120;
pub(crate) const ELEM_REPR_BRACKET: u16 = 121;
pub(crate) const ELEM_FROM_NEG: u16 = 122;
/// Element._new step, part 2b (`_order_infinite`): a Rust Element coefficient's sign is read negated (a wrong value).
pub(crate) const REL_ELEM_SIGN_FLIP: u16 = 123;
// Step 5c8 (relevance.rs): one per moved method; `consistent-fault`
// raises a TermFault inside `_consistent`'s body, which must come out loud.
pub(crate) const CONST_BASE_NO_POW: u16 = 124;
pub(crate) const CONST_FREE_NO_MUL: u16 = 125;
pub(crate) const CLOSED_KEYS_NO_UNDEF: u16 = 126;
pub(crate) const EXPR_KEYS_CLOSED_SKIP: u16 = 127;
pub(crate) const ARG_KEYS_NO_CLOSED: u16 = 128;
pub(crate) const KEYS_EMPTY: u16 = 129;
pub(crate) const KEYS_REL_NO_FLAG: u16 = 130;
pub(crate) const BOOL_KEYS_OPAQUE_IN: u16 = 131;
pub(crate) const SIDES_KEYS_FIRST_ONLY: u16 = 132;
pub(crate) const SPLIT_NO_MERGE: u16 = 133;
pub(crate) const SPLIT_PART_FIRST: u16 = 134;
pub(crate) const RELEVANT_ASSUME_CONSISTENT: u16 = 135;
pub(crate) const VOCAB_NO_DERIVED: u16 = 136;
pub(crate) const PART_CONSISTENT_TRUE: u16 = 137;
pub(crate) const CONSISTENT_FAULT: u16 = 138;
pub(crate) const CONSISTENT_IGNORE_VERDICT: u16 = 139;
// Step 5c9a (memos.rs): 170-177; the 6g stack's plants sit below 170.
/// The registry view leaves `SPEC_ROWS` out (the inventory's planted bug: a table left out of the registry view).
pub(crate) const MEMO_VIEW_DROP: u16 = 170;
/// `ENCLOSURES`' view doesn't empty the map on `clear()`.
pub(crate) const MEMO_CLEAR_SKIP: u16 = 171;
/// Rust's `Table.restamp` empties the table but leaves the stamp.
pub(crate) const MEMO_RESTAMP_NO_STAMP: u16 = 172;
/// `Engine.transfer` read by Rust gives the opposite value.
pub(crate) const MEMO_SET_TRANSFER: u16 = 173;
/// `Engine.uninterpreted` read by Rust gives the other value.
pub(crate) const MEMO_SET_UNINTERP: u16 = 174;
/// `Engine.relation_specs` read by Rust gives `()`.
pub(crate) const MEMO_SET_RELSPECS: u16 = 175;
/// `Engine.extensions` read by Rust gives None.
pub(crate) const MEMO_SET_EXT: u16 = 176;
/// `SPEC_ROWS` is never emptied at its bound.
pub(crate) const MEMO_SPEC_UNBOUNDED: u16 = 177;
// Step 5c9b (procmemo.rs): 180-187.
/// `_SPLIT` isn't emptied at 100,000 (the inventory's planted bug, first half).
pub(crate) const PM_SPLIT_NO_FULL_CLEAR: u16 = 180;
/// `_SPLIT`'s view doesn't empty the map on `clear()` (the registry's clear; second half).
pub(crate) const PM_SPLIT_CLEAR_SKIP: u16 = 181;
/// `_WANT` answers from any entry of the same size.
pub(crate) const PM_WANT_KEY_LEN: u16 = 182;
/// `neighbourhood` leaves the predicate itself out.
pub(crate) const PM_NEIGH_NO_SELF: u16 = 183;
/// `_NEIGH` answers every index with its first entry.
pub(crate) const PM_NEIGH_MEMO_FIRST: u16 = 184;
/// A `_CLOSED` hit answers None.
pub(crate) const PM_CLOSED_HIT_NONE: u16 = 185;
/// `_SYMPY_ATOMS` answers a miss from an entry with the same `expr` and any `pred`.
pub(crate) const PM_ATOMS_KEY_EXPR: u16 = 186;
/// `_SPLIT`'s view isn't put in the registry (a moved table left out of the registry view).
pub(crate) const PM_VIEW_DROP: u16 = 187;
// Step 5c9c (engmemo.rs, budget.rs): 190-198.
/// `_qcones`' `clear()` leaves the map as it is (the inventory's planted bug: `_drop_cones` not clearing `_qcones` on a
/// settings change).
pub(crate) const EM_QCONES_CLEAR_SKIP: u16 = 190;
/// `_kids[k] = v` from Python's `_struct` is dropped.
pub(crate) const EM_KIDS_SET_DROP: u16 = 191;
/// `guarded_adapters` doesn't store what it built in `_glue_adapters`.
pub(crate) const EM_GLUE_NO_STORE: u16 = 192;
/// A `_xbasis` hit answers the map's first entry.
pub(crate) const EM_XBASIS_FIRST: u16 = 193;
/// `splits` isn't emptied at its `maxsize` (test only: 20,000).
pub(crate) const EM_SPLITS_NO_BOUND: u16 = 194;
/// `_query_cone` gives an empty `sums`.
pub(crate) const EM_QCONE_NO_SUMS: u16 = 195;
/// `_qcones`' key leaves `link` out.
pub(crate) const EM_QCONE_KEY_F: u16 = 196;
/// An assigned `AnswerMemo`'s `maxsize` is dropped (test only).
pub(crate) const EM_SLOT_NO_MAXSIZE: u16 = 197;
/// `relevant`'s `splits.put` is dropped.
pub(crate) const EM_SPLITS_PUT_DROP: u16 = 198;
/// Step 5c10a (factcache.rs). The inventory's planted bug, a put lost on a shared DictCache: `sync` compares the settings by
/// identity, so a second engine with equal settings empties what the first one put.
pub(crate) const FC_SHARED_SYNC_IS: u16 = 200;
/// `put` drops a new node.
pub(crate) const FC_PUT_NEW_DROP: u16 = 201;
/// `DictCache(maxsize)` ignores `maxsize`.
pub(crate) const FC_NEW_NO_MAXSIZE: u16 = 202;
/// `sync` keeps the store on another epoch.
pub(crate) const FC_SYNC_NO_CLEAR: u16 = 203;
/// `facts` gives only the node's first fact.
pub(crate) const FC_FACTS_FIRST: u16 = 204;
/// `get` ignores its default.
pub(crate) const FC_GET_NO_DEFAULT: u16 = 205;
/// `put` never empties a full store.
pub(crate) const FC_NO_BOUND: u16 = 206;
/// `put` drops a custom predicate's fact (the `custom_cache` container).
pub(crate) const FC_CUSTOM_PUT_DROP: u16 = 207;
/// The view leaves the last node out.
pub(crate) const FC_VIEW_DROP_LAST: u16 = 208;
/// The rollback keeps what the refused run added.
pub(crate) const FC_ROLLBACK_SKIP: u16 = 209;
/// `clear` keeps the store.
pub(crate) const FC_CLEAR_SKIP: u16 = 210;
/// `_verdict` kept across a settings change: its view's `clear` does nothing (the inventory's planted bug).
pub(crate) const CTX_VERDICT_CLEAR_SKIP: u16 = 211;
/// `_failed` kept across a clear.
pub(crate) const CTX_FAILED_CLEAR_SKIP: u16 = 212;
/// `_build_context_memoized` records no `Uninterpreted`.
pub(crate) const CTX_FAILED_NO_MEMO: u16 = 213;
/// `_verdict` never emptied at 20,000.
pub(crate) const CTX_VERDICT_NO_BOUND: u16 = 214;
/// `_context_session` returns an inconsistent set's session instead of raising.
pub(crate) const CTX_SESSION_INCONSISTENT_PASS: u16 = 215;
/// `_build_context` keeps the checked session when a theory gave up.
pub(crate) const CTX_BUILD_NO_FALLBACK: u16 = 216;
/// `_build_context` skips `link_set`.
pub(crate) const CTX_BUILD_NO_LINK: u16 = 217;
/// `verdict` builds a session for a set over the discovery budget.
pub(crate) const CTX_VERDICT_SKIP_BUDGET: u16 = 218;
/// `_complete_check` doesn't escalate an incomplete session.
pub(crate) const CTX_CHECK_NO_ESCALATE: u16 = 219;
/// `_complete_check` says consistent when a theory gave up, ran out, or the session is incomplete or truncated.
pub(crate) const CTX_CHECK_NO_TRUNCATED: u16 = 220;
/// `_complete_check` raises a ValueError (engine.py:1906's handler count moves).
pub(crate) const CTX_CHECK_RAISE: u16 = 221;
/// `_context_session` keeps the session in `_context_sessions`.
pub(crate) const CTX_SESSIONS_STORE: u16 = 222;
/// Step 5c10c (budget.rs cone rows, engmemo.rs slots 8-9). The inventory's planted bug: a node left in `_constructing`
/// (its `discard`, from `core_visit` or `_struct`, keeps the node).
pub(crate) const CN_DISCARD_SKIP: u16 = 223;
/// `_struct` gives weight 1 to a node with both compiled patterns and formulas.
pub(crate) const CONE_STRUCT_WEIGHT_ONE: u16 = 224;
/// `_cone_info` returns the cone of a walk that went over the budget as if it fit.
pub(crate) const CONE_INFO_OVER_FITS: u16 = 225;
/// `_drop_cones` leaves `_cones` as it is.
pub(crate) const CONE_DROP_SKIP_CONES: u16 = 226;
/// The `_cones` map drops a store.
pub(crate) const EM_CONES_STORE_DROP: u16 = 227;
/// `_struct` doesn't empty `_kids` at 200,000 entries (test_cones_core.py only).
pub(crate) const CONE_KIDS_NO_BOUND: u16 = 228;
/// `_cone_info` doesn't empty `_cones` at 100,000 entries (test_cones_core.py only).
pub(crate) const CONE_CONES_NO_BOUND: u16 = 229;
/// `_struct` skips the wide-sum guard (#180 C-WIDEADD).
pub(crate) const CONE_STRUCT_WIDE_SKIP: u16 = 230;
/// Step 5c10d (entry.rs, query entry and counters).
/// `is_` doesn't count a fact-cache hit in `stats`.
pub(crate) const ENT_IS_NO_HIT_COUNT: u16 = 231;
/// `is_many` counts one query fewer than it decides in its session.
pub(crate) const ENT_IS_MANY_QUERIES_SHORT: u16 = 232;
/// `_decide` doesn't escalate an incomplete session (goes to search).
pub(crate) const ENT_DECIDE_NO_ESCALATE: u16 = 233;
/// `_put_result` doesn't store the answer in the fact cache.
pub(crate) const ENT_PUT_RESULT_NO_PUT: u16 = 234;
/// `_is_custom` ignores the custom fact cache's facts.
pub(crate) const ENT_IS_CUSTOM_NO_HIT: u16 = 235;
/// `ask` doesn't clear `last_budget_limited` on entry.
pub(crate) const ENT_ASK_NO_CLEAR_FLAG: u16 = 236;
/// `_ask` doesn't count `theory_gave_up`.
pub(crate) const ENT_ASK_NO_GAVE_UP: u16 = 237;
/// `_check_version` doesn't sync the fact caches.
pub(crate) const ENT_CHECK_VERSION_NO_SYNC: u16 = 238;
/// `_settings_changed` doesn't clear the fact caches' stores.
pub(crate) const ENT_SETTINGS_NO_CLEAR: u16 = 239;
/// `_drop_set_memos` doesn't clear the answer memo.
pub(crate) const ENT_DROP_MEMOS_KEEP_ANSWERS: u16 = 240;
/// `_fresh_session` doesn't count the session.
pub(crate) const ENT_FRESH_NO_COUNT: u16 = 241;
/// The record method for sympy_api's cache hit is lost.
pub(crate) const ST_CACHE_HIT_DROP: u16 = 242;
/// The record method for sympy_api's relevant count is lost.
pub(crate) const ST_RELEVANT_DROP: u16 = 243;
/// `_consistent`'s count (relevance.rs) is lost.
pub(crate) const ST_CONSISTENCY_DROP: u16 = 244;
/// A scope miss is counted twice.
pub(crate) const ST_SCOPE_MISS_DOUBLE: u16 = 245;
/// The record method that clears `last_budget_limited` (sympy_api) doesn't.
pub(crate) const ST_CLEAR_FLAG_SKIP: u16 = 246;
/// The record method that keeps the constant's budget flag (sympy_api `_ask`) drops it.
pub(crate) const ST_KEEP_FLAG_DROP: u16 = 247;
/// The `stats` view lists `budget_limited` first (Python's order is the dict's).
pub(crate) const ST_VIEW_ORDER: u16 = 248;
/// The `last_budget_limited` view reads False always.
pub(crate) const ST_FLAG_VIEW_STALE: u16 = 249;
/// `_note_budget` counts `budget_limited` for an untruncated session.
pub(crate) const NOTE_BUDGET_COUNT: u16 = 250;
/// State step, part 1 (adapters.rs LraQuery): the slot's memo key drops the kind, so `interpret`'s result serves `order_sides`.
pub(crate) const AD_LRA_KIND_KEY: u16 = 251;
/// ... the slot isn't replaced when the query changes: the old table, ids and memo serve the new query.
pub(crate) const AD_LRA_SLOT_STALE: u16 = 252;
/// ... the memo key drops `GENERIC_CONSTANTS`: a flip inside a query is served the other flag's result.
pub(crate) const AD_LRA_FLAG_KEY: u16 = 253;
/// ... the patch guard is skipped: a patched `_memoized`/read function is bypassed.
pub(crate) const AD_LRA_PATCH_GUARD: u16 = 254;
/// ... the first two (term, coefficient) pairs of a result swap coefficients.
pub(crate) const AD_LRA_PAIR_SWAP: u16 = 255;
/// State step, part 2 (i) (adapters.rs `Reader.integer_form`): a side that isn't an `Expr` is read as the number row of its
/// value (an int as its `Integer`), not answered None as lra_adapter.integer_form's first line does.
pub(crate) const AD_LRA_NOT_EXPR: u16 = 256;
/// State step, part 2 (ii) (session.rs `SessionCore.xfer`/`solver`): `s.xfer` read from the core is None after engagement.
pub(crate) const XF_SESSION_NONE: u16 = 257;
/// ... a `Relations`' `xfer_sel` read from the core is None after engagement.
pub(crate) const XF_SEL_NONE: u16 = 258;
/// ... the record lookup ignores which `Relations` asks: the last engaged one's answers for any.
pub(crate) const XF_REL_ANY: u16 = 259;
/// ... the core keeps a fresh solver of the same class, not the session's.
pub(crate) const XF_SOLVER_FRESH: u16 = 260;
/// ... the Python views `Relations.xfer`/`xfer_sel`/`_xadapter` read None after engagement (Rust's reads unchanged).
pub(crate) const XF_REL_VIEW_NONE: u16 = 261;
/// ... the core's GC traversal skips the solver and the transfer records.
pub(crate) const XF_TRAVERSE_SKIP: u16 = 262;
/// State step part 2 (iii): `glue_objects_plain` leaves out `link_objects` of the sides (each side itself stays).
pub(crate) const GL_PLAIN_NO_LINK: u16 = 263;
/// State step part 2 (iii)(b) (session.rs `SessionCore.relc`): `_xterm`'s write is dropped, so transfer_terms walks every side again.
pub(crate) const RC_XTERM_STALE: u16 = 266;
/// ... `_xhseen`'s write is dropped, so sync_transfer never takes its early return.
pub(crate) const RC_HSEEN_STALE: u16 = 267;
/// ... sync_transfer writes `_xslot` one past the slots it scanned, so the next scan skips a slot.
pub(crate) const RC_XSLOT_SKIP: u16 = 268;
/// S2 (block.rs): a non-model in the generated table; another block's built models short by one; the generated table for
/// any block with nvars = NPRED; the clean-clause check skipped.
pub(crate) const RB_GEN_MODEL_FLIP: u16 = 320;
pub(crate) const RB_BUILT_MODEL_DROP: u16 = 321;
pub(crate) const RB_GEN_ANY: u16 = 322;
pub(crate) const RB_CHECK_SKIP: u16 = 323;

#[pyfunction]
fn rel_install(term_live: Py<PyAny>, relations: Py<PyAny>, euf_adapter: Py<PyAny>, fault: Py<PyAny>) {
    *HOOKS.write().unwrap() = Some(Arc::new(Hooks { term_live, relations, euf_adapter, fault }));
}

#[pyfunction]
fn rel_plant(name: Option<&str>) -> PyResult<()> {
    let v = match name {
        None => 0,
        Some("link-none") => LINK_NONE,
        Some("drop-order-sides") => DROP_SIDES,
        Some("drop-order-infinite") => DROP_INFINITE,
        Some("drop-trichotomy") => DROP_TRICHOTOMY,
        Some("drop-interpret") => DROP_INTERPRET,
        Some("drop-guard") => DROP_GUARD,
        Some("drop-bound") => DROP_BOUND,
        Some("drop-link") => DROP_LINK,
        Some("drop-selector") => DROP_SELECTOR,
        Some("drop-eq-infinity") => DROP_EQ_INFINITY,
        Some("fresh-not-inert") => FRESH_NOT_INERT,
        Some("fresh-skew") => FRESH_SKEW,
        Some("skip-trichotomy") => SKIP_TRICHOTOMY,
        Some("drop-add-role") => DROP_ADD_ROLE,
        Some("drop-apply-role") => DROP_APPLY_ROLE,
        Some("drop-candidacy") => DROP_CANDIDACY,
        Some("drop-tsource") => DROP_TSOURCE,
        Some("drop-tvar") => DROP_TVAR,
        Some("drop-tvar-mc") => DROP_TVAR_MC,
        Some("drop-engage") => DROP_ENGAGE,
        Some("drop-terms") => DROP_TERMS,
        Some("drop-terms-side") => DROP_TERMS_SIDE,
        Some("drop-fixed") => DROP_FIXED,
        Some("drop-sync") => DROP_SYNC,
        Some("drop-sync-polar") => DROP_SYNC_POLAR,
        Some("drop-xswitch") => DROP_XSWITCH,
        Some("drop-congruence") => DROP_CONGRUENCE,
        Some("congruent-never") => CONGRUENT_NEVER,
        Some("share-guard-one") => SHARE_GUARD_ONE,
        Some("drop-ensure-demand") => DROP_ENSURE_DEMAND,
        Some("drop-discover-flush") => DROP_DISCOVER_FLUSH,
        Some("drop-discover-visit") => DROP_DISCOVER_VISIT,
        Some("drop-esc-pattern") => DROP_ESC_PATTERN,
        Some("drop-esc-compile") => DROP_ESC_COMPILE,
        Some("drop-esc-deferred") => DROP_ESC_DEFERRED,
        Some("truncated-never") => TRUNCATED_NEVER,
        Some("incomplete-never") => INCOMPLETE_NEVER,
        Some("drop-split-later") => DROP_SPLIT_LATER,
        Some("drop-emit-ment") => DROP_EMIT_MENT,
        Some("drop-flush-custom") => DROP_FLUSH_CUSTOM,
        Some("drop-compile-demand") => DROP_COMPILE_DEMAND,
        Some("drop-pend-compile") => DROP_PEND_COMPILE,
        Some("want-empty") => WANT_EMPTY,
        Some("drop-pat-demand") => DROP_PAT_DEMAND,
        Some("drop-custom-rel") => DROP_CUSTOM_REL,
        Some("drop-custom-facts") => DROP_CUSTOM_FACTS,
        Some("drop-visit-items") => DROP_VISIT_ITEMS,
        Some("drop-dv-link") => DROP_DV_LINK,
        Some("drop-prep-twins") => DROP_PREP_TWINS,
        Some("drop-prep-rel") => DROP_PREP_REL,
        Some("query-lit-tuple") => QUERY_LIT_TUPLE,
        Some("drop-ql-mention") => DROP_QL_MENTION,
        Some("ql-skip-consistent") => QL_SKIP_CONSISTENT,
        Some("drop-qa-mention") => DROP_QA_MENTION,
        Some("drop-lo-memo") => DROP_LO_MEMO,
        Some("drop-lo-discover") => DROP_LO_DISCOVER,
        Some("drop-rel-process") => DROP_REL_PROCESS,
        Some("drop-ea-ensure") => DROP_EA_ENSURE,
        Some("drop-twins-var") => DROP_TWINS_VAR,
        Some("drop-emit") => DROP_EMIT,
        Some("drop-init-engage") => DROP_INIT_ENGAGE,
        Some("drop-enqueue") => DROP_ENQUEUE,
        Some("drop-note-top") => DROP_NOTE_TOP,
        Some("drop-proc-eq-links") => DROP_PROC_EQ_LINKS,
        Some("drop-link-later") => DROP_LINK_LATER,
        Some("wants-never") => WANTS_NEVER,
        Some("drop-share") => DROP_SHARE,
        Some("skip-share") => SKIP_SHARE,
        Some("drop-share-tri") => DROP_SHARE_TRI,
        Some("adapter-fresh") => ADAPTER_FRESH,
        Some("selector-no-memo") => SELECTOR_NO_MEMO,
        Some("atom-var-skew") => ATOM_VAR_SKEW,
        Some("drop-note-sides") => DROP_NOTE_SIDES,
        Some("drop-eq-links-zero") => DROP_EQ_LINKS_ZERO,
        Some("own-term-false") => OWN_TERM_FALSE,
        Some("constant-term-never") => CONSTANT_TERM_NEVER,
        Some("basis-all") => BASIS_ALL,
        Some("sympy-atom-swap") => SYMPY_ATOM_SWAP,
        Some("zero-args-empty") => ZERO_ARGS_EMPTY,
        Some("under-of-empty") => UNDER_OF_EMPTY,
        Some("zero-twins-first") => ZERO_TWINS_FIRST,
        Some("glue-no-twins") => GLUE_NO_TWINS,
        Some("guarded-none") => GUARDED_NONE,
        Some("terms-of-no-order") => TERMS_OF_NO_ORDER,
        Some("link-objects-bare") => LINK_OBJECTS_BARE,
        Some("closed-units-none") => CLOSED_UNITS_NONE,
        Some("with-closed-skip") => WITH_CLOSED_SKIP,
        Some("specs-no-euf") => SPECS_NO_EUF,
        Some("relname-swap") => RELNAME_SWAP,
        Some("spec-row-flip") => SPEC_ROW_FLIP,
        Some("scope-linked-empty") => SCOPE_LINKED_EMPTY,
        Some("linked-no-rel") => LINKED_NO_REL,
        Some("scope-no-affine") => SCOPE_NO_AFFINE,
        Some("theory-no-assume") => THEORY_NO_ASSUME,
        Some("custom-never") => CUSTOM_NEVER,
        Some("ext-shallow") => EXT_SHALLOW,
        Some("init-no-relations") => INIT_NO_RELATIONS,
        Some("af-drop-relations") => AF_DROP_RELATIONS,
        Some("link-set-skip") => LINK_SET_SKIP,
        Some("al-drop-delta") => AL_DROP_DELTA,
        Some("set-glue-no-emit") => SET_GLUE_NO_EMIT,
        Some("group-sel-no-impl") => GROUP_SEL_NO_IMPL,
        Some("glue-of-plain") => GLUE_OF_PLAIN,
        Some("ad-lra-shared") => AD_LRA_SHARED,
        Some("ad-euf-node") => AD_EUF_NODE,
        Some("ad-kind-swap") => AD_KIND_SWAP,
        Some("ad-euf-shared") => AD_EUF_SHARED,
        Some("pay-neg-twice") => PAY_NEG_TWICE,
        Some("pay-int-offset") => PAY_INT_OFFSET,
        Some("pay-eq-flip") => PAY_EQ_FLIP,
        Some("cf-laurent-rational") => CF_LAURENT_RATIONAL,
        Some("cf-laurent-refuse") => CF_LAURENT_REFUSE,
        Some("cf-laurent-raise") => CF_LAURENT_RAISE,
        Some("union-skip-overlap") => UNION_SKIP_OVERLAP,
        Some("within-no-link") => WITHIN_NO_LINK,
        Some("over-budget-no-flag") => OVER_BUDGET_NO_FLAG,
        Some("note-budget-keep-flag") => NOTE_BUDGET_KEEP_FLAG,
        Some("elem-memo-plus1") => ELEM_MEMO_PLUS1,
        Some("elem-eq-flip") => ELEM_EQ_FLIP,
        Some("elem-hash-skew") => ELEM_HASH_SKEW,
        Some("elem-repr-bracket") => ELEM_REPR_BRACKET,
        Some("elem-from-neg") => ELEM_FROM_NEG,
        Some("rel-elem-sign-flip") => REL_ELEM_SIGN_FLIP,
        Some("const-base-no-pow") => CONST_BASE_NO_POW,
        Some("const-free-no-mul") => CONST_FREE_NO_MUL,
        Some("closed-keys-no-undef") => CLOSED_KEYS_NO_UNDEF,
        Some("expr-keys-closed-skip") => EXPR_KEYS_CLOSED_SKIP,
        Some("arg-keys-no-closed") => ARG_KEYS_NO_CLOSED,
        Some("keys-empty") => KEYS_EMPTY,
        Some("keys-rel-no-flag") => KEYS_REL_NO_FLAG,
        Some("bool-keys-opaque-in") => BOOL_KEYS_OPAQUE_IN,
        Some("sides-keys-first-only") => SIDES_KEYS_FIRST_ONLY,
        Some("split-no-merge") => SPLIT_NO_MERGE,
        Some("split-part-first") => SPLIT_PART_FIRST,
        Some("relevant-assume-consistent") => RELEVANT_ASSUME_CONSISTENT,
        Some("vocab-no-derived") => VOCAB_NO_DERIVED,
        Some("part-consistent-true") => PART_CONSISTENT_TRUE,
        Some("consistent-fault") => CONSISTENT_FAULT,
        Some("consistent-ignore-verdict") => CONSISTENT_IGNORE_VERDICT,
        Some("memo-view-drop") => MEMO_VIEW_DROP,
        Some("memo-clear-skip") => MEMO_CLEAR_SKIP,
        Some("memo-restamp-no-stamp") => MEMO_RESTAMP_NO_STAMP,
        Some("memo-set-transfer") => MEMO_SET_TRANSFER,
        Some("memo-set-uninterp") => MEMO_SET_UNINTERP,
        Some("memo-set-relspecs") => MEMO_SET_RELSPECS,
        Some("memo-set-ext") => MEMO_SET_EXT,
        Some("memo-spec-unbounded") => MEMO_SPEC_UNBOUNDED,
        Some("pm-split-no-full-clear") => PM_SPLIT_NO_FULL_CLEAR,
        Some("pm-split-clear-skip") => PM_SPLIT_CLEAR_SKIP,
        Some("pm-want-key-len") => PM_WANT_KEY_LEN,
        Some("pm-neigh-no-self") => PM_NEIGH_NO_SELF,
        Some("pm-neigh-memo-first") => PM_NEIGH_MEMO_FIRST,
        Some("pm-closed-hit-none") => PM_CLOSED_HIT_NONE,
        Some("pm-atoms-key-expr") => PM_ATOMS_KEY_EXPR,
        Some("pm-view-drop") => PM_VIEW_DROP,
        Some("em-qcones-clear-skip") => EM_QCONES_CLEAR_SKIP,
        Some("em-kids-set-drop") => EM_KIDS_SET_DROP,
        Some("em-glue-no-store") => EM_GLUE_NO_STORE,
        Some("em-xbasis-first") => EM_XBASIS_FIRST,
        Some("em-splits-no-bound") => EM_SPLITS_NO_BOUND,
        Some("em-qcone-no-sums") => EM_QCONE_NO_SUMS,
        Some("em-qcone-key-f") => EM_QCONE_KEY_F,
        Some("em-slot-no-maxsize") => EM_SLOT_NO_MAXSIZE,
        Some("em-splits-put-drop") => EM_SPLITS_PUT_DROP,
        Some("fc-shared-sync-is") => FC_SHARED_SYNC_IS,
        Some("fc-put-new-drop") => FC_PUT_NEW_DROP,
        Some("fc-new-no-maxsize") => FC_NEW_NO_MAXSIZE,
        Some("fc-sync-no-clear") => FC_SYNC_NO_CLEAR,
        Some("fc-facts-first") => FC_FACTS_FIRST,
        Some("fc-get-no-default") => FC_GET_NO_DEFAULT,
        Some("fc-no-bound") => FC_NO_BOUND,
        Some("fc-custom-put-drop") => FC_CUSTOM_PUT_DROP,
        Some("fc-view-drop-last") => FC_VIEW_DROP_LAST,
        Some("fc-rollback-skip") => FC_ROLLBACK_SKIP,
        Some("fc-clear-skip") => FC_CLEAR_SKIP,
        Some("ctx-verdict-clear-skip") => CTX_VERDICT_CLEAR_SKIP,
        Some("ctx-failed-clear-skip") => CTX_FAILED_CLEAR_SKIP,
        Some("ctx-failed-no-memo") => CTX_FAILED_NO_MEMO,
        Some("ctx-verdict-no-bound") => CTX_VERDICT_NO_BOUND,
        Some("ctx-session-inconsistent-pass") => CTX_SESSION_INCONSISTENT_PASS,
        Some("ctx-build-no-fallback") => CTX_BUILD_NO_FALLBACK,
        Some("ctx-build-no-link") => CTX_BUILD_NO_LINK,
        Some("ctx-verdict-skip-budget") => CTX_VERDICT_SKIP_BUDGET,
        Some("ctx-check-no-escalate") => CTX_CHECK_NO_ESCALATE,
        Some("ctx-check-no-truncated") => CTX_CHECK_NO_TRUNCATED,
        Some("ctx-check-raise") => CTX_CHECK_RAISE,
        Some("ctx-sessions-store") => CTX_SESSIONS_STORE,
        Some("cn-discard-skip") => CN_DISCARD_SKIP,
        Some("cone-struct-weight-one") => CONE_STRUCT_WEIGHT_ONE,
        Some("cone-info-over-fits") => CONE_INFO_OVER_FITS,
        Some("cone-drop-skip-cones") => CONE_DROP_SKIP_CONES,
        Some("em-cones-store-drop") => EM_CONES_STORE_DROP,
        Some("cone-kids-no-bound") => CONE_KIDS_NO_BOUND,
        Some("cone-cones-no-bound") => CONE_CONES_NO_BOUND,
        Some("cone-struct-wide-skip") => CONE_STRUCT_WIDE_SKIP,
        Some("ent-is-no-hit-count") => ENT_IS_NO_HIT_COUNT,
        Some("ent-is-many-queries-short") => ENT_IS_MANY_QUERIES_SHORT,
        Some("ent-decide-no-escalate") => ENT_DECIDE_NO_ESCALATE,
        Some("ent-put-result-no-put") => ENT_PUT_RESULT_NO_PUT,
        Some("ent-is-custom-no-hit") => ENT_IS_CUSTOM_NO_HIT,
        Some("ent-ask-no-clear-flag") => ENT_ASK_NO_CLEAR_FLAG,
        Some("ent-ask-no-gave-up") => ENT_ASK_NO_GAVE_UP,
        Some("ent-check-version-no-sync") => ENT_CHECK_VERSION_NO_SYNC,
        Some("ent-settings-no-clear") => ENT_SETTINGS_NO_CLEAR,
        Some("ent-drop-memos-keep-answers") => ENT_DROP_MEMOS_KEEP_ANSWERS,
        Some("ent-fresh-no-count") => ENT_FRESH_NO_COUNT,
        Some("st-cache-hit-drop") => ST_CACHE_HIT_DROP,
        Some("st-relevant-drop") => ST_RELEVANT_DROP,
        Some("st-consistency-drop") => ST_CONSISTENCY_DROP,
        Some("st-scope-miss-double") => ST_SCOPE_MISS_DOUBLE,
        Some("st-clear-flag-skip") => ST_CLEAR_FLAG_SKIP,
        Some("st-keep-flag-drop") => ST_KEEP_FLAG_DROP,
        Some("st-view-order") => ST_VIEW_ORDER,
        Some("st-flag-view-stale") => ST_FLAG_VIEW_STALE,
        Some("note-budget-count") => NOTE_BUDGET_COUNT,
        Some("ad-lra-kind-key") => AD_LRA_KIND_KEY,
        Some("ad-lra-slot-stale") => AD_LRA_SLOT_STALE,
        Some("ad-lra-flag-key") => AD_LRA_FLAG_KEY,
        Some("ad-lra-patch-guard") => AD_LRA_PATCH_GUARD,
        Some("ad-lra-pair-swap") => AD_LRA_PAIR_SWAP,
        Some("ad-lra-not-expr") => AD_LRA_NOT_EXPR,
        Some("xf-session-none") => XF_SESSION_NONE,
        Some("xf-sel-none") => XF_SEL_NONE,
        Some("xf-rel-any") => XF_REL_ANY,
        Some("xf-solver-fresh") => XF_SOLVER_FRESH,
        Some("xf-rel-view-none") => XF_REL_VIEW_NONE,
        Some("xf-traverse-skip") => XF_TRAVERSE_SKIP,
        Some("gl-plain-no-link") => GL_PLAIN_NO_LINK,
        Some("rc-xterm-stale") => RC_XTERM_STALE,
        Some("rc-hseen-stale") => RC_HSEEN_STALE,
        Some("rc-xslot-skip") => RC_XSLOT_SKIP,
        Some("rb-gen-model-flip") => RB_GEN_MODEL_FLIP,
        Some("rb-built-model-drop") => RB_BUILT_MODEL_DROP,
        Some("rb-gen-any") => RB_GEN_ANY,
        Some("rb-check-skip") => RB_CHECK_SKIP,
        // (iii)(b) rest: `rs-<set>-drop` (relkeys.rs RS_PLANT0 + k, 269-277), the moved set's add a no-op
        Some(x) if x.starts_with("rs-") && x.ends_with("-drop") => {
            let n = &x[3..x.len() - 5];
            match crate::session::RS_NAMES.iter().position(|m| m.trim_start_matches('_') == n) {
                Some(k) => crate::relkeys::RS_PLANT0 + k as u16,
                None => return Err(PyValueError::new_err(format!("no plant {x}"))),
            }
        }
        // (iii)(b) rest: `rl-<list>-drop` (relkeys.rs RL_PLANT0 + k, 405-408), the moved list's push a no-op
        Some(x) if x.starts_with("rl-") && x.ends_with("-drop") => {
            let n = &x[3..x.len() - 5];
            match crate::session::RL_NAMES.iter().position(|m| m.trim_start_matches('_') == n) {
                Some(k) => crate::relkeys::RL_PLANT0 + k as u16,
                None => return Err(PyValueError::new_err(format!("no plant {x}"))),
            }
        }
        // (iii)(b) rest: `rd-<dict>-drop` (relkeys.rs RD_PLANT0 + k, 390-404), the moved dict's set a no-op
        Some(x) if x.starts_with("rd-") && x.ends_with("-drop") => {
            let n = &x[3..x.len() - 5];
            match crate::session::RD_NAMES.iter().position(|m| m.trim_start_matches('_') == n) {
                Some(k) => crate::relkeys::RD_PLANT0 + k as u16,
                None => return Err(PyValueError::new_err(format!("no plant {x}"))),
            }
        }
        Some(x) => return Err(PyValueError::new_err(format!("no plant {x}"))),
    };
    PLANT.store(v, Relaxed);
    Ok(())
}

/// `relations`' package, for adapters.rs to find its modules; None before `rel_install`.
pub(crate) fn relations_package(p: Python<'_>) -> Option<String> {
    let h = HOOKS.read().unwrap().clone()?;
    h.relations.bind(p).getattr(intern!(p, "__package__")).ok()?.extract().ok()
}

/// Whether `rel_install` has run (relations on Rust); budget.rs keeps Python's `glue_objects` before it (SLICE_REL=py).
pub(crate) fn installed() -> bool {
    HOOKS.read().unwrap().is_some()
}

pub(crate) fn hooks() -> PyResult<Arc<Hooks>> {
    HOOKS.read().unwrap().clone().ok_or_else(|| PyException::new_err("relations_core: rel_install hasn't run"))
}

/// This file's own failure, as a `TermFault`.
fn fault(p: Python<'_>, h: &Hooks, site: &str, text: String) -> PyErr {
    match h.fault.bind(p).call1((site, text)) {
        Ok(x) => PyErr::from_value(x),
        Err(e) => e,
    }
}

/// An ordinary exception from a term read or from reaching the session becomes a fault; a `BaseException` goes on up as itself.
fn faulted<T>(p: Python<'_>, h: &Hooks, site: &str, r: PyResult<T>) -> PyResult<T> {
    r.map_err(|e| if e.is_instance_of::<PyException>(p) { fault(p, h, site, e.to_string()) } else { e })
}

/// A resolved term: the query's table and the id in it.
pub(crate) struct Linked<'py> {
    pub(crate) table: Bound<'py, PyTermTable>,
    pub(crate) id: u32,
}

/// The current query's term id for the object `x`, or None. See the file's header.
pub(crate) fn term_of<'py>(c: &SessionCore, h: &Hooks, x: &Bound<'py, PyAny>) -> PyResult<Option<Linked<'py>>> {
    let p = x.py();
    tick(session::LINK_CALLS);
    if PLANT.load(Relaxed) == LINK_NONE {
        tick(session::LINK_NONE);
        tick(session::REL_PLANT);
        return Ok(None);
    }
    let tl = h.term_live.bind(p);
    tick(session::LINK_CROSS_CURRENT);
    let q = faulted(p, h, "link", tl.call_method0(intern!(p, "current")))?;
    if q.is_none() || !faulted(p, h, "link", q.getattr(intern!(p, "kept")))?.is_none() {
        tick(session::LINK_NO_TABLE);
        return Ok(None);
    }
    let table = faulted(p, h, "link", q.getattr(intern!(p, "table")).and_then(|t| t.cast_into::<PyTermTable>().map_err(Into::into)))?;
    tick(session::LINK_CROSS_HASH);
    let nid = faulted(p, h, "link", c.node_quiet(x))?;
    match nid {
        Some(n) => {
            let held = table.try_borrow().map_err(|e| fault(p, h, "link", e.to_string()))?.link_get(c.serial, n, x);
            match held {
                Ok(Some(id)) => {
                    tick(session::LINK_HIT);
                    return Ok(Some(Linked { table, id }));
                }
                Ok(None) => {}
                Err(()) => tick(session::LINK_SECOND),
            }
        }
        None => tick(session::LINK_NO_NODE),
    }
    // Python's one rule, including that a row counts only for its own class. It may add a row, so no borrow is held.
    tick(session::LINK_CROSS_TERM_ID);
    let got = faulted(p, h, "link", tl.call_method1(intern!(p, "term_id"), (&q, x, intern!(p, "link"))))?;
    if got.is_none() {
        tick(session::LINK_NONE);
        return Ok(None);
    }
    let id: u32 = faulted(p, h, "link", got.extract().map_err(Into::into))?;
    tick(session::LINK_RESOLVED);
    if let Some(n) = nid {
        table.try_borrow_mut().map_err(|e| fault(p, h, "link", e.to_string()))?.link_put(c.serial, n, x, id);
    }
    Ok(Some(Linked { table, id }))
}

fn read<'py, T>(p: Python<'py>, h: &Hooks, l: &Linked<'py>, f: impl FnOnce(&PyTermTable, u32) -> T) -> PyResult<T> {
    let t = l.table.try_borrow().map_err(|e| fault(p, h, "link-read", e.to_string()))?;
    Ok(f(&t, l.id))
}

/// `rel.session`, and the core under it.
fn session_of<'py>(p: Python<'py>, h: &Hooks, rel: &Bound<'py, PyAny>) -> PyResult<(Bound<'py, PyAny>, Bound<'py, SessionCore>)> {
    let s = rel.getattr(intern!(p, "session"))?;
    let c = faulted(
        p,
        h,
        "session",
        // the core from the session's plain attribute, not the `table` property (a Python frame per read)
        session::core_of(&s),
    )?;
    Ok((s, c))
}

/// `s.ensure(e, {preds})`: a real set in the literal's order, since discovery may read its order.
fn ensure(s: &Bound<'_, PyAny>, e: &Bound<'_, PyAny>, preds: &[&str]) -> PyResult<()> {
    let p = s.py();
    s.call_method1(intern!(p, "ensure"), (e, PySet::new(p, preds)?))?;
    Ok(())
}

fn is_number(c: &SessionCore, h: &Hooks, e: &Bound<'_, PyAny>) -> PyResult<bool> {
    let p = e.py();
    match term_of(c, h, e)? {
        Some(l) => read(p, h, &l, |t, i| t.read_is_number(i)),
        None => h.relations.bind(p).getattr(intern!(p, "_is_number"))?.call1((e,))?.is_truthy(),
    }
}

/// `_closed_extended_real`: True, False, None, or what `Engine.is_` said.
fn closed_extended_real<'py>(rel: &Bound<'py, PyAny>, s: &Bound<'py, PyAny>, c: &SessionCore, h: &Hooks, e: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let p = rel.py();
    tick(session::REL_CLOSED);
    let yes = || PyBool::new(p, true).to_owned().into_any();
    let no = || PyBool::new(p, false).to_owned().into_any();
    let none = || p.None().into_bound(p);
    match term_of(c, h, e)? {
        Some(l) => {
            let (rational, number, nan) = read(p, h, &l, |t, i| (t.read_is_rational(i), t.read_is_number(i), t.read_is_nan(i)))?;
            if rational {
                return Ok(yes());
            }
            if !number {
                return Ok(none());
            }
            if nan {
                return Ok(no());
            }
        }
        None => {
            // `getattr(e, "is_Rational", False)`
            if let Some(v) = e.getattr_opt(intern!(p, "is_Rational"))? {
                if v.is_truthy()? {
                    return Ok(yes());
                }
            }
            let r = h.relations.bind(p);
            if !r.getattr(intern!(p, "_is_number"))?.call1((e,))?.is_truthy()? {
                return Ok(none());
            }
            if e.is(&p.import(intern!(p, "sympy"))?.getattr(intern!(p, "S"))?.getattr(intern!(p, "NaN"))?) {
                return Ok(no());
            }
        }
    }
    s.getattr(intern!(p, "engine"))?.call_method1(intern!(p, "is_"), (e, intern!(p, "extended_real")))
}

#[pyfunction]
fn rel_closed_extended_real<'py>(rel: &Bound<'py, PyAny>, e: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let h = hooks()?;
    let (s, c) = session_of(rel.py(), &h, rel)?;
    closed_extended_real(rel, &s, &c.borrow(), &h, e)
}

#[pyfunction]
fn rel_order_sides<'py>(rel: &Bound<'py, PyAny>, var: i32, atom: &Bound<'py, PyAny>) -> PyResult<bool> {
    let p = rel.py();
    tick(session::REL_ORDER_SIDES);
    let h = hooks()?;
    let (s, c) = session_of(p, &h, rel)?;
    let c = c.borrow();
    let mut need = vec![];
    for e in atom.getattr(intern!(p, "expr"))?.try_iter()? {
        let e = e?;
        let v = closed_extended_real(rel, &s, &c, &h, &e)?;
        if v.is(PyBool::new(p, false)) {
            c.emit_direct(p, &[-var])?;
            return Ok(true);
        }
        if v.is_none() {
            need.push(e);
        }
    }
    for e in need {
        ensure(&s, &e, &["extended_real"])?;
        let v = c.var_direct(intern!(p, "extended_real").as_any(), &e)?;
        if PLANT.load(Relaxed) == DROP_SIDES {
            tick(session::REL_PLANT);
            continue;
        }
        c.emit_direct(p, &[-var, v])?;
    }
    Ok(false)
}

/// Exactly two items, as `a, b = x` unpacks them.
fn two<'py>(x: &Bound<'py, PyAny>) -> PyResult<(Bound<'py, PyAny>, Bound<'py, PyAny>)> {
    let mut v = x.try_iter()?.collect::<PyResult<Vec<_>>>()?;
    if v.len() != 2 {
        return Err(PyValueError::new_err(format!("expected 2 values to unpack, got {}", v.len())));
    }
    let b = v.pop().unwrap();
    Ok((v.pop().unwrap(), b))
}

#[pyfunction]
fn rel_order_infinite<'py>(rel: &Bound<'py, PyAny>, var: i32, sides: &Bound<'py, PyAny>) -> PyResult<()> {
    let p = rel.py();
    tick(session::REL_ORDER_INFINITE);
    let h = hooks()?;
    let (s, c) = session_of(p, &h, rel)?;
    let c = c.borrow();
    let r = h.relations.bind(p);
    let fraction = r.getattr(intern!(p, "Fraction"))?;
    let (pos, neg, ext_real) = (intern!(p, "positive_infinite"), intern!(p, "negative_infinite"), intern!(p, "extended_real"));
    let mut push: Vec<(Vec<i32>, Vec<i32>, bool, bool)> = vec![];
    let mut ext = vec![];
    let mut exact = true;
    // A real set: `==` joins here as it does in Python's.
    let seen = PySet::empty(p)?;
    for side in sides.try_iter()? {
        let (form, inf) = two(&side?)?;
        let (mut up, mut down) = (vec![], vec![]);
        for item in form.call_method0(intern!(p, "items"))?.try_iter()? {
            let (u, co) = two(&item?)?;
            if is_number(&c, &h, &u)? {
                continue;
            }
            let (nonzero, positive) = if co.get_type().is(&fraction) {
                (co.is_truthy()?, co.gt(0)?)
            } else if let Ok(pe) = co.cast::<crate::constfield::PyElem>() {
                // The Rust Element (an lra_* memo coefficient): its sign on Rust, as Python's `sign` gives Element.sign().
                tick(session::REL_ELEM_SIGN);
                match crate::constfield::Num::E(pe.borrow().e.clone()).sign() {
                    Ok(sg) if plant_on(REL_ELEM_SIGN_FLIP) => (sg != 0, sg < 0),
                    Ok(sg) => (sg != 0, sg > 0),
                    Err(e) if e.is_undecided() => return Ok(()),
                    Err(e) => return Err(e.into()),
                }
            } else {
                match r.getattr(intern!(p, "sign"))?.call1((&co,)) {
                    Ok(sg) => (sg.is_truthy()?, sg.gt(0)?),
                    // Unknown sign: no clauses 2. What `ensure` and `var` did for earlier terms stays.
                    Err(e) if e.is_instance(p, &r.getattr(intern!(p, "Undecided"))?) => return Ok(()),
                    Err(e) => return Err(e),
                }
            };
            if !nonzero {
                exact = false;
                continue;
            }
            ensure(&s, &u, &["extended_real", "positive_infinite", "negative_infinite"])?;
            let (a, b) = (c.var_direct(pos.as_any(), &u)?, c.var_direct(neg.as_any(), &u)?);
            if positive {
                up.push(a);
                down.push(b);
            } else {
                down.push(a);
                up.push(b);
            }
            if !seen.contains(&u)? {
                seen.add(&u)?;
                ext.push(-c.var_direct(ext_real.as_any(), &u)?);
            }
        }
        push.push((up, down, inf.gt(0)?, inf.lt(0)?));
    }
    if push.len() != 2 {
        return Err(PyValueError::new_err(format!("expected 2 sides, got {}", push.len())));
    }
    let (up_b, down_b, cup_b, cdown_b) = push.pop().unwrap();
    let (up_a, down_a, cup_a, cdown_a) = push.pop().unwrap();
    if cup_a || cdown_b {
        return c.emit_direct(p, &[-var]);
    }
    for &l in &up_a {
        if PLANT.load(Relaxed) == DROP_INFINITE {
            tick(session::REL_PLANT);
            continue;
        }
        c.emit_direct(p, &[-l, -var])?;
    }
    for &l in &down_b {
        c.emit_direct(p, &[-l, -var])?;
    }
    if !exact {
        return Ok(());
    }
    let rest: Vec<i32> = up_a.iter().chain(&down_b).chain(&ext).copied().chain([var]).collect();
    if cdown_a {
        c.emit_direct(p, &rest)?;
    } else {
        for &l in &down_a {
            let mut cl = vec![-l];
            cl.extend(&rest);
            c.emit_direct(p, &cl)?;
        }
    }
    let rest: Vec<i32> = down_b.iter().chain(&up_a).chain(&ext).copied().chain([var]).collect();
    if cup_b {
        c.emit_direct(p, &rest)?;
    } else {
        for &l in &up_b {
            let mut cl = vec![-l];
            cl.extend(&rest);
            c.emit_direct(p, &cl)?;
        }
    }
    Ok(())
}

#[pyfunction]
fn rel_trichotomy<'py>(rel: &Bound<'py, PyAny>, var: i32, atom: &Bound<'py, PyAny>) -> PyResult<()> {
    let p = rel.py();
    tick(session::REL_TRICHOTOMY);
    if matches!(PLANT.load(Relaxed), SKIP_TRICHOTOMY | SKIP_SHARE | DROP_SHARE_TRI) {
        tick(session::REL_PLANT);
        return Ok(());
    }
    let h = hooks()?;
    let (s, c) = session_of(p, &h, rel)?;
    let c = c.borrow();
    let r = h.relations.bind(p);
    let (a, b) = two(&atom.getattr(intern!(p, "expr"))?)?;
    let args = r.getattr(intern!(p, "Args"))?.call1((PyTuple::new(p, [&b, &a])?,))?;
    let rev = r.getattr(intern!(p, "P"))?.call1((intern!(p, "lt"), args))?;
    let Some(rvar) = c.custom_direct(&rev)? else { return Ok(()) };
    let lk = RDict::of(rel, crate::session::RD_LINK_LT)?;
    let la = lk.get(atom)?;
    if !la.is_none() && la.is(&lk.get(&rev)?) {
        return Ok(());
    }
    let eqa = r.getattr(intern!(p, "relation_atom"))?.call1((intern!(p, "eq"), &a, &b))?;
    if c.custom_direct(&eqa)?.is_none() {
        RSet::of(rel, session::RS_AUX_EQ)?.add(&eqa)?;
    }
    let eq: i32 = rel.call_method1(intern!(p, "_atom_var"), (&eqa,))?.extract()?;
    rel.call_method1(intern!(p, "_note_sides"), (&eqa, 2))?;
    let sel_a: i32 = rel.call_method1(intern!(p, "_atom_selector"), (atom,))?.extract()?;
    let sel_r: i32 = rel.call_method1(intern!(p, "_atom_selector"), (&rev,))?.extract()?;
    let both = [-sel_a, -sel_r];
    // A list of its own: `_add_role` keeps it.
    Cx { rel, s: &s, c: &c, h: &h }.add_role(&eqa, PyList::new(p, both)?.as_any(), intern!(p, "tri").as_any())?;
    let mut clause = vec![both[0], both[1], var, rvar, eq];
    for e in r.getattr(intern!(p, "_ext_atoms"))?.call1((&a, &b))?.try_iter()? {
        let x = e?.getattr(intern!(p, "expr"))?;
        ensure(&s, &x, &["extended_real"])?;
        clause.push(-c.var_direct(intern!(p, "extended_real").as_any(), &x)?);
    }
    if PLANT.load(Relaxed) == DROP_TRICHOTOMY {
        tick(session::REL_PLANT);
        return Ok(());
    }
    c.emit_direct(p, &clause)
}

#[pyfunction]
fn rel_mention_number<'py>(rel: &Bound<'py, PyAny>, e: &Bound<'py, PyAny>) -> PyResult<()> {
    let p = rel.py();
    tick(session::REL_MENTION);
    let h = hooks()?;
    let num_sel = RDict::of(rel, crate::session::RD_NUM_SEL)?;
    if num_sel.contains(e)? {
        return Ok(());
    }
    let (s, c) = session_of(p, &h, rel)?;
    let c = c.borrow();
    let structural = match term_of(&c, &h, e)? {
        Some(l) => read(p, &h, &l, |t, i| t.read_structural(i))?,
        None => h.euf_adapter.bind(p).getattr(intern!(p, "structural"))?.call1((e,))?.is_truthy()?,
    };
    if !structural {
        return Ok(());
    }
    let sel = fresh(&s, &c, true)?;
    num_sel.set_item(e, sel)?;
    Cx { rel, s: &s, c: &c, h: &h }.tsource(e, IE, PyList::new(p, [-sel])?.as_any())?;
    RList::of(rel, session::RL_XEXTRA)?.push(e)?;
    Ok(())
}

#[pyfunction]
fn rel_link_integer<'py>(rel: &Bound<'py, PyAny>, ad: &Bound<'py, PyAny>, e: &Bound<'py, PyAny>, g: i32) -> PyResult<()> {
    let p = rel.py();
    tick(session::REL_LINK_INTEGER);
    let h = hooks()?;
    let form = ad.call_method1(intern!(p, "integer_form"), (e,))?;
    if form.is_none() {
        return Ok(());
    }
    let (s, c) = session_of(p, &h, rel)?;
    let c = c.borrow();
    let i = fresh(&s, &c, false)?;
    ad.call_method1(intern!(p, "register_integer"), (crate::session::solver_of(&s)?, i, &form))?;
    let guard: Vec<i32> = guard(rel, &s, &c, &h, ad, &form.get_item(1)?)?.extract()?;
    let z = c.var_direct(intern!(p, "integer").as_any(), e)?;
    let with = |x: [i32; 3]| guard.iter().copied().chain(x).collect::<Vec<i32>>();
    c.emit_direct(p, &with([-z, i, g]))?;
    c.emit_direct(p, &with([z, -i, g]))
}

/// `_fresh`.
fn fresh(s: &Bound<'_, PyAny>, c: &SessionCore, inert: bool) -> PyResult<i32> {
    let p = s.py();
    tick(session::REL_FRESH);
    let mut v = c.aux_direct();
    if PLANT.load(Relaxed) == FRESH_SKEW {
        tick(session::REL_PLANT);
        v = c.aux_direct();
    }
    c.ensure_vars_direct(p, v)?;
    if inert {
        if PLANT.load(Relaxed) == FRESH_NOT_INERT {
            tick(session::REL_PLANT);
        } else {
            crate::session::solver_of(&s)?.call_method1(intern!(p, "set_inert"), (v,))?;
        }
    }
    Ok(v)
}

#[pyfunction]
#[pyo3(signature = (rel, inert=false))]
fn rel_fresh(rel: &Bound<'_, PyAny>, inert: bool) -> PyResult<i32> {
    let h = hooks()?;
    let (s, c) = session_of(rel.py(), &h, rel)?;
    fresh(&s, &c.borrow(), inert)
}

/// `_bound`. What `register_bounds` returns is read as it's emitted, as Python's `for` does.
fn bound(rel: &Bound<'_, PyAny>, s: &Bound<'_, PyAny>, c: &SessionCore, ad: &Bound<'_, PyAny>, u: &Bound<'_, PyAny>) -> PyResult<()> {
    let p = rel.py();
    tick(session::REL_BOUND);
    let Some(register) = ad.getattr_opt(intern!(p, "register_bounds"))? else { return Ok(()) };
    if register.is_none() {
        return Ok(());
    }
    // A bound method, so the adapter can call it as Python's would; `session_live` routes it back here.
    let vs = register.call1((crate::session::solver_of(&s)?, u, rel.getattr(intern!(p, "_fresh"))?))?;
    for v in vs.try_iter()? {
        let v: i32 = v?.extract()?;
        if PLANT.load(Relaxed) == DROP_BOUND {
            tick(session::REL_PLANT);
            continue;
        }
        c.emit_direct(p, &[v])?;
    }
    Ok(())
}

#[pyfunction]
fn rel_bound(rel: &Bound<'_, PyAny>, ad: &Bound<'_, PyAny>, u: &Bound<'_, PyAny>) -> PyResult<()> {
    let h = hooks()?;
    let (s, c) = session_of(rel.py(), &h, rel)?;
    bound(rel, &s, &c.borrow(), ad, u)
}

/// `_guard`. The memo's list is put in before it's filled, as Python's is, so a callback that comes back in sees it partial, and
/// every caller holds that one list. It stays Python's dict on `rel`, since it isn't a term table and it dies with the session.
fn guard<'py>(rel: &Bound<'py, PyAny>, s: &Bound<'py, PyAny>, c: &SessionCore, h: &Hooks, ad: &Bound<'py, PyAny>, terms: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyList>> {
    let p = rel.py();
    tick(session::REL_GUARD);
    let tup = PyTuple::new(p, terms.try_iter()?.collect::<PyResult<Vec<_>>>()?)?;
    let key = PyTuple::new(p, [ad.clone(), tup.into_any()])?;
    let memo = RDict::of(rel, crate::session::RD_GUARDS)?;
    let got = memo.get(&key)?;
    if !got.is_none() {
        return got.cast_into::<PyList>().map_err(Into::into);
    }
    let out = PyList::empty(p);
    memo.set_item(&key, &out)?;
    for u in terms.try_iter()? {
        let u = u?;
        if is_number(c, h, &u)? {
            let bounded = RSet::of(rel, session::RS_BOUNDED)?;
            if !bounded.contains(&u)? {
                bounded.add(&u)?;
                bound(rel, s, c, ad, &u)?;
            }
            if s.getattr(intern!(p, "engine"))?.call_method1(intern!(p, "is_"), (&u, intern!(p, "real")))?.is(PyBool::new(p, true)) {
                continue;
            }
        }
        ensure(s, &u, &["real"])?;
        let v = c.var_direct(intern!(p, "real").as_any(), &u)?;
        if PLANT.load(Relaxed) == DROP_GUARD {
            tick(session::REL_PLANT);
            continue;
        }
        out.append(-v)?;
    }
    Ok(out)
}

#[pyfunction]
fn rel_guard<'py>(rel: &Bound<'py, PyAny>, ad: &Bound<'py, PyAny>, terms: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyList>> {
    let h = hooks()?;
    let (s, c) = session_of(rel.py(), &h, rel)?;
    guard(rel, &s, &c.borrow(), &h, ad, terms)
}

/// `_eq_infinity`. It replaces C1's plan: `_interpret` was its only caller. It holds the atom's own objects, so nothing is
/// rebuilt and no term goes back to a node.
fn eq_infinity<'py>(rel: &Bound<'py, PyAny>, s: &Bound<'py, PyAny>, c: &SessionCore, h: &Hooks, var: i32, atom: &Bound<'py, PyAny>) -> PyResult<()> {
    let p = rel.py();
    tick(session::REL_EQ_INFINITY);
    let sy = p.import(intern!(p, "sympy"))?.getattr(intern!(p, "S"))?;
    let (a, b) = two(&atom.getattr(intern!(p, "expr"))?)?;
    for (inf, pred) in [(intern!(p, "Infinity"), intern!(p, "positive_infinite")), (intern!(p, "NegativeInfinity"), intern!(p, "negative_infinite"))] {
        let inf = sy.getattr(inf)?;
        let e = if b.is(&inf) {
            &a
        } else if a.is(&inf) {
            &b
        } else {
            continue;
        };
        if is_number(c, h, e)? {
            let v = s.getattr(intern!(p, "engine"))?.call_method1(intern!(p, "is_"), (e, pred))?;
            if !v.is_none() {
                return c.emit_direct(p, &[if v.is_truthy()? { var } else { -var }]);
            }
        }
        s.call_method1(intern!(p, "ensure"), (e, PySet::new(p, [pred])?))?;
        let pv = c.var_direct(pred.as_any(), e)?;
        let g: i32 = rel.call_method1(intern!(p, "_atom_selector"), (atom,))?.extract()?;
        c.emit_direct(p, &[-var, pv, -g])?;
        if PLANT.load(Relaxed) == DROP_EQ_INFINITY {
            tick(session::REL_PLANT);
            return Ok(());
        }
        return c.emit_direct(p, &[var, -pv, -g]);
    }
    Ok(())
}

#[pyfunction]
fn rel_eq_infinity<'py>(rel: &Bound<'py, PyAny>, var: i32, atom: &Bound<'py, PyAny>) -> PyResult<()> {
    let h = hooks()?;
    let (s, c) = session_of(rel.py(), &h, rel)?;
    eq_infinity(rel, &s, &c.borrow(), &h, var, atom)
}


/// C2 (group-d-cause.md): the slice's own adapter types (adapters.rs `LRAAdapter`, `EUFAdapter`; pyo3 classes that
/// can't be subclassed, so the type fixes every method) are called directly, not through Python's method protocol and
/// back. A user's adapter keeps the Python call. The same methods run, in the same order.
fn ad_register(ad: &Bound<'_, PyAny>, solver: &Bound<'_, PyAny>, var: i32, sat: &Bound<'_, PyAny>) -> PyResult<bool> {
    let p = ad.py();
    let var = &var.into_pyobject(p)?.into_any();
    if let Ok(a) = ad.cast_exact::<LraAdapter>() {
        return a.try_borrow_mut()?.register(p, solver, var, sat);
    }
    if let Ok(a) = ad.cast_exact::<EufAdapter>() {
        return a.try_borrow_mut()?.register(p, solver, var, sat);
    }
    ad.call_method1(intern!(p, "register"), (solver, var, sat))?.is_truthy()
}

/// Whether `ad` has the method `name`: from the type for the slice's own adapters (`node_term` is EUF's only,
/// `order_sides` LRA's only).
fn ad_has(ad: &Bound<'_, PyAny>, name: &Bound<'_, PyString>) -> PyResult<bool> {
    let n = name.to_str()?;
    if ad.is_exact_instance_of::<LraAdapter>() && (n == "node_term" || n == "order_sides") {
        return Ok(n == "order_sides");
    }
    if ad.is_exact_instance_of::<EufAdapter>() && (n == "node_term" || n == "order_sides") {
        return Ok(n == "node_term");
    }
    Ok(ad.getattr_opt(name)?.is_some())
}

fn ad_interned<'py>(ad: &Bound<'py, PyAny>, exprs: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    if let Ok(a) = ad.cast_exact::<EufAdapter>() {
        return EufAdapter::interned(a, exprs);
    }
    ad.call_method1(intern!(ad.py(), "interned"), (exprs,))
}

fn ad_order_sides<'py>(ad: &Bound<'py, PyAny>, sat: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    if let Ok(a) = ad.cast_exact::<LraAdapter>() {
        return a.try_borrow()?.order_sides(ad.py(), sat);
    }
    ad.call_method1(intern!(ad.py(), "order_sides"), (sat,))
}

/// `_interpret`. The adapters, `sympy_atom`, `_note_sides` and `_adapter` stay Python and are called back.
#[pyfunction]
fn rel_interpret<'py>(rel: &Bound<'py, PyAny>, atom: &Bound<'py, PyAny>) -> PyResult<bool> {
    observe(rel, "interpret")?;
    let p = rel.py();
    tick(session::REL_INTERPRET);
    let h = hooks()?;
    let (s, c) = session_of(p, &h, rel)?;
    let c = c.borrow();
    let r = h.relations.bind(p);
    let solver = crate::session::solver_of(&s)?;
    let Some(var) = c.custom_direct(atom)? else { return Err(PyKeyError::new_err(atom.clone().unbind())) };
    let pred = atom.getattr(intern!(p, "pred"))?;
    let order = pred.eq(intern!(p, "lt"))?;
    let link = if order { RDict::of(rel, crate::session::RD_LINK_LT)?.get(atom)? } else { p.None().into_bound(p) };
    if !link.is_none() {
        ensure(&s, &link, &["extended_real"])?;
    } else if order && rel_order_sides(rel, var, atom)? {
        return Ok(true);
    }
    if order {
        rel_trichotomy(rel, var, atom)?;
    }
    let eq = pred.eq(intern!(p, "eq"))?;
    if eq {
        eq_infinity(rel, &s, &c, &h, var, atom)?;
    }
    let sat = sympy_atom(&h, atom)?;
    let mut ok = false;
    let (twins, lterms, eterms) = (PyList::empty(p), PyList::empty(p), PyList::empty(p));
    for spec in rel.getattr(intern!(p, "specs"))?.try_iter()? {
        let spec = spec?;
        let ad = rel.call_method1(intern!(p, "_adapter"), (&spec,))?;
        if !spec_row(&spec)?.guarded {
            if ad_register(&ad, &solver, var, &sat)? {
                ok = true;
                if eq && ad_has(&ad, intern!(p, "node_term"))? {
                    eterms.call_method1(intern!(p, "extend"), (ad_interned(&ad, &atom.getattr(intern!(p, "expr"))?)?,))?;
                    if !RSet::of(rel, session::RS_AUX_EQ)?.contains(atom)? {
                        rel.call_method1(intern!(p, "_note_sides"), (atom, 2))?;
                    } else if RSet::of(rel, session::RS_LINK_EQ)?.contains(atom)? {
                        rel.call_method1(intern!(p, "_note_sides"), (atom, 1))?;
                    }
                }
            }
            continue;
        }
        if order && ad_has(&ad, intern!(p, "order_sides"))? {
            let sides = ad_order_sides(&ad, &sat)?;
            if !sides.is_none() {
                if !link.is_none() && own_term(&sides, &link)? {
                    s.call_method1(intern!(p, "ensure"), (&link, r.getattr(intern!(p, "_INF_PREDS"))?))?;
                } else {
                    rel_order_infinite(rel, var, &sides)?;
                }
                if sides.get_item(0)?.get_item(1)?.is_truthy()? || sides.get_item(1)?.get_item(1)?.is_truthy()? {
                    ok = true;
                    continue;
                }
            }
        }
        let terms = ad.call_method1(intern!(p, "terms"), (&sat,))?;
        if terms.is_none() {
            continue;
        }
        let t = fresh(&s, &c, false)?;
        if !ad.call_method1(intern!(p, "register"), (&solver, t, &sat))?.is_truthy()? {
            continue;
        }
        ok = true;
        let g = guard(rel, &s, &c, &h, &ad, &terms)?;
        lterms.call_method1(intern!(p, "extend"), (&terms,))?;
        if eq {
            twins.append((t, &g))?;
            continue;
        }
        let lits: Vec<i32> = g.extract()?;
        let with = |x: [i32; 2]| lits.iter().copied().chain(x).collect::<Vec<i32>>();
        c.emit_direct(p, &with([-var, t]))?;
        if PLANT.load(Relaxed) == DROP_INTERPRET {
            tick(session::REL_PLANT);
            continue;
        }
        c.emit_direct(p, &with([var, -t]))?;
    }
    let info = PyTuple::new(p, [twins.into_any(), lterms.into_any(), eterms.into_any()])?;
    RDict::of(rel, crate::session::RD_INFO)?.set_item(atom, &info)?;
    let cx = Cx { rel, s: &s, c: &c, h: &h };
    for role in RDict::of(rel, crate::session::RD_ROLES)?.get_item(atom)?.unwrap_or_else(|| PyTuple::empty(p).into_any()).try_iter()? {
        let (kind, g) = two(&role?)?;
        cx.apply_role(atom, info.as_any(), &kind, &g)?;
    }
    Ok(ok)
}

/// `_link`.
#[pyfunction]
fn rel_link<'py>(rel: &Bound<'py, PyAny>, e: &Bound<'py, PyAny>) -> PyResult<()> {
    observe(rel, "link")?;
    let p = rel.py();
    tick(session::REL_LINK);
    let h = hooks()?;
    let (s, c) = session_of(p, &h, rel)?;
    let c = c.borrow();
    let r = h.relations.bind(p);
    let zero_obj = p.import(intern!(p, "sympy"))?.getattr(intern!(p, "S"))?.getattr(intern!(p, "Zero"))?;
    ensure(&s, e, &["extended_positive", "extended_negative", "zero"])?;
    let pos = c.var_direct(intern!(p, "extended_positive").as_any(), e)?;
    let neg = c.var_direct(intern!(p, "extended_negative").as_any(), e)?;
    let zero = c.var_direct(intern!(p, "zero").as_any(), e)?;
    let atom = r.getattr(intern!(p, "relation_atom"))?;
    let gta = atom.call1((intern!(p, "lt"), &zero_obj, e))?;
    let lta = atom.call1((intern!(p, "lt"), e, &zero_obj))?;
    let link_lt = RDict::of(rel, crate::session::RD_LINK_LT)?;
    link_lt.set_item(&gta, e)?;
    link_lt.set_item(&lta, e)?;
    let gt: i32 = rel.call_method1(intern!(p, "_atom_var"), (&gta,))?.extract()?;
    let lt: i32 = rel.call_method1(intern!(p, "_atom_var"), (&lta,))?.extract()?;
    let eqa = r.getattr(intern!(p, "relation_atom"))?.call1((intern!(p, "eq"), e, &zero_obj))?;
    if c.custom_direct(&eqa)?.is_none() {
        RSet::of(rel, session::RS_AUX_EQ)?.add(&eqa)?;
        RSet::of(rel, session::RS_LINK_EQ)?.add(&eqa)?;
    }
    let eq: i32 = rel.call_method1(intern!(p, "_atom_var"), (&eqa,))?.extract()?;
    let sel = fresh(&s, &c, true)?;
    RDict::of(rel, crate::session::RD_LINK_SEL)?.set_item(e, sel)?;
    let g = -sel;
    // One guard object: `_tsource` drops repeats of it.
    let gl = PyList::new(p, [g])?;
    let link_of = RDict::of(rel, crate::session::RD_LINK_OF)?;
    let cx = Cx { rel, s: &s, c: &c, h: &h };
    for f in [&gta, &lta, &eqa] {
        link_of.set_item(f, e)?;
        cx.add_role(f, gl.as_any(), intern!(p, "link").as_any())?;
    }
    c.emit_direct(p, &[-pos, gt, g])?;
    c.emit_direct(p, &[-gt, pos, g])?;
    c.emit_direct(p, &[-neg, lt, g])?;
    c.emit_direct(p, &[-lt, neg, g])?;
    c.emit_direct(p, &[-zero, eq, g])?;
    if PLANT.load(Relaxed) == DROP_LINK {
        tick(session::REL_PLANT);
    } else {
        c.emit_direct(p, &[-eq, zero, g])?;
    }
    if r.getattr(intern!(p, "INTEGERS"))?.is_truthy()? {
        for spec in rel.getattr(intern!(p, "specs"))?.try_iter()? {
            let spec = spec?;
            if spec_row(&spec)?.guarded {
                let ad = rel.call_method1(intern!(p, "_adapter"), (&spec,))?;
                if ad.getattr_opt(intern!(p, "integer_form"))?.is_some() {
                    rel_link_integer(rel, &ad, e, g)?;
                }
            }
        }
    }
    Ok(())
}

/// `selectors_of`: sorted and distinct, so a `BTreeSet`. The three maps stay Python's dicts, so `==` joins as it does there.
#[pyfunction]
fn rel_selectors_of<'py>(rel: &Bound<'py, PyAny>, atoms: &Bound<'py, PyAny>) -> PyResult<Vec<i32>> {
    let p = rel.py();
    tick(session::REL_SELECTORS);
    let h = hooks()?;
    let r = h.relations.bind(p);
    let (index, rels) = (r.getattr(intern!(p, "PRED_INDEX"))?, r.getattr(intern!(p, "RELATION_ATOMS"))?);
    let sel = RDict::of(rel, crate::session::RD_LINK_SEL)?;
    let nsel = RDict::of(rel, crate::session::RD_NUM_SEL)?;
    let status = RDict::of(rel, crate::session::RD_STATUS)?;
    let asel = RDict::of(rel, crate::session::RD_ATOM_SEL)?;
    let mut out = std::collections::BTreeSet::new();
    for a in atoms.try_iter()? {
        let a = a?;
        let pred = a.getattr(intern!(p, "pred"))?;
        if index.contains(&pred)? {
            let e = a.getattr(intern!(p, "expr"))?;
            if let Some(v) = sel.get_item(&e)? {
                out.insert(v.extract::<i32>()?);
            } else if let Some(v) = nsel.get_item(&e)? {
                out.insert(v.extract::<i32>()?);
            }
        } else if rels.contains(&pred)? {
            if status.get(&a)?.is_truthy()? {
                for e in a.getattr(intern!(p, "expr"))?.try_iter()? {
                    if let Some(v) = sel.get_item(e?)? {
                        out.insert(v.extract::<i32>()?);
                    }
                }
            }
            if let Some(v) = asel.get_item(&a)? {
                if PLANT.load(Relaxed) == DROP_SELECTOR {
                    tick(session::REL_PLANT);
                } else {
                    out.insert(v.extract::<i32>()?);
                }
            }
        }
    }
    Ok(out.into_iter().collect())
}

// C2c: roles, the per-term variables, and predicate transfer. Their maps stay Python's dicts, lists and sets on `rel`, as `_guard`'s
// memo does: they aren't term tables, they die with the session, and `==` joins as it does there. Of those, the sets (`_xcand`,
// `_xpart`, `_xpairs`, `_xcounted`) are only added to and asked `in`, and what is walked is a list, a tuple or a dict's insertion order.
const SD: usize = 0;
const EN: usize = 1;
const MC: usize = 2;
const IE: usize = 3;
const IL: usize = 4;

/// Turns the plant off: for a fault that fires once.
pub(crate) fn unplant() {
    PLANT.store(0, Relaxed);
}

static FW_INTERPRET: pyo3::sync::PyOnceLock<Py<PyAny>> = pyo3::sync::PyOnceLock::new();
static FW_LINK: pyo3::sync::PyOnceLock<Py<PyAny>> = pyo3::sync::PyOnceLock::new();
static FW_SHARE_GUARD: pyo3::sync::PyOnceLock<Py<PyAny>> = pyo3::sync::PyOnceLock::new();

/// The counter every relations plant ticks when it fires.
pub(crate) fn plant_counter() -> usize {
    session::REL_PLANT
}

pub(crate) fn planted(x: u16) -> bool {
    let on = PLANT.load(Relaxed) == x;
    if on {
        tick(session::REL_PLANT);
    }
    on
}

/// `g + tail`, read when it's emitted, as Python's `+` is: `_guard`'s list can still be filling.
fn with_tail(g: &Bound<'_, PyAny>, tail: &[i32]) -> PyResult<Vec<i32>> {
    let mut v: Vec<i32> = g.extract()?;
    v.extend_from_slice(tail);
    Ok(v)
}

/// `(e.func, len(e.args))`, the key of `_xheads`.
fn head<'py>(e: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyTuple>> {
    let p = e.py();
    (e.getattr(intern!(p, "func"))?, e.getattr(intern!(p, "args"))?.len()?).into_pyobject(p)
}

/// `x in cand or x in xside`.
fn mergeable<'py>(cand: &RSet<'_, 'py>, xside: &RDict<'_, 'py>, x: &Bound<'py, PyAny>) -> PyResult<bool> {
    Ok(cand.contains(x)? || xside.contains(x)?)
}

fn rational_flag(x: &Bound<'_, PyAny>) -> PyResult<bool> {
    x.getattr(intern!(x.py(), "is_Rational"))?.is_truthy()
}

/// What C2c's methods share.
struct Cx<'a, 'py> {
    rel: &'a Bound<'py, PyAny>,
    s: &'a Bound<'py, PyAny>,
    c: &'a SessionCore,
    h: &'a Hooks,
}

impl<'a, 'py> Cx<'a, 'py> {
    /// A moved dict (state step part 2 (iii)(b), rest): the core's, or Python's on a session with no core.
    fn dict(&self, k: usize) -> PyResult<RDict<'a, 'py>> {
        RDict::of(self.rel, k)
    }

    /// State step, part 2 (ii): the core's copy of `s.solver`, not Python's attribute.
    fn solver(&self) -> PyResult<Bound<'py, PyAny>> {
        self.c.solver_direct(self.s.py())
    }

    /// `(rel.xfer, rel._xadapter)` from the core, Python's None where unset (a call on it fails as Python's would).
    fn xfer(&self) -> PyResult<(Bound<'py, PyAny>, Bound<'py, PyAny>)> {
        Ok((self.c.xfer_obj(self.rel, session::XTH), self.c.xfer_obj(self.rel, session::XAD)))
    }

    /// `structural(e)`: the term's row if it has one. No row is an ordinary answer, and that read goes to Python's own function.
    fn structural(&self, e: &Bound<'py, PyAny>) -> PyResult<bool> {
        let p = e.py();
        match term_of(self.c, self.h, e)? {
            Some(l) => read(p, self.h, &l, |t, i| t.read_structural(i)),
            None => self.h.euf_adapter.bind(p).getattr(intern!(p, "structural"))?.call1((e,))?.is_truthy(),
        }
    }

    /// `_add_role`.
    fn add_role(&self, atom: &Bound<'py, PyAny>, g: &Bound<'py, PyAny>, kind: &Bound<'py, PyAny>) -> PyResult<()> {
        let p = atom.py();
        tick(session::REL_ADD_ROLE);
        let map = self.dict(session::RD_ROLES)?;
        match map.get_item(atom)? {
            None => map.set_item(atom, PyList::new(p, [(kind, g)])?)?,
            Some(roles) => {
                for r in roles.try_iter()? {
                    let (k, h) = two(&r?)?;
                    if k.eq(kind)? && h.eq(g)? {
                        return Ok(());
                    }
                }
                roles.call_method1(intern!(p, "append"), ((kind, g),))?;
            }
        }
        if planted(DROP_ADD_ROLE) {
            return Ok(());
        }
        if let Some(info) = self.dict(session::RD_INFO)?.get_item(atom)? {
            self.apply_role(atom, &info, kind, g)?;
        }
        Ok(())
    }

    /// `_apply_role`.
    fn apply_role(&self, atom: &Bound<'py, PyAny>, info: &Bound<'py, PyAny>, kind: &Bound<'py, PyAny>, g: &Bound<'py, PyAny>) -> PyResult<()> {
        let p = atom.py();
        tick(session::REL_APPLY_ROLE);
        let (twins, lterms, eterms) = (info.get_item(0)?, info.get_item(1)?, info.get_item(2)?);
        if twins.is_truthy()? {
            let Some(var) = self.c.custom_direct(atom)? else { return Err(PyKeyError::new_err(atom.clone().unbind())) };
            for tw in twins.try_iter()? {
                let (t, guard) = two(&tw?)?;
                let t: i32 = t.extract()?;
                let mut c1: Vec<i32> = guard.extract()?;
                c1.extend(with_tail(g, &[-var, t])?);
                self.c.emit_direct(p, &c1)?;
                if planted(DROP_APPLY_ROLE) {
                    continue;
                }
                let mut c2: Vec<i32> = guard.extract()?;
                c2.extend(with_tail(g, &[var, -t])?);
                self.c.emit_direct(p, &c2)?;
            }
        }
        let link = kind.eq(intern!(p, "link"))?;
        if link {
            for u in lterms.try_iter()? {
                self.tsource(&u?, IL, g)?;
            }
            for u in eterms.try_iter()? {
                self.tsource(&u?, IE, g)?;
            }
        }
        if atom.getattr(intern!(p, "pred"))?.ne(intern!(p, "eq"))? || !eterms.is_truthy()? || kind.eq(intern!(p, "iface"))? {
            return Ok(());
        }
        let expr = atom.getattr(intern!(p, "expr"))?;
        if link {
            self.tsource(&RDict::of(self.rel, crate::session::RD_LINK_OF)?.item(atom)?, SD, g)?;
            let first = expr.get_item(0)?;
            let side = if is_number(self.c, self.h, &first)? { first } else { expr.get_item(1)? };
            self.tsource(&side, SD, g)
        } else {
            for e in expr.try_iter()? {
                let e = e?;
                let rational = match e.getattr_opt(intern!(p, "is_Rational"))? {
                    Some(x) => x.is_truthy()?,
                    None => false,
                };
                if !rational && !planted(DROP_CANDIDACY) {
                    self.tsource(&e, EN, g)?;
                }
                self.tsource(&e, SD, g)?;
            }
            Ok(())
        }
    }

    /// `_tsource`.
    fn tsource(&self, u: &Bound<'py, PyAny>, k: usize, g: &Bound<'py, PyAny>) -> PyResult<()> {
        let p = u.py();
        tick(session::REL_TSOURCE);
        let map = self.dict(session::RD_TSRC)?;
        let key = (u, k).into_pyobject(p)?;
        match map.get_item(&key)? {
            None => map.set_item(&key, PyList::new(p, [g])?)?,
            Some(lst) => {
                if lst.get_item(-1)?.is(g) {
                    return Ok(());
                }
                lst.call_method1(intern!(p, "append"), (g,))?;
            }
        }
        if let Some(tv) = self.dict(session::RD_TV)?.get_item(u)? {
            let v: i32 = tv.get_item(k)?.extract()?;
            if v != 0 {
                if planted(DROP_TSOURCE) {
                    return Ok(());
                }
                self.c.emit_direct(p, &with_tail(g, &[v])?)?;
            } else if k < MC && tv.get_item(MC)?.extract::<i32>()? != 0 {
                self.tvar(u, k)?;
            }
        }
        Ok(())
    }

    /// `_tvar`.
    fn tvar(&self, u: &Bound<'py, PyAny>, k: usize) -> PyResult<i32> {
        let p = u.py();
        tick(session::REL_TVAR);
        let map = self.dict(session::RD_TV)?;
        let tv = match map.get_item(u)? {
            Some(t) => t,
            None => {
                let t = PyList::new(p, [0, 0, 0, 0, 0])?.into_any();
                map.set_item(u, &t)?;
                t
            }
        };
        let v: i32 = tv.get_item(k)?.extract()?;
        if v != 0 {
            return Ok(v);
        }
        let v = fresh(self.s, self.c, true)?;
        tv.set_item(k, v)?;
        let tsrc = self.dict(session::RD_TSRC)?;
        if k == MC {
            for j in [SD, EN] {
                let w: i32 = tv.get_item(j)?.extract()?;
                if w != 0 {
                    if !planted(DROP_TVAR_MC) {
                        self.c.emit_direct(p, &[-w, v])?;
                    }
                } else if tsrc.contains((u, j))? {
                    self.tvar(u, j)?;
                }
            }
            return Ok(v);
        }
        if let Some(lst) = tsrc.get_item((u, k))? {
            for g in lst.try_iter()? {
                if planted(DROP_TVAR) {
                    continue;
                }
                self.c.emit_direct(p, &with_tail(&g?, &[v])?)?;
            }
        }
        if k == SD || k == EN {
            let m: i32 = tv.get_item(MC)?.extract()?;
            if m != 0 && !planted(DROP_TVAR_MC) {
                self.c.emit_direct(p, &[-v, m])?;
            }
        }
        Ok(v)
    }

    /// `_share_guard`.
    fn share_guard(&self, u: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyList>> {
        tick(session::REL_SHARE_GUARD);
        let il = self.tvar(u, IL)?;
        let ie = self.tvar(u, IE)?;
        if planted(SHARE_GUARD_ONE) {
            return PyList::new(u.py(), [-il]);
        }
        PyList::new(u.py(), [-il, -ie])
    }

    /// `_congruent`.
    fn congruent(&self, node: &Bound<'py, PyAny>) -> PyResult<bool> {
        let p = node.py();
        tick(session::REL_CONGRUENT);
        let Some(others) = self.dict(session::RD_XHEADS)?.get_item(head(node)?)? else { return Ok(false) };
        if others.len()? < 2 {
            return Ok(false);
        }
        if self.xfer()?.1.call_method1(intern!(p, "term_of"), (node,))?.is_none()
            && !RDict::of(self.rel, crate::session::RD_NUM_SEL)?.contains(node)?
        {
            return Ok(false);
        }
        let (cand, xside) = (RSet::of(self.rel, session::RS_XCAND)?, RDict::of(self.rel, crate::session::RD_XSIDE)?);
        let args = node.getattr(intern!(p, "args"))?;
        for o in others.try_iter()? {
            let o = o?;
            if o.is(node) || o.eq(node)? {
                continue;
            }
            let mut differ = false;
            let mut broke = false;
            for pair in args.try_iter()?.zip(o.getattr(intern!(p, "args"))?.try_iter()?) {
                let (a, b) = (pair.0?, pair.1?);
                if a.eq(&b)? {
                    continue;
                }
                if !(mergeable(&cand, &xside, &a)? && mergeable(&cand, &xside, &b)?) || (rational_flag(&a)? && rational_flag(&b)?) {
                    broke = true;
                    break;
                }
                differ = true;
            }
            if !broke && differ {
                return Ok(!planted(CONGRUENT_NEVER));
            }
        }
        Ok(false)
    }

    /// `_engage_transfer`. The theory's class is read at each call, as Python's `from ... import` is: `backend` and tests replace it.
    fn engage_transfer(&self) -> PyResult<()> {
        let p = self.rel.py();
        tick(session::REL_ENGAGE);
        if !self.s.getattr(intern!(p, "engine")).and_then(|e| crate::memos::setting(&e, intern!(p, "_transfer"), intern!(p, "transfer")))?.is_truthy()? {
            return Ok(());
        }
        let mut ad = None;
        for spec in self.rel.getattr(intern!(p, "specs"))?.try_iter()? {
            let spec = spec?;
            if !spec_row(&spec)?.guarded {
                let a = self.rel.call_method1(intern!(p, "_adapter"), (&spec,))?;
                if ad_has(&a, intern!(p, "node_term"))? {
                    ad = Some(a);
                    break;
                }
            }
        }
        let Some(ad) = ad else { return Ok(()) };
        let class = p.import(intern!(p, "satassume.theories.transfer"))?.getattr(intern!(p, "TransferTheory"))?;
        let solver = self.solver()?;
        ad.call_method1(intern!(p, "attach"), (&solver,))?;
        let th = class.call1((ad.getattr(intern!(p, "theory"))?,))?;
        solver.call_method1(intern!(p, "attach_theory"), (&th,))?;
        let sel = fresh(self.s, self.c, true)?;
        th.call_method1(intern!(p, "guard"), (sel,))?;
        if !planted(DROP_ENGAGE) {
            solver.call_method1(intern!(p, "register_atom"), (&th, sel, (intern!(p, "enable"),)))?;
        }
        // State step, part 2 (ii): `rel.xfer_sel`, `rel._xadapter`, `rel.xfer` and `s.xfer = rel`, held in the core.
        self.c.xfer_engage(self.rel, &th, &ad, sel.into_pyobject(p)?.as_any());
        Ok(())
    }

    /// `_transfer_terms`.
    fn transfer_terms(&self) -> PyResult<bool> {
        let p = self.rel.py();
        tick(session::REL_TRANSFER_TERMS);
        let sy = p.import(intern!(p, "sympy"))?;
        let (basic, expr, rational) = (sy.getattr(intern!(p, "Basic"))?, sy.getattr(intern!(p, "Expr"))?, sy.getattr(intern!(p, "Rational"))?);
        let rel = self.rel;
        let (th, ad) = self.xfer()?;
        let mut visited = false;
        let sides = RDict::of(rel, crate::session::RD_XSIDE)?;
        let n = sides.len()?;
        let from = self.c.relc_get(rel, session::XTERM) as usize;
        if from < n {
            let new = sides.items()?.into_iter().map(|e| e.0).skip(from).take(n - from).collect::<Vec<_>>();
            self.c.relc_put(rel, session::XTERM, n as i64);
            for e in &new {
                if e.is_instance(&rational)? {
                    let t = ad.call_method1(intern!(p, "term_of"), (e,))?;
                    if !t.is_none() && !planted(DROP_FIXED) {
                        let facts = number_basis(&self.s.getattr(intern!(p, "engine"))?, e, true)?;
                        th.call_method1(intern!(p, "set_fixed"), (t, facts))?;
                    }
                    continue;
                }
                if e.is_instance(&expr)? && !self.c.base_contains_direct(e)? {
                    if planted(DROP_TERMS_SIDE) {
                        continue;
                    }
                    self.s.call_method1(intern!(p, "ensure"), (e,))?;
                    visited = true;
                }
            }
        }
        let new = ad.call_method1(intern!(p, "terms_since"), (self.c.relc_get(rel, session::XTCUR),))?;
        let extra = RList::of(rel, session::RL_XEXTRA)?;
        if new.is_truthy()? || extra.is_truthy() {
            let cur = self.c.relc_get(rel, session::XTCUR);
            self.c.relc_put(rel, session::XTCUR, cur + new.len()? as i64);
            if extra.is_truthy() {
                new.call_method1(intern!(p, "extend"), (PyList::new(p, extra.items())?,))?;
                extra.clear()?;
            }
            let heads = self.dict(session::RD_XHEADS)?;
            let counted = RSet::of(rel, session::RS_XCOUNTED)?;
            // A dict, as Python's: distinct by `==`, in insertion order.
            let grown = PyDict::new(p);
            for e in new.try_iter()? {
                let e = e?;
                if !counted.contains(&e)? && e.is_instance(&basic)? && self.structural(&e)? {
                    counted.add(&e)?;
                    let k = head(&e)?;
                    match heads.get_item(&k)? {
                        None => heads.set_item(&k, PyList::new(p, [&e])?)?,
                        Some(h) => {
                            h.call_method1(intern!(p, "append"), (&e,))?;
                            grown.set_item(&k, p.None())?;
                        }
                    }
                }
            }
            if !grown.is_empty() {
                let hn = self.c.relc_get(rel, session::XHN);
                self.c.relc_put(rel, session::XHN, hn + 1);
                for k in grown.as_any().try_iter()? {
                    for e in heads.item(&k?)?.try_iter()? {
                        let e = e?;
                        if e.is_instance(&expr)? && !self.c.base_contains_direct(&e)? {
                            if planted(DROP_TERMS) {
                                continue;
                            }
                            self.s.call_method1(intern!(p, "ensure"), (&e,))?;
                            visited = true;
                        }
                    }
                }
            }
        }
        Ok(visited)
    }

    /// `_xswitch`. Moved with `sync_transfer`, its only caller.
    fn xswitch(&self, node: &Bound<'py, PyAny>, t: &Bound<'py, PyAny>) -> PyResult<()> {
        let p = node.py();
        tick(session::REL_XSWITCH);
        let solver = self.solver()?;
        let (th, _) = self.xfer()?;
        let en = self.tvar(node, EN)?;
        let sd = self.tvar(node, SD)?;
        for v in th.call_method1(intern!(p, "switch"), (t, en, sd))?.try_iter()? {
            let v = v?;
            if planted(DROP_XSWITCH) {
                continue;
            }
            solver.call_method1(intern!(p, "register_atom"), (&th, v, (intern!(p, "on"),)))?;
        }
        Ok(())
    }

    /// `sync_transfer`. `slots` is read past its view: a custom atom's slot is built only for Python to see it isn't a tuple.
    fn sync_transfer(&self) -> PyResult<()> {
        let p = self.rel.py();
        let rel = self.rel;
        tick(session::REL_SYNC_TRANSFER);
        let mut i = self.c.relc_get(rel, session::XSLOT).max(0) as usize;
        let n = self.c.n_slots_direct();
        let nside = self.c.relc_get(rel, session::XSIDES_N);
        let hn = self.c.relc_get(rel, session::XHN);
        if i >= n && nside == self.c.relc_get(rel, session::XNSIDES) && hn == self.c.relc_get(rel, session::XHSEEN) {
            return Ok(());
        }
        let r = self.h.relations.bind(p);
        let npred: usize = r.getattr(intern!(p, "NPRED"))?.extract()?;
        let sy = p.import(intern!(p, "sympy"))?;
        let (basic, rational, nan) = (sy.getattr(intern!(p, "Basic"))?, sy.getattr(intern!(p, "Rational"))?, sy.getattr(intern!(p, "nan"))?);
        let pend = RList::of(rel, session::RL_XPEND)?;
        while i < n {
            if let Some(node) = self.c.block_direct(p, i) {
                if node.is_instance(&basic)? && !node.call_method1(intern!(p, "has"), (&nan,))?.is_truthy()? {
                    pend.push(pyo3::types::PyTuple::new(p, [node.clone(), i.into_pyobject(p)?.into_any()])?.as_any())?;
                }
                i += npred;
            } else {
                i += 1;
            }
        }
        self.c.relc_put(rel, session::XSLOT, n as i64 + planted(RC_XSLOT_SKIP) as i64);
        self.c.relc_put(rel, session::XNSIDES, nside);
        self.c.relc_put(rel, session::XHSEEN, hn);
        let cand = RSet::of(rel, session::RS_XCAND)?;
        let part = RSet::of(rel, session::RS_XPART)?;
        let xside = self.dict(session::RD_XSIDE)?;
        let (th, ad) = self.xfer()?;
        let solver = self.solver()?;
        let polar: i32 = r.getattr(intern!(p, "BASIS_INDEX"))?.get_item(intern!(p, "polar"))?.extract()?;
        let mut changed = true;
        while changed && pend.is_truthy() {
            changed = false;
            let keep = PyList::empty(p);
            for entry in pend.items() {
                let entry = entry;
                let (node, b) = two(&entry)?;
                let b: i32 = b.extract()?;
                let lv: i64 = match xside.get_item(&node)? {
                    Some(x) => x.extract()?,
                    None => 0,
                };
                if lv == 2 || (self.structural(&node)? && self.congruent(&node)?) {
                    cand.add(&node)?;
                    changed = true;
                    let t = ad.call_method1(intern!(p, "node_term"), (&node,))?;
                    self.c.ensure_vars_direct(p, b + npred as i32 - 1)?;
                    let is_rational = node.is_instance(&rational)?;
                    // `_number_basis` is a sorted tuple.
                    let preds: Vec<i32> = if is_rational {
                        number_basis(&self.s.getattr(intern!(p, "engine"))?, &node, false)?.extract()?
                    } else {
                        (0..npred as i32).collect()
                    };
                    let full = !is_rational || preds.len() == npred;
                    for k in preds {
                        if k != polar || !part.contains(&node)? {
                            if k == 0 && planted(DROP_SYNC) {
                                continue;
                            }
                            let tag = if full { (&t, k).into_pyobject(p)?.into_any() } else { (&t, k, true).into_pyobject(p)?.into_any() };
                            solver.call_method1(intern!(p, "register_atom"), (&th, b + k, tag, false))?;
                        }
                    }
                    if !is_rational {
                        self.xswitch(&node, &t)?;
                    }
                    continue;
                }
                if lv == 1 && !part.contains(&node)? {
                    part.add(&node)?;
                    let t = ad.call_method1(intern!(p, "node_term"), (&node,))?;
                    if !planted(DROP_SYNC_POLAR) {
                        solver.call_method1(intern!(p, "register_atom"), (&th, b + polar, (&t, polar, true), false))?;
                    }
                    self.xswitch(&node, &t)?;
                }
                keep.append(&entry)?;
            }
            pend.replace(keep.iter().collect())?;
        }
        self.congruence_pairs()
    }

    /// `_congruence_pairs`. Groups are walked in `_xheads`' insertion order and pairs by position.
    fn congruence_pairs(&self) -> PyResult<()> {
        let p = self.rel.py();
        let rel = self.rel;
        tick(session::REL_CONGRUENCE_PAIRS);
        let (xside, cand, done) = (RDict::of(rel, crate::session::RD_XSIDE)?, RSet::of(rel, session::RS_XCAND)?, RSet::of(rel, session::RS_XPAIRS)?);
        for group in RDict::of(rel, crate::session::RD_XHEADS)?.values()? {
            let group = group.cast_into::<PyList>()?;
            let n = group.len();
            if n < 2 {
                continue;
            }
            for j in 1..n {
                let g2 = group.get_item(j)?;
                let g2_args = g2.getattr(intern!(p, "args"))?;
                for f in group.get_slice(0, j).iter() {
                    let key = (&f, &g2).into_pyobject(p)?;
                    if done.contains(&key)? {
                        continue;
                    }
                    let mut diff = Vec::new();
                    // Python's `ok`: Some(true), Some(false), or None for two distinct rationals.
                    let mut ok = Some(true);
                    for pair in f.getattr(intern!(p, "args"))?.try_iter()?.zip(g2_args.try_iter()?) {
                        let (x, y) = (pair.0?, pair.1?);
                        if x.eq(&y)? {
                            continue;
                        }
                        if rational_flag(&x)? && rational_flag(&y)? {
                            ok = None;
                            break;
                        }
                        if !(mergeable(&cand, &xside, &x)? && mergeable(&cand, &xside, &y)?) {
                            ok = Some(false);
                            break;
                        }
                        diff.push((x, y));
                    }
                    if ok.is_none() || (ok == Some(true) && !diff.is_empty()) {
                        done.add(&key)?;
                    }
                    if ok != Some(true) || diff.is_empty() {
                        continue;
                    }
                    let mut body = vec![-self.tvar(&f, IE)?, -self.tvar(&g2, IE)?];
                    for (x, y) in &diff {
                        body.push(-self.tvar(x, MC)?);
                        body.push(-self.tvar(y, MC)?);
                    }
                    let mut c1 = body.clone();
                    c1.push(self.tvar(&f, EN)?);
                    self.c.emit_direct(p, &c1)?;
                    if planted(DROP_CONGRUENCE) {
                        continue;
                    }
                    let mut c2 = body;
                    c2.push(self.tvar(&g2, EN)?);
                    self.c.emit_direct(p, &c2)?;
                }
            }
        }
        Ok(())
    }
}

/// Runs `f` with `rel`'s session. A callback can come back in; the core is frozen, so holding this borrow across one is safe.
fn with_cx<'py, T>(rel: &Bound<'py, PyAny>, f: impl FnOnce(&Cx<'_, 'py>) -> PyResult<T>) -> PyResult<T> {
    let h = hooks()?;
    let (s, c) = session_of(rel.py(), &h, rel)?;
    let c = c.borrow();
    f(&Cx { rel, s: &s, c: &c, h: &h })
}

#[pyfunction]
fn rel_add_role<'py>(rel: &Bound<'py, PyAny>, atom: &Bound<'py, PyAny>, g: &Bound<'py, PyAny>, kind: &Bound<'py, PyAny>) -> PyResult<()> {
    with_cx(rel, |x| x.add_role(atom, g, kind))
}

#[pyfunction]
fn rel_apply_role<'py>(rel: &Bound<'py, PyAny>, atom: &Bound<'py, PyAny>, info: &Bound<'py, PyAny>, kind: &Bound<'py, PyAny>, g: &Bound<'py, PyAny>) -> PyResult<()> {
    with_cx(rel, |x| x.apply_role(atom, info, kind, g))
}

#[pyfunction]
fn rel_tsource<'py>(rel: &Bound<'py, PyAny>, u: &Bound<'py, PyAny>, k: usize, g: &Bound<'py, PyAny>) -> PyResult<()> {
    with_cx(rel, |x| x.tsource(u, k, g))
}

#[pyfunction]
fn rel_tvar<'py>(rel: &Bound<'py, PyAny>, u: &Bound<'py, PyAny>, k: usize) -> PyResult<i32> {
    with_cx(rel, |x| x.tvar(u, k))
}

#[pyfunction]
fn rel_share_guard<'py>(rel: &Bound<'py, PyAny>, u: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyList>> {
    with_cx(rel, |x| x.share_guard(u))
}

#[pyfunction]
fn rel_congruent<'py>(rel: &Bound<'py, PyAny>, node: &Bound<'py, PyAny>) -> PyResult<bool> {
    with_cx(rel, |x| x.congruent(node))
}

#[pyfunction]
fn rel_engage_transfer(rel: &Bound<'_, PyAny>) -> PyResult<()> {
    with_cx(rel, |x| x.engage_transfer())
}

#[pyfunction]
fn rel_transfer_terms(rel: &Bound<'_, PyAny>) -> PyResult<bool> {
    with_cx(rel, |x| x.transfer_terms())
}

#[pyfunction]
fn rel_sync_transfer(rel: &Bound<'_, PyAny>) -> PyResult<()> {
    with_cx(rel, |x| x.sync_transfer())
}

#[pyfunction]
fn rel_xswitch<'py>(rel: &Bound<'py, PyAny>, node: &Bound<'py, PyAny>, t: &Bound<'py, PyAny>) -> PyResult<()> {
    with_cx(rel, |x| x.xswitch(node, t))
}

#[pyfunction]
fn rel_congruence_pairs(rel: &Bound<'_, PyAny>) -> PyResult<()> {
    with_cx(rel, |x| x.congruence_pairs())
}

/// The link alone, for its tests.
#[pyfunction]
fn rel_link_probe(core: &Bound<'_, SessionCore>, x: &Bound<'_, PyAny>) -> PyResult<Option<u32>> {
    let h = hooks()?;
    Ok(term_of(&core.borrow(), &h, x)?.map(|l| l.id))
}

// -- step 5c4: the rest of `Relations` (relations.py:777-979, 1516-1598) ------------------------------------------------------
//
// `__init__`, `enqueue`, `note_formula`, `process`, `_link_later`, `wants_transfer`, `_share`. As in C2b and C2c, the object's
// containers stay Python's dicts, sets and lists on the instance, so what Python reads later is Python's by construction; each read
// and call Python makes, these make in the same order. Other methods are called by name, as Python calls them, so a patch on the
// class or the instance is honoured (`process` is the driver loop: what it calls, a test may have replaced). Still Python and called
// back, each counted (`rel:cb_*`): `_note_sides`, `_eq_links`, `_atom_selector`, `_atom_var` (5c4's "called back" rows) and
// `_constant_term` (5c5's). `Session.discover`, `EqualitySharing` and `transfer_wanted` are read from their modules at each call:
// `backend.install_transfer` replaces the last two with Rust's.

fn plant_on(x: u16) -> bool {
    planted(x)
}

/// `Relations.__init__`. Attributes are set in Python's order, since `vars(rel)` is something Python can read.
#[pyfunction]
fn rel_init<'py>(rel: &Bound<'py, PyAny>, session: &Bound<'py, PyAny>, specs: &Bound<'py, PyAny>) -> PyResult<()> {
    let p = rel.py();
    tick(session::REL_INIT);
    let h = hooks()?;
    let r = h.relations.bind(p);
    let proxy = p.import(intern!(p, "weakref"))?.getattr(intern!(p, "proxy"))?.call1((session,))?;
    let set = |name: &str, v: Bound<'py, PyAny>| rel.setattr(name, v);
    // state step, part 2 (iii)(b), rest: the moved sets (relkeys.rs) are the core's; a session with no core keeps Python's
    let has_core = session::core_of(session).is_ok();
    let pset = |name: &str| if has_core { Ok(()) } else { rel.setattr(name, PySet::empty(p)?) };
    let pdict = |name: &str| if has_core { Ok(()) } else { rel.setattr(name, PyDict::new(p)) };
    let plist = |name: &str| if has_core { Ok(()) } else { rel.setattr(name, PyList::empty(p)) };
    set("session", proxy)?;
    set("specs", PyList::new(p, specs.try_iter()?.collect::<PyResult<Vec<_>>>()?)?.into_any())?;
    pdict("adapters")?;
    pdict("status")?;
    plist("queue")?;
    pset("linked")?;
    pset("_bounded")?;
    pdict("_guards")?;
    pdict("_link_lt")?;
    pdict("top")?;
    set("active", PyBool::new(p, false).to_owned().into_any())?;
    set("sharing", r.getattr(intern!(p, "EqualitySharing"))?.call0()?)?;
    plist("_pending_links")?;
    pdict("link_sel")?;
    pdict("atom_sel")?;
    pdict("num_sel")?;
    plist("_xextra")?;
    pset("_user_eq")?;
    pdict("_roles")?;
    pdict("_info")?;
    pdict("_link_of")?;
    pdict("_tv")?;
    pdict("_tsrc")?;
    pset("_xpairs")?;
    pset("_aux_eq")?;
    pset("_link_eq")?;
    pdict("_xside")?;
    // state step, part 2 (iii)(b): the scalar cursors are the core's (session.rs `relc`); a session with no core keeps
    // Python's attributes
    match session::core_of(session) {
        Ok(c) => {
            c.borrow().relc_init(rel);
            c.borrow().rs_init(rel);
        }
        Err(_) => {
            for (n, v) in session::RC_NAMES.iter().zip(session::RC_INIT) {
                set(n, v.into_pyobject(p)?.into_any())?;
            }
        }
    }
    pset("_xpart")?;
    pdict("_xheads")?;
    pset("_xcounted")?;
    plist("_xpend")?;
    pset("_xcand")?;
    let scope = session.getattr(intern!(p, "scope"))?;
    set("scope", scope.clone())?;
    if scope.getattr(intern!(p, "glue"))?.is_truthy()? {
        set("active", PyBool::new(p, true).to_owned().into_any())?;
        if scope.getattr(intern!(p, "transfer"))?.is_truthy()? && !plant_on(DROP_INIT_ENGAGE) {
            rel.call_method0(intern!(p, "_engage_transfer"))?;
        }
    }
    Ok(())
}

#[pyfunction]
fn rel_enqueue(rel: &Bound<'_, PyAny>, atom: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(session::REL_ENQUEUE);
    if plant_on(DROP_ENQUEUE) {
        return Ok(());
    }
    RList::of(rel, session::RL_QUEUE)?.push(atom)?;
    Ok(())
}

#[pyfunction]
fn rel_note_formula(rel: &Bound<'_, PyAny>, atoms: &Bound<'_, PyAny>) -> PyResult<()> {
    let p = rel.py();
    tick(session::REL_NOTE_FORMULA);
    let h = hooks()?;
    for a in atoms.try_iter()? {
        let a = a?;
        let index = h.relations.bind(p).getattr(intern!(p, "PRED_INDEX"))?;
        if index.contains(a.getattr(intern!(p, "pred"))?)? {
            let e = a.getattr(intern!(p, "expr"))?;
            if !RSet::of(rel, session::RS_LINKED)?.contains(&e)? {
                if plant_on(DROP_NOTE_TOP) {
                    continue;
                }
                RDict::of(rel, crate::session::RD_TOP)?.set_item(&e, p.None())?;
            }
        }
    }
    Ok(())
}

/// `_is_number(e)` as the moved methods read it: the term's row, else Python's function. The session borrow is held for that read only.
fn number(rel: &Bound<'_, PyAny>, h: &Hooks, e: &Bound<'_, PyAny>) -> PyResult<bool> {
    let (_, c) = session_of(rel.py(), h, rel)?;
    let c = c.borrow();
    is_number(&c, h, e)
}

fn link_later(rel: &Bound<'_, PyAny>, h: &Hooks, e: &Bound<'_, PyAny>) -> PyResult<()> {
    tick(session::REL_LINK_LATER);
    let linked = RSet::of(rel, session::RS_LINKED)?;
    if !linked.contains(e)? && !number(rel, h, e)? {
        linked.add(e)?;
        if plant_on(DROP_LINK_LATER) {
            return Ok(());
        }
        RList::of(rel, session::RL_PENDING_LINKS)?.push(e)?;
    }
    Ok(())
}

#[pyfunction]
fn rel_link_later(rel: &Bound<'_, PyAny>, e: &Bound<'_, PyAny>) -> PyResult<()> {
    let h = hooks()?;
    link_later(rel, &h, e)
}

#[pyfunction]
fn rel_wants_transfer<'py>(rel: &Bound<'py, PyAny>, atoms: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let p = rel.py();
    tick(session::REL_WANTS_TRANSFER);
    let h = hooks()?;
    let got = h.relations.bind(p).getattr(intern!(p, "transfer_wanted"))?.call1((atoms,))?;
    if plant_on(WANTS_NEVER) {
        return Ok(PyBool::new(p, false).to_owned().into_any());
    }
    Ok(got)
}

/// `_share`. The adapters' `shared_terms()` reach `update` as a lazy `map`, as Python's generator does.
#[pyfunction]
fn rel_share<'py>(rel: &Bound<'py, PyAny>) -> PyResult<bool> {
    let p = rel.py();
    tick(session::REL_SHARE);
    if plant_on(SKIP_SHARE) {
        return Ok(false);
    }
    let h = hooks()?;
    let adapters = RDict::of(rel, crate::session::RD_ADAPTERS)?;
    if adapters.len()? < 2 {
        return Ok(false);
    }
    let builtins = p.import(intern!(p, "builtins"))?;
    let caller = p.import(intern!(p, "operator"))?.getattr(intern!(p, "methodcaller"))?.call1((intern!(p, "shared_terms"),))?;
    let terms = builtins.getattr(intern!(p, "map"))?.call1((caller, PyList::new(p, adapters.values()?)?))?;
    let pairs = rel.getattr(intern!(p, "sharing"))?.call_method1(intern!(p, "update"), (terms,))?;
    let r = h.relations.bind(p);
    let zero_drop = plant_on(DROP_SHARE) || plant_on(DROP_SHARE_TRI);
    for pair in pairs.try_iter()? {
        let (a, b) = two(&pair?)?;
        if number(rel, &h, &a)? && number(rel, &h, &b)? {
            continue;
        }
        if constant_term(rel, &h, &a)? || constant_term(rel, &h, &b)? {
            continue;
        }
        if zero_drop {
            continue;
        }
        let eqa = r.getattr(intern!(p, "relation_atom"))?.call1((intern!(p, "eq"), &a, &b))?;
        let s = rel.getattr(intern!(p, "session"))?;
        if !session::table_of(&s)?.getattr(intern!(p, "custom"))?.contains(&eqa)? {
            RSet::of(rel, session::RS_AUX_EQ)?.add(&eqa)?;
        }
        tick(session::REL_CB_ATOM_VAR);
        rel.call_method1(intern!(p, "_atom_var"), (&eqa,))?;
        // state part 3, sub-part 5: directly, unless the method was replaced (session.rs `named`)
        let sg = |u: &Bound<'py, PyAny>| -> PyResult<Bound<'py, PyAny>> {
            match session::named(rel, intern!(p, "_share_guard"), &FW_SHARE_GUARD, "_rel_share_guard")? {
                None => Ok(rel_share_guard(rel, u)?.into_any()),
                Some(m) => m.call1((u,)),
            }
        };
        let ga = sg(&a)?;
        let gb = sg(&b)?;
        let g = ga.add(gb)?;
        rel.call_method1(intern!(p, "_add_role"), (&eqa, g, intern!(p, "iface")))?;
    }
    pairs.is_truthy()
}

#[pyfunction]
#[pyo3(signature = (rel, user_atoms=None))]
fn rel_process<'py>(rel: &Bound<'py, PyAny>, user_atoms: Option<&Bound<'py, PyAny>>) -> PyResult<()> {
    let p = rel.py();
    tick(session::REL_PROCESS);
    let h = hooks()?;
    let r = h.relations.bind(p);
    let (s, c) = session_of(p, &h, rel)?;
    let pred = intern!(p, "pred");
    let expr = intern!(p, "expr");
    let mut user: Vec<Bound<'py, PyAny>> = Vec::new();
    if let Some(ua) = user_atoms {
        let ratoms = r.getattr(intern!(p, "RELATION_ATOMS"))?;
        for a in ua.try_iter()? {
            let a = a?;
            if ratoms.contains(a.getattr(pred)?)? {
                user.push(a);
            }
        }
    }
    let unlinked = PySet::empty(p)?;
    for a in &user {
        let st = RDict::of(rel, crate::session::RD_STATUS)?.get(a)?;
        if st.is_truthy()? {
            for side in a.getattr(expr)?.try_iter()? {
                rel.call_method1(intern!(p, "_link_later"), (side?,))?;
            }
        } else if st.is_none() {
            unlinked.add(a)?;
        }
    }
    for a in &user {
        if a.getattr(pred)?.eq(intern!(p, "eq"))? {
            if c.borrow().xfer_get(rel, session::XTH).is_none()
                && !rel.getattr(intern!(p, "_want_transfer"))?.is_truthy()?
                && s.getattr(intern!(p, "engine")).and_then(|e| crate::memos::setting(&e, intern!(p, "_transfer"), intern!(p, "transfer")))?.is_truthy()?
            {
                crate::entry::scope_miss(&s.getattr(intern!(p, "engine"))?)?;
                rel.setattr(intern!(p, "_want_transfer"), true)?;
            }
            tick(session::REL_CB_NOTE_SIDES);
            rel.call_method1(intern!(p, "_note_sides"), (a, 2))?;
            let var = session::table_of(&s)?.getattr(intern!(p, "custom"))?.call_method1(intern!(p, "get"), (a,))?;
            let user_eq = RSet::of(rel, session::RS_USER_EQ)?;
            if !var.is_none() && !user_eq.contains(a)? {
                user_eq.add(a)?;
                if plant_on(DROP_PROC_EQ_LINKS) {
                    continue;
                }
                tick(session::REL_CB_EQ_LINKS);
                rel.call_method1(intern!(p, "_eq_links"), (&var, a))?;
                tick(session::REL_CB_ATOM_SELECTOR);
                let sel = rel.call_method1(intern!(p, "_atom_selector"), (a,))?;
                let g = PyList::new(p, [sel.neg()?])?;
                rel.call_method1(intern!(p, "_add_role"), (a, g, intern!(p, "user")))?;
            }
        }
    }
    loop {
        s.call_method0(intern!(p, "discover"))?;
        if let Some(atom) = RList::of(rel, session::RL_QUEUE)?.pop()? {
            let ok = match session::named(rel, intern!(p, "_interpret"), &FW_INTERPRET, "_rel_interpret")? {
                None => pyo3::types::PyBool::new(p, rel_interpret(rel, &atom)?).to_owned().into_any(),
                Some(m) => m.call1((&atom,))?,
            };
            RDict::of(rel, crate::session::RD_STATUS)?.set_item(&atom, &ok)?;
            rel.setattr(intern!(p, "active"), true)?;
            if ok.is_truthy()? && unlinked.contains(&atom)? {
                for side in atom.getattr(expr)?.try_iter()? {
                    rel.call_method1(intern!(p, "_link_later"), (side?,))?;
                }
            }
            continue;
        }
        if rel.getattr(intern!(p, "active"))?.is_truthy()? && RDict::of(rel, crate::session::RD_TOP)?.is_truthy()? {
            // `top = self.top; self.top = {}; for e in top:` (the keys taken, then the dict emptied)
            let top = RDict::of(rel, crate::session::RD_TOP)?;
            let keys: Vec<_> = top.items()?.into_iter().map(|e| e.0).collect();
            top.clear();
            for e in keys {
                if number(rel, &h, &e)? {
                    rel.call_method1(intern!(p, "_mention_number"), (&e,))?;
                } else {
                    rel.call_method1(intern!(p, "_link_later"), (&e,))?;
                }
            }
        }
        if let Some(e) = RList::of(rel, session::RL_PENDING_LINKS)?.pop()? {
            match session::named(rel, intern!(p, "_link"), &FW_LINK, "_rel_link")? {
                None => {
                    if !session::sb_planted(session::SB_FWD_SKIP_LINK) {
                        rel_link(rel, &e)?;
                    }
                }
                Some(m) => {
                    m.call1((e,))?;
                }
            }
            continue;
        }
        if rel.call_method0(intern!(p, "_share"))?.is_truthy()? {
            continue;
        }
        if rel.getattr(intern!(p, "_want_transfer"))?.is_truthy()? && c.borrow().xfer_get(rel, session::XTH).is_none() {
            rel.call_method0(intern!(p, "_engage_transfer"))?;
        }
        if c.borrow().xfer_get(rel, session::XTH).is_some() && rel.call_method0(intern!(p, "_transfer_terms"))?.is_truthy()? {
            continue;
        }
        break;
    }
    if c.borrow().xfer_get(rel, session::XTH).is_some() {
        rel.call_method0(intern!(p, "sync_transfer"))?;
    }
    if s.getattr(intern!(p, "engine")).and_then(|e| crate::memos::setting(&e, intern!(p, "_uninterpreted"), intern!(p, "uninterpreted")))?.eq(intern!(p, "free"))? {
        return Ok(());
    }
    for a in &user {
        if !RDict::of(rel, crate::session::RD_STATUS)?.get(a)?.is_truthy()? {
            let msg = format!("no theory interprets {}", a.str()?);
            return Err(PyErr::from_value(r.getattr(intern!(p, "Uninterpreted"))?.call1((msg,))?));
        }
    }
    Ok(())
}

// -- step 5c5: the five methods 5c4 left -------------------------------------------------------------------------------------------
//
// `_adapter`, `_atom_selector`, `_atom_var`, `_note_sides`, `_eq_links` (relations.py:992, 1317, 1325, 1475, 1654). Containers stay
// Python's, read and written in Python's order; other methods (`_fresh`) and the session's `table.var` are called by name, so a patch
// is honoured. `_eq_links` builds `p - q` with SymPy's `-`, and calls Python's `_termwise` (counted, `rel:cb_termwise`): it reads SymPy's
// `Add.make_args`, negation and `is_finite`, and the module-function step decides it.

/// `_adapter`.
#[pyfunction]
fn rel_adapter<'py>(rel: &Bound<'py, PyAny>, spec: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let p = rel.py();
    tick(session::REL_ADAPTER);
    let adapters = RDict::of(rel, crate::session::RD_ADAPTERS)?;
    let row = spec_row(spec)?;
    let name = row.name.bind(p);
    let ad = adapters.get(name)?;
    if !ad.is_none() {
        return Ok(ad);
    }
    let ad = make_adapter(p, &row)?;
    if plant_on(ADAPTER_FRESH) {
        return Ok(ad);
    }
    adapters.set_item(name, &ad)?;
    Ok(ad)
}

/// `_atom_selector`.
#[pyfunction]
fn rel_atom_selector<'py>(rel: &Bound<'py, PyAny>, atom: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let p = rel.py();
    tick(session::REL_ATOM_SELECTOR);
    let sels = RDict::of(rel, crate::session::RD_ATOM_SEL)?;
    let sel = sels.get(atom)?;
    if !sel.is_none() {
        return Ok(sel);
    }
    let kw = PyDict::new(p);
    kw.set_item(intern!(p, "inert"), true)?;
    let sel = rel.call_method(intern!(p, "_fresh"), (), Some(&kw))?;
    if plant_on(SELECTOR_NO_MEMO) {
        return Ok(sel);
    }
    sels.set_item(atom, &sel)?;
    Ok(sel)
}

/// `_atom_var`.
#[pyfunction]
fn rel_atom_var<'py>(rel: &Bound<'py, PyAny>, f: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let p = rel.py();
    tick(session::REL_ATOM_VAR);
    let table = session::table_of(&rel.getattr(intern!(p, "session"))?)?;
    let v = table.call_method1(intern!(p, "var"), (f,))?;
    if plant_on(ATOM_VAR_SKEW) {
        return v.neg();
    }
    Ok(v)
}

/// `_note_sides`.
#[pyfunction]
fn rel_note_sides<'py>(rel: &Bound<'py, PyAny>, atom: &Bound<'py, PyAny>, level: i64) -> PyResult<()> {
    let p = rel.py();
    tick(session::REL_NOTE_SIDES);
    let h = hooks()?;
    let xs = RDict::of(rel, crate::session::RD_XSIDE)?;
    for e in atom.getattr(intern!(p, "expr"))?.try_iter()? {
        let e = e?;
        let lv: i64 = if number(rel, &h, &e)? { 2 } else { level };
        let had: i64 = match xs.get_item(&e)? { Some(v) => v.extract()?, None => 0 };
        if had < lv {
            if plant_on(DROP_NOTE_SIDES) {
                continue;
            }
            xs.set_item(&e, lv)?;
            match session::core_of(&rel.getattr(intern!(p, "session"))?) {
                Ok(c) => {
                    let c = c.borrow();
                    let k = c.relc_get(rel, session::XSIDES_N);
                    c.relc_put(rel, session::XSIDES_N, k + 1);
                }
                Err(_) => {
                    let k = intern!(p, "_xsides_n");
                    rel.setattr(k, rel.getattr(k)?.add(1)?)?;
                }
            }
        }
    }
    Ok(())
}

/// `_eq_links`.
#[pyfunction]
fn rel_eq_links<'py>(rel: &Bound<'py, PyAny>, var: i32, atom: &Bound<'py, PyAny>) -> PyResult<()> {
    let p = rel.py();
    tick(session::REL_EQ_LINKS);
    let h = hooks()?;
    let (a, b) = two(&atom.getattr(intern!(p, "expr"))?)?;
    if number(rel, &h, &a)? || number(rel, &h, &b)? {
        return Ok(());
    }
    let (s, core) = session_of(p, &h, rel)?;
    tick(session::REL_CB_ATOM_SELECTOR);
    let g: i32 = -rel.call_method1(intern!(p, "_atom_selector"), (atom,))?.extract::<i32>()?;
    const INF: [&str; 2] = ["positive_infinite", "negative_infinite"];
    ensure(&s, &a, &INF)?;
    ensure(&s, &b, &INF)?;
    for pred in INF {
        let pr = PyString::new(p, pred);
        let c = core.borrow();
        let cl = [-c.var_direct(pr.as_any(), &a)?, -c.var_direct(pr.as_any(), &b)?, var, g];
        c.emit_direct(p, &cl)?;
    }
    let tw = h.relations.bind(p).getattr(intern!(p, "_termwise"))?;
    for (x, y) in [(&a, &b), (&b, &a)] {
        let d = x.sub(y)?;
        if number(rel, &h, &d)? {
            continue;
        }
        tick(session::REL_CB_TERMWISE);
        if !tw.call1((x, y, &d))?.is_truthy()? {
            continue;
        }
        if plant_on(DROP_EQ_LINKS_ZERO) {
            continue;
        }
        ensure(&s, &d, &["zero", "nonzero"])?;
        let c = core.borrow();
        let z = c.var_direct(intern!(p, "zero").as_any(), &d)?;
        c.emit_direct(p, &[-z, var, g])?;
        let nz = c.var_direct(intern!(p, "nonzero").as_any(), &d)?;
        c.emit_direct(p, &[-nz, -var, g])?;
    }
    Ok(())
}

// -- step 5c5, second part: relations.py's module functions ------------------------------------------------------------------------
// Each follows its Python function line for line. They take no session, so a term resolves through `term_live.term_id` with no node
// cache (`term_free`). `engine._xbasis` and the adapter memo (`_glue_adapters`) are Rust-native since 5c9c (engmemo.rs: read natively,
// a foreign container through its methods); `_SYMPY_ATOMS` and `_CLOSED` since 5c9b. Everything Python can read later is the same. What stays Python is a named, counted callback: the engine's `is_many`, SymPy's
// `Q.eq`/`Q.lt`, the adapters' reads, `closed_sign`, the templates' `units`, and `_under_apps`, `zero_twin`, `relation_atom` and
// `_structural_subterms`, which `term_live` answers on ids. `AdapterSpec` and `Uninterpreted` are types, with nothing to run.

/// The current query's id for `x`, with no session: Python's one rule, `term_live.term_id`. None for a non-SymPy object, as
/// `term_live`'s wrappers give it to Python without asking.
fn term_free<'py>(h: &Hooks, x: &Bound<'py, PyAny>) -> PyResult<Option<Linked<'py>>> {
    let p = x.py();
    if PLANT.load(Relaxed) == LINK_NONE {
        tick(session::LINK_NONE);
        tick(session::REL_PLANT);
        return Ok(None);
    }
    let tl = h.term_live.bind(p);
    if !x.is_instance(&faulted(p, h, "link", tl.getattr(intern!(p, "Basic")))?)? {
        return Ok(None);
    }
    let q = faulted(p, h, "link", tl.call_method0(intern!(p, "current")))?;
    if q.is_none() || !faulted(p, h, "link", q.getattr(intern!(p, "kept")))?.is_none() {
        return Ok(None);
    }
    let table = faulted(p, h, "link", q.getattr(intern!(p, "table")).and_then(|t| t.cast_into::<PyTermTable>().map_err(Into::into)))?;
    let got = faulted(p, h, "link", tl.call_method1(intern!(p, "term_id"), (&q, x, intern!(p, "link"))))?;
    if got.is_none() {
        return Ok(None);
    }
    let id: u32 = faulted(p, h, "link", got.extract().map_err(Into::into))?;
    Ok(Some(Linked { table, id }))
}

/// `_is_number` with no session: the row, else Python's.
pub(crate) fn free_is_number(h: &Hooks, e: &Bound<'_, PyAny>) -> PyResult<bool> {
    let p = e.py();
    if let Some(l) = term_free(h, e)? {
        return read(p, h, &l, |t, i| t.read_is_number(i));
    }
    tick(session::REL_PY_IS_NUMBER);
    h.relations.bind(p).getattr(intern!(p, "_is_number"))?.call1((e,))?.is_truthy()
}

/// `_own_term`: the order sides of `0 < e` or `e < 0` are `0` and `e` alone, coefficient 1, no `oo`.
fn own_term(sides: &Bound<'_, PyAny>, e: &Bound<'_, PyAny>) -> PyResult<bool> {
    tick(session::REL_OWN_TERM);
    let (a, b) = two(sides)?;
    let ((mut fa, ia), (mut fb, ib)) = (two(&a)?, two(&b)?);
    if ia.is_truthy()? || ib.is_truthy()? {
        return Ok(false);
    }
    if fa.is_truthy()? {
        std::mem::swap(&mut fa, &mut fb);
    }
    let r = !fa.is_truthy()? && fb.len()? == 1 && fb.call_method1(intern!(e.py(), "get"), (e,))?.eq(1)?;
    if r && planted(OWN_TERM_FALSE) {
        return Ok(false);
    }
    Ok(r)
}

#[pyfunction]
fn rel_own_term(sides: &Bound<'_, PyAny>, e: &Bound<'_, PyAny>) -> PyResult<bool> {
    own_term(sides, e)
}

/// `_constant_term`: a closed constant that isn't a rational number. In a session, so the session's link answers.
fn constant_term(rel: &Bound<'_, PyAny>, h: &Hooks, e: &Bound<'_, PyAny>) -> PyResult<bool> {
    let p = rel.py();
    tick(session::REL_CONSTANT_TERM);
    let (_, c) = session_of(p, h, rel)?;
    let l = term_of(&c.borrow(), h, e)?;
    let r = match l {
        Some(l) => read(p, h, &l, |t, i| t.read_is_number(i) && !t.read_is_rational(i))?,
        None => {
            tick(session::REL_PY_IS_NUMBER);
            h.relations.bind(p).getattr(intern!(p, "_is_number"))?.call1((e,))?.is_truthy()? && !e.getattr(intern!(p, "is_Rational"))?.is_truthy()?
        }
    };
    if r && planted(CONSTANT_TERM_NEVER) {
        return Ok(false);
    }
    Ok(r)
}

/// `RULE_INSTANTIATED` as clause masks, kept with the object they came from, as `rules._masks` keys by identity.
/// An `AdapterSpec`, read once. A spec is a NamedTuple, so its fields can't change after Rust reads them. The memo holds the spec
/// itself, so its address isn't reused while the row stands. Specs are made when an engine is set up, so the memo stays small;
/// it's cleared past 4,096 entries anyway.
pub(crate) struct SpecRow {
    pub(crate) name: Py<PyAny>,
    pub(crate) factory: Py<PyAny>,
    pub(crate) guarded: bool,
    /// The factory is one of the default adapter classes (Python's or adapters.rs'), so Rust builds that adapter itself.
    pub(crate) kind: AdKind,
}

#[derive(Clone, Copy, PartialEq, Eq)]
pub(crate) enum AdKind {
    Lra,
    Euf,
    User,
}

/// The adapter for `row`: a default kind is built in Rust (adapters.rs) with no call into Python's factory; a user's factory is
/// called, counted `ad:cb_factory`.
pub(crate) fn make_adapter<'py>(p: Python<'py>, row: &SpecRow) -> PyResult<Bound<'py, PyAny>> {
    let kind = match (row.kind, planted(AD_KIND_SWAP)) {
        (AdKind::Lra, true) => AdKind::Euf,
        (AdKind::Euf, true) => AdKind::Lra,
        (k, _) => k,
    };
    match kind {
        AdKind::Lra => Ok(Bound::new(p, crate::adapters::LraAdapter::build(p, None)?)?.into_any()),
        AdKind::Euf => Ok(Bound::new(p, crate::adapters::EufAdapter::build(p, None)?)?.into_any()),
        AdKind::User => {
            tick(session::AD_CB_FACTORY);
            row.factory.bind(p).call0()
        }
    }
}

/// Which adapter `factory` builds: the default classes by identity, Python's (read from their modules) or Rust's.
fn ad_kind(factory: &Bound<'_, PyAny>) -> PyResult<AdKind> {
    let p = factory.py();
    if factory.is(&p.get_type::<crate::adapters::LraAdapter>()) {
        return Ok(AdKind::Lra);
    }
    if factory.is(&p.get_type::<crate::adapters::EufAdapter>()) {
        return Ok(AdKind::Euf);
    }
    let package = relations_package(p).unwrap_or_else(|| "satassume".to_string());
    for (module, cls, kind) in [("theories.lra.lra_adapter", "LRAAdapter", AdKind::Lra), ("theories.euf.euf_adapter", "EUFAdapter", AdKind::Euf)] {
        // only a module already imported: a factory from a module that never loaded can't be its class
        let sys = p.import(intern!(p, "sys"))?.getattr(intern!(p, "modules"))?;
        if let Some(m) = sys.call_method1(intern!(p, "get"), (format!("{package}.{module}"),)).ok().filter(|m| !m.is_none()) {
            if factory.is(&m.getattr(cls)?) {
                return Ok(kind);
            }
        }
    }
    Ok(AdKind::User)
}

static SPEC_ROWS: std::sync::Mutex<Option<std::collections::HashMap<usize, (Py<PyAny>, Arc<SpecRow>)>>> = std::sync::Mutex::new(None);
/// The specs added to `SPEC_ROWS`, for `_Mark`'s rollback (memos.rs `AddLog`).
static SPEC_LOG: std::sync::Mutex<crate::memos::AddLog<usize>> = std::sync::Mutex::new(crate::memos::AddLog::new());

/// `spec`'s fields, read from Python the first time Rust sees this spec (counted `rel:cb_spec_read`, one tick a field) and from
/// the memo after that. The specs are configuration the user passes in, so they stay Python objects; only this conversion reads them.
pub(crate) fn spec_row(spec: &Bound<'_, PyAny>) -> PyResult<Arc<SpecRow>> {
    let p = spec.py();
    let key = spec.as_ptr() as usize;
    if let Some((_, row)) = SPEC_ROWS.lock().unwrap().as_ref().and_then(|m| m.get(&key)) {
        if planted(SPEC_ROW_FLIP) {
            return Ok(Arc::new(SpecRow { name: row.name.clone_ref(p), factory: row.factory.clone_ref(p), guarded: !row.guarded, kind: row.kind }));
        }
        return Ok(row.clone());
    }
    for _ in 0..3 {
        tick(session::REL_CB_SPEC_READ);
    }
    let factory = spec.getattr(intern!(p, "factory"))?;
    let row = Arc::new(SpecRow {
        name: spec.getattr(intern!(p, "name"))?.unbind(),
        kind: ad_kind(&factory)?,
        factory: factory.unbind(),
        guarded: spec.getattr(intern!(p, "guarded"))?.is_truthy()?,
    });
    let mut g = SPEC_ROWS.lock().unwrap();
    let m = g.get_or_insert_with(Default::default);
    if m.len() >= SPEC_ROWS_SIZE && !planted(MEMO_SPEC_UNBOUNDED) {
        tick(session::MEMO_FULL);
        m.clear();
        SPEC_LOG.lock().unwrap().cleared();
    }
    if m.insert(key, (spec.clone().unbind(), row.clone())).is_none() {
        SPEC_LOG.lock().unwrap().added(key);
    }
    Ok(row)
}

/// `SPEC_ROWS`' bound, as the registry's `NativeTable.size` gives it.
pub(crate) const SPEC_ROWS_SIZE: usize = 4096;

/// memos.rs's accessors of `SPEC_ROWS`.
pub(crate) fn spec_rows_len() -> usize {
    SPEC_ROWS.lock().unwrap().as_ref().map_or(0, |m| m.len())
}

pub(crate) fn spec_rows_clear() {
    if let Some(m) = SPEC_ROWS.lock().unwrap().as_mut() {
        m.clear();
    }
    SPEC_LOG.lock().unwrap().cleared();
}

pub(crate) fn spec_rows_mark() -> (usize, u64) {
    SPEC_LOG.lock().unwrap().mark()
}

/// `_Mark`'s rollback: the rows added after `mark` go; True when the table had to be emptied (it was emptied since the mark).
pub(crate) fn spec_rows_rollback(mark: (usize, u64)) -> bool {
    let since = SPEC_LOG.lock().unwrap().since(mark);
    let mut gone = Vec::new();
    let emptied = {
        let mut g = SPEC_ROWS.lock().unwrap();
        match (since, g.as_mut()) {
            (Some(ks), Some(m)) => {
                gone.extend(ks.into_iter().filter_map(|k| m.remove(&k)));
                false
            }
            (Some(_), None) => false,
            (None, m) => {
                let was = m.as_ref().map_or(0, |m| m.len());
                if let Some(m) = m {
                    gone.extend(m.drain().map(|(_, v)| v));
                }
                SPEC_LOG.lock().unwrap().cleared();
                was > 0 || mark.0 > 0
            }
        }
    };
    drop(gone);     // after the lock is released: a spec's dealloc can run Python code
    emptied
}

/// `[(spec, (name, factory, guarded))]`, converted for the registry view's `items()`.
pub(crate) fn spec_rows_items(p: Python<'_>) -> PyResult<Vec<(Py<PyAny>, Py<PyAny>)>> {
    let g = SPEC_ROWS.lock().unwrap();
    let mut out = Vec::new();
    if let Some(m) = g.as_ref() {
        for (spec, row) in m.values() {
            let v = PyTuple::new(p, [row.name.clone_ref(p).into_bound(p), row.factory.clone_ref(p).into_bound(p),
                                     pyo3::types::PyBool::new(p, row.guarded).to_owned().into_any()])?;
            out.push((spec.clone_ref(p), v.into_any().unbind()));
        }
    }
    Ok(out)
}

static RULE_MASKS: RwLock<Option<(Py<PyAny>, Arc<Vec<u64>>)>> = RwLock::new(None);

fn lit_bit(l: i64) -> PyResult<u32> {
    let b = if l > 0 { 2 * (l - 1) } else { 2 * (-l - 1) + 1 };
    if !(0..64).contains(&b) {
        return Err(PyValueError::new_err(format!("_number_basis: literal {l} outside 64 bits")));
    }
    Ok(b as u32)
}

fn rule_masks(clauses: &Bound<'_, PyAny>) -> PyResult<Arc<Vec<u64>>> {
    if let Some((o, m)) = RULE_MASKS.read().unwrap().as_ref() {
        if o.bind(clauses.py()).is(clauses) {
            return Ok(m.clone());
        }
    }
    let mut masks = Vec::new();
    for c in clauses.try_iter()? {
        let mut m = 0u64;
        for l in c?.try_iter()? {
            m |= 1u64 << lit_bit(l?.extract()?)?;
        }
        masks.push(m);
    }
    let m = Arc::new(masks);
    *RULE_MASKS.write().unwrap() = Some((clauses.clone().unbind(), m.clone()));
    Ok(m)
}

/// `closure_mask`: the unit-propagation fixpoint of `a`, or None on a conflict. All 32 variables' bits are in `even`, which is
/// Python's answer too, since `a` and the clauses set no bit past the variables they reach.
fn closure_mask(masks: &[u64], mut a: u64) -> Option<u64> {
    const EVEN: u64 = 0x5555_5555_5555_5555;
    let mut sw = ((a & EVEN) << 1) | ((a >> 1) & EVEN);
    if a & sw != 0 {
        return None;
    }
    let mut changed = true;
    while changed {
        changed = false;
        for &m in masks {
            if a & m != 0 {
                continue;
            }
            let free = m & !sw;
            if free == 0 {
                return None;
            }
            if free & (free - 1) == 0 {
                a |= free;
                sw |= if free & EVEN != 0 { free << 1 } else { free >> 1 };
                changed = true;
            }
        }
    }
    Some(a)
}

fn lits_mask(ls: &[i64]) -> PyResult<u64> {
    ls.iter().try_fold(0u64, |m, &l| Ok(m | 1u64 << lit_bit(l)?))
}

/// `_number_basis(engine, c, facts)`, memoized in `engine._xbasis` as Python's is. The facts are the engine's (`is_many`, a callback).
fn number_basis<'py>(engine: &Bound<'py, PyAny>, c: &Bound<'py, PyAny>, facts: bool) -> PyResult<Bound<'py, PyAny>> {
    let p = engine.py();
    tick(session::REL_NUMBER_BASIS);
    let pick = |r: &Bound<'py, PyAny>| r.get_item(if facts { 1 } else { 0 });
    let memo = engine.getattr(intern!(p, "_xbasis"))?;
    if let Some(r) = crate::engmemo::get(&memo, c)? {
        if planted(EM_XBASIS_FIRST) {
            if let Some(f) = crate::engmemo::first(&memo)? {
                return pick(&f);
            }
        }
        return pick(&r);
    }
    let rules = p.import(intern!(p, "satassume.knowledge.rules"))?;
    let basis_names = rules.getattr(intern!(p, "BASIS"))?;
    let masks = rule_masks(&rules.getattr(intern!(p, "RULE_INSTANTIATED"))?)?;
    tick(session::REL_CB_IS_MANY);
    let (mut decided, mut open) = (Vec::<i64>::new(), Vec::<i64>::new());
    for (k, v) in engine.call_method1(intern!(p, "is_many"), (c, &basis_names))?.try_iter()?.enumerate() {
        let v = v?;
        let k = k as i64;
        if v.is_none() {
            open.push(k);
        } else if v.is_truthy()? {
            decided.push(k + 1);
        } else {
            decided.push(-(k + 1));
        }
    }
    let want = lits_mask(&decided)?;
    let closes = |lits: &[i64]| -> PyResult<bool> {
        let m = lits_mask(lits)?;
        Ok(match closure_mask(&masks, m) {
            Some(d) => want & !(d | m) == 0,
            None => false,
        })
    };
    let mut basis: Vec<i64>;
    if planted(BASIS_ALL) {
        basis = decided.clone();
    } else {
        basis = Vec::new();
        let mut closed: Option<u64> = Some(0);
        for &l in &decided {
            let bit = 1u64 << lit_bit(l)?;
            if let Some(cm) = closed {
                if cm & bit != 0 {
                    continue;
                }
            }
            basis.push(l);
            if let Some(cm) = closed {
                closed = closure_mask(&masks, cm | bit);
            }
        }
        for l in basis.clone() {
            let rest: Vec<i64> = basis.iter().copied().filter(|&m| m != l).collect();
            if closes(&rest)? {
                basis = rest;
            }
        }
        if !closes(&basis)? {
            basis = decided.clone();
        }
    }
    let mut preds: Vec<i64> = basis.iter().map(|l| l.abs() - 1).chain(open.iter().copied()).collect();
    preds.sort_unstable();
    preds.dedup();
    let fl: Vec<Bound<'py, PyTuple>> =
        basis.iter().map(|&l| PyTuple::new(p, [(l.abs() - 1).into_pyobject(p)?.into_any(), PyBool::new(p, l > 0).to_owned().into_any()])).collect::<PyResult<_>>()?;
    let r = PyTuple::new(p, [PyTuple::new(p, preds)?.into_any(), PyTuple::new(p, fl)?.into_any()])?.into_any();
    crate::engmemo::set(&memo, c, &r)?;
    pick(&r)
}

#[pyfunction]
#[pyo3(signature = (engine, c, facts=false))]
fn rel_number_basis<'py>(engine: &Bound<'py, PyAny>, c: &Bound<'py, PyAny>, facts: bool) -> PyResult<Bound<'py, PyAny>> {
    number_basis(engine, c, facts)
}

#[pyfunction]
fn rel_number_facts<'py>(engine: &Bound<'py, PyAny>, c: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    number_basis(engine, c, true)
}

/// `sympy_atom`: `Q.eq(a, b)` / `Q.lt(a, b)` for a normalised relation atom, memoized in Python's `_SYMPY_ATOMS`.
fn sympy_atom<'py>(_h: &Hooks, atom: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let p = atom.py();
    tick(session::REL_SYMPY_ATOM);
    if let Some(r) = crate::procmemo::atoms_get(atom)? {
        if !r.is_none() {
            return Ok(r);
        }
    }
    let q = p.import(intern!(p, "sympy.assumptions"))?.getattr(intern!(p, "Q"))?;
    let pred = atom.getattr(intern!(p, "pred"))?;
    let ps: String = pred.extract()?;
    let f = match ps.as_str() {
        "eq" => q.getattr(intern!(p, "eq"))?,
        "lt" => q.getattr(intern!(p, "lt"))?,
        _ => return Err(PyKeyError::new_err(pred.unbind())),
    };
    let mut args: Vec<Bound<'py, PyAny>> = atom.getattr(intern!(p, "expr"))?.try_iter()?.collect::<PyResult<_>>()?;
    if ps == "lt" && args.len() == 2 && planted(SYMPY_ATOM_SWAP) {
        args.swap(0, 1);
    }
    tick(session::REL_CB_SYMPY_Q);
    let r = f.call1(PyTuple::new(p, args)?)?;
    crate::procmemo::atoms_put(atom, &r)?;
    Ok(r)
}

#[pyfunction]
fn rel_sympy_atom<'py>(atom: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    sympy_atom(&*hooks()?, atom)
}

/// `zero_args`: the arguments (no number) of the `zero` atoms, in first-seen order.
fn zero_args<'py>(h: &Hooks, atoms: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyTuple>> {
    let p = atoms.py();
    tick(session::REL_ZERO_ARGS);
    let zs = PyList::empty(p);
    for a in atoms.try_iter()? {
        let a = a?;
        if a.getattr(intern!(p, "pred"))?.eq(intern!(p, "zero"))? {
            let e = a.getattr(intern!(p, "expr"))?;
            if !zs.contains(&e)? && !free_is_number(h, &e)? {
                if planted(ZERO_ARGS_EMPTY) {
                    continue;
                }
                zs.append(e)?;
            }
        }
    }
    PyTuple::new(p, zs)
}

#[pyfunction]
fn rel_zero_args<'py>(atoms: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyTuple>> {
    zero_args(&*hooks()?, atoms)
}

/// `under_of`: the union of `_under_apps` of each atom's argument, built as Python's `|` builds it.
fn under_of<'py>(h: &Hooks, atoms: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let p = atoms.py();
    tick(session::REL_UNDER_OF);
    let ua = h.relations.bind(p).getattr(intern!(p, "_under_apps"))?;
    let mut out = pyo3::types::PyFrozenSet::empty(p)?.into_any();
    for a in atoms.try_iter()? {
        tick(session::REL_CB_UNDER_APPS);
        let u = ua.call1((a?.getattr(intern!(p, "expr"))?,))?;
        if u.is_truthy()? {
            if planted(UNDER_OF_EMPTY) {
                continue;
            }
            out = out.bitor(&u)?;
        }
    }
    Ok(out)
}

#[pyfunction]
fn rel_under_of<'py>(atoms: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    under_of(&*hooks()?, atoms)
}

/// `zero_twins(atoms, context, cinfo)`.
fn zero_twins<'py>(h: &Hooks, atoms: &Bound<'py, PyAny>, context: &Bound<'py, PyAny>, cinfo: Option<&Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyList>> {
    let p = atoms.py();
    tick(session::REL_ZERO_TWINS);
    let (czs, mut cunder) = match cinfo {
        None => (zero_args(h, context)?.into_any(), None),
        Some(ci) => {
            let (a, b) = two(ci)?;
            (a, if b.is_none() { None } else { Some(b) })
        }
    };
    let zs = zero_args(h, atoms)?;
    let out = PyList::empty(p);
    if !zs.is_truthy()? && !czs.is_truthy()? {
        return Ok(out);
    }
    let cunder = match cunder.take() {
        Some(u) => u,
        None => under_of(h, context)?,
    };
    let under = under_of(h, atoms)?;
    if !under.is_truthy()? && !cunder.is_truthy()? {
        return Ok(out);
    }
    let zt = h.relations.bind(p).getattr(intern!(p, "zero_twin"))?;
    for e in zs.into_any().add(&czs)?.try_iter()? {
        let e = e?;
        if under.contains(&e)? || cunder.contains(&e)? {
            tick(session::REL_CB_ZERO_TWIN);
            let tw = zt.call1((&e,))?;
            if !out.contains(&tw)? {
                if !out.is_empty() && planted(ZERO_TWINS_FIRST) {
                    continue;
                }
                out.append(tw)?;
            }
        }
    }
    Ok(out)
}

#[pyfunction]
#[pyo3(signature = (atoms, context=None, cinfo=None))]
fn rel_zero_twins<'py>(atoms: &Bound<'py, PyAny>, context: Option<&Bound<'py, PyAny>>, cinfo: Option<&Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyList>> {
    let p = atoms.py();
    let empty = PyTuple::empty(p).into_any();
    zero_twins(&*hooks()?, atoms, context.unwrap_or(&empty), cinfo.filter(|c| !c.is_none()))
}

/// `glue_atoms`: `atoms`, then the twins it lacks; `atoms` itself if there is none.
#[pyfunction]
#[pyo3(signature = (atoms, context=None, cinfo=None))]
pub(crate) fn rel_glue_atoms<'py>(atoms: &Bound<'py, PyAny>, context: Option<&Bound<'py, PyAny>>, cinfo: Option<&Bound<'py, PyAny>>) -> PyResult<Bound<'py, PyAny>> {
    let p = atoms.py();
    let h = hooks()?;
    tick(session::REL_GLUE_ATOMS);
    let empty = PyTuple::empty(p).into_any();
    let twins = zero_twins(&h, atoms, context.unwrap_or(&empty), cinfo.filter(|c| !c.is_none()))?;
    if twins.is_empty() || planted(GLUE_NO_TWINS) {
        return Ok(atoms.clone());
    }
    let have = PySet::new(p, atoms.try_iter()?.collect::<PyResult<Vec<_>>>()?)?;
    let mut v: Vec<Bound<'py, PyAny>> = atoms.try_iter()?.collect::<PyResult<_>>()?;
    for tw in twins.iter() {
        if !have.contains(&tw)? {
            v.push(tw);
        }
    }
    Ok(PyTuple::new(p, v)?.into_any())
}

/// `_guarded_adapters`: one adapter per guarded spec, kept in `memo` by name.
fn guarded_adapters<'py>(specs: &Bound<'py, PyAny>, memo: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyList>> {
    let p = specs.py();
    tick(session::REL_GUARDED_ADAPTERS);
    let out = PyList::empty(p);
    for spec in specs.try_iter()? {
        let spec = spec?;
        let row = spec_row(&spec)?;
        if row.guarded {
            if planted(GUARDED_NONE) {
                continue;
            }
            let name = row.name.bind(p);
            let ad = match crate::engmemo::get(memo, name.as_any())? {
                Some(ad) => ad,
                None => {
                    tick(session::REL_CB_ADAPTER_READ);
                    let ad = make_adapter(p, &row)?;
                    if !planted(EM_GLUE_NO_STORE) {
                        crate::engmemo::set(memo, name.as_any(), &ad)?;
                    }
                    ad
                }
            };
            out.append(ad)?;
        }
    }
    Ok(out)
}

#[pyfunction]
fn rel_guarded_adapters<'py>(specs: &Bound<'py, PyAny>, memo: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyList>> {
    guarded_adapters(specs, memo)
}

/// `_terms_of`: the opaque terms an adapter reads in `sat`, the order sides' too when `order`.
fn terms_of<'py>(ad: &Bound<'py, PyAny>, sat: &Bound<'py, PyAny>, order: bool) -> PyResult<Bound<'py, PySet>> {
    let p = ad.py();
    tick(session::REL_TERMS_OF);
    let k = PySet::empty(p)?;
    if order && ad.hasattr(intern!(p, "order_sides"))? {
        tick(session::REL_CB_ADAPTER_READ);
        let sides = ad.call_method1(intern!(p, "order_sides"), (sat,))?;
        if !sides.is_none() && !planted(TERMS_OF_NO_ORDER) {
            for s in sides.try_iter()? {
                let (form, _inf) = two(&s?)?;
                k.call_method1(intern!(p, "update"), (form,))?;
            }
        }
    }
    tick(session::REL_CB_ADAPTER_READ);
    let terms = ad.call_method1(intern!(p, "terms"), (sat,))?;
    if terms.is_truthy()? {
        k.call_method1(intern!(p, "update"), (terms,))?;
    }
    Ok(k)
}

#[pyfunction]
fn rel_terms_of<'py>(ad: &Bound<'py, PyAny>, sat: &Bound<'py, PyAny>, order: bool) -> PyResult<Bound<'py, PySet>> {
    terms_of(ad, sat, order)
}

/// `glue_objects(atom, specs, memo)` for a relation atom that isn't a two-sided `eq` (state step part 2 (iii)): Python's
/// relations.py:1994 without its eq branch. Each side, and `link_objects` of each side that isn't a number, then the adapters'
/// terms of the atom (`lt` reads order), the atom itself left out. Its `except Exception` around the adapters is Python's.
/// The two-sided `eq` keeps term_live's `glue_objects` (the difference on ids).
pub(crate) fn glue_objects_plain<'py>(atom: &Bound<'py, PyAny>, specs: &Bound<'py, PyAny>, memo: &Bound<'py, PyAny>)
    -> PyResult<Bound<'py, PySet>> {
    let p = atom.py();
    let h = hooks()?;
    tick(session::GL_PLAIN);
    let k = PySet::empty(p)?;
    for e in atom.getattr(intern!(p, "expr"))?.try_iter()? {
        let e = e?;
        k.add(&e)?;
        if !free_is_number(&h, &e)? && !planted(GL_PLAIN_NO_LINK) {
            k.call_method1(intern!(p, "update"), (rel_link_objects(&e, specs, memo)?,))?;
        }
    }
    if specs.is_truthy()? {
        let body = || -> PyResult<()> {
            let sat = sympy_atom(&h, atom)?;
            let lt = atom.getattr(intern!(p, "pred"))?.eq(intern!(p, "lt"))?;
            for ad in guarded_adapters(specs, memo)?.iter() {
                k.call_method1(intern!(p, "update"), (terms_of(&ad, &sat, lt)?,))?;
            }
            Ok(())
        };
        match body() {
            Ok(()) => {}
            Err(x) if x.is_instance_of::<PyException>(p) => {}
            Err(x) => return Err(x),
        }
    }
    k.discard(atom)?;
    Ok(k)
}

/// `glue_objects_plain` for tests (test_glue_plain.py compares it with Python's `glue_objects`).
#[pyfunction]
fn rel_glue_objects_plain<'py>(atom: &Bound<'py, PyAny>, specs: &Bound<'py, PyAny>, memo: &Bound<'py, PyAny>)
    -> PyResult<Bound<'py, PySet>> {
    glue_objects_plain(atom, specs, memo)
}

/// `link_objects`: the nodes `Relations._link(e)` can visit. Its `except Exception` is Python's: an ordinary exception from a side
/// the adapters can't read ends the reading, and a `BaseException` (`TermFault`) goes on up.
#[pyfunction]
fn rel_link_objects<'py>(e: &Bound<'py, PyAny>, specs: &Bound<'py, PyAny>, memo: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PySet>> {
    let p = e.py();
    let h = hooks()?;
    tick(session::REL_LINK_OBJECTS);
    let k = PySet::new(p, [e])?;
    if free_is_number(&h, e)? {
        return Ok(k);
    }
    if planted(LINK_OBJECTS_BARE) {
        return Ok(k);
    }
    let r = h.relations.bind(p);
    tick(session::REL_CB_STRUCTURAL_SUBTERMS);
    k.call_method1(intern!(p, "update"), (r.getattr(intern!(p, "_structural_subterms"))?.call1((e,))?,))?;
    let body = || -> PyResult<()> {
        let zero = p.import(intern!(p, "sympy"))?.getattr(intern!(p, "S"))?.getattr(intern!(p, "Zero"))?;
        let ra = r.getattr(intern!(p, "relation_atom"))?;
        for ad in guarded_adapters(specs, memo)?.iter() {
            if r.getattr(intern!(p, "INTEGERS"))?.is_truthy()? && ad.hasattr(intern!(p, "integer_form"))? {
                tick(session::REL_CB_ADAPTER_READ);
                let form = ad.call_method1(intern!(p, "integer_form"), (e,))?;
                if !form.is_none() {
                    k.call_method1(intern!(p, "update"), (form.get_item(1)?,))?;
                }
            }
            let mut atoms = Vec::with_capacity(3);
            for (pr, a, b) in [("lt", &zero, e), ("lt", e, &zero), ("eq", e, &zero)] {
                tick(session::REL_CB_RELATION_ATOM);
                atoms.push(ra.call1((pr, a, b))?);
            }
            for atom in &atoms {
                let lt = atom.getattr(intern!(p, "pred"))?.eq(intern!(p, "lt"))?;
                k.call_method1(intern!(p, "update"), (terms_of(&ad, &sympy_atom(&h, atom)?, lt)?,))?;
            }
        }
        Ok(())
    };
    match body() {
        Ok(()) => {}
        Err(x) if x.is_instance_of::<PyException>(p) => {}
        Err(x) => return Err(x),
    }
    Ok(k)
}

/// `closed_units`: the sign facts of a closed compound term as a unit pattern, memoized in Python's `_CLOSED`.
fn closed_units<'py>(node: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let p = node.py();
    let h = hooks()?;
    tick(session::REL_CLOSED_UNITS);
    let _ = &h;
    match crate::procmemo::closed_get(node) {
        Ok(Some(r)) => return Ok(r),
        Ok(None) => {}
        Err(x) if x.is_instance_of::<pyo3::exceptions::PyTypeError>(p) => return Ok(p.None().into_bound(p)),
        Err(x) => return Err(x),
    }
    let mut r = p.None().into_bound(p);
    let num = match node.getattr_opt(intern!(p, "is_number"))? {
        Some(v) => v.is_truthy()?,
        None => false,
    };
    if num && !node.getattr(intern!(p, "is_Atom"))?.is_truthy()? {
        let closed_sign = p.import(intern!(p, "satassume.theories.lra.lra_adapter"))?.getattr(intern!(p, "closed_sign"))?;
        let units = p.import(intern!(p, "satassume.knowledge.templates._common"))?.getattr(intern!(p, "units"))?;
        tick(session::REL_CB_CLOSED_SIGN);
        let (s, real) = two(&closed_sign.call1((node,))?)?;
        if !s.is_none() || real.is_truthy()? {
            let sv: Option<i64> = s.extract()?;
            let pred = match sv {
                Some(1) => "positive",
                Some(-1) => "negative",
                Some(0) => "zero",
                None => "real",
                Some(_) => return Err(PyKeyError::new_err(s.unbind())),
            };
            let facts: Py<PyAny> = PyList::new(p, [(pred, true)])?.into_any().unbind();
            let thunk = pyo3::types::PyCFunction::new_closure(p, None, None, move |a, _| Ok::<_, PyErr>(facts.clone_ref(a.py())))?;
            if planted(CLOSED_UNITS_NONE) {
                // the pattern is left out, as if nothing were decided
            } else {
                tick(session::REL_CB_UNITS);
                r = units.call1((("closed_sign", &s), thunk, node))?;
            }
        }
    }
    crate::procmemo::closed_put(node, &r)?;
    Ok(r)
}

#[pyfunction]
fn rel_closed_units<'py>(node: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    closed_units(node)
}

/// `with_closed_units(clause_templates)`'s closure.
#[pyclass(name = "ClosedUnits", module = "sa_solver", frozen)]
struct ClosedUnits {
    inner: Py<PyAny>,
}

#[pymethods]
impl ClosedUnits {
    fn __call__<'py>(&self, node: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyTuple>> {
        let p = node.py();
        tick(session::REL_WITH_CLOSED_UNITS);
        tick(session::REL_CB_CLAUSE_TEMPLATES);
        let (compiled, formulas) = two(&self.inner.bind(p).call1((node,))?)?;
        let c = closed_units(node)?;
        if c.is_none() || planted(WITH_CLOSED_SKIP) {
            return PyTuple::new(p, [compiled, formulas]);
        }
        let l = PyList::new(p, compiled.try_iter()?.collect::<PyResult<Vec<_>>>()?)?;
        l.append(c)?;
        PyTuple::new(p, [l.into_any(), formulas])
    }
}

#[pyfunction]
fn rel_with_closed_units(clause_templates: Py<PyAny>) -> ClosedUnits {
    ClosedUnits { inner: clause_templates }
}

/// `_missing`: whether `e` says `module` (relative to the package) doesn't exist, not that a module it imports is missing.
fn missing(p: Python<'_>, e: &PyErr, package: &str, module: &str) -> PyResult<bool> {
    Ok(e.value(p).getattr(intern!(p, "name"))?.eq(format!("{package}.{module}"))?)
}

#[pyfunction]
fn rel_missing(p: Python<'_>, e: &Bound<'_, PyAny>, module: &str) -> PyResult<bool> {
    let h = hooks()?;
    let package: String = h.relations.bind(p).getattr(intern!(p, "__package__"))?.extract()?;
    missing(p, &PyErr::from_value(e.clone()), &package, module)
}

/// `default_specs`: the real adapters; one whose module doesn't exist is left out, one that fails to import raises.
#[pyfunction]
fn rel_default_specs(p: Python<'_>) -> PyResult<Bound<'_, PyList>> {
    let h = hooks()?;
    tick(session::REL_DEFAULT_SPECS);
    let r = h.relations.bind(p);
    let package: String = r.getattr(intern!(p, "__package__"))?.extract()?;
    let spec = r.getattr(intern!(p, "AdapterSpec"))?;
    let specs = PyList::empty(p);
    for (module, cls, name, guarded) in [("theories.lra.lra_adapter", "LRAAdapter", "lra", true), ("theories.euf.euf_adapter", "EUFAdapter", "euf", false)] {
        match p.import(format!("{package}.{module}").as_str()) {
            Ok(m) => {
                if name == "euf" && planted(SPECS_NO_EUF) {
                    continue;
                }
                specs.append(spec.call1((name, m.getattr(cls)?, guarded))?)?;
            }
            Err(e) if e.is_instance_of::<pyo3::exceptions::PyModuleNotFoundError>(p) => {
                if !missing(p, &e, &package, module)? {
                    return Err(e);
                }
            }
            Err(e) => return Err(e),
        }
    }
    Ok(specs)
}

/// `relational_name`: `eq ne lt le gt ge` for a SymPy `Relational`.
#[pyfunction]
fn rel_relational_name<'py>(rel: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyString>> {
    let p = rel.py();
    tick(session::REL_RELATIONAL_NAME);
    let op = rel.getattr(intern!(p, "rel_op"))?;
    let name = match op.extract::<String>().ok().as_deref() {
        Some("==") => "eq",
        Some("!=") => "ne",
        Some("<") => if planted(RELNAME_SWAP) { "gt" } else { "lt" },
        Some("<=") => "le",
        Some(">") => "gt",
        Some(">=") => "ge",
        _ => return Err(PyKeyError::new_err(op.unbind())),
    };
    Ok(PyString::new(p, name))
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("REL_KINDS", (SD, EN, MC, IE, IL))?;
    m.add_function(wrap_pyfunction!(rel_link_probe, m)?)?;
    m.add_function(wrap_pyfunction!(rel_install, m)?)?;
    m.add_function(wrap_pyfunction!(rel_plant, m)?)?;
    m.add_function(wrap_pyfunction!(rel_closed_extended_real, m)?)?;
    m.add_function(wrap_pyfunction!(rel_order_sides, m)?)?;
    m.add_function(wrap_pyfunction!(rel_order_infinite, m)?)?;
    m.add_function(wrap_pyfunction!(rel_trichotomy, m)?)?;
    m.add_function(wrap_pyfunction!(rel_mention_number, m)?)?;
    m.add_function(wrap_pyfunction!(rel_link_integer, m)?)?;
    m.add_function(wrap_pyfunction!(rel_fresh, m)?)?;
    m.add_function(wrap_pyfunction!(rel_bound, m)?)?;
    m.add_function(wrap_pyfunction!(rel_guard, m)?)?;
    m.add_function(wrap_pyfunction!(rel_eq_infinity, m)?)?;
    m.add_function(wrap_pyfunction!(rel_interpret, m)?)?;
    m.add_function(wrap_pyfunction!(rel_link, m)?)?;
    m.add_function(wrap_pyfunction!(rel_observe, m)?)?;
    m.add_function(wrap_pyfunction!(rel_selectors_of, m)?)?;
    m.add_function(wrap_pyfunction!(rel_add_role, m)?)?;
    m.add_function(wrap_pyfunction!(rel_apply_role, m)?)?;
    m.add_function(wrap_pyfunction!(rel_tsource, m)?)?;
    m.add_function(wrap_pyfunction!(rel_tvar, m)?)?;
    m.add_function(wrap_pyfunction!(rel_share_guard, m)?)?;
    m.add_function(wrap_pyfunction!(rel_congruent, m)?)?;
    m.add_function(wrap_pyfunction!(rel_engage_transfer, m)?)?;
    m.add_function(wrap_pyfunction!(rel_transfer_terms, m)?)?;
    m.add_function(wrap_pyfunction!(rel_sync_transfer, m)?)?;
    m.add_function(wrap_pyfunction!(rel_xswitch, m)?)?;
    m.add_function(wrap_pyfunction!(rel_congruence_pairs, m)?)?;
    m.add_function(wrap_pyfunction!(rel_init, m)?)?;
    m.add_function(wrap_pyfunction!(rel_enqueue, m)?)?;
    m.add_function(wrap_pyfunction!(rel_note_formula, m)?)?;
    m.add_function(wrap_pyfunction!(rel_process, m)?)?;
    m.add_function(wrap_pyfunction!(rel_link_later, m)?)?;
    m.add_function(wrap_pyfunction!(rel_wants_transfer, m)?)?;
    m.add_function(wrap_pyfunction!(rel_share, m)?)?;
    m.add_function(wrap_pyfunction!(rel_adapter, m)?)?;
    m.add_function(wrap_pyfunction!(rel_atom_selector, m)?)?;
    m.add_function(wrap_pyfunction!(rel_atom_var, m)?)?;
    m.add_function(wrap_pyfunction!(rel_note_sides, m)?)?;
    m.add_function(wrap_pyfunction!(rel_eq_links, m)?)?;
    m.add_class::<ClosedUnits>()?;
    m.add_function(wrap_pyfunction!(rel_own_term, m)?)?;
    m.add_function(wrap_pyfunction!(rel_number_basis, m)?)?;
    m.add_function(wrap_pyfunction!(rel_number_facts, m)?)?;
    m.add_function(wrap_pyfunction!(rel_sympy_atom, m)?)?;
    m.add_function(wrap_pyfunction!(rel_zero_args, m)?)?;
    m.add_function(wrap_pyfunction!(rel_under_of, m)?)?;
    m.add_function(wrap_pyfunction!(rel_zero_twins, m)?)?;
    m.add_function(wrap_pyfunction!(rel_glue_atoms, m)?)?;
    m.add_function(wrap_pyfunction!(rel_guarded_adapters, m)?)?;
    m.add_function(wrap_pyfunction!(rel_terms_of, m)?)?;
    m.add_function(wrap_pyfunction!(rel_link_objects, m)?)?;
    m.add_function(wrap_pyfunction!(rel_glue_objects_plain, m)?)?;
    m.add_function(wrap_pyfunction!(rel_closed_units, m)?)?;
    m.add_function(wrap_pyfunction!(rel_with_closed_units, m)?)?;
    m.add_function(wrap_pyfunction!(rel_missing, m)?)?;
    m.add_function(wrap_pyfunction!(rel_default_specs, m)?)?;
    m.add_function(wrap_pyfunction!(rel_relational_name, m)?)?;
    Ok(())
}
