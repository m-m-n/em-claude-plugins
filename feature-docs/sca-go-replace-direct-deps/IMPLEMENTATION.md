# Implementation Plan: sca-go-replace-direct-deps

## Overview

The Go SCA direct set computed from go.mod is extended so that a `replace`
directive applied to a non-indirect require adds its module replacement path.
The whole change is one task (task0001): the go.mod direct-set logic in
`em-workflow/scripts/scan-dependencies.py` and its regression tests under
`tests/`.

## Technology Stack

- **Language**: Python 3 (existing script, existing test suite)
- **Test framework**: stdlib `unittest`, run by `python3 -m unittest discover -s tests`
- **Key libraries**: none added
- **New dependencies and licenses**: none. No new dependency is introduced, so
  there is no license to record. `project.license` is `none`.

## Layer Structure

Single layer: the Go normalization section of `scan-dependencies.py`. The
direct set is produced from the go.mod of one scan unit and consumed only by
the existing directness check of the same section. No other script, hook or
reference document depends on the direct set.

Allowed dependency direction is unchanged: the Go normalization section reads
go.mod only through the script's existing project-relative confinement and
reuses the script's existing go.mod tokenizer.

## Shared Components

None. This feature has a single task, so no component is shared across tasks.

## Conventions

- Error-handling policy (untrusted go.mod): content that does not fit the
  expected shape contributes nothing and is never an error. No new skip reason
  and no new summary note token is introduced (SPEC NFR3).
- Output policy: summary notes stay counts-only; no text taken from go.mod
  enters any output field (SPEC NFR3).
- Existing test modules under `tests/` are left byte-identical (SPEC NFR2).

## Cross-task Design Decisions

### Single-task decomposition

- **Decision**: one task owns the parser change, the docstring/comment update
  and the regression tests.
- **Rationale**: every requirement (FR1-FR6, NFR1-NFR3) lands in the same
  section of one script, and the tests are the TDD contract of that same
  change. Splitting would only create two tasks editing the same function.
- **Affected tasks**: task0001.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Exact-version matching of a versioned replace misjudges when the build selects a version other than the require version (SPEC A2 known limitation) | Low | Low (one advisory may be missed or extra) | Accepted as specified; behaviour is pinned by the TS5 cases |
| The new parsing changes the result of the existing replace cases in the prior feature's test module | Medium | Medium (NFR2 regression) | TS8 full-suite run; the existing module is not edited |
| A malformed replace line raises or marks go.mod unreadable, dropping the whole Go unit | Medium | High | THREAT-MODEL.md TM-1 |

## Open Questions

- None.
