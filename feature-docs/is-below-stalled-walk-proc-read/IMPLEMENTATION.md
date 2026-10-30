# Implementation Plan: is-below-stalled-walk-proc-read

## Overview
The stage walk inside `is_below` (`em-workflow/hooks/bash_guard.py`) no longer
ends at an absent or non-directory stage. It continues under the lenient
realpath rule and refuses at any /proc or /dev/fd stage, so the realpath calls
that follow never probe or read anything under /proc or /dev/fd. The rule
statements and the tests change to match. One task, task0001, carries the
whole change.

## Technology Stack
- **Language**: Python 3. The recorder guard test targets Python 3.14 (FR8).
- **Libraries**: standard library only (NFR4). No new dependency is
  introduced, so there is no license to record (`project.license: none`).
- **Test framework**: the standard library's unittest, run as
  `python3 -m unittest discover -s tests`.

## Layer Structure
The feature stays inside one hook module and adds no layer. Within
`bash_guard.py` the call direction is unchanged: hook entry → cd prefix
candidate check → `is_below` → stage walk → lexical /proc and /dev/fd
predicate. The test module depends on the hook only by loading its source
as a module. The protocol document has no code dependency.

## Shared Components
None. The feature has a single task, so no component is used across tasks
and no cross-task contract is needed. The existing contracts the task keeps
(FR6) are listed in its plan.

## Conventions
- The four rule statements describe one rule (FR5): the stage-walk
  docstring, the /proc and /dev/fd paragraph of the `is_below` docstring,
  the path item of the module docstring, and the path item of the
  protocol's Verbatim execution rule. The module docstring path item and the
  protocol path item use identical wording.
- Error policy: any exception that escapes the walk or the realpath calls
  still makes `is_below` return False, as today. The new leniency covers only
  operating-system failures while probing a stage or reading a link, and
  only after the walk has stalled.
- Tests follow the existing conventions of `tests/test_bash_guard_cd_prefix.py`:
  - one section comment and one module-docstring paragraph per feature
  - fixtures built idempotently in locations used by no other test
  - /proc cases under `needs_proc` and /dev/fd cases under `needs_dev_fd`
- The em-workflow version is not changed (NFR4).

## Cross-task Design Decisions

### D1: The feature is a single task
- **Decision**: task0001 carries the walk change, the four rule statements and
  the tests.
- **Rationale**: the behavior and its statements share one function and the
  same three files. A split would put two parallel tasks on the same
  docstring block and the same end of the test module.
- **Affected tasks**: task0001.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The continuation diverges from the lenient realpath: realpath visits a stage the walk did not check, so realpath can still read under /proc | Medium | High | task0001 Design gives the walk realpath's per-component rules. The recorder tests (task0001 AC-1, AC-2) and the recorder guard test (AC-3) catch any divergence |
| Lenient error handling leaks into the walk before the stall and weakens existing refusals | Low | High | Phase split in task0001 Design; task0001 AC-5 before-stall and after-stall error tests; the existing `TestLinkBoundAndProbeErrors` tests |
| Wording edits break the structure-based wording tests: path item boundaries, which paragraph holds /dev/fd, the identical link-target sentence pair | Medium | Medium | Constraints listed in task0001 Design; task0001 AC-6 and the full-suite run |
| A test module other than the one in scope pins text of the protocol's Verbatim execution rule | Low | Medium | Full-suite run (task0001 AC-7) |
| Python's realpath stops probing through the os module's attributes, so the recorder sees nothing and the recorder tests pass vacuously | Low | High | The recorder guard test (task0001 AC-3) fails in that case |

## Open Questions
- None.
