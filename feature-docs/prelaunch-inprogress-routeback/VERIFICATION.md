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
- Expected: both commands exit 0, and every test passes.
- Coverage target: not measured. The tests are document contracts plus
  hook and validator behavior. Every acceptance criterion maps to at least
  one test.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Unchanged. In I.2.a, the approval gate, the `Task()` launch loop, the `LAUNCH_TIP` capture, the refresh, the write and the commit appear in strictly increasing positions (`tests/test_prelaunch_inprogress_launch_order.py`) | The ordering tests pass unmodified | Unit (document contract) |
| TS2 | Unchanged. The `in_progress` write set is limited to launches the re-read journal confirms. A partial launch yields one write set and one commit, and an unconfirmed task stays `pending` (`tests/test_prelaunch_inprogress_launch_order.py`) | The tests pass unmodified | Unit (document contract) |
| TS3 | Unchanged. An empty write set omits the write and the commit, and the turn ends after the commit or its omission (`tests/test_prelaunch_inprogress_launch_order.py`) | The tests pass unmodified. The `--batch` marker sentence occurs exactly once in I.2.a | Unit (document contract) |
| TS4 | Unchanged. The journal is re-read for the commit and for the exit-4 retry. Terminal tasks are never written `in_progress`. A second exit 4 keeps the records, worktrees and branches (`tests/test_prelaunch_inprogress_launch_order.py`) | The tests pass unmodified | Unit (document contract) |
| TS5 | I.2.a contains no never-arise claim. The `pending` + `launched` sentence and the recursion invariant remain. I.2.a states that a task which failed without reaching the launch-state commit does not match the record, so the carve-out does not apply (`tests/test_prelaunch_inprogress_pending_launched.py`, `tests/test_routeback_record_carve_out.py`) | The tests pass. The task0002 module passes unmodified | Unit (document contract) |
| TS6 | Negative proof: every new wording matcher (TS1–TS3, TS8, TS9, TS11–TS13) fails against a verbatim pre-change sample of its region. Each failure is backed by a non-vacuity guard. The new modules use only standard-library `unittest` under `tests/` | Every negative-proof test passes | Unit (document contract) |
| TS7 | Regression guards `tests/test_implement_routeback_gate.py` and `tests/test_exit4_tip_argument_consistency.py` pass. They are unmodified, or follow only the I.2.c record item. With that single item removed, the whitespace-normalized I.2.c section equals the implement-base text (`tests/test_routeback_record_carve_out.py`). `git diff {implement base_commit}..em-workflow/prelaunch-inprogress-routeback/integration -- em-workflow/references/implement-phase.md` shows changes to `### I.2.c: Failed handling` only in the route-back write set's record item, and no hunk in the Branch & Worktree Model's exit-4 recovery bullet | Modules pass. The I.2.c digest check passes. The diff matches the stated containment | Integration (regression guard + diff inspection) |
| TS8 | Region L defines the write set's failed part. A task whose `launched` was appended after the selection-time replay and whose re-read last event is `failed` gets `status = failed` and `branch` in the same launch-state commit, and never `in_progress`. A task with no `launched` appended after the selection-time replay is not written, including one already `pending` + `failed` at selection. The launch-state write leaves the record unchanged. The exit-4 retry re-derives both parts (`tests/test_prelaunch_failed_launch_state.py`) | The tests pass. Matchers fail on the pre-change Region L | Unit (document contract) |
| TS9 | Three sites state the three conditions and route a non-matching task to I.2.c as `failed`: the I.2.a carve-out definition, I.2.b step 1 and the Stop-hook bullet. The three conditions are: `pending`, journal last event `failed`, and that event's line equal to `tasks.{T}.routeback_failed_journal_line`. The I.2.c route-back write set writes the record, and the route-back commit records it (`tests/test_routeback_record_carve_out.py`) | The tests pass. Matchers fail on the pre-change "pending + failed → unlaunched"-only wording | Unit (document contract) |
| TS10 | `queue_stop_guard.py` is run as a subprocess (`tests/test_queue_stop_guard_routeback_record.py`). Cases: (a) a matching record gives exit 2, naming the task; (b) no record gives exit 0; (c) `null` gives exit 0; (d) a different line gives exit 0; (e) non-canonical values give exit 0: 0, negative, non-integer, quoted, empty, leading zero; (f) blank, malformed, unknown-event or invalid-task lines before the target are counted, so the correct line gives exit 2 and the skipped-count line gives exit 0; (g) a record in another task's block or on a step line is ignored. The three existing recycled-task-id tests in `tests/test_queue_stop_guard.py` carry a matching record and still give exit 2. `TestQueueStopGuardStdlibOnly` passes | Every case matches. No existing case is deleted | Integration (hook subprocess) |
| TS11 | I.2.a has no "arises only from I.2.c's own reset". The Reason sentence names the not-reached-launch-state-commit failure path and states that the record match distinguishes it. The allocation-rule citation remains (`tests/test_routeback_record_carve_out.py`) | The tests pass. Matchers fail on the pre-change Reason sentence | Unit (document contract) |
| TS12 | `workflow-schema.md` defines `routeback_failed_journal_line` as optional, under the heading ``## `routeback_failed_journal_line` ``. The definition covers: the meaning; the 1-based LF physical-line value, counting blank and malformed lines; the canonical form; absent or `null` meaning no record; the sole writer; and no rewrite at launch or on ordinary status updates (`tests/test_routeback_record_schema_patch.py`) | The tests pass. Matchers fail on the pre-change schema | Unit (document contract) |
| TS13 | The verbatim carry-over list in `workflow-patch.md` equals `CARRIED_RECORD_FIELDS` and includes the record. A carried task keeps its record value through `apply_patch`. The preserve vocabulary has no entry for the record (`tests/test_replanning_carry_over.py`, `tests/test_routeback_record_schema_patch.py`) | The tests pass | Unit (contract + in-process apply) |
| TS14 | Workflow-patch validation rejects `replace_all` and `append` patches whose entries carry `routeback_failed_journal_line`, with an integer value and with `null`. It still accepts the same patches without the key (`tests/test_routeback_record_schema_patch.py`) | Rejections carry the machine-readable error code. Existing valid patches still pass | Unit (in-process validator) |
| TS15 | `python3 -m unittest discover -s tests` runs the full suite | Exit 0, all green | Integration (full suite) |
| TS16 | NFR2 change containment. Run `git diff --name-only {implement base_commit}..em-workflow/prelaunch-inprogress-routeback/integration`. It lists only these paths: `em-workflow/references/implement-phase.md`, `em-workflow/hooks/queue_stop_guard.py`, `em-workflow/references/workflow-schema.md`, `em-workflow/references/workflow-patch.md`, `em-workflow/scripts/validate-worker-output.py`, paths under `tests/`, `feature-docs/prelaunch-inprogress-routeback/**` and `test-docs/prelaunch-inprogress-routeback/**` | No other path is listed. In particular, no diff appears in `queue_launch_guard.py`, `queue_failure_net.py`, `queue_taskstop_net.py`, `merge-task.sh` or `journal-append-failed.py` | Integration (diff inspection) |

## Code Quality Verification
- Format: none configured (`format_command` is empty for both components).
- Static analysis: `python3 em-workflow/scripts/check-plugin-invariants.py .` exits 0.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | The approval gate and the launch loop precede the `LAUNCH_TIP` capture | TS1 |
| AC2 | Capture, refresh, write and commit stay in order. `tests/test_exit4_tip_argument_consistency.py` passes unmodified | TS1, TS7 |
| AC3 | The `in_progress` write set is the confirmed launches. Unconfirmed tasks stay `pending`. A partial launch, including FR7 failed records, yields one write set and one commit | TS2, TS8 |
| AC4 | An empty write set omits the commit, and the turn ends after the commit processing | TS3, TS8 |
| AC5 | Re-read on commit and on retry. Terminal tasks are never `in_progress`. A second exit 4 keeps the records, worktrees and branches | TS4, TS8 |
| AC6 | No never-arise claim. The `pending` + `launched` sentence remains. A not-reached-commit failure does not match the record | TS5 |
| AC7 | The I.2.c section and the exit-4 recovery bullet are unchanged except for the one record item | TS7 |
| AC8 | New tests cover AC1–AC15 and fail on the pre-change wording. The full suite is green | TS6, TS15 |
| AC9 | FR7: the failed part of the launch-state write set; tasks with no post-selection `launched` are not written | TS8 |
| AC10 | FR8: the three conditions at I.2.a, I.2.b step 1 and the Stop-hook bullet; non-matching tasks go to I.2.c; I.2.c writes the record | TS9 |
| AC11 | FR9 / NFR5: hook classification by record match, value parsing, block scoping, physical-line counting, stdlib-only | TS10 |
| AC12 | FR10: the Reason sentence is corrected | TS11 |
| AC13 | FR11: schema definition | TS12 |
| AC14 | FR12: carry-over list and `apply_patch` preservation | TS13 |
| AC15 | FR13: worker entries carrying the record are rejected | TS14 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1 |
| FR2 | task0001, task0003 | TS2, TS8 |
| FR3 | task0001, task0003 | TS3, TS8 |
| FR4 | task0001, task0003 | TS4, TS8 |
| FR5 | task0002, task0004 | TS5 |
| FR6 | task0001, task0002, task0003, task0004, task0005, task0006 | TS5, TS6, TS15 |
| FR7 | task0003 | TS8 |
| FR8 | task0004 | TS9, TS7 |
| FR9 | task0004, task0005 | TS10 |
| FR10 | task0004 | TS11 |
| FR11 | task0006 | TS12 |
| FR12 | task0006 | TS13 |
| FR13 | task0006 | TS14 |
| NFR1 | task0001, task0002, task0003, task0004 | TS7 |
| NFR2 | task0001, task0002, task0003, task0004, task0005, task0006 | TS16 |
| NFR3 | task0001, task0002, task0003, task0004, task0005, task0006 | TS6, TS15 |
| NFR4 | task0001, task0002, task0003, task0004, task0005, task0006 | TS6 |
| NFR5 | task0005 | TS10 |

## Manual Testing (E2E Not Possible)
- [ ] Read the I.2.a carve-out definition, I.2.b step 1's exception clause,
  the Stop-hook bullet and the `queue_stop_guard.py` module docstring side
  by side. Confirm that all four state the same three conditions and the
  same `failed` outcome, and that each one's implementation matches its
  text.
- [ ] Confirm that `implement-phase.md`'s citation of
  `references/workflow-schema.md` for the record resolves to the
  ``## `routeback_failed_journal_line` `` section.
- [ ] Confirm that the line-counting rule the schema states matches the
  hook's behavior. The two were written by different tasks.
- [ ] Walk SPEC.md's edge cases through the merged text. Each must have
  exactly one stated outcome:
  - partial launch;
  - launched and already failed before the commit;
  - already `pending` + `failed` and not launched;
  - empty write set;
  - terminal task at the exit-4 retry;
  - second exit 4;
  - not-reached commit, then failure;
  - re-failure after reset;
  - reset task with no journal event;
  - pre-upgrade route-back without a record;
  - blank or malformed lines before the target;
  - record in another block.

## Performance / Security Verification (if applicable)
- Performance: SPEC.md states no performance requirement.
- TM-1: workers cannot set `routeback_failed_journal_line`. Checked by TS14:
  validation rejects `replace_all` and `append` entries carrying the key,
  with an integer value or `null`. Also checked by TS12: the schema names
  the orchestrator's I.2.c write set as the sole writer.
- TM-2: the carve-out requires the three-condition record match, and
  anything else is `failed`, routed to I.2.c with no hook BLOCK. Checked by
  TS9 for the protocol text at all three sites, and by TS10 cases (a)–(e)
  and (g) for hook behavior.
- TM-3: the orchestrator and the hook use identical LF-only physical-line
  counting. Checked by TS10 case (f) for the hook and by TS12 for the
  schema's single counting rule. The manual counting-rule check confirms
  the two agree.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS1–TS16) | 16 | 16 | 0 | 0 |
| Code quality | 1 | 1 | 0 | 0 |
| Success criteria (AC1–AC15) | 15 | 15 | 0 | 0 |
| Manual reading checks | 4 | 0 | 0 | 4 |
| Security (TM-1–TM-3) | 3 | 3 | 0 | 0 |
