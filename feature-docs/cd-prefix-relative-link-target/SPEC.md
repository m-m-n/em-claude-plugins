# Feature: cd-prefix-relative-link-target

## Overview

In the cd-prefix check of `em-workflow/hooks/bash_guard.py`, a relative link
whose target is an ordinary directory inside the allowed area (one named
`proc`, or `dev/fd`) is no longer refused as being under `/proc` or
`/dev/fd`. Auto-approval of approved commands applies in that case as well.

## Objectives

- In the cd-prefix check of `em-workflow/hooks/bash_guard.py`, do not refuse
  a relative link that points to an ordinary directory inside the allowed
  area (named `proc`, or `dev/fd`) as being under `/proc` / `/dev/fd`.
  Auto-approval of approved commands applies in that case as well.
- Resolve the regression against the SPEC of feature
  `cd-prefix-process-dependent-paths`: its FR1 (directories named `proc` /
  `dev/fd` that are not directly under the root are not excluded) and its
  FR4 (other checks are unchanged).

## User Stories

### US1: Relative links to in-area `proc` / `dev/fd` directories are accepted

**Acceptance Criteria:**
- [ ] AC-1: With real directories `<dir>/proc` and `<dir>/dev/fd` inside the
  allowed area, and `<dir>/alias` whose target is the relative `proc`,
  `./proc` or `dev/fd`, `is_below('<dir>/alias', area)` returns True.
  (FR1)
- [ ] AC-2: For paths containing a link whose target is the absolute
  `/proc/self/cwd`, `/proc/self` (followed by `cwd/<name>`) or
  `/dev/fd/<N>`, `is_below` returns False (the existing AC-3 tests in
  `TestProcessDependentPathCheck` pass). (FR2)
- [ ] AC-3: For a link whose relative target climbs back to the root with
  repeated `..` and reaches under `/proc` (e.g. `../../…/proc/self/cwd`),
  `is_below` returns False. (FR3)
- [ ] AC-4: `python3 -m unittest discover -s tests` passes with no failures
  other than the same skips as before the change (including
  `tests/test_bash_guard_cd_prefix.py` and
  `tests/test_bash_guard_cd_prefix_operators.py`). (FR4, FR5)
- [ ] AC-5: The `_stage_walk_refuses` docstring, the path item of the module
  docstring, and the path item of the protocol state that the lexical check
  applies to absolute targets, and that relative targets are checked at the
  resolution stages. (FR5)

## Technical Requirements

### Functional Requirements

- **FR1: Relative targets are not checked lexically.** When a link's target
  (the return value of `os.readlink`) is a relative path (does not start
  with `/`), `_stage_walk_refuses` does not apply `_under_proc_or_dev_fd` to
  that string. A relative target is judged by the stage checks
  (`_under_proc_or_dev_fd` at each stage, and the check after applying `..`)
  after it is joined to the directory containing the link.
- **FR2: The check of absolute targets is unchanged.** Links whose target is
  an absolute path (e.g. `/proc/self/cwd`, `/proc/self`, `/dev/fd/<N>`) are
  refused as before. `is_below` returns False for paths containing such
  links.
- **FR3: A relative target that resolves under `/proc` / `/dev/fd` is
  refused.** When a relative target reaches under `/proc` or `/dev/fd` at a
  resolution stage (via `..` or otherwise), the stage checks refuse it
  (`is_below` returns False).
- **FR4: Other checks are unchanged.** The followed-link limit
  (`FOLLOWED_LINK_LIMIT`), loop refusal, handling of `OSError` /
  `ValueError` during the stage checks, the lexical check on the path as
  written, the arguments and callers of `is_below`, not spawning child
  processes, and standard-library-only imports are unchanged.
- **FR5: Descriptions match the behavior.** The `_stage_walk_refuses`
  docstring (`"follows a link whose target text is under one"`), the path
  item of the module docstring's cd prefix section, and the path item of the
  Verbatim execution rule in
  `em-workflow/references/command-execution-protocol.md` read as: the lexical
  check of the target string applies only to absolute targets, and relative
  targets are judged at the resolution stages. The phrase
  `"the target of each link followed"` and every other phrase in
  `PROCESS_DEPENDENT_PATH_NEEDLES` checked by existing tests are kept.

### Non-Functional Requirements

- **NFR1 - Version:** The implementation does not change the em-workflow
  version (`plugin.json`, `marketplace.json`).
- **NFR2 - Resolution boundary:** The check keeps the property of not
  resolving the filesystem into `/proc` (it stops at the first refused
  stage).
- **NFR3 - Test dependencies:** Tests use the standard library only.

## Implementation Approach

### Assumptions

- The change targets only the lexical check of the link target in
  `_stage_walk_refuses` of `bash_guard.py` (lines 317-318). The lexical
  check on the path as written at the start of `is_below` is unchanged.
- The FR5 description update is in scope. The protocol's path item reads as
  lexically checking "the target of each link", which as written would
  disagree with the behavior after this fix. Phrases checked by existing
  wording tests are kept.
- Removing relative targets from the lexical check does not lose the
  safe-side property, because targets reaching `/proc` / `/dev/fd` are
  refused by the stage checks (line 307, and line 303 after `..`).
- New tests are placed in `tests/test_bash_guard_cd_prefix.py`, following
  its Layout (`procdep/names`, `procdep/links`).

### Affected Files

- `em-workflow/hooks/bash_guard.py` (FR1, FR5)
- `em-workflow/references/command-execution-protocol.md` (FR5)
- `tests/test_bash_guard_cd_prefix.py` (TS-1 to TS-4)

### Dependencies

**Internal Dependencies:**
- feature `cd-prefix-process-dependent-paths`: its SPEC FR1 and FR4 are the
  requirements this feature restores.

**External Dependencies:**
- None (standard library only).

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/cd-prefix-relative-link-target/**`
- `test-docs/cd-prefix-relative-link-target/**`

`feature-docs/cd-prefix-relative-link-target/**` covers `REQUIREMENTS.md`,
`SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/cd-prefix-relative-link-target/**` covers
`test-docs/cd-prefix-relative-link-target/{T}.tests.yaml`, the per-task test
record. It is generated and owned by `implement-phase.md`; this section
cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/cd-prefix-relative-link-target/` directory at all; the declared
`test-docs/cd-prefix-relative-link-target/**` entry is still correct in
that case — a declared path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1 (AC-1; FR1): For the three relative targets `proc`, `./proc` and
  `dev/fd`, `is_below` returns True (first confirm it returns False before
  the change).
- [ ] TS-2 (AC-1; FR1): For the same three cases with the target set to the
  absolute `<dir>/proc` / `<dir>/dev/fd`, `is_below` stays True (control).
- [ ] TS-3 (AC-3; FR3): For a link whose relative target climbs back to the
  root with `..` and reaches `/proc/self/cwd`, `is_below` returns False.
- [ ] TS-4 (AC-2; FR2): The existing absolute-target cases (cwd-link,
  self-link, link to `/dev/fd/<N>`) stay False.

### Integration Tests
- [ ] TS-5 (AC-4, AC-5; FR4, FR5): The full test suite runs with no
  regression, and the wording needle tests pass.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

## Success Criteria

- [ ] AC-1 to AC-5 are satisfied
- [ ] TS-1 to TS-5 pass

## Open Questions

None.

## References

- SPEC of feature `cd-prefix-process-dependent-paths` (FR1, FR4)
- `em-workflow/references/command-execution-protocol.md`
