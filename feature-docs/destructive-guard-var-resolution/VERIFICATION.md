# Verification Document: destructive-guard-var-resolution

## Overview

**Feature**: destructive-guard-var-resolution /
**SPEC.md**: `feature-docs/destructive-guard-var-resolution/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/destructive-guard-var-resolution/IMPLEMENTATION.md`

This document covers the INTEGRATED verification run after every task is
merged — the two first-pass tasks and the rework task added after review round
1. Per-task acceptance criteria live in the task plans.

## Build Verification

- Command: none. Both components in workflow.yaml declare an empty
  `build_command` — the hook is an interpreted script and the manifests are
  data files.
- Expected: not applicable; the suites below execute the hook directly.

## Test Verification

- Command (hooks component):
  `python3 em-workflow/hooks/tests/run-destructive-guard.py`
- Command (main component): `python3 -m unittest discover -s tests`
- Expected: both exit 0, with no failing case reported by either.
- Coverage target: none configured for this repository. Coverage is expressed
  as scenario coverage of the table below and as retention of every
  pre-existing expectation entry (58 at the base revision).

### Test Scenarios from SPEC.md

Each scenario's verdict is checked by an expectation entry in
`em-workflow/hooks/tests/destructive-guard-cases.json`, executed by the hooks
component command. Where a scenario also asserts a rule identifier or reason
content, the runner cannot see it (its entries carry the expected verdict
only), so that half is a manual check — see IMPLEMENTATION.md D3 and the
manual section below.

TS-1 through TS-11 come from SPEC.md's own scenario list. TS-13 onward were
added by the rework round that followed review round 1: each states a property
the round-1 findings showed the merged implementation does not hold, and each
is exercised the same way — an expectation entry in
`em-workflow/hooks/tests/destructive-guard-cases.json`, plus the manual half
where the row asserts a rule identifier or reason text.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Standalone literal assignment of a scratch-area path, then a recursive delete through that variable at the same nesting level | allow | Unit |
| TS-2 | Same shape aimed at a path outside the scratch area | deny, rule `rm-recursive`, reason carries the replacement-command suggestion built from the resolved path | Unit (verdict) + Manual (rule, reason) |
| TS-3 | The same name assigned twice, then a recursive delete through it | ask, rule `rm-unresolvable`, reason states that splitting the values across separate variables makes it resolvable | Unit (verdict) + Manual (rule, reason) |
| TS-4 | Assignment separated from its use by a shell `-c` payload, and separately by a subshell | ask, rule `rm-unresolvable` | Unit |
| TS-5 | Command-prefix assignment on the delete command itself | ask, rule `rm-unresolvable` | Unit |
| TS-6 | Resolved value still containing a glob metacharacter | ask, rule `rm-unresolvable` | Unit |
| TS-7 | Resolved value still containing a command substitution | ask, rule `rm-unresolvable` | Unit |
| TS-8 | Resolved value that is the bare home shorthand, and one that is the filesystem root | deny, rule `rm-root` | Unit |
| TS-9 | Resolved value reaching a write target under Claude Code's own configuration | ask, rule `self-modification` | Unit |
| TS-10 | Resolved value reaching a session transcript write target | deny, rule `transcript-write` | Unit |
| TS-11 | The full pre-existing expectation set, plus the trailing unattended-demotion check the runner performs after the table | every recorded verdict unchanged; runner exits 0 | Integration |
| TS-13 | An assignment that the shell does not execute before the use site: the assignment written after the delete, an assignment reached only through a short-circuit that does not run, and an assignment terminated so it runs in the background | the reference stays unresolved and the command keeps the verdict it had before any resolution existed — the home-directory form stays a `rm-root` deny, the unknown-target form stays an `rm-unresolvable` ask | Unit (verdict) + Manual (rule) |
| TS-14 | The same name bound a second time through a form other than a bare assignment statement — the export / declare / typeset / local / readonly assignment forms, the append form, `read`, and `printf -v` | the name is excluded from resolution exactly as a twice-written bare assignment is; the delete through it is an `rm-unresolvable` ask | Unit (verdict) + Manual (rule) |
| TS-15 | An assignment whose right-hand side contains a command substitution, in either spelling | the value is never collected as a literal: the scratch-directory idiom that captures a command substitution and then deletes through the variable is an `rm-unresolvable` ask — neither an allow nor a deny, and no replacement-command suggestion is emitted for it | Unit (verdict) + Manual (rule, reason) |
| TS-16 | An assignment inside one pipeline element used from outside that pipeline, taken in both directions — assignment in the pipeline's FIRST element, and assignment in a later element — and an assignment in a statement terminated as a background job | the use site outside the pipeline or background job stays unresolved, keeping its pre-resolution verdict | Unit |
| TS-17 | Subshell group boundaries under two spellings that must not change the answer: the group's closing parenthesis written adjacent to a redirection operator, and the group's statements separated by `;` versus by a newline | a use inside the group resolves the group's own assignment identically under both spellings; a use outside the group stays unresolved under both spellings, and no statement after the group inherits the group's identity | Unit |
| TS-18 | A resolved value that contains whitespace, so the real command names more than one target — the first word inside the scratch area, a later word outside it | never allowed on the strength of the first word: either the reference stays unresolved (`rm-unresolvable` ask) or every word is judged as an independent target and the outside word produces its own deny | Unit (verdict) + Manual (rule) |
| TS-19 | A resolved target that begins inside a scratch root and then climbs out of it with parent-reference segments, and a target whose leading path component merely starts with a scratch-area name as a string prefix | judged on the path the shell would actually act on, at path-component boundaries: neither is treated as inside the scratch area, and the denial reason's replacement-command suggestion names that same path | Unit (verdict) + Manual (reason) |
| TS-20 | A reference that substitutes to an empty or whitespace-only value | not treated as resolved: the pre-resolution `rm-unresolvable` ask stands, and no denial reason is emitted whose replacement-command suggestion names the current working directory | Unit (verdict) + Manual (reason) |
| TS-21 | A recursive-delete flag supplied through a variable rather than written literally | the delete is recognised as recursive and the target is judged by the recursive-delete path, matching the verdict of the same command with the flag written literally | Unit |

### Additional verification scenarios (verification-plan additions)

Not present in SPEC.md's scenario list. Added here so the requirements they
cover have a named, automated check rather than an empty mapping.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-12 | The repository suite's plugin version-parity module reads both registries | the two version values agree and compare past the module's recorded baseline; the suite exits 0 | Integration |

## Code Quality Verification

- Format: none configured (`format_command` is empty for both components).
- Static analysis: none configured. Two properties are instead checked by
  reading the diff, in the manual section below: the hook's import list stays
  within the standard library, and the resolution path performs no filesystem,
  subprocess or shell operation.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | The reported false positive is allowed | TS-1 |
| AC-2 | The same shape outside the scratch area is denied with rule `rm-recursive` and the replacement-command suggestion for the resolved path | TS-2 (verdict) plus the manual rule/reason check |
| AC-3 | A resolved value reaching root or home is denied with rule `rm-root` | TS-8 (verdict) plus the manual rule check |
| AC-4 | A resolved write target under Claude Code's config asks; one naming a transcript denies | TS-9, TS-10 (verdicts) plus the manual rule check |
| AC-5 | Every unresolvable form keeps its pre-change verdict, and the reassignment reason carries the split hint | TS-3, TS-4, TS-5, TS-6, TS-7 plus the manual reason check |
| AC-6 | The hook expectation suite passes with every pre-existing deny/ask entry still present | TS-11 plus the additions-only diff check |
| AC-7 | Both manifests read 0.1.57 | TS-12 plus the manual manifest read |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0003 | TS-1, TS-13, TS-14, TS-15 |
| FR2 | task0001, task0003 | TS-1, TS-2, TS-6, TS-7, TS-8, TS-15, TS-18, TS-20, TS-21 |
| FR3 | task0001, task0003 | TS-1, TS-2, TS-8, TS-9, TS-10, TS-18, TS-19, TS-21 |
| FR4 | task0001, task0003 | TS-2, TS-19, TS-20, plus the manual reason check confirming the suggestion is built from the resolved path |
| FR5 | task0001, task0003 | TS-5, TS-14 |
| FR6 | task0001, task0003 | TS-3, TS-14, plus the manual reason check for the split hint |
| FR7 | task0001, task0003 | TS-4, TS-13, TS-16, TS-17 |
| FR8 | task0001, task0003 | TS-11, plus the additions-only diff check |
| FR9 | task0002 | TS-12, plus the manual manifest read |
| NFR1 | task0001, task0003 | TS-11 (the suite runs the hook hermetically and repeatably), plus the diff inspection for filesystem/subprocess/shell operations |
| NFR2 | task0001, task0003 | TS-3, TS-4, TS-5, TS-6, TS-7, TS-11, and TS-13 through TS-21 — every shape the resolver cannot settle keeps its pre-resolution verdict |
| NFR3 | task0001, task0003 | TS-11, run twice with identical output |
| NFR4 | task0001, task0003 | No automated scenario — SPEC.md states this is met structurally; checked by the cost-shape inspection in the manual section |
| NFR5 | task0001, task0003 | TS-11 (both suites run under a plain interpreter with no package installation, so a non-standard-library import would fail the run), plus the import-list inspection |
| NFR6 | task0001, task0003 | TS-11, plus the diff inspection confirming the four pattern definitions are unchanged |

## E2E Testing

No E2E framework exists in this repository and none is introduced by this
feature (`e2e_test_command` is empty for both components). No E2E scenario
applies.

## Manual Testing (E2E Not Possible)

- [ ] Rule identifier and reason content: invoke the hook directly with a tool
      payload for the TS-2, TS-3, TS-8, TS-9 and TS-10 command strings and read
      the emitted reason. Confirm the bracketed rule identifier is
      `rm-recursive`, `rm-unresolvable`, `rm-root`, `self-modification` and
      `transcript-write` respectively; confirm TS-2's reason carries the
      replacement-command suggestion for the RESOLVED path (not the variable
      reference), and TS-3's reason carries the split-the-variables hint.
      (AC-2, AC-3, AC-4, AC-5, FR4, FR6)
- [ ] Expectation-list diff is additions only: every pre-existing entry (58 at
      the base revision) is present and byte-identical, with no deletion,
      edit or expectation change. (AC-6, FR8)
- [ ] Red-run evidence: the implement-phase test record for task0001 shows the
      suite failing on the newly added entries before the resolution stage was
      implemented, with those entries as the only failures. (FR8)
- [ ] Static-only inspection: the hook diff introduces no filesystem access,
      path realization, subprocess or shell invocation on the resolution path,
      and no import outside the standard library modules already used. (NFR1,
      NFR5)
- [ ] Cost-shape inspection: collection is a single pass over the statements
      the hook already produces; nothing re-lexes the command string per target
      and no new expansion loop is added. (NFR4)
- [ ] Untouched-pattern inspection: the scratch-area allowance, the
      Claude-Code-config pattern, the session-transcript pattern and the
      dynamic-construct pattern are unchanged, and no new rule identifier
      exists. (NFR6)
- [ ] Determinism: run the hook expectation suite twice and confirm identical
      output. (NFR3)
- [ ] Manifest read: parse both registries, confirm the two version values are
      identical and read 0.1.57, and confirm no other plugin's version key was
      added or changed. (AC-7, FR9)
- [ ] Rework round 1 rule/reason checks: invoke the hook directly with a tool
      payload for the TS-13, TS-14, TS-15, TS-18, TS-19 and TS-20 command
      strings and read the emitted reason. Confirm the bracketed rule
      identifier is the one the row states, that TS-15 and TS-20 emit no
      replacement-command suggestion at all, and that TS-19's suggestion names
      the path the command would really act on rather than the text as
      written. (TS-13, TS-14, TS-15, TS-18, TS-19, TS-20)
- [ ] Pre-resolution parity check for the rework scenarios: for every command
      string added by TS-13 through TS-21, confirm the verdict is no weaker
      than the verdict the same command string receives from the hook as it
      stood at `workflow.implement.base_commit` — resolution may turn an ask
      into a deny or leave it, never into an allow. (NFR2)
- [ ] Optional, environment-dependent: after the installed plugin cache has
      picked up the new version, run the hook expectation suite against the
      installed copy by passing its path to the runner. Requires a Claude Code
      restart first.

## Performance / Security Verification

- NFR4 (bounded cost): no threshold is specified; met structurally and checked
  by the cost-shape inspection above.
- Fail-closed (NFR2): every shape the resolver cannot settle keeps its
  pre-change verdict — covered by TS-3 through TS-7 and by the retained
  expectation set.
- Detection preservation: the asymmetric-cost property of this hook means a new
  false positive ends an unattended run on the spot, and a missed real target
  is unrecoverable. Both directions are held by the same retained expectation
  set (TS-11): the allow entries guard the false-positive cost, the deny/ask
  entries guard detection.
- Static-only analysis (NFR1): the judgment path executes nothing and touches
  no filesystem object belonging to the inspected command.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 21 | 21 | 0 | 9 also carry a manual rule/reason half (TS-2, TS-3, TS-12, TS-13, TS-14, TS-15, TS-18, TS-19, TS-20) |
| Success criteria | 7 | 7 | 0 | 5 also carry a manual half (AC-2, AC-3, AC-4, AC-5, AC-7) |
| Requirements | 15 | 14 | 0 | NFR4 is manual only; 7 others also carry a manual check |
| Manual checks | 11 | — | — | 11 (1 optional, environment-dependent) |
