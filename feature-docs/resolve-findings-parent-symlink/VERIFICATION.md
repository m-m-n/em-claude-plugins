# Verification Document: resolve-findings-parent-symlink

## Overview
**Feature**: resolve-findings-parent-symlink / **SPEC.md**: `feature-docs/resolve-findings-parent-symlink/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/resolve-findings-parent-symlink/IMPLEMENTATION.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the change is a Python script)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Targeted command: `python3 -m unittest tests.test_resolve_verified_findings`
- Expected: exit code 0 for both, no failures or errors
- Coverage target: no coverage tool is configured; every scenario below maps to at least one test
  in `tests/test_resolve_verified_findings.py` (TS-7 is checked by review)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `feature-docs/current/reviews` is a link to `feature-docs/other/reviews`, other's `round1.yaml` holds a deferred high/spec finding; run with `--feature-dir` current; commit other and run `merge-preflight.py` on other | `invalid-round-record` (exit 1, stdout empty, stderr one line); other's `reviews` tree unchanged with no file added; preflight stops with `unresolved_findings` | Integration |
| TS-2 | Broken-input table gains "reviews is a link to a directory outside the repository" and "reviews is a dangling link" | `invalid-round-record`; feature directory and link target unchanged | Integration |
| TS-3 | `feature-docs/current` is a link to `feature-docs/other`; run with current | `invalid-workflow`; other unchanged | Integration |
| TS-4 | In a child process, the YAML serializer is wrapped so that, when called, `current/reviews` is moved aside and replaced by a link to `other/reviews`; the script runs as the main module | other's `reviews` tree unchanged; no temporary file left; no CPU load used | Integration |
| TS-5 | A link to the repository is placed in a temporary directory and the feature directory is passed through it, in the eligible state | The finding becomes `fixed`, exit 0 | Integration |
| TS-6 | The whole suite, including the existing tests for record links, directory records, absent `reviews`, read-only directories, file mode and no added files | Every existing test kept unweakened and passing | Integration |
| TS-7 | Review of the module docstring | Boundaries section names the refused links and their codes | Review |
| TS-8 | Same layout as TS-3, with `--feature-dir` given as `current/` and as `current//` | `invalid-workflow`, stdout empty, stderr one line, other's tree unchanged for both | Integration |
| TS-9 | A feature directory that is not a link, eligible state, given as `DIR/` and as `DIR//` | exit 0, finding `fixed`, stdout JSON equal to the run without the separator | Integration |
| TS-10 | In a child process, the OS-level open is wrapped so that, on the round record's name, the record is moved aside and replaced by a link to other's record before the original open runs | `invalid-round-record`; other's record unchanged; no CPU load used | Integration |
| TS-11 | Broken-input table gains "round record is a FIFO", with a timeout on the child process | `invalid-round-record` without waiting | Integration |

## Code Quality Verification
- Format: none configured (`project.components.main.format_command` is empty)
- Static analysis: none configured
- NFR1 import check: the import lines of `tests/test_resolve_verified_findings.py` name only
  standard-library modules (PyYAML appears only inside child-process program text), and the
  imports of `em-workflow/scripts/resolve-verified-findings.py` are the standard library plus
  PyYAML
- NFR5 unchanged files: `git diff --exit-code <implement base commit> HEAD -- em-workflow/skills/develop/SKILL.md em-workflow/scripts/merge-preflight.py tests/test_merge_preflight.py`
  exits 0

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below; TS-1 to TS-11 pass |
| SC-2 | All test scenarios pass | Test Verification commands exit 0 |
| SC-3 | Security requirements are satisfied | Performance / Security Verification items TM-1 to TM-6 |
| SC-4 | Documentation is complete (FR6 docstring) | TS-7 |
| SC-5 | Code review is completed | Review phase result |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2 |
| FR2 | task0001 | TS-3, TS-8 |
| FR3 | task0001 | TS-4 |
| FR4 | task0001 | TS-6 |
| FR5 | task0001 | TS-5 |
| FR6 | task0001 | TS-7 (review) |
| FR7 | task0001 | TS-8, TS-9 |
| FR8 | task0001 | TS-10, TS-11 |
| NFR1 | task0001 | NFR1 import check (Code Quality Verification) |
| NFR2 | task0001 | TS-6 run on the POSIX target |
| NFR3 | task0001 | TS-4, TS-10 (swaps from wrapper hooks, no load) |
| NFR4 | task0001 | TS-1, TS-2, TS-3, TS-8 (stdout empty, stderr exactly the code line) |
| NFR5 | task0001 | NFR5 unchanged-files diff (Code Quality Verification) |

## Manual Testing (E2E Not Possible)
- [ ] TS-7: read the Boundaries section of the module docstring of
      `em-workflow/scripts/resolve-verified-findings.py` and confirm it names the feature directory
      (including the trailing-separator form), `reviews` and the round record as refused links,
      with `invalid-workflow`, `invalid-round-record` and `invalid-round-record`

## Performance / Security Verification (if applicable)
- TM-1: `reviews` opened relative to the feature-directory handle without following a link, a link
  rejected as `invalid-round-record` — checked by TS-1 and TS-2 (other feature's and outside
  target's bytes unchanged, preflight still stops)
- TM-2: trailing separators removed and the feature directory's final element opened without
  following a link, failing as `invalid-workflow` — checked by TS-3 and TS-8
- TM-3: every operation after opening `reviews` relative to that handle — checked by TS-4 (swap at
  the serializer call; other feature unchanged, no temporary file left)
- TM-4: record opened without following a link and checked as a regular file through the opened
  handle — checked by TS-10 (swap at the record open; `invalid-round-record`, other record
  unchanged)
- TM-5: non-regular round records refused by the no-follow pre-check before any open — checked by
  TS-11 (FIFO fails within the timeout)
- TM-6: failures print only the code line — checked by the stdout / stderr assertions of TS-1,
  TS-2, TS-3 and TS-8, and by the sentinel-named link targets never appearing in the output

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 11 (TS-1 to TS-11) | 10 | 0 | 1 (TS-7) |
| Code quality | 2 (NFR1 import check, NFR5 diff) | 1 (NFR5 diff) | 0 | 1 (NFR1 import check) |
| Security (TM) | 6 (TM-1 to TM-6) | 6 | 0 | 0 |
| Success criteria | 5 (SC-1 to SC-5) | 3 | 0 | 2 (SC-4, SC-5) |
