# Verification Document: scripts-test-bytecode-suppression

## Overview

**Feature**: scripts-test-bytecode-suppression / **SPEC.md**: `feature-docs/scripts-test-bytecode-suppression/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/scripts-test-bytecode-suppression/IMPLEMENTATION.md`

All commands run from the repository root of the integration worktree.

## Build Verification

- Command: none (`project.components.main.build_command` is empty)
- Expected: not applicable

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Coverage target: not measured (no coverage tool is configured; test code
  uses the standard library only)

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Confirm `em-workflow/scripts/__pycache__` is absent, run `python3 -m unittest discover -s tests`, then look for any `__pycache__` under `em-workflow/scripts/` | The run exits 0 (every test passes) and no `__pycache__` exists anywhere under `em-workflow/scripts/` (SPEC AC1, AC2) | Integration (command) |
| TS-2 | Each in-process load site is driven against a probe module in a test-owned temporary directory, for the starting flag values True and False, with a probe that records the flag and a probe that raises | The flag is True while the body runs, equals the starting value after a normal return and after a raising body (whose error reaches the caller), and the probe directory holds no `__pycache__` (SPEC AC3) | Unit (`tests/test_bytecode_free_loads_scan_dependencies.py`, `tests/test_bytecode_free_loads_validator.py`, `tests/test_bytecode_free_loads_other_scripts.py`, probe class in `tests/test_report_name_entry.py`) |
| TS-3 | Run each module of the run-alone list below on its own, one after another, each starting with `em-workflow/scripts/__pycache__` absent | After each run no `__pycache__` exists under `em-workflow/scripts/`, and each module's result matches the base commit | Integration (command) |
| TS-4 | Confirm `em-workflow/scripts/__pycache__` is absent and run `python3 -m unittest tests.test_report_name_entry` on its own | No `__pycache__` exists under `em-workflow/scripts/` (no bytecode for `validate-worker-output` is written through the child process), and the module passes (SPEC AC4) | Integration (command) + Unit (launch class in `tests/test_report_name_entry.py`) |
| TS-5 | Derived from NFR1 (not in SPEC's Test Scenarios): list the files changed between `workflow.implement.base_commit` and the integration head | No changed path lies under `em-workflow/`; every changed path is under `tests/`, `feature-docs/scripts-test-bytecode-suppression/` or `test-docs/scripts-test-bytecode-suppression/` | Inspection (command) |
| TS-6 | Derived from NFR2: process-wide environment | The environment-equality test in `tests/test_report_name_entry.py` passes, and the diff adds no write to, deletion from or patch of the process-wide `os.environ` in any test module | Unit + Inspection |
| TS-7 | Derived from NFR3: standard-library imports only | The existing standard-library import checks pass in the TS-1 run, and every import added by the diff names a standard-library module; no test module imports another test module by name | Unit + Inspection |
| TS-8 | Derived from NFR4: existing verification unchanged | In every modified existing test module, the diff is limited to the loader body, added standard-library imports and, in `tests/test_report_name_entry.py` only, the launch arguments of `run_entry` plus new test classes; no existing assertion is removed or changed | Inspection |

### Run-alone list (TS-3)

Run each with `python3 -m unittest tests.<module>`, sequentially. Before the
first run, and before any run that follows a leftover, confirm
`em-workflow/scripts/__pycache__` is absent; if it exists, move it to the
trash with `gio trash` and record that.

- Loaders of `scan-dependencies.py`: test_sca_file_tasks_unexpected_exceptions,
  test_sca_listing_undecodable_output, test_sca_pip_lockfile_audit,
  test_scan_dependencies_cargo_directness,
  test_sca_absolute_executable_resolution, test_sca_file_tasks_oserror,
  test_scan_dependencies_pyproject_directness,
  test_sca_child_env_path_filtering, test_sca_go_govulncheck_real_output,
  test_sca_scanner_project_config_isolation, test_sca_scan_job_grouping,
  test_sca_task_filing, test_sca_run_scan_plan_units,
  test_sca_scan_unchanged_surfaces, test_sca_per_project_scan_binding,
  test_reproduction_output_contract, test_sca_scan_execution,
  test_scan_dependencies_pip_directness, test_sca_scan_invocation,
  test_sca_finding_title_roundtrip, test_sca_scan_normalization, and
  test_sca_go_replace_direct_deps (reaches a loader through another test
  module).
- Loaders of `validate-worker-output.py`: test_digest_contract_alignment,
  test_requirements_tests_replace, test_replanning_producer_alignment,
  test_final_path_correction, test_routeback_record_schema_patch,
  test_report_name_validation, test_validate_worker_output,
  test_spec_change_gate_binding, test_tier_rework_path,
  test_replanning_carry_over, test_spec_change_replan_authorization,
  test_classification_audit_retention, test_tier_task_document_plan,
  test_tier_phase_preconditions, test_rework_docs_only_validator_rules,
  test_gate_outcome_packet_lifecycle.
- Loaders of other scripts: test_tier_evaluator_contract,
  test_tier_rules_buckets_codex_facts, test_decide_tier_final_score,
  test_tier_rules, test_check_plugin_invariants,
  test_self_write_digest_wiring, test_self_write_digest_docs,
  test_worker_digest_results, test_recover_orphaned_task,
  test_stale_launched_recovery_chain, test_journal_append_failed,
  test_review_shards, test_review_coverage, test_self_write_digest,
  test_merge_ci_wait, test_codex_hook_tty_reaper.
- Probe modules: test_bytecode_free_loads_scan_dependencies,
  test_bytecode_free_loads_validator, test_bytecode_free_loads_other_scripts.

## Code Quality Verification

- Format: none configured (`format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | After a full run from a state without it, no `__pycache__` exists under `em-workflow/scripts/` | TS-1 |
| AC2 | In the same full run every existing test passes | TS-1 |
| AC3 | After an in-process load the flag is back to its pre-call value, also when the module body raises | TS-2 |
| AC4 | After running the test that launches `report-name-entry.py` on its own, no `__pycache__` exists under `em-workflow/scripts/` | TS-4 |
| All scenarios | All test scenarios pass | TS-1 to TS-8 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0002, task0003, task0004 | TS-1, TS-2, TS-3 |
| FR2 | task0004 | TS-1, TS-4 |
| FR3 | task0001, task0002, task0003, task0004 | TS-1, TS-2, TS-3, TS-4 |
| NFR1 | task0001, task0002, task0003, task0004 | TS-5 |
| NFR2 | task0001, task0002, task0003, task0004 | TS-6 |
| NFR3 | task0001, task0002, task0003, task0004 | TS-7 |
| NFR4 | task0001, task0002, task0003, task0004 | TS-1, TS-8 |

## Manual Testing (E2E Not Possible)

- [ ] Load-site enumeration: search `tests/` for every file-path module load
  (spec from a file location followed by execution of the module body,
  including loads inside code strings handed to child processes). Every
  load whose target is a file under `em-workflow/scripts/` is a row of
  exactly one of the four site tables (the three probe modules and the probe
  class of `tests/test_report_name_entry.py`). Loads whose target is under
  `em-workflow/hooks/`, `em-review/` or `tests/`, and loader text that is
  only a string literal, are not rows.
- [ ] Child-launch enumeration: every test launch of a script under
  `em-workflow/scripts/` whose script loads a sibling script into its own
  process carries bytecode suppression in that launch (today only the
  `report-name-entry.py` launch in `tests/test_report_name_entry.py`).

## Performance / Security Verification (if applicable)

- Not applicable. SPEC.md states no performance requirement, and
  THREAT-MODEL.md's verdict is `no-trust-boundary`, so there is no mitigation
  to verify.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 8 (TS-1 to TS-8) | 8 (TS-5 and TS-8 by command plus diff inspection) | 0 | 0 |
| Success criteria | 5 | 5 | 0 | 0 |
| Manual checks | 2 | 0 | 0 | 2 |
