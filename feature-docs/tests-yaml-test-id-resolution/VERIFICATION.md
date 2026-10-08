# Verification Document: tests-yaml-test-id-resolution

## Overview
**Feature**: tests-yaml-test-id-resolution / **SPEC.md**: `feature-docs/tests-yaml-test-id-resolution/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/tests-yaml-test-id-resolution/IMPLEMENTATION.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`, run from the repository root
- Expected: exit code 0
- Coverage target: none (no coverage tool is configured)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | (AC-1) The record check's per-record tests run against the real `test-docs/**/*.tests.yaml` as part of the full suite | Every per-record test passes | Integration |
| TS-2 | (AC-2) Reproduction procedure, see Verify Check Procedures | Zero unresolved IDs | Verify check |
| TS-3 | (AC-3, AC-4) Base-to-HEAD diff of the records and the SC-3 mapping files, see Verify Check Procedures | Only `tests` elements and SC-5 appends change; the mapping row count equals the removed-occurrence count | Verify check |
| TS-4 | (AC-5) Fixture record holding nonexistent module, class and method IDs, an ID without the `tests.` prefix, a `path::Class::method` ID and free text | One failure message naming the file, the AC and every invalid ID | Unit |
| TS-5 | (AC-6) Nonexistent method on an existing class through the loader's error path; fixture test module whose test body creates a marker; callable module attribute; attribute that is not a test case class | Judged failures where invalid; no marker is created; the callable and the non-test-case attribute are rejected without being called | Unit |
| TS-6 | (AC-7) Fixture per supported notation; unsupported notation, duplicate AC key, duplicate `tests` key, missing `tests` key, missing `acceptance_tests` | Exactly the expected IDs are extracted; each error names the file and the AC | Unit |
| TS-7 | (AC-8) Record whose every AC is `tests: []`, unreadable record, root without any record | The first passes; the other two fail | Unit |
| TS-8 | (AC-9) Two fixture records, the first already failing, an invalid ID added to the second | The set of failed test names grows by the second record's test | Unit |
| TS-9 | (AC-10) Document-contract test over `em-workflow/agents/implementer.md` and `test/README.md` | The FR10 to FR13 rules and the FR7 notation are present | Integration |
| TS-10 | (AC-11) Syntax-tree listing of the record check's imports; full suite | Every import is a standard-library module; the full suite passes with `tests/test_exit4_ac2_test_id_drift.py` unchanged | Integration |
| TS-11 | (NFR4) Base-to-HEAD diff of the plugin manifests | `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` are unchanged | Verify check |

TS-4 to TS-8 and TS-10 are implemented by task0001; TS-9 by task0005. TS-1, TS-2, TS-3 and TS-11 hold only on the integrated branch.

### Verify Check Procedures

**TS-2, reproduction procedure.** Run from the repository root, with the repository root and `tests/` on the module search path.
1. Read every `test-docs/**/*.tests.yaml` and take every element of every `acceptance_tests.*.tests` list.
2. Pass each element to the standard unittest loader's load-by-name operation on a fresh loader.
3. Count the elements for which the operation raises, the loader's error list gains an entry, the result contains a failed-test placeholder, or the result contains zero tests.
Expected: 0.

**TS-3, record diff.** Base is `workflow.implement.base_commit`; head is the integration branch HEAD; the scope is every record outside `test-docs/tests-yaml-test-id-resolution/` changed between them.
1. Parse each changed record at base and at head.
2. Confirm that only `tests` lists and `red_reason` values differ; that every changed `red_reason` at head starts with its exact base value followed by the SC-5 sentence; that no `red_reason` key was added; and that `red_confirmed`, `baseline_failures` and `final_failures` are identical.
3. For every file and AC, take the multiset of elements present at base and absent at head; sum the counts.
4. Count the table rows of `id-mapping-range1.md`, `id-mapping-range2.md` and `id-mapping-range3.md` under `test-docs/tests-yaml-test-id-resolution/`. Confirm that the total equals the sum from step 3 and that each row's File, AC and Old ID match one removed occurrence.
5. Confirm that `test-docs/exit4-tip-argument/task0002.tests.yaml` keeps its number of IDs per AC, the one-line quoted form of its AC-2 `red_reason`, and `red_confirmed: true` (NFR3).

**TS-11, version.** The base-to-HEAD diff contains no change to `em-workflow/.claude-plugin/plugin.json` or to `.claude-plugin/marketplace.json`.

## Code Quality Verification
- Format: none configured / Static analysis: none configured

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | Every ID of every record resolves in the record check without extraction or resolution errors | TS-1 |
| AC-2 | The reproduction procedure finds zero unresolved IDs | TS-2 |
| AC-3 | Every changed or deleted ID has a mapping row; the row count matches the diff | TS-3 steps 3 and 4 |
| AC-4 | `red_confirmed`, `baseline_failures` and `final_failures` are unchanged; `red_reason` changes only by FR2 appends | TS-3 step 2 |
| AC-5 | Invalid IDs fail with file, AC and ID, all in one failure message | TS-4 |
| AC-6 | Loader error-path results are failures; no test is executed | TS-5 |
| AC-7 | Supported notations extract exactly the expected IDs; error notations fail with file and AC | TS-6 |
| AC-8 | All-empty records pass; unreadable records and zero records fail | TS-7 |
| AC-9 | A new invalid ID adds a new failed test name | TS-8 |
| AC-10 | `implementer.md` holds the FR10 to FR12 rules; `test/README.md` holds the FR13 content | TS-9 |
| AC-11 | Standard-library imports only; collected by the normal run; the drift test passes unchanged | TS-10 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0002, task0003, task0004 | TS-1, TS-2 |
| FR2 | task0002, task0003, task0004 | TS-1, TS-2, TS-3 |
| FR3 | task0002, task0003, task0004 | TS-1, TS-2, TS-3 |
| FR4 | task0001, task0002, task0003, task0004 | TS-3, TS-6 |
| FR5 | task0001 | TS-1, TS-4 |
| FR6 | task0001 | TS-1, TS-2, TS-4, TS-5 |
| FR7 | task0001, task0005 | TS-6, TS-9 |
| FR8 | task0001 | TS-7 |
| FR9 | task0001 | TS-8 |
| FR10 | task0005 | TS-9 |
| FR11 | task0005 | TS-9 |
| FR12 | task0005 | TS-9 |
| FR13 | task0005 | TS-9 |
| NFR1 | task0001 | TS-10 |
| NFR2 | task0001 | TS-10 |
| NFR3 | task0001, task0003 | TS-3, TS-10 |
| NFR4 | task0005 | TS-11 |

## Manual Testing (E2E Not Possible)
- [ ] Sample SC-3 rows of each basis category: a `renamed` row's commit renames or merges the old test into the new one; a `runner-replaced` row's test exercises the same target as the removed entry; a `no-counterpart` row's old ID has no counterpart in git history or under `tests/`.
- [ ] Read the Step 4c additions in `em-workflow/agents/implementer.md`: the rules name no programming language, test framework, module of this repository, or the `tests.` prefix (FR10).

## Performance / Security Verification (if applicable)
- TM-1: syntax gate before any import — task0001's AC-4 fixture test (an ID naming a marker-creating module outside the `tests` package) passes in the full suite and leaves no marker.
- TM-2: nothing resolved is called and no test is run — task0001's AC-5 fixture tests pass in the full suite and leave no marker.
- TM-3: module search path restored and fixture modules discarded — task0001's AC-6 tests pass in the full suite.
- TM-4: mapping completeness — TS-3 steps 3 and 4.
- TM-5: field restriction on rewritten records — TS-3 step 2.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-11) | 11 | 11 | 0 | 0 |
| Code quality | 0 | 0 | 0 | 0 |
| Manual checks | 2 | 0 | 0 | 2 |
| Security (TM-1 to TM-5) | 5 | 5 | 0 | 0 |
| Total | 18 | 16 | 0 | 2 |
