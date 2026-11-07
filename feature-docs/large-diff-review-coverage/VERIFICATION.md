# Verification Document: large-diff-review-coverage

## Overview
**Feature**: large-diff-review-coverage / **SPEC.md**: `feature-docs/large-diff-review-coverage/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/large-diff-review-coverage/IMPLEMENTATION.md`

## Build Verification
- Command: none (the project defines no build command)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Plugin invariants: `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Expected: both exit 0
- Coverage target: no line-coverage tool is used; every scenario below maps to at least one test

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Text-inspect Step 6 of codex-reviewer in both plugins (FR1, FR2, FR17) | The exit code 124 check comes before JSON parsing and returns the FR1 skip object; non-JSON output returns the FR2 skip object; em-review's protocol aligns its skip description and keeps no splitting rule | Unit |
| TS-2 | Classify every combination of origin, findings count and summary (FR3) | `failed` only for litellm origin, zero findings and a byte-exact fixed summary; `completed` otherwise | Unit |
| TS-3 | Measure and split in a disposable git repository: tracked, untracked, whole-codebase, rename, binary and single oversized file (FR5, FR6) | Each file measured by the stated rule; above 200,000 every file is in exactly one shard of at most 200,000, an oversized file alone | Unit |
| TS-4 | Shard cap and excess shards for selected perspective counts 1 to 6 (FR7) | `shard_cap` equals floor(24 / N); excess shards are the trailing shards, identical across runs | Unit |
| TS-5 | Coverage from combinations of perspective_runs, including post-fix invalidation (FR4, FR13, FR14) | Unreviewed and partially reviewed perspectives, unreviewed files and reasons as defined; a fixed file is not covered by a pre-fix run | Unit |
| TS-6 | run_id uniqueness where shards, chains and loops overlap, and shard-level result replacement (FR8, FR9) | Grammar accepted and malformed or duplicate ids rejected; one shard's last result never affects another shard | Unit |
| TS-7 | Text-inspect the Phase R2b table, spec ordering, rescue-run handling, completion gate, Reporting, source map and Phase R3a input (FR10, FR11, FR12, FR15, FR16) | Each rule is present as specified, with negative proofs | Unit |
| TS-8 | Input at or below the limit forms one shard; schema and Inputs section pins hold (NFR1, NFR5) | One shard, `split` false, unsplit dispatch text unchanged; existing schema and Inputs digests still pass | Unit |
| TS-9 | Full suite and plugin invariants (FR18) | Both commands exit 0; each new script has its own unit test module and each changed rule a text-inspection test | Integration |
| TS-10 | vertex-review unchanged (NFR2) | No task changes a vertex-review file; the litellm rules key only on outputs the vertex reviewer already emits; the reviewer input fields are unchanged | Unit |
| TS-11 | Orchestrator context (NFR3) | A sentinel string placed in diff content never appears in either script's stdout; each output has a closed key set | Unit |
| TS-12 | Determinism (NFR4) | Repeated runs and permuted `changed_files` give byte-identical review-shards output; repeated coverage runs give byte-identical output | Unit |
| TS-13 | Test constraints (NFR6) | The new scripts and test modules import only standard-library modules; tests use `unittest` and temporary git repositories | Unit |

## Code Quality Verification
- Format: none (the project defines no format command)
- Static analysis: `python3 em-workflow/scripts/check-plugin-invariants.py .`

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Codex exit 124 yields skipped true, `harness_unavailable`, empty findings | TS-1 |
| AC2 | Codex non-JSON and the two litellm summaries do not become completed; other combinations are untouched | TS-1, TS-2 |
| AC3 | A dispatched perspective ending with only non-retryable skips is in `unreviewed_perspectives` | TS-5 |
| AC4 | Input over 200,000 characters always splits the same way, each file in one shard; whole-codebase and untracked files are measured | TS-3, TS-12 |
| AC5 | Shards per perspective stay at or below floor(24 / N); the excess is recorded as unreviewed | TS-4, TS-5 |
| AC6 | run_id values do not collide; one shard's skip or replacement does not affect another | TS-6 |
| AC7 | Over 300,000 characters, performance and architecture keep completed runs and the incomplete range is recorded | TS-3, TS-5, TS-7, Manual Testing item 1 |
| AC8 | spec rescues only after every full-diff path failed, is recorded as partial, and its rescue missing-implementation findings enter neither auto-fix nor residual | TS-5, TS-7 |
| AC9 | A file changed by a fix whose re-review did not complete is recorded as unreviewed | TS-5 |
| AC10 | The completion gate is unchanged; both fields appear in Phase R6, Reporting, the source map and the Phase R3a input | TS-7 |
| AC11 | em-review codex-reviewer skips on exit 124 and on non-JSON and carries no splitting rule | TS-1 |
| AC12 | At or below 200,000 characters a single input is dispatched; reviewer input fields and the output schema are unchanged | TS-8 |
| AC13 | Both commands succeed | TS-9 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 |
| FR2 | task0001 | TS-1 |
| FR3 | task0003, task0004 | TS-2 |
| FR4 | task0003, task0005 | TS-5 |
| FR5 | task0002, task0004 | TS-3 |
| FR6 | task0002, task0004 | TS-3 |
| FR7 | task0002, task0004, task0005 | TS-4 |
| FR8 | task0003, task0004, task0005 | TS-6 |
| FR9 | task0003, task0004 | TS-6 |
| FR10 | task0001, task0004 | TS-7 |
| FR11 | task0003, task0004 | TS-7 |
| FR12 | task0005 | TS-7 |
| FR13 | task0003, task0005 | TS-5 |
| FR14 | task0003, task0005 | TS-5 |
| FR15 | task0005, task0006 | TS-7 |
| FR16 | task0006 | TS-7 |
| FR17 | task0001 | TS-1 |
| FR18 | task0001, task0002, task0003, task0004, task0005, task0006 | TS-9 |
| NFR1 | task0002, task0004 | TS-8 |
| NFR2 | task0004 | TS-10 |
| NFR3 | task0002, task0003 | TS-11 |
| NFR4 | task0002, task0003 | TS-12 |
| NFR5 | task0004 | TS-8 |
| NFR6 | task0002, task0003 | TS-13 |

## Manual Testing (E2E Not Possible)

The review phase dispatches LLM reviewers, so the end-to-end reproduction is
checked by hand.

- [ ] 1. In a disposable git repository, create a change over 300,000
  characters across several files. Run review-shards with five selected
  perspectives and confirm the split, the cap of 4 and the excess shards. Feed
  its output to review-coverage with hand-written runs: performance and
  architecture completed on the dispatched shards, spec failed on the full diff
  and rescued. Confirm performance and architecture appear as partial with
  `shard_cap_exceeded` and the excess files, and spec as partial with
  `spec_rescue`.
- [ ] 2. Walk the original reproduction (a 423 KB diff) through Phase R2, R2b, R5
  and R6 of `em-workflow/references/review-phase.md`: a Codex run past 540
  seconds becomes a `harness_unavailable` skip and walks its chain; a litellm
  `review_data_too_large` skip walks to Codex; no selected perspective can end the
  round as "no findings" without a completed run, and every unreviewed range is
  named in the round record and the report.

## Performance / Security Verification

- TM-1: path revalidation, argument-list `git` with an end-of-options separator,
  literal pathspecs, external diff and text conversion off — checked by
  `tests/test_review_shards.py` with option-like and pathspec-magic file names
  and a configured text-conversion driver whose marker file is never created.
- TM-2: non-regular files and symlinks refused before open, exit 2 — checked by
  `tests/test_review_shards.py` with a FIFO and a symlink, each run under a
  subprocess timeout.
- TM-3: shards per perspective capped at floor(24 / N) — checked by
  `tests/test_review_shards.py` for N from 1 to 6.
- TM-4: the timeout is decided by exit code 124 before any parse, never by output
  text — checked by `tests/test_codex_reviewer_skip_handling.py` on both agents,
  with a forged parse-first text rejected.
- TM-5: the litellm rule keys on the recorded harness, zero findings and a
  byte-exact summary — checked by `tests/test_review_coverage.py` and by
  `tests/test_review_phase_shard_dispatch.py` on the Phase R2b text.
- TM-6: coverage uses only run_id, status and the pass manifests — checked by
  `tests/test_review_coverage.py` (extra row fields have no effect) and by
  `tests/test_review_phase_coverage_record.py` on the Phase R5 text.
- TM-7: rescue-run missing-implementation findings are unresolved,
  `unverified`, and outside auto-fix and residual on all three paths — checked by
  `tests/test_review_phase_coverage_record.py`.
- TM-8: exact unreviewed file lists and reasons in the round record, Phase R6 and
  the batch final result — checked by `tests/test_review_phase_coverage_record.py`
  and `tests/test_review_coverage_disclosure.py`.
- TM-9: project-relative paths only — checked by `tests/test_review_shards.py`
  and `tests/test_review_coverage.py` (absolute input path gives exit 2, no
  absolute path in output) and by `tests/test_review_phase_coverage_record.py`.
- TM-10: each shard's `diff_cmd_quoted` is built from the Phase R0 step 3
  validated paths with the same quoting — checked by
  `tests/test_review_phase_shard_dispatch.py`.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 13 (TS-1 to TS-13) | 13 | 0 | 0 |
| Success criteria | 13 (AC1 to AC13) | 13 | 0 | 1 (AC7 also by hand) |
| Requirements coverage | 24 (FR1 to FR18, NFR1 to NFR6) | 24 | 0 | 0 |
| Threat mitigations | 10 (TM-1 to TM-10) | 10 | 0 | 0 |
| Manual checks | 2 | 0 | 0 | 2 |
