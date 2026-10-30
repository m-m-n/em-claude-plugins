# Feature: is-below-stalled-walk-proc-read

## Overview

When the stage walk of `is_below` in `em-workflow/hooks/bash_guard.py` stops
at an absent stage or a regular-file stage, the walk continues under the same
rule as non-strict `os.path.realpath` instead of ending. During that
continuation the existing `/proc` / `/dev/fd` stage check applies, so the
`os.path.realpath` calls that follow never `lstat` or `readlink` anything under
`/proc` or `/dev/fd`, on both the physical-path side and the logical-path side.
Requirements document: `feature-docs/is-below-stalled-walk-proc-read/REQUIREMENTS.md`.

## Objectives

- When the stage walk of `is_below` stops at an absent stage or a regular-file
  stage, the `os.path.realpath` calls that follow do not `lstat` or `readlink`
  anything under `/proc` or `/dev/fd`. This holds on both the physical-path
  side and the logical-path side.
- The judgment no longer depends on the hook process's own cwd or fds
  (`/proc/self/...`).

## User Stories

Not applicable.

## Technical Requirements

### Functional Requirements

- **FR1: Continue a stalled stage walk with the lenient realpath rule.**
  When `_stage_walk_refuses` reaches an absent stage or a non-directory stage,
  it does not end the walk. It continues under the same rule as non-strict
  `os.path.realpath`:
  - That stage joins the reached location as an ordinary name, and a later
    `..` removes it.
  - Once the walk is back at an existing location, it probes stages and
    follows links again.
  - A relative link target resolves from the directory that holds the link.
  - An absolute link target resets the reached location to the root.
  - This applies to both the logical-path walk
    (`_stage_walk_refuses(os.path.normpath(path))`) and the physical-path walk
    (`_stage_walk_refuses(path)`).
- **FR2: Refuse at a /proc or /dev/fd stage during continuation.**
  During continuation the existing stage check applies unchanged:
  - The walk refuses when a stage it reaches is under `/proc` or `/dev/fd` per
    `_under_proc_or_dev_fd`, including the location left after a `..`.
  - The walk refuses when a link it follows has an absolute target whose text
    is under `/proc` or `/dev/fd`.
  - The walk refuses before probing that stage.
  - When either walk refuses, `is_below` returns `False` without calling
    `os.path.realpath`.
- **FR3: No refusal when continuation never reaches /proc or /dev/fd.**
  When the continuation reaches the end of the path without touching a
  `/proc` or `/dev/fd` stage, the walk does not refuse. The existing rule
  decides the outcome after the walk: both logical path and physical path
  strictly below the area when the logical path is a directory, otherwise the
  physical path alone. This keeps the rule pinned at
  `tests/test_bash_guard_cd_prefix.py:1572`: a stopped walk is not a refusal.
- **FR4: Link bound and errors during continuation.**
  - Links followed during continuation count toward the same
    `FOLLOWED_LINK_LIMIT` (40), and following more than that refuses.
  - An `lstat` or `readlink` failure during continuation is handled the way
    non-strict realpath handles it: the stage is treated as an ordinary name
    and the walk continues, with no refusal.
  - Before a stall, the existing error rule is kept: errors other than an
    absent or non-directory stage refuse.
- **FR5: Update the rule statements.**
  - The `_stage_walk_refuses` docstring loses the sentence
    'A stage that does not exist, or a non-directory, ends the walk without
    refusal ...'. In its place it states the continuation rule from FR1 and
    FR2.
  - The following all state that the stage check continues past an absent or
    non-directory stage the way the lenient realpath does:
    - the `/proc` and `/dev/fd` paragraph of the `is_below` docstring
    - the path item of the module docstring
    - the path item of the Verbatim execution rule in
      `em-workflow/references/command-execution-protocol.md`
  - The module docstring path item and the protocol path item state it in
    identical wording.
  - The needles of the existing wording tests are kept.
- **FR6: What stays unchanged.**
  - The signature and caller of `is_below` and `_stage_walk_refuses`
  - `_under_proc_or_dev_fd`
  - The value of `FOLLOWED_LINK_LIMIT`
  - The order in which `is_below` runs its checks
  - The decision table of the cd prefix allowance (allow / silent / deny)
  - No pre-check that calls `resolves_to_directory(path)` before realpath is
    added (A6).
- **FR7: Tests that record file operations.**
  Add tests to `tests/test_bash_guard_cd_prefix.py` that use
  `_recorded_probes`, the recorder of `os.lstat`, `os.stat` and `os.readlink`.
  They place the following link targets in the fixture and check two things
  for each: `is_below` returns `False`, and nothing under `/proc` or `/dev/fd`
  is probed or read during the judgment.
  - (a) A relative target that starts with `proc`: `proc/missing/` followed by
    `..` and then `proc/self/cwd`.
  - (b) A relative target that does not start with `proc`: `x/missing/`
    followed by `..` and then `proc/self/cwd`.
  - (c) An absolute target: `<area>/task/missing/` followed by `..` and then
    `proc/self/cwd`.
  - (d) A target that stops at a regular-file stage instead of an absent
    stage.
  - (e) A target that ends in `/dev/fd/<n>` instead of `/proc`.

  The number of `..` in each target is computed from the depth of the
  temporary directory, as `climb_target` does, so that it climbs to the root.
  Also add the logical-path corner (A1) form, both at module level and through
  the hook.
- **FR8: Guard test for the recorder.**
  Add a guard test showing that, on this Python (3.14), `_recorded_probes`
  captures the `lstat` and `readlink` calls made inside `os.path.realpath`.
  Example: run `os.path.realpath` directly on the stalled form from FR7(a) or
  (b) inside the recorder, and assert that it records at least one probe or
  link read under `/proc`. This keeps the FR7 tests from passing vacuously.
  Each FR7 case also asserts that the link itself appears in
  `record['reads']`.

### Non-Functional Requirements

- **NFR1 - Direction and scope of judgment changes:** `is_below`'s judgment
  changes in only two cases, and only from `True` to `False`. The first is the
  logical-path corner in A1: the stalled logical-path walk's lexical
  continuation reaches a `/proc` or `/dev/fd` stage. The second is the link
  bound in A3. Every other judgment, including the physical-path side (A5) and
  every form that goes through the stalling link directly, stays unchanged.
- **NFR2 - No reads under /proc or /dev/fd:** While `is_below` judges a path
  whose stage walk stops at an absent or regular-file stage, nothing under
  `/proc` or `/dev/fd` is probed with `os.lstat` or `os.stat` or read with
  `os.readlink`, on either the physical-path side or the logical-path side.
  The `os.path.realpath` calls are included.
- **NFR3 - Existing tests are kept:** No existing test or assertion in
  `tests/test_bash_guard_cd_prefix.py` is removed or weakened. In particular,
  `test_ac6_a_missing_stage_or_a_non_directory_stage_is_not_an_error`,
  `test_ac2_the_logical_walk_refuses_a_form_only_the_collapsed_path_reaches`,
  `test_ac4_the_decision_does_not_depend_on_strict_mode_realpath`, and all of
  `TestRelativeLinkTarget` pass unchanged.
- **NFR4 - Implementation constraints:** Standard library only. The path check
  starts no child process. The plugin version is not touched.

## Implementation Approach

### Architecture

The change is confined to the stage walk inside `is_below`. The walk runs
before both `os.path.realpath` calls (A6). When neither walk refuses, the
existing post-walk decision rule (FR3) applies unchanged.

**Component Diagram:**
```
is_below(path)                                 # order of checks unchanged (FR6)
├── _stage_walk_refuses(os.path.normpath(path)) # logical-path walk
├── _stage_walk_refuses(path)                   # physical-path walk
│     ├── _under_proc_or_dev_fd                 # stage check, unchanged (FR6)
│     └── FOLLOWED_LINK_LIMIT (40)              # shared link bound (FR4)
└── os.path.realpath(...)                       # reached only when no walk refuses
```

### Data Flow

```
path
 → stage walk (probe stage, follow links)
     ├─ stage under /proc or /dev/fd, or absolute link target under them → refuse
     ├─ links followed > FOLLOWED_LINK_LIMIT                              → refuse
     ├─ absent / non-directory stage
     │     → continue as an ordinary name (lexical `..` removes it);
     │       probe and follow links again once back at an existing location;
     │       lstat/readlink failure during continuation → ordinary name, no refusal
     └─ end of path reached                                              → no refusal
 refuse     → is_below returns False (os.path.realpath is not called)
 no refusal → os.path.realpath + existing post-walk decision rule
```

### API Design

Not applicable. The signatures of `is_below` and `_stage_walk_refuses` stay
unchanged (FR6).

### Database Schema

Not applicable.

### Dependencies

**Internal Dependencies:**
- `_under_proc_or_dev_fd`: stage check reused unchanged during continuation.
- `FOLLOWED_LINK_LIMIT`: link bound shared by the walk before and after a
  stall.
- `_recorded_probes` (tests): recorder of `os.lstat`, `os.stat` and
  `os.readlink`.
- `climb_target` (tests): the way the number of `..` is computed from the
  temporary directory's depth.

**External Dependencies:**
- Python standard library only (NFR4). The guard test targets Python 3.14
  (FR8).

### File Structure

```
em-workflow/
├── hooks/
│   └── bash_guard.py                       # _stage_walk_refuses continuation; docstrings (FR1-FR5)
└── references/
    └── command-execution-protocol.md       # Verbatim execution rule path item (FR5)
tests/
└── test_bash_guard_cd_prefix.py            # recorder-based tests and guard test (FR7, FR8)
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/is-below-stalled-walk-proc-read/**`
- `test-docs/is-below-stalled-walk-proc-read/**`

`feature-docs/is-below-stalled-walk-proc-read/**` covers `REQUIREMENTS.md`,
`SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/is-below-stalled-walk-proc-read/**` covers
`test-docs/is-below-stalled-walk-proc-read/{T}.tests.yaml`, the per-task test
record. It is generated and owned by `implement-phase.md`; this section cites
it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/is-below-stalled-walk-proc-read/` directory at all; the declared
`test-docs/is-below-stalled-walk-proc-read/**` entry is still correct in that
case — a declared path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS1 (AC1; FR1, FR2, FR7, NFR2): For each of FR7 (a) relative
  `proc/missing/...`, (b) relative `x/missing/...`, (c) absolute
  `<area>/task/missing/...`, (d) a regular-file stage, and (e) the
  `/dev/fd/<n>` variant: build the link, call `is_below` inside
  `_recorded_probes`, and assert `False`, no recorded path under `/proc` or
  `/dev/fd` per `_is_proc_or_dev_fd_location`, and the link present in reads.
  Run (e) only when `/dev/fd` is a directory (`needs_dev_fd`). Run the `/proc`
  cases under `needs_proc`.
- [ ] TS2 (AC1, red check; FR1, FR2, FR7, NFR2): Before the change, the same
  forms record a probe or read under `/proc`. Confirm this when the test is
  written.
- [ ] TS3 (AC2; FR1, FR2, FR7, NFR1, NFR2): The A1 corner form. With the cwd
  set to `procdep/work`, assert at module level that `is_below` is `False`
  with nothing recorded under `/proc`. Through the hook with
  `process_cwd=work`, assert silent. Additionally, with
  `resolves_to_directory` mocked to `True`, assert that the logical-path walk
  alone refuses.
- [ ] TS4 (AC3; FR8): Guard test. Call `os.path.realpath` directly on a
  stalled form inside `_recorded_probes` and assert a probe or read under
  `/proc` is recorded.
- [ ] TS5 (AC4; FR3, NFR1, NFR3): The existing tests listed in AC4 pass
  unchanged.
- [ ] TS6 (AC5; FR4): A chain that follows more than 40 links after the stall
  gives `False`. Mock `os.lstat` or `os.readlink` to raise only for one stage
  in the continuation, and confirm that the error alone does not make the walk
  refuse.
- [ ] TS7 (AC6; FR5): Check the docstring and protocol text, and confirm that
  the existing wording tests pass.

Run:
- Targeted: `python3 -m unittest tests.test_bash_guard_cd_prefix`
- Full: `python3 -m unittest discover -s tests`

### Integration Tests
- Covered by TS3 (through the hook with `process_cwd=work`).

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] More than `FOLLOWED_LINK_LIMIT` links followed after a stall: refuse,
  `is_below` returns `False` (FR4, TS6).
- [ ] `lstat` / `readlink` failure during continuation: treated as an ordinary
  name, no refusal (FR4, TS6).
- [ ] Stall at a regular-file stage instead of an absent stage (FR7 (d), TS1).
- [ ] `/dev/fd/<n>` instead of `/proc` (FR7 (e), TS1).

### Performance Tests
Not applicable.

## Security Considerations

- **Input Validation:** During continuation, a stage under `/proc` or
  `/dev/fd`, or a followed link whose absolute target text is under them, is
  refused before it is probed (FR2). Nothing under `/proc` or `/dev/fd` is
  probed or read while a stalled path is judged (NFR2).
- **Authentication / Authorization / Data Protection / XSS / SQL Injection /
  CSRF:** Not applicable.

## Error Handling

### Error Codes

Not applicable. The walk's outcomes are refusal (`is_below` returns `False`)
or no refusal.

| Condition | Outcome |
|-----------|---------|
| Links followed exceed `FOLLOWED_LINK_LIMIT` (before or after a stall) | Refuse |
| `lstat` / `readlink` failure during continuation | Ordinary name, continue, no refusal |
| Error other than an absent or non-directory stage, before a stall | Refuse (existing rule) |

### Error Flow

```
Error during walk → before stall? → absent / non-directory stage → continue (FR1)
                                  → other error                  → refuse
                 → during continuation (lstat / readlink)        → ordinary name, no refusal
```

## Performance Optimization

Not applicable.

## Success Criteria

- [ ] AC1: For every form in FR7 (a) to (e), `is_below` returns `False`. In
  `_recorded_probes`, no probe and no read under `/proc` or `/dev/fd` is
  recorded, and the link itself is recorded in reads. This holds on both the
  physical-path side and the logical-path side. (FR1, FR2, FR7, NFR2)
- [ ] AC2: Take a form whose logical path goes through a stalling link that
  climbs to `/proc/self/cwd/<name>`, while its physical path is an existing
  directory below the area. Example: `<root>/hop/../<link name>`, where
  `<root>/<link name>` is the stalling link and `area/task0001/<link name>` is
  a directory. The fixture first confirms that the old rule (the lenient
  realpath) would have judged this form `True`. Then, with the hook process's
  cwd inside the area, `is_below` returns `False`, the hook stays silent, and
  nothing under `/proc` or `/dev/fd` is probed or read during the judgment.
  (FR1, FR2, FR7, NFR1, NFR2)
- [ ] AC3: The guard test shows that `_recorded_probes` captures a probe or
  link read under `/proc` made inside a direct `os.path.realpath` call. (FR8)
- [ ] AC4: Forms whose stalled continuation never reaches `/proc` or
  `/dev/fd` keep their existing judgment. These include the line-1572 test
  (`True` with `resolves_to_directory` mocked), the absent and regular-file
  `..` forms of cd-prefix-non-directory-dotdot (`False`), the physical-path
  fallback forms of is-below-physical-fallback (allow), and
  `TestRelativeLinkTarget` (relative targets `proc`, `./proc` and `dev/fd`
  stay `True`; the climbing link stays `False`). (FR3, NFR1, NFR3)
- [ ] AC5: If links followed after the stall push the total past
  `FOLLOWED_LINK_LIMIT`, the result is `False`. If an `lstat` or `readlink`
  error occurs during continuation, the walk does not refuse because of that
  error. (FR4)
- [ ] AC6: The `_stage_walk_refuses` docstring no longer contains
  'ends the walk without refusal'. The four places in FR5 state the
  continuation rule. The module docstring path item and the protocol path item
  use identical wording for it. The existing wording tests
  (`TestPathConditionWording`, `TestProcessDependentPathWording`,
  `TestLinkTargetWording`) pass. (FR5)
- [ ] AC7: `python3 -m unittest discover -s tests` passes in full. No existing
  assertion is removed or weakened. The test module imports the standard
  library only. While the added forms are judged, the path check starts no
  child process. `is_below` gains no pre-check that calls
  `resolves_to_directory` before realpath. (FR6, NFR3, NFR4)

## Assumptions

- **A1:** The `True` to `False` change in the logical-path corner (the stalled
  walk's lexical continuation reaches a `/proc` or `/dev/fd` stage) is an
  accepted exception to the task's acceptance criterion "`is_below`'s judgment
  does not change". Answer to requirement.logical-side-stalled-walk:
  `refuse_on_proc_stage`, decided in batch Codex consultation.
- **A2:** Refusing every stopped walk would break the existing test at
  `tests/test_bash_guard_cd_prefix.py:1572`, which pins that a stopped walk is
  not a refusal. So the walk refuses only when the continuation reaches a
  `/proc` or `/dev/fd` stage.
- **A3:** Links followed after the stall also count toward
  `FOLLOWED_LINK_LIMIT`, and exceeding it refuses. Without the bound, the walk
  could not guarantee that realpath never reaches `/proc` at the end of a long
  chain. This is a `True` to `False` change outside the A1 corner. It happens
  only when more than 40 links are followed after a stall.
- **A4:** An `lstat` or `readlink` error during continuation is treated the way
  non-strict realpath (Python 3.14) treats it: as an ordinary name, with no
  refusal. When realpath cannot read a link, it cannot follow that link into
  `/proc` either, so mirroring realpath here keeps the no-read guarantee and
  keeps the judgment unchanged.
- **A5:** The same continuation rule also applies to the physical-path walk.
  When the physical-path walk stalls, the kernel resolution
  (`resolves_to_directory`) also fails, so `is_below` was already `False` and
  its judgment does not change. The purpose is to stop the `/proc` read in
  `os.path.realpath(path)`.
- **A6:** The physical-side pre-check suggested by the task (call
  `resolves_to_directory(path)` before realpath) is not adopted. (1) The
  continued walk runs before both realpath calls. It follows the same lenient
  rule as realpath (absent and regular-file stages treated as ordinary names,
  lexical `..`, link following). When the walk does not refuse, realpath
  cannot reach a `/proc` or `/dev/fd` stage, so the walk alone covers both
  sides. (2) The pre-check covers only the physical-path side. The
  logical-path side, `realpath(normpath(path))`, would still need the walk.
  (3) Keeping a single mechanism keeps the rule statement and the tests on one
  place. The order of `is_below` stays as it is (FR6).
- **A7:** The em-workflow version is not changed. GitHub Actions bumps the
  patch number on push to main.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None.

## Implementation Phases (if applicable)

Not applicable. The design step is skipped.

## References

- `feature-docs/is-below-stalled-walk-proc-read/REQUIREMENTS.md`
- `em-workflow/hooks/bash_guard.py`
- `em-workflow/references/command-execution-protocol.md`
- `tests/test_bash_guard_cd_prefix.py`
