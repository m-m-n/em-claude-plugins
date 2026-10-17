# Implementation Plan: codex-guard-anon-fn-pipe

## Overview

Pin, with three regression entries in the shared CASES table of
`tests/test_codex_hook_interactive_guard.py`, that a pipe or a stdin redirect
in the head of a zsh anonymous function `function () { ...; }` connects its
body in both copies of `codex-hook-interactive-guard.py`. The hook copies
change only if one of the new entries fails on the current code (FR5).

## Technology Stack

- **Language / Framework**: Python 3, standard library only; tests run with
  unittest (NFR3).
- **New dependencies**: none. No license to record (`project.license: none`).

## Layer Structure

| Layer | Location | Responsibility |
|---|---|---|
| Guard | `em-workflow/scripts/codex-hook-interactive-guard.py`, `em-review/scripts/codex-hook-interactive-guard.py` | Read one PreToolUse payload on standard input; print one deny object or nothing; exit 0. The two files are byte-identical copies. |
| Contract tests | `tests/test_codex_hook_interactive_guard.py` | Run every CASES entry against both copies as separate processes. The hook module is never imported. |

Dependency direction: contract tests -> guard, across a process boundary only.

## Shared Components

The feature has one task, so nothing is handed between tasks. The rows below
are the feature-wide contracts that task keeps.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| CASES table | One table that drives both hook copies | Each entry is (expected, label, command); expected is `deny` or `silent`; the label is Japanese; no two entries share a command. Post: for `silent`, each copy exits 0 with empty standard output and standard error; for `deny`, each copy exits 0 with empty standard error and one object on standard output whose permissionDecision is `deny` | task0001 |
| Hook copies | Judge one Bash command string | Pre: one PreToolUse JSON object on standard input. Post: nothing, or one deny object, on standard output; exit 0; the two copies are byte-identical | task0001 |

## Conventions

- Both hook copies change together in the same commit and stay
  byte-identical (NFR1; `.claude/rules/hook-tests.md`).
- Existing CASES entries are neither removed nor modified; new entries are
  only added (NFR2).
- CASES labels are written in Japanese, like the existing entries.
- No plugin version field is touched (NFR4;
  `.claude/rules/core-plugin-version-bump.md`).

## Cross-task Design Decisions

### D1: Regression pin first; a hook change is conditional

- **Decision**: The deliverable is the three CASES entries. The current
  parser already hands the head's pending pipe, and a stdin redirect read in
  the head, to the brace body that follows the empty `()` of an anonymous
  function (SPEC A1; the planner's reading of the current source agrees), so
  no hook change is planned. The hook copies change only when one of the new
  entries fails on the unmodified code.
- **Rationale**: FR5.
- **Affected tasks**: task0001.

### D2: The hook copies are in the task's file set

- **Decision**: task0001 lists both hook copies among its files even though
  no change to them is planned.
- **Rationale**: The declared change set is derived from the task files
  (`references/phases/create-plan-phase.md` section 12); listing the copies
  keeps an FR5 fix inside it.
- **Affected tasks**: task0001.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The source literal of a new entry yields a different command string from the one FR4 gives (for example a real newline in place of the backslash and n inside the printf argument) | Medium | Medium: the entry pins a different input from the reported one | task0001 AC-1 states the exact command string the hook receives; SPEC "File Structure" gives the source literal form |
| A parser change made under FR5 carries the connection beyond the anonymous body | Low | Medium: a launch that opens a REPL passes the guard | THREAT-MODEL.md TM-1 |

## Open Questions

- None.
