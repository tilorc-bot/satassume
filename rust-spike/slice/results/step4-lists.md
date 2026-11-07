## internals

| test | raised at | reason | on Python |
|---|---|---|---|
| `tests/test_euf.py::test_solver_congruence_unsat_and_sat` | `tests/theory_harness.py:219` | _val | passed |
| `tests/test_euf.py::test_solver_transitivity_unsat` | `tests/theory_harness.py:219` | _val | passed |
| `tests/test_euf.py::test_solver_values` | `tests/theory_harness.py:219` | _val | passed |
| `tests/test_euf_fuzz.py::test_perf_through_solver_chain` | `tests/theory_harness.py:219` | _val | passed |
| `tests/test_euf_fuzz.py::test_perf_through_solver_disjunctive_chain` | `tests/theory_harness.py:219` | _val | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[13]` | `tests/theory_harness.py:219` | _val | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[15]` | `tests/theory_harness.py:219` | _val | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[16]` | `tests/theory_harness.py:219` | _val | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[18]` | `tests/theory_harness.py:345` | _trail_lim | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[20]` | `tests/theory_harness.py:219` | _val | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[23]` | `tests/theory_harness.py:219` | _val | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[25]` | `tests/theory_harness.py:219` | _val | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[26]` | `tests/theory_harness.py:345` | _trail_lim | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[27]` | `tests/theory_harness.py:219` | _val | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[6]` | `tests/theory_harness.py:219` | _val | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[8]` | `tests/theory_harness.py:345` | _trail_lim | passed |
| `tests/test_lra_fuzz.py::test_solver_finds_the_only_consistent_assignment` | `tests/theory_harness.py:219` | _val | passed |
| `tests/test_solver.py::test_held_levels_continue_from_the_common_prefix` | `tests/test_solver.py:1010` | _held | passed |
| `tests/test_solver.py::test_mention_blocks_inside_a_registered_block` | `tests/test_solver.py:825` | _lazy | passed |
| `tests/test_solver.py::test_mention_blocks_kept_until_an_overlapping_registration` | `tests/test_solver.py:837` | _lazy | passed |
| `tests/test_solver.py::test_provenance_keeps_literals_dropped_from_a_shortened_clause[add_clause]` | `tests/test_solver.py:962` | provenance | passed |
| `tests/test_solver.py::test_provenance_keeps_literals_dropped_from_a_shortened_clause[add_clauses]` | `tests/test_solver.py:962` | provenance | passed |
| `tests/test_solver.py::test_provenance_keeps_literals_dropped_from_a_shortened_clause[add_internal]` | `tests/test_solver.py:962` | provenance | passed |
| `tests/test_solver.py::test_provenance_keeps_literals_dropped_from_a_shortened_clause[add_pattern]` | `tests/test_solver.py:962` | provenance | passed |
| `tests/test_solver.py::test_register_block_mentions_either_literal_bit` | `tests/test_solver.py:815` | _lazy | passed |
| `tests/test_solver.py::test_register_block_while_levels_are_held` | `tests/test_solver.py:748` | _held | passed |
| `tests/test_solver.py::test_rule_block_api_errors_and_shared_tables` | `tests/test_solver.py:852` | _rbc | passed |
| `tests/test_solver.py::test_rule_block_conflict_analysis_reads_propagator_reasons` | `tests/test_solver.py:650` | subclass override of _rb_reason | passed |
| `tests/test_solver.py::test_rule_block_final_conflict_reads_propagator_reasons` | `tests/test_solver.py:664` | subclass override of _rb_reason | passed |
| `tests/test_solver.py::test_rule_block_random_search_like_clauses` | `tests/test_solver.py:699` | subclass override of _rb_reason | passed |
| `tests/test_solver.py::test_rule_block_with_held_levels` | `tests/test_solver.py:710` | _held | passed |
| `tests/test_solver_incremental.py::test_block_mix_covers_the_propagator_paths` | `tests/test_solver_incremental.py:310` | _held | passed |
| `tests/test_solver_incremental.py::test_block_propagator_matches_clauses[0]` | `tests/test_solver_incremental.py:310` | _held | passed |
| `tests/test_solver_incremental.py::test_block_propagator_matches_clauses[1]` | `tests/test_solver_incremental.py:359` | _trail_lim | passed |
| `tests/test_solver_incremental.py::test_block_propagator_matches_clauses[2]` | `tests/test_solver_incremental.py:270` | _ok | passed |
| `tests/test_solver_incremental.py::test_block_propagator_matches_clauses[3]` | `tests/test_solver_incremental.py:310` | _held | passed |
| `tests/test_solver_incremental.py::test_block_propagator_matches_clauses[4]` | `tests/test_solver_incremental.py:359` | _trail_lim | passed |
| `tests/test_solver_incremental.py::test_block_propagator_matches_clauses[5]` | `tests/test_solver_incremental.py:359` | _trail_lim | passed |
| `tests/test_solver_incremental.py::test_block_propagator_with_theory_matches_clauses[0]` | `tests/test_solver_incremental.py:310` | _held | passed |
| `tests/test_solver_incremental.py::test_block_propagator_with_theory_matches_clauses[1]` | `tests/test_solver_incremental.py:359` | _trail_lim | passed |
| `tests/test_solver_incremental.py::test_block_propagator_with_theory_matches_clauses[2]` | `tests/test_solver_incremental.py:270` | _ok | passed |
| `tests/test_solver_incremental.py::test_block_propagator_with_theory_matches_clauses[3]` | `tests/test_solver_incremental.py:310` | _held | passed |
| `tests/test_solver_incremental.py::test_block_propagator_with_theory_matches_clauses[4]` | `tests/test_solver_incremental.py:359` | _trail_lim | passed |
| `tests/test_solver_incremental.py::test_block_propagator_with_theory_matches_clauses[5]` | `tests/test_solver_incremental.py:359` | _trail_lim | passed |
| `tests/test_solver_incremental.py::test_engine_mention_paths_cover` | `tests/test_solver_incremental.py:939` | _rb_n | passed |
| `tests/test_solver_incremental.py::test_engine_mention_paths_match_clauses[0]` | `tests/test_solver_incremental.py:939` | _rb_n | passed |
| `tests/test_solver_incremental.py::test_engine_mention_paths_match_clauses[1]` | `tests/test_solver_incremental.py:939` | _rb_n | passed |
| `tests/test_solver_incremental.py::test_engine_mention_paths_match_clauses[2]` | `tests/test_solver_incremental.py:939` | _rb_n | passed |
| `tests/test_solver_incremental.py::test_engine_mention_paths_match_clauses[3]` | `tests/test_solver_incremental.py:939` | _rb_n | passed |
| `tests/test_solver_incremental.py::test_engine_mention_paths_match_clauses[4]` | `tests/test_solver_incremental.py:939` | _rb_n | passed |
| `tests/test_solver_incremental.py::test_engine_mention_paths_match_clauses[5]` | `tests/test_solver_incremental.py:939` | _rb_n | passed |
| `tests/test_solver_incremental.py::test_harness_catches_a_dropped_clause` | `tests/test_solver_incremental.py:359` | _trail_lim | passed |
| `tests/test_solver_incremental.py::test_harness_catches_a_stale_witness` | `tests/test_solver_incremental.py:1118` | _ring_hit | passed |
| `tests/test_solver_incremental.py::test_harness_catches_a_weak_propagator` | `tests/test_solver_incremental.py:310` | _held | passed |
| `tests/test_solver_incremental.py::test_incremental_matches_fresh[0]` | `tests/test_solver_incremental.py:359` | _trail_lim | passed |
| `tests/test_solver_incremental.py::test_incremental_matches_fresh[1]` | `tests/test_solver_incremental.py:359` | _trail_lim | passed |
| `tests/test_solver_incremental.py::test_incremental_matches_fresh[2]` | `tests/test_solver_incremental.py:359` | _trail_lim | passed |
| `tests/test_solver_incremental.py::test_incremental_matches_fresh[3]` | `tests/test_solver_incremental.py:310` | _held | passed |
| `tests/test_solver_incremental.py::test_incremental_matches_fresh[4]` | `tests/test_solver_incremental.py:270` | _ok | passed |
| `tests/test_solver_incremental.py::test_incremental_matches_fresh[5]` | `tests/test_solver_incremental.py:310` | _held | passed |
| `tests/test_solver_incremental.py::test_incremental_matches_fresh_with_hold[0]` | `tests/test_solver_incremental.py:359` | _trail_lim | passed |
| `tests/test_solver_incremental.py::test_incremental_matches_fresh_with_hold[1]` | `tests/test_solver_incremental.py:359` | _trail_lim | passed |
| `tests/test_solver_incremental.py::test_incremental_matches_fresh_with_hold[2]` | `tests/test_solver_incremental.py:359` | _trail_lim | passed |
| `tests/test_solver_incremental.py::test_incremental_matches_fresh_with_hold[3]` | `tests/test_solver_incremental.py:310` | _held | passed |
| `tests/test_solver_incremental.py::test_incremental_matches_fresh_with_hold[4]` | `tests/test_solver_incremental.py:270` | _ok | passed |
| `tests/test_solver_incremental.py::test_incremental_matches_fresh_with_hold[5]` | `tests/test_solver_incremental.py:310` | _held | passed |
| `tests/test_solver_incremental.py::test_mix_covers_the_incremental_paths` | `tests/test_solver_incremental.py:359` | _trail_lim | passed |
| `tests/test_solver_real_theories.py::test_real_theories_match_fresh_solvers[euf]` | `tests/theory_harness.py:269` | _trail_lim | passed |
| `tests/test_solver_real_theories.py::test_real_theories_match_fresh_solvers[lra]` | `tests/theory_harness.py:269` | _trail_lim | passed |
| `tests/test_theory_hooks.py::test_implied_and_entails_see_theory_conflicts` | `tests/theory_harness.py:219` | _val | passed |
| `tests/test_theory_hooks.py::test_root_conflict_makes_solver_unsat` | `tests/theory_harness.py:219` | _val | passed |
| `tests/test_theory_hooks.py::test_theories_see_only_their_atoms` | `tests/theory_harness.py:219` | _val | passed |
| `tests/test_transfer.py::test_models_respect_transfer` | `tests/test_transfer.py:182` | _solve | passed |
| `tests/test_verify_integration.py::test_theory_levels_match_the_solver_after_ask` | `tests/test_verify_integration.py:95` | _trail_lim | passed |
| `tests/test_writeback_provenance.py::test_root_only_is_the_default_and_sessions_track_no_owners` | `tests/test_writeback_provenance.py:212` | _cowner | passed |
| `tests/test_writeback_provenance.py::test_solver_provenance_through_a_reason_dag` | `tests/test_writeback_provenance.py:29` | provenance | passed |
| `tests/test_writeback_provenance.py::test_solver_provenance_unknown_unit_is_bottom` | `tests/test_writeback_provenance.py:60` | provenance | passed |

## reentry

| test | raised at | reason | on Python |
|---|---|---|---|
| `tests/test_euf.py::test_solver_entails_equality_and_disequality` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_euf.py::test_solver_picks_consistent_disjunct` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_euf.py::test_solver_reflexive_atom_is_valid` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_euf.py::test_solver_repeated_queries_reuse_learnt_theory_clauses` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_euf_fuzz.py::test_dpll_t_matches_enumeration` | `tests/test_euf_fuzz.py:555` | borrow RuntimeError | passed |
| `tests/test_euf_fuzz.py::test_every_full_assignment_through_solver` | `tests/test_euf_fuzz.py:574` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_fuzz_entails_and_implied` | `tests/test_lra_fuzz.py:212` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_fuzz_solve_against_enumeration` | `tests/test_lra_fuzz.py:200` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[0]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[10]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[11]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[12]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[14]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[17]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[19]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[1]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[21]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[22]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[24]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[28]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[29]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[2]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[30]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[31]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[32]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[33]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[34]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[35]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[36]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[37]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[38]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[39]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[3]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[4]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[5]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[7]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_lra_fuzz.py::test_random_cnf_repeated_queries[9]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_solver_real_theories.py::test_real_theories_match_fresh_solvers[both]` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_theory_hooks.py::test_assumptions_already_true_open_levels_too` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_theory_hooks.py::test_exact_sequence_eager` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_theory_hooks.py::test_exact_sequence_lazy_conflict_is_learnt` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_theory_hooks.py::test_propagation_assigns_with_reason` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_theory_hooks.py::test_random_forbid_theory_matches_brute_force` | `tests/test_theory_hooks.py:217` | borrow RuntimeError | passed |
| `tests/test_theory_hooks.py::test_registration_after_cursor_is_not_double_reported` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_theory_hooks.py::test_root_facts_are_reported_once_without_levels` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |
| `tests/test_transfer.py::test_protocol_on_fuzz` | `tests/theory_harness.py:242` | borrow RuntimeError | passed |

