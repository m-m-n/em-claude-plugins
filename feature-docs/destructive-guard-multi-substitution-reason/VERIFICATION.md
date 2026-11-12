# Verification Document: destructive-guard-multi-substitution-reason

## Overview
**Feature**: destructive-guard-multi-substitution-reason / **SPEC.md**: `feature-docs/destructive-guard-multi-substitution-reason/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/destructive-guard-multi-substitution-reason/IMPLEMENTATION.md`

## Build Verification
- Command: none (workflow.yaml `project.components.main.build_command` is empty)
- Expected: not applicable

## Test Verification
- Command, from the repository root: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures or errors
- Coverage target: no coverage tool is configured; every scenario below must pass

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `rm -rf $(cat a) $(cat b)`, HOME and PATH set by the test, CLAUDE_BATCH absent | ask / rm-unresolvable; designations exactly [`` 1番目のrmの1番目の対象[`$(...)`] ``, `` 1番目のrmの2番目の対象[`$(...)`] ``]; `cat a` and `cat b` absent from the reason text (AC-1) | Integration |
| TS-2 | `rm -rf $(cat a); rm -rf $(cat b)`, CLAUDE_BATCH absent | designations exactly [`` 1番目のrmの1番目の対象[`$(...)`] ``, `` 2番目のrmの1番目の対象[`$(...)`] ``] (AC-2) | Integration |
| TS-3 | `rm -rf $(cat a) $(cat b)`, CLAUDE_BATCH=1 | deny / rm-unresolvable; designations the same as TS-1 (AC-3) | Integration |
| TS-4 | `python3 em-workflow/hooks/tests/run-destructive-guard.py` and `python3 -m unittest discover -s tests` | both succeed in full, with every existing test unchanged except `tests/test_destructive_guard_mixed_rm_precedence.py`, whose change is limited to FR12's scope (AC-4) | Integration |
| TS-5 | `` rm -rf `cat a` `cat b` ``, CLAUDE_BATCH absent | ask / rm-unresolvable; designations exactly [`` 1番目のrmの1番目の対象[`$(...)`] ``, `` 1番目のrmの2番目の対象[`$(...)`] ``] (AC-5) | Integration |
| TS-6 | `` rm -rf $(cat a) `cat b` ``, CLAUDE_BATCH absent | ask / rm-unresolvable; designations exactly [`` 1番目のrmの1番目の対象[`$(...)`] ``, `` 1番目のrmの2番目の対象[`$(...)`] ``] (AC-6) | Integration |
| TS-7 | `rm -rf <(cat a) <(cat b)`, CLAUDE_BATCH absent | ask / rm-unresolvable; designations exactly [`` 1番目のrmの1番目の対象[`$(...)`] ``, `` 1番目のrmの2番目の対象[`$(...)`] ``] (AC-7) | Integration |
| TS-8 | `rm -rf $(cat a) /tmp/scratch $(cat b)`, CLAUDE_BATCH absent | ask / rm-unresolvable; designations exactly [`` 1番目のrmの1番目の対象[`$(...)`] ``, `` 1番目のrmの3番目の対象[`$(...)`] ``]; the text 1番目のrmの2番目の対象 absent (AC-8) | Integration |
| TS-9 | `rm -rf $(printf MULTISUBBODYALPHA) $(printf MULTISUBBODYBETA)`, CLAUDE_BATCH absent | ask / rm-unresolvable; designations exactly [`` 1番目のrmの1番目の対象[`$(...)`] ``, `` 1番目のrmの2番目の対象[`$(...)`] ``]; MULTISUBBODYALPHA and MULTISUBBODYBETA absent (AC-9) | Integration |
| TS-10 | Diff of `em-workflow/hooks/destructive-guard.py` against the implement base commit (derived from FR5, FR6) | The diff is empty. When it is not, the task0001 implementation report names a new test that failed on the unmodified hook, and the diff leaves the SUBSTITUTION_STANDIN value `$(...)` and the four inert conditions in its comment unchanged | Diff check |
| TS-11 | Diff of the repository against the implement base commit (derived from FR4, NFR3) | No pre-existing file under `tests/` or `em-workflow/hooks/tests/` is modified or deleted, except `tests/test_destructive_guard_mixed_rm_precedence.py`, whose scope TS-12 checks; the version values in `em-workflow/.claude-plugin/plugin.json` and in the em-workflow entry of `.claude-plugin/marketplace.json` equal those at the base commit | Diff check |
| TS-12 | `python3 -m unittest tests.test_destructive_guard_mixed_rm_precedence` from the repository root, plus the diffs of that module and of `em-workflow/hooks/tests/destructive-guard-cases.json` against the implement base commit | failures 0 and errors 0; the module selects its own cases as those whose label begins with destructive-guard-mixed-rm-precedence followed by one space (33 cases on the current case table), and TestCaseTable checks that they form a contiguous run starting at position PRE_EXISTING_CASE_COUNT; no selection by `[PRE_EXISTING_CASE_COUNT:]` remains in the module; PRE_EXISTING_CASE_COUNT, PRE_EXISTING_CASES_DIGEST and each scenario's expected count are unchanged; the module's diff is limited to that selection and that check; the case table has no diff (AC-10) | Integration / Diff check |

TS-1 to TS-9 and TS-12 are SPEC.md's scenarios; the AC labels in their rows are
SPEC.md's user-story criteria. TS-10 and TS-11 are not in SPEC.md's Test Scenarios:
they derive from FR4, FR5, FR6 and NFR3, which no SPEC.md scenario checks on the diff.

## Code Quality Verification
- Format: none configured (workflow.yaml `format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below; every listed scenario passes |
| SC-2 | All test scenarios pass | Test Verification command exits 0; TS-10, TS-11 and TS-12 hold |
| SC-3 | SPEC.md AC-1 to AC-10 hold | AC-1 by TS-1, AC-2 by TS-2, AC-3 by TS-3, AC-4 by TS-4, AC-5 by TS-5, AC-6 by TS-6, AC-7 by TS-7, AC-8 by TS-8, AC-9 by TS-9, AC-10 by TS-12 |
| SC-4 | Code review is completed | The review step of workflow.yaml is completed |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 |
| FR2 | task0001 | TS-2 |
| FR3 | task0001 | TS-3 |
| FR4 | task0001, task0002 | TS-4, TS-11, TS-12 |
| FR5 | task0001 | TS-4, TS-10 |
| FR6 | task0001 | TS-10 |
| FR7 | task0001 | TS-5 |
| FR8 | task0001 | TS-6 |
| FR9 | task0001 | TS-7 |
| FR10 | task0001 | TS-8 |
| FR11 | task0001 | TS-9 |
| FR12 | task0002 | TS-4, TS-12 |
| NFR1 | task0001 | TS-4 (the new module runs under unittest discovery) |
| NFR2 | task0001 | TS-4 (the existing suites pass) |
| NFR3 | task0001 | TS-11 |
| NFR4 | task0001 | TS-1, TS-2, TS-3, TS-5, TS-6, TS-7, TS-8, TS-9 (each compares the whole ordered designation list) |

## Manual Testing (E2E Not Possible)
- None: every scenario above is automated. The judgment steps are TS-10's follow-up,
  needed only when the hook diff is not empty, and the part of TS-12 that reads the
  module's diff to confirm it is limited to the case selection and the added check.

## Performance / Security Verification (if applicable)
- TM-1: a substitution-only target is rendered only as its positional designation with the fixed stand-in, never with its body text — checked by TS-1 (`cat a` and `cat b` absent from the reason text) and TS-9 (MULTISUBBODYALPHA and MULTISUBBODYBETA absent).
- TM-2: the decision for multi-substitution targets stays ask (deny under CLAUDE_BATCH) with reason ID rm-unresolvable, a hook change happens only after a new test fails, and the existing suites pass with no existing test changed beyond FR12's scope — checked by TS-1, TS-3, TS-5, TS-6, TS-7, TS-8 and TS-9 (decision and reason ID pinned), TS-4 (existing suites pass) and TS-10 (hook diff empty, or justified by a failing test).
- TM-3: the mixed-rm-precedence module selects its own cases by label and checks that they form a contiguous run starting at PRE_EXISTING_CASE_COUNT, with PRE_EXISTING_CASE_COUNT, PRE_EXISTING_CASES_DIGEST, each scenario's expected count and the case table unchanged, so every recorded precedence case still runs against the hook — checked by TS-12.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-9, TS-12) | 10 | 10 | 0 | 0 |
| Diff checks (TS-10, TS-11) | 2 | 2 | 0 | 0 |
| Security (TM-1, TM-2, TM-3) | 3 | 3 | 0 | 0 |
| Success criteria | 4 | 3 | 0 | 1 |
