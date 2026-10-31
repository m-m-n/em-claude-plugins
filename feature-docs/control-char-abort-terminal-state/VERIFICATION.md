# Verification Document: control-char-abort-terminal-state

## Overview
**Feature**: control-char-abort-terminal-state / **SPEC.md**: `feature-docs/control-char-abort-terminal-state/SPEC.md` / **IMPLEMENTATION.md**: not produced (`reduced` tier, single task; the plan is `feature-docs/control-char-abort-terminal-state/tasks/task0001.md`) / **THREAT-MODEL.md**: `feature-docs/control-char-abort-terminal-state/THREAT-MODEL.md`

Scenarios TS-1 to TS-5 below correspond, in order, to SPEC.md's unit and
integration scenarios TS1 to TS5. TS-6 is added by this plan for the
change-set requirements (NFR2, NFR3).

## Build Verification
- Command: none configured (`project.components.main.build_command` is empty)
- Expected: no build step

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Coverage target: not measured (document tests); every Acceptance Criterion of task0001 maps to at least one scenario below

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Live `em-workflow/references/implement-phase.md`: the new terminal-handling check against the Step I.2.a section | Returns no problem: the control-character paragraph names Step I.2.c's abort phase, `failed`, `failed_kind` `decision` and `commit-docs.sh` | Unit (document test) |
| TS-2 | Forged copy of the live section with the terminal-handling text removed from the control-character paragraph | The copy differs from the live section; the new check returns at least one problem | Unit (document test) |
| TS-3 | Forged copy of the live section with the `decision` value replaced by another value (for example `infra`) | The copy differs from the live section; the new check returns at least one problem | Unit (document test) |
| TS-4 | Live document: `check_control_char_stop`, `check_control_char_scope`, `check_control_char_rejected_set`, `check_control_char_placement` | Each returns no problem; exactly one sentence with 'ABORT the implement phase'; the paragraph is still one block | Unit (document test) |
| TS-5 | Full suite | `python3 -m unittest discover -s tests` passes, including the updated byte-identical capture of the `failed_kind` section (four write paths), the stdlib-only import test, and `tests/test_queue_stop_guard.py` | Integration |
| TS-6 | Change-set containment: the integrated diff from the `implement` step's `base_commit` to the integration branch tip | Only `em-workflow/references/implement-phase.md`, `em-workflow/references/workflow-schema.md`, `tests/test_canonical_worktree_path_docs.py`, `tests/test_workflow_schema_journal_readers_doc_contract.py`, and paths under `feature-docs/control-char-abort-terminal-state/` and `test-docs/control-char-abort-terminal-state/` appear; `em-workflow/hooks/queue_stop_guard.py` is absent | Verification check (git diff) |

## Code Quality Verification
- Format: none configured / Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | The control-character paragraph states the abort-phase terminal handling: one write of `failed` / `decision`, committed with `commit-docs.sh`, no cleanup, return through stop condition 3 | TS-1, TS-2, TS-3 |
| AC-2 | Exactly one 'ABORT the implement phase' sentence; the existing control-character tests pass unchanged | TS-4, TS-5 |
| AC-3 | Live-document test and forged-copy tests for the terminal-handling citation exist | TS-1, TS-2, TS-3 |
| AC-4 | The `failed_kind` section's write-path count equals the number of `implement`-failed write paths in `implement-phase.md` | TS-5 (byte-identical pin), plus a reading check: route-back gate rejected, abort phase, batch second failure, control-character stop = four |
| AC-5 | The full suite passes | TS-5 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2 |
| FR2 | task0001 | TS-1, TS-3 |
| FR3 | task0001 | TS-4 |
| FR4 | task0001 | TS-5 |
| FR5 | task0001 | TS-1, TS-2, TS-3, TS-5 |
| NFR1 | task0001 | TS-5 |
| NFR2 | task0001 | TS-6 |
| NFR3 | task0001 | TS-6 |
| NFR4 | task0001 | TS-4 |

## Manual Testing (E2E Not Possible)
- [ ] Reproduction (workflow.yaml goal, reproduction steps): make a task worktree path resolve to a directory whose name contains a line feed, then run develop into the implement phase. After the control-character stop: the `implement` step reads `failed` with `failed_kind` `decision` in a commit made through `commit-docs.sh`; no implementer is launched; the Stop hook neither blocks the turn end nor names a launch target; develop stops at stop condition 3; task worktrees and branches remain.

## Performance / Security Verification (if applicable)
- TM-1: the control-character stop leaves the `implement` step `failed` in a committed write (abort-phase terminal handling), so the queue Stop hook has no candidate and requests no launch of a rejected task — checked by TS-1 and TS-2 (the paragraph carries the terminal handling) and by `tests/test_queue_stop_guard.py` within TS-5 (a feature whose `implement` step is not `in_progress` passes the hook).
- TM-2: `failed_kind` is `decision` unconditionally on this path, so batch's `failed_kind` auto-resume does not re-enter the phase into the same rejection — checked by TS-1 (live value) and TS-3 (a forged copy with another value fails).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 6 | 6 | 0 | 0 |
| Success criteria | 5 | 5 | 0 | 0 |
| Requirements coverage | 9 | 9 | 0 | 0 |
| Security (TM-n) | 2 | 2 | 0 | 0 |
| Manual testing | 1 | 0 | 0 | 1 |
