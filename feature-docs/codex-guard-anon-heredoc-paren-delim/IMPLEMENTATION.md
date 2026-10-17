# Implementation Plan: codex-guard-anon-heredoc-paren-delim

## Overview
codex-hook-interactive-guard derives a heredoc delimiter from a `(`...`)`
range in an anonymous-function argument position the way zsh does, in both
plugin copies, with regression cases. The feature is one task (task0001).

## Technology Stack
- **Language**: Python 3 - the guard script and its tests
- **Libraries**: standard library only (NFR3); the existing `unittest` test module
- **New dependencies**: none (no license to record; `project.license` is `none`)

## Layer Structure
- **Guard module**: one logical component shipped as two byte-identical
  files, `em-workflow/scripts/codex-hook-interactive-guard.py` and
  `em-review/scripts/codex-hook-interactive-guard.py`. It reads hook JSON on
  standard input, statically parses `tool_input.command`, and emits a deny or
  nothing.
- **Test module**: `tests/test_codex_hook_interactive_guard.py` runs one
  `CASES` table against both copies and holds the structural checks (CASES
  duplicates, byte identity, docstring markers, deep-input timing, recursion
  AST check, standard-library / side-effect constraint).
- **Dependency direction**: tests drive the guard copies; the guard depends
  on nothing project-internal.

## Shared Components
None. The feature has a single task, so no component is consumed across
tasks. The two guard copies are one component edited by the same task.

## Conventions
- The two copies change together, in the same commit, and stay
  byte-identical (FR5).
- `CASES` entries are `(expected verdict, label, command)` with verdict
  `deny` or `silent`; the same table runs on both copies; no existing entry is
  removed or has its verdict changed (`.claude/rules/hook-tests.md`).
- The guard's existing unknowable outcome (no output) is the only channel for
  an input the guard cannot read (NFR4); no new output form is added.
- No recursion or call cycles (NFR2); standard library only, no file,
  network or child-process access (NFR3).
- The module docstring describes the decision procedure; behavior changes are
  written into it, and the sentences `TestGuardDocumentation` checks stay
  unchanged (FR6).

## Cross-task Design Decisions

### D1: One task
- **Decision**: the delimiter fix, the docstring update, both copies and the
  regression cases form one task.
- **Rationale**: FR5 requires both copies in the same change, and the `CASES`
  entries are the test-first contract for the same parser function; parallel
  tasks on that function would only conflict.
- **Affected tasks**: task0001

### D2: Planner-derived verification scenarios
- **Decision**: VERIFICATION.md adds TS-12 (FR3), TS-13 (FR2) and TS-14 to
  TS-19 (the existing-suite checks SPEC.md AC-9 / AC-10 name, one ID per
  requirement) to the SPEC.md scenarios TS-1 to TS-11.
- **Rationale**: TS-8 and TS-9 also pass under plain quote removal without
  the FR3 rule, and no SPEC.md scenario detects a second removal of the part
  outside the range (FR2). TS-14 to TS-19 give FR4-FR6 and NFR1-NFR4
  traceable test IDs.
- **Affected tasks**: task0001

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A misderived delimiter ends the heredoc body later than zsh, so a real launch is skipped as body (fail-open) | Medium | High | THREAT-MODEL.md TM-1; deny cases after the true terminator (TS-2, TS-4 to TS-7, TS-10, TS-11, TS-13) |
| The fix passes TS-8 / TS-9 through plain quote removal while the FR3 rule is missing | Medium | Medium | TS-12 |
| A test command is mis-escaped (an outer `$` makes the input dynamic), so a case is silent for the wrong reason | Medium | Medium | Unwrapped form for TS-8 to TS-13; expected pre-fix outcomes listed in the task plan |
| The two copies drift | Low | Medium | Byte-identity test (TS-15) |
| Super-linear cost on long or numerous ranges | Low | Medium | THREAT-MODEL.md TM-2; TS-17 |

## Open Questions
- None.
