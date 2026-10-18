# Implementation Plan: codex-guard-anon-arg-escaped-backquote

## Overview
The guard's search for the closing backquote of an unquoted backquote span
skips backslash pairs, in both byte-identical copies of the guard, and the
reproduction command is pinned as a deny row. One task carries the whole
change.

## Technology Stack
- **Language**: Python 3, standard library only (NFR2).
- **Tests**: the standard-library unit test runner already used under `tests/`.
- **New dependencies**: none, so there is no new license to record
  (`project.license: none`).

## Layer Structure
One layer: the guard script (its parse routine and helpers), shipped as two
byte-identical copies, one per plugin
(`em-workflow/scripts/codex-hook-interactive-guard.py`,
`em-review/scripts/codex-hook-interactive-guard.py`). The guard test module
runs the same case table against both copies. No dependency direction
changes.

## Shared Components
None. The feature has a single task, so no component built by one task is
used by another.

## Conventions
- **Two copies, one change**: every edit to either copy is applied to both in
  the same commit, and the copies stay byte-identical (FR2; enforced by the
  copy-identity test).
- **Decision vocabulary unchanged**: the guard either denies or stays silent;
  an undecidable parse stays fail-open (silent), as today.
- **One backslash-pair rule**: the closing search follows the pair rule that
  the `b` context of `_skip_substitution` already applies. It does not define
  a second, different rule.
- **Cases are only added**: no existing row of the case table or other
  existing test is edited or removed (NFR3).

## Cross-task Design Decisions

### D1: Single task
- **Decision**: one task owns both copies and the new case row.
- **Rationale**: FR2 requires the two copies to change together and stay
  byte-identical, and the copy-identity test fails on any branch that changes
  only one copy. The new deny row passes only once the fix exists. Split
  tasks would produce branches that cannot pass their own tests on their own.
- **Affected tasks**: task0001.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A span now ends at a later backquote, which changes the decision of an existing row (an escaped backquote that used to close a span no longer does) | Low | Medium: a deny row that turns silent reopens a fail-open path | The full existing suite must pass unchanged (NFR3) |
| The two copies drift apart | Low | Medium: one plugin keeps the evasion (TM-1) | Copy-identity test (FR2) |
| The new search becomes super-linear on long backslash runs | Low | Medium: the guard times out (TM-2) | One forward pass with no recursion; deep-input tests (NFR1) |

## Open Questions
- [ ] Out of this feature's scope: the SPEC fixes only where the span ends,
  not how the text inside a span is inspected. So whether an explicit
  `python3 -i` inside a nested, backslash-escaped substitution is denied
  does not change here. The review phase judges whether this needs a
  follow-up.
