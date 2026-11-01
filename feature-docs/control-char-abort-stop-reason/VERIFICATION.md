# Verification Document: control-char-abort-stop-reason

## Overview
**Feature**: control-char-abort-stop-reason / **SPEC.md**: `feature-docs/control-char-abort-stop-reason/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/control-char-abort-stop-reason/IMPLEMENTATION.md` / **THREAT-MODEL.md**: `feature-docs/control-char-abort-stop-reason/THREAT-MODEL.md`

Scenarios TS-1 to TS-5 below correspond one-to-one, in order, to SPEC.md's
test scenarios. TS-6 is added to verify NFR5 and SPEC A1.

## Build Verification
- Command: none. `project.components.main.build_command` is empty: the
  feature edits a Markdown document and adds a Python test module.
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`, run from the root of the
  integration worktree
- Expected: exit code 0, no failures or errors
- Coverage target: not measured (document tests; no coverage tooling is
  configured)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Slice the "Precedence rule:" paragraph of `em-workflow/references/batch-terminal-line.md` from its label to the next blank line, then normalize whitespace | The paragraph names the Control-character check of Step I.2.a and binds that stop to `stop-condition-3` / `step_needs_intervention`, not `unmapped_stop`. It states no affirmative binding to `unmapped_stop` | Unit (document test) |
| TS-2 | The same paragraph: the current-run exclusion and its exception | "no route of the current run produced" is still present inside the unchanged exclusion anchor. The control-character binding follows it, stated as a named exception to it | Unit (document test) |
| TS-3 | Run the binding matcher and the exception matcher against the verbatim pre-change paragraph | Each raises an assertion failure. A non-vacuity guard shows the sample is the real pre-change Precedence paragraph | Unit (document test) |
| TS-4 | Structural guards on the live document | The paragraph contains no blank line. The Stop point coverage table has fourteen rows, none for the control-character stop. Forged samples (a blank line inserted; a row added) are rejected | Unit (document test) |
| TS-5 | Run the full suite `python3 -m unittest discover -s tests` | Exit 0. The existing modules that pin the paragraph, the coverage table and the Step I.2.a paragraph pass unmodified | Integration |
| TS-6 | On the integration branch, list the files changed since the implement step's `base_commit` (`git diff --name-only`) | No listed path is `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` or `em-workflow/references/implement-phase.md`. Every listed path is in the declared change set: the task's files, `feature-docs/control-char-abort-stop-reason/**` or `test-docs/control-char-abort-stop-reason/**` | Integration (command check) |

## Code Quality Verification
- Format: none configured (`format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | The Step I.2.a control-character stop binds to `step_needs_intervention`, not `unmapped_stop`, under the Stop point coverage and the Precedence rule | TS-1; manual reproduction reading check below |
| AC2 | The Precedence rule still restricts `stop-condition-3` to statuses no route of the current run produced, with the control-character stop as the named exception | TS-2 |
| AC3 | The new document test passes against the live document, and each of its binding matchers fails against the verbatim pre-change paragraph | TS-1, TS-2, TS-3 |
| AC4 | The full suite passes, including the existing Precedence-rule, coverage-table and control-character-paragraph tests | TS-4, TS-5 |
| SC-1 | All functional requirements are implemented and tested | Coverage table below; TS-1 to TS-3 pass |
| SC-2 | All test scenarios pass | TS-1 to TS-6 |
| SC-3 | Code review is completed | Review phase result recorded in `workflow.yaml` |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-3 |
| FR2 | task0001 | TS-2, TS-3 |
| FR3 | task0001 | TS-1, TS-2, TS-3 |
| NFR1 | task0001 | TS-4, TS-5 |
| NFR2 | task0001 | TS-5 (existing anchor pins in `tests/test_batch_stop_contract.py`, `tests/test_abort_terminal_commit_precedence.py`, `tests/test_failed_kind_batch_docs.py`) |
| NFR3 | task0001 | TS-4, TS-5 |
| NFR4 | task0001 | TS-3; review of the new module's imports |
| NFR5 | task0001 | TS-6 |

## Manual Testing (E2E Not Possible)
- [ ] Reproduction reading check (the goal's definition of done: the
  reproduction no longer yields `unmapped_stop`). Follow reproduction step 4
  as a reading exercise: take the stop raised by Step I.2.a's
  Control-character check after it commits `implement: failed` /
  `failed_kind: decision`. Read `## Stop point coverage`, the "Precedence
  rule:" paragraph and the Fallback rule of
  `em-workflow/references/batch-terminal-line.md` for that stop. Confirm that
  exactly one code results, `step_needs_intervention`, and that the Fallback
  rule does not reach the stop. No batch run with a control-character
  worktree path is performed.
- [ ] Cross-read: the route the new text states (a current-run write, no
  phase-specific row, return through develop's stop condition 3) matches the
  unchanged Control-character check paragraph of Step I.2.a in
  `em-workflow/references/implement-phase.md`.

## Performance / Security Verification (if applicable)
- Not applicable. THREAT-MODEL.md's verdict is `no-applicable-threat`, so
  there is no TM-n.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-6) | 6 | 6 | 0 | 0 |
| Code quality | 0 | 0 | 0 | 0 |
| Manual reading checks | 2 | 0 | 0 | 2 |
| Security (TM-n) | 0 | 0 | 0 | 0 |
| Total | 8 | 6 | 0 | 2 |
