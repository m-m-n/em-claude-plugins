# Verification Document: worktree-path-control-char-stop

## Overview
**Feature**: worktree-path-control-char-stop / **SPEC.md**: `feature-docs/worktree-path-control-char-stop/SPEC.md` / **IMPLEMENTATION.md**: none (reduced tier; a single task, so no file is declared by two tasks) / **THREAT-MODEL.md**: `feature-docs/worktree-path-control-char-stop/THREAT-MODEL.md`

Scenarios TS-1 to TS-4 correspond one-to-one to the four test scenarios of
SPEC.md; TS-5 and TS-6 are added by this plan to make NFR1 and NFR2 checkable.

## Build Verification
- Command: none (Python; `project.components.main.build_command` is empty)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures and no errors
- Coverage target: no coverage tooling is configured (standard-library unittest only); every scenario below maps to at least one test or static check

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `python3 -m unittest tests.test_canonical_worktree_path_docs` against the live Step I.2.a section: the control-character check content | The new checks report no problem: the paragraph covers every selected task, names Cc (U+0000–U+001F, U+007F, U+0080–U+009F), U+2028 and U+2029, ABORTs the implement phase, reports the offending task IDs and builds no launch prompt for any selected task | Unit (document test) |
| TS-2 | Placement of the check paragraph | Live section: the paragraph is after the Canonical worktree path paragraph and before the launch-loop paragraph; a forged copy with the paragraph moved after the launch-loop paragraph is detected | Unit (document test) |
| TS-3 | Forged copies of the section | Each is detected: check paragraph removed; rejected set reduced to the line feed only; ABORT statement replaced by escape-and-continue; scope narrowed to a single task; task-ID report removed | Unit (document test) |
| TS-4 | `python3 -m unittest discover -s tests` | Every test passes, including the module's existing tests for its AC-1 to AC-4 (canonicalization sentence, payload placeholders, consumer procedures, citation without restatement) | Integration (regression) |
| TS-5 | Diff of `tests/test_canonical_worktree_path_docs.py` between the base and the integrated revision | Additions only; no existing test method, check function or constant is modified or removed | Static (manual) |
| TS-6 | The new checks and the module's imports | The new checks locate text by heading slice and stable phrases, never by line number; the module imports the standard library only (also asserted by the module's existing import test, run under TS-4) | Static (manual) |

## Code Quality Verification
- Format: none configured (`format_command` is empty) / Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Step I.2.a states the check over every selected task's canonical worktree_path, the rejected set, the ABORT with the task-ID report, and that no launch prompt is built | TS-1, TS-3 |
| AC2 | The check sits after the Canonical worktree path paragraph and before the launch-loop paragraph | TS-2 |
| AC3 | The test module checks AC1 and AC2 on the live document, and the forged copies (check removed, set missing, ABORT missing, check moved after the launch loop) fail | TS-1, TS-2, TS-3, TS-6 |
| AC4 | The module's existing tests and the full suite pass | TS-4, TS-5 |
| FR1-FR4 implemented and tested | All four functional requirements map to task0001 and to at least one scenario | Functional Requirements Coverage below |
| NFR1-NFR3 met | All three non-functional requirements map to task0001 and to at least one scenario | Functional Requirements Coverage below |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2 |
| FR2 | task0001 | TS-1, TS-3 |
| FR3 | task0001 | TS-1, TS-3 |
| FR4 | task0001 | TS-1, TS-2, TS-3 |
| NFR1 | task0001 | TS-4, TS-5 |
| NFR2 | task0001 | TS-6 |
| NFR3 | task0001 | TS-4 |

## Manual Testing (E2E Not Possible)
- [ ] TS-5: inspect the diff of the test module against the base revision; only additions are present.
- [ ] TS-6: inspect the new checks for heading-slice and stable-phrase location (no line numbers) and the module's import statements.

## Performance / Security Verification (if applicable)
- TM-1: before the launch loop, Step I.2.a checks every selected task's canonical worktree_path for Unicode Cc characters, U+2028 and U+2029, and on any hit aborts the implement phase with the task IDs reported and no launch prompt built — checked by TS-1 (the live paragraph states the set, the scope and the stop), TS-2 (the paragraph precedes the launch-loop paragraph) and TS-3 (copies lacking the paragraph, the full set, the scope, the ABORT or the task-ID report are detected).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Document-test scenarios (TS-1 to TS-3) | 3 | 3 | 0 | 0 |
| Regression suite (TS-4) | 1 | 1 | 0 | 0 |
| Static checks (TS-5, TS-6) | 2 | 0 | 0 | 2 |
| Security (TM-1) | 1 | 1 | 0 | 0 |
| **Total** | 7 | 5 | 0 | 2 |
