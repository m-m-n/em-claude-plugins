# Implementation Plan: destructive-guard-heredoc-syntax-error

## Overview
Stop the destructive-guard lexer from registering a heredoc operator for a
`<<` / `<<-` written directly inside an array compound-assignment
parenthesis, so the lines bash executes after discarding that line are
classified as commands. The whole change is one task (task0001).

## Technology Stack
- **Language**: Python 3 (the existing hook).
- **New dependencies**: none, so no license entry is recorded
  (`project.license: none`).
- **Test instruments**: the case table
  `em-workflow/hooks/tests/destructive-guard-cases.json` run by
  `em-workflow/hooks/tests/run-destructive-guard.py`, and the unittest suite
  under `tests/`.

## Layer Structure
All layers live in `em-workflow/hooks/destructive-guard.py` and are
unchanged in shape by this feature (unified-lexer contract):

1. **Lexer** — lex_shell() with _lex_pass(): the only place that decides
   whether a `<<` / `<<-` is a heredoc operator and which lines are its body.
   Produces the map.
2. **Map consumers** — strip_heredocs(), scan_structure(), _TrackingLexer,
   tokens(): read the map; never classify heredoc operators themselves
   (NFR1).
3. **Verdict logic** — classifies the resulting command lines into allow /
   ask / deny.

Dependency direction: verdict logic → consumers → map. Nothing feeds back
into the lexer.

## Shared Components
This feature has a single task, so no component is built by one task and
used by another. The row below records the existing contract task0001
must keep intact, because the review and verify phases rely on it.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| lex_shell() map | Sole authority on heredoc operators and their bodies | Pre: a command string. Post: every `<<` / `<<-` is either registered with a body range or not registered; consumers read only this map. Work stays within LEX_WORK_FACTOR × length + floor; past that the hook returns the scan-budget ask. | task0001 |

## Conventions
- **Case-table format**: each case is a `[expected verdict, label, command]`
  triple in `em-workflow/hooks/tests/destructive-guard-cases.json`.
  Pre-existing entries are never removed or rewritten (FR6).
- **Verdict direction**: a change may only move a target form from allow to
  deny or ask; no pre-existing case may change its verdict (NFR3, FR6).
- **Test commands**: every change to the hook runs, in the same change,
  `python3 em-workflow/hooks/tests/run-destructive-guard.py` and
  `python3 -m unittest discover -s tests`, both from the repository root
  (NFR4).

## Cross-task Design Decisions

### D1: One task for the whole feature
FR1–FR4 change one state machine (_lex_pass()). Parallel tasks would edit
the same function, and a cases-only task could not pass its own runner
before the lexer change merged. The case-table additions (FR5) are the TDD
tests of the lexer change and belong to the same task. Affected: task0001.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A pre-existing allow case contains a direct-position `<<` inside an array and flips to deny, conflicting with FR6 | Low | Medium | task0001 runs the full table; a flip is reported as a plan deviation, never fixed by editing the existing case |
| Array-context detection is too narrow (misses `+=`, declaration builtins, or multi-line arrays) and the bypass stays open | Medium | High | Each form is a deny case (task0001 AC-2) |
| Array-context detection is too broad (an ancestor array suppresses registration inside a substitution) and legitimate heredocs become commands, halting batch runs | Medium | High | Direct-position rule; allow cases for substitution, closed-array and post-reset forms (task0001 AC-4, AC-5) |
| Cancelling same-line pending operators re-reads input and breaks the work bound | Low | Medium | Cancellation uses the existing pending-operator record inside the single pass (task0001 AC-7) |

## Open Questions
- None.
