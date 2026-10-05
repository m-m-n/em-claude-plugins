# Verification Document: prelaunch-inprogress-routeback

## Overview
**Feature**: prelaunch-inprogress-routeback / **SPEC.md**: `feature-docs/prelaunch-inprogress-routeback/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/prelaunch-inprogress-routeback/IMPLEMENTATION.md`

## Build Verification
- Command: none. Both components (`repo-tests`, `plugin-invariants`) have an
  empty `build_command`.
- Expected: not applicable.

## Test Verification
- Command (repo-tests): `python3 -m unittest discover -s tests`
- Command (plugin-invariants): `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Expected: both exit 0; every test passes.
- Coverage target: not measured (document-contract tests). Every acceptance
  criterion maps to at least one test.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | In the I.2.a section, the positions of the approval gate, the `Task()` launch loop, the `LAUNCH_TIP` capture, the refresh, the write and the commit increase strictly in that order (`tests/test_prelaunch_inprogress_launch_order.py`) | The ordering test passes | Unit (document contract) |
| TS2 | The write set is limited to tasks whose launch the re-read journal confirms, not every selected task. A partial launch yields one write set and one commit, and an unconfirmed task stays `pending` (`tests/test_prelaunch_inprogress_launch_order.py`) | Tests pass; the old "for EVERY task selected in this entry" phrase is absent | Unit (document contract) |
| TS3 | An empty write set omits the write and the commit. The turn ends after the launch-state commit or its omission. No "immediately after launching" remains in the Step I.2 intro or I.2.a (`tests/test_prelaunch_inprogress_launch_order.py`) | Tests pass; the `--batch` marker-only sentence occurs exactly once in I.2.a | Unit (document contract) |
| TS4 | The journal is re-read for the first commit and for the exit-4 retry, and terminal tasks are excluded. A second exit 4 stops while keeping the launch records, worktrees and branches (`tests/test_prelaunch_inprogress_launch_order.py`) | Tests pass | Unit (document contract) |
| TS5 | The "can never arise." claim is gone from I.2.a. The replacement names the launch-state commit window, the not-reached case and the in-flight rule. The recursion invariant and the in-flight sentence remain (`tests/test_prelaunch_inprogress_pending_launched.py`, plus the retargeted tests in `tests/test_routeback_reset_scope_consistency.py` and `tests/test_recycled_task_id_consistency.py`) | Tests pass | Unit (document contract) |
| TS6 | Negative proof: the TS1–TS3 matchers fail against a verbatim pre-change I.2.a sample (where the commit precedes the approval gate and the launch loop), and a non-vacuity guard backs each failure. The new modules use only standard-library `unittest` under `tests/`. The full suite is green | Every negative-proof test passes; `python3 -m unittest discover -s tests` exits 0 | Unit (document contract) |
| TS7 | `tests/test_implement_routeback_gate.py` and `tests/test_exit4_tip_argument_consistency.py` pass with no modification. `git diff {implement base_commit}..em-workflow/prelaunch-inprogress-routeback/integration -- em-workflow/references/implement-phase.md` shows no hunk inside the `### I.2.c: Failed handling` section or the `## Branch & Worktree Model` section | Both modules pass; the diff of both files is empty; no hunk in either protected section | Integration (regression guard + diff inspection) |
| TS8 | `git diff --name-only {implement base_commit}..em-workflow/prelaunch-inprogress-routeback/integration` lists only `em-workflow/references/implement-phase.md`, paths under `tests/`, `feature-docs/prelaunch-inprogress-routeback/**` and `test-docs/prelaunch-inprogress-routeback/**` | No path outside that set; no file under `em-workflow/hooks/` or `em-workflow/scripts/` | Integration (diff inspection) |

## Code Quality Verification
- Format: none configured (`format_command` is empty for both components).
- Static analysis: `python3 em-workflow/scripts/check-plugin-invariants.py .` exits 0.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | The approval gate and the `Task()` launch loop precede the `LAUNCH_TIP` capture in I.2.a | TS1 |
| AC2 | Capture / refresh / write / commit stay in order with the `"$LAUNCH_TIP"` third argument; the refill statement remains; `tests/test_exit4_tip_argument_consistency.py` passes unmodified | TS1, TS7 |
| AC3 | The write set is the tasks whose launch is confirmed; unconfirmed tasks stay `pending`; a partial launch yields one commit | TS2 |
| AC4 | An empty write set omits the commit; the turn ends after the commit processing; no "end immediately after launching" remains | TS3 |
| AC5 | The journal is re-read for both the commit and the exit-4 retry; terminal tasks are never written `in_progress`; a second exit 4 keeps the records, worktrees and branches | TS4 |
| AC6 | The "can never arise" claim is gone and replaced; the recursion invariant and the in-flight sentence remain | TS5 |
| AC7 | The I.2.c section and the exit-4 recovery bullet are unchanged; `tests/test_implement_routeback_gate.py` passes unmodified | TS7 |
| AC8 | The new tests cover AC1–AC6 and fail on the pre-change wording; the full suite is green | TS6 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1 |
| FR2 | task0001 | TS2 |
| FR3 | task0001 | TS3 |
| FR4 | task0001 | TS4 |
| FR5 | task0002 | TS5 |
| FR6 | task0001, task0002 | TS5, TS6 |
| NFR1 | task0001, task0002 | TS7 |
| NFR2 | task0001, task0002 | TS8 |
| NFR3 | task0001, task0002 | TS6 |
| NFR4 | task0001, task0002 | TS6 |

## Manual Testing (E2E Not Possible)
- [ ] Read the Step I.2 intro and I.2.a end to end. Confirm the flow reads: task selection → worktree creation (resume guard) → approval gate → launch loop → journal re-read → capture → refresh → write → commit → end of turn. This must match SPEC.md's Architecture section.
- [ ] Confirm that the rewritten Region P sentence's "launch-state commit" names the same commit Region L defines, and that both describe the same window.
- [ ] Walk the four edge cases (partial launch, zero launch, terminal task at the exit-4 retry, second exit 4) through the merged text. Each must have exactly one stated outcome.

## Performance / Security Verification (if applicable)
- Not applicable. THREAT-MODEL.md's verdict is `no-applicable-threat` (no TM-n), and SPEC.md states no performance requirement.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS1–TS8) | 8 | 8 | 0 | 0 |
| Code quality | 1 | 1 | 0 | 0 |
| Success criteria (AC1–AC8) | 8 | 8 | 0 | 0 |
| Manual reading checks | 3 | 0 | 0 | 3 |
| Security (TM-n) | 0 | 0 | 0 | 0 |
