# Verification Document: is-below-stalled-walk-proc-read

## Overview
**Feature**: is-below-stalled-walk-proc-read / **SPEC.md**: `feature-docs/is-below-stalled-walk-proc-read/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/is-below-stalled-walk-proc-read/IMPLEMENTATION.md`

## Build Verification
- Command: none. `project.components.main.build_command` is empty, and the
  Python hook has no build step.
- Expected: not applicable.

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Targeted: `python3 -m unittest tests.test_bash_guard_cd_prefix`
- Coverage target: no coverage tool is configured. Every success criterion
  below maps to at least one scenario, and every task Acceptance Criterion
  maps to at least one test.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Each FR7 form, judged by `is_below` inside `_recorded_probes`: (a) relative `proc/missing/...`, (b) relative `x/missing/...`, (c) absolute `<area>/task0001/missing/...`, (d) a regular-file stage, (e) the `/dev/fd/<n>` variant. Also the physical-only variant `<link directory>/<link>/../<existing directory>` | `is_below` is False; no recorded probe or read path is under /proc or /dev/fd; the link itself is in the reads. /proc cases run under `needs_proc`, (e) under `needs_dev_fd` | Unit |
| TS2 | Red check: the TS1 and TS3 forms against the walk before the change | Before the change, the same forms record a probe or read under /proc or /dev/fd, and the TS3 corner form is judged True. Confirmed when the tests are written and recorded in the task's test record | Unit (red phase) |
| TS3 | Logical-path corner (SPEC A1): the form `<hop>/../<name>`, where `<name>` beside `<hop>` is a stalling link climbing to `proc/self/cwd/shared` and the physical resolution is an existing directory below the area | A fixture guard confirms that the old rule judged it True. With the cwd in `procdep/work`, `is_below` is False with nothing recorded under /proc or /dev/fd. The logical-path walk refuses and the physical-path walk does not. Still False with `resolves_to_directory` mocked to True. Through the hook with `process_cwd=work`, the decision is silent | Unit + Integration (hook subprocess) |
| TS4 | Recorder guard: a direct call to the lenient realpath on a stalled form (a) or (b) inside `_recorded_probes` | At least one probe or read under /proc is recorded | Unit |
| TS5 | The existing tests named in SPEC AC4, and the rest of `tests/test_bash_guard_cd_prefix.py` | All pass unchanged. A direct walk call on the missing-stage, regular-file and dangling-link `..` forms refuses on neither side | Unit + Integration |
| TS6 | Link bound and errors during continuation: a form with links before and after its stall; error injection for one stage or one link read | 41 links in total refuses and 40 does not; `is_below` is False for the 41-link form even with `resolves_to_directory` mocked to True. An operating-system error after the stall does not refuse, before the stall it refuses, and a ValueError after the stall refuses | Unit |
| TS7 | Rule statements: the four places of FR5 and the existing wording tests | The stage-walk docstring lacks 'ends the walk without refusal'. The continuation needle is in all four places. The continuation statement is identical in the module docstring path item and the protocol path item. `TestPathConditionWording`, `TestProcessDependentPathWording` and `TestLinkTargetWording` pass | Unit |
| TS8 | What stays unchanged (added at create-plan from SPEC AC7, which no SPEC scenario covers): the full suite, signatures, link limit, check order, child processes, imports, version files | The full suite passes. `is_below(path, area)` and `_stage_walk_refuses(path)` keep their parameters, and FOLLOWED_LINK_LIMIT is 40. `resolves_to_directory` is first called after both realpath calls. No child process starts for the added forms. The test module imports the standard library only. The change set has no edit to em-workflow's plugin.json or the root marketplace.json | Unit |

## Code Quality Verification
- Format: none configured (`format_command` is empty).
- Static analysis: none configured.
- `TestAc7StandardLibraryOnly` checks standard-library-only imports and the
  hook's `status`-free executable text.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | FR7 forms (a) to (e): False, no /proc or /dev/fd probe or read, link in reads, on both sides | TS1, with TS2 as the red check |
| AC2 | Logical-path corner: the old rule said True; now False, silent through the hook, nothing read under /proc or /dev/fd | TS3, with TS2 as the red check |
| AC3 | The recorder captures probes and reads made inside a direct realpath call | TS4 |
| AC4 | Forms whose continuation never reaches /proc or /dev/fd keep their judgment | TS5 |
| AC5 | Link bound across the stall; errors during continuation do not refuse | TS6 |
| AC6 | The four rule statements state the continuation rule; the two path items are identical; existing wording tests pass | TS7 |
| AC7 | Full suite passes; nothing weakened; standard library only; no child process; no pre-check | TS8 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1, TS2, TS3 |
| FR2 | task0001 | TS1, TS2, TS3 |
| FR3 | task0001 | TS5 |
| FR4 | task0001 | TS6 |
| FR5 | task0001 | TS7 |
| FR6 | task0001 | TS5, TS8 |
| FR7 | task0001 | TS1, TS2, TS3 |
| FR8 | task0001 | TS4 |
| NFR1 | task0001 | TS3, TS5, TS6 |
| NFR2 | task0001 | TS1, TS2, TS3 |
| NFR3 | task0001 | TS5, TS8 |
| NFR4 | task0001 | TS8 |

## Manual Testing (E2E Not Possible)
- [ ] TS2: the implementer's red-phase record in
  `test-docs/is-below-stalled-walk-proc-read/task0001.tests.yaml` shows the
  TS1, TS3 and TS6 tests failing against the unchanged walk.
- [ ] FR5 read-through: the four rule statements describe the same rule as
  the code, covering each of these:
  - the stage joins as an ordinary name, and `..` removes it
  - links are followed again
  - /proc and /dev/fd are refused before probing
  - the link bound is shared before and after the stall
  - a probe or link-read failure after the stall does not refuse

## Performance / Security Verification (if applicable)
- TM-1: the stalled walk continues under the lenient realpath rule and
  refuses at /proc or /dev/fd stages on both walks. Checked by TS1 and TS3:
  the recorder shows no /proc or /dev/fd probe or read, `is_below` is False,
  and the hook is silent.
- TM-2: links followed after the stall count toward FOLLOWED_LINK_LIMIT.
  Checked by TS6: 41 links in total refuses, and 40 does not.
- TM-3: lenient error handling starts only at the stall, and `is_below`'s
  order and post-walk rule stay unchanged. Checked by TS5 (existing tests),
  TS6 (an error before the stall refuses) and TS8 (check order, signatures,
  link limit).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS1-TS8) | 8 | 7 | 0 | 1 |
| Success criteria (AC1-AC7) | 7 | 7 | 0 | 0 |
| Security (TM-1-TM-3) | 3 | 3 | 0 | 0 |
| Manual read-through (FR5) | 1 | 0 | 0 | 1 |
