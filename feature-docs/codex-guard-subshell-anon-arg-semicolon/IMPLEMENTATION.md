# Implementation Plan: codex-guard-subshell-anon-arg-semicolon

## Overview
Both byte-identical copies of codex-hook-interactive-guard learn to rescue a
chain of provisional groups at an unquoted `)` when the group just outside the
chain is a `(` group, so the subshell-wrapped reproduction is denied. The feature
is one task (task0001); this document holds only the rules that any task
touching this guard — task0001 and any later rework task — must share.

## Technology Stack
- **Language**: Python 3, standard library only (NFR3).
- **Tests**: the standard-library unit-test runner, driving
  `tests/test_codex_hook_interactive_guard.py`, which runs each copy as a
  separate process.
- **New dependencies**: none. No license check applies (`project.license: none`,
  and nothing is added).

## Layer Structure
The guard is one module with three stages, each consuming only the output of the
one before it:

1. **Parser** (`_Parser`, `_Group`, `_rescue_separator`): splits the command
   string into simple commands, each tagged with its innermost group, and settles
   every group's connection and skip in one pass after reading.
2. **Walk** (`_scan`): visits the simple commands, and the literal shell `-c`
   strings nested in them, with a work list.
3. **Judge** (`_judge` and the option readers): decides per simple command.

This feature changes stage 1 only. Stages 2 and 3, the hook's input/output
contract (one deny object on stdout, or nothing; exit status 0) and the deny
reason text are unchanged.

## Shared Components
No component is built by one task and consumed by another: the feature has a
single task. The existing parser contracts the change builds on, and which any
rework task must keep, are:

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| `_rescue_separator` | The one definition of the separator condition for rescuing a provisional group | Unchanged. Pre: a group's own first direct separator (or none) and the inherited one. Post: the rescuing separator (`;` or a lone `&`) or none. Applied by the end-of-input rescue, the `}` rescue and the new `)` rescue alike (FR3). | task0001 |
| Chain values on `_Group` (`provisional`, `first_sep`, `chain_base`, `outer_blocked`) | Fixed when a provisional group opens (`_mark_provisional`), from its parent alone | Unchanged. Readable in constant time at any `}` or `)`; never recomputed by walking the enclosing groups (NFR1). | task0001 |

## Conventions
- **Two copies**: `em-workflow/scripts/codex-hook-interactive-guard.py` and
  `em-review/scripts/codex-hook-interactive-guard.py` change in the same change
  and stay byte-identical (FR10, `.claude/rules/hook-tests.md`).
- **Case table**: rows in `CASES` are (expected verdict, label, command) with the
  expected verdict `deny` or `silent`; the one table runs against both copies;
  commands stay unique. A row that pins an accepted false deny says
  既知の誤拒否 in its label.
- **Fail-open**: an input the new reading does not cover keeps its present
  verdict, and anything the parser cannot settle still yields no output (NFR4).
- **Cost**: parsing stays linear in the length of the string, and no function
  calls itself or joins a call cycle (NFR1, NFR2).
- **Docstrings follow the parser**: the marker sentences the documentation tests
  check stay; the stale sentences those tests forbid are not written back (FR9).
- **Line numbers**: line numbers in SPEC.md and REQUIREMENTS.md refer to the base
  revision of `tests/test_codex_hook_interactive_guard.py` (and, for
  `_close_paren` 1071-1072, of the script). Once rows move, a row is identified by
  its label and command.
- **Plugin version**: version files are outside this feature's file set (A3).

## Cross-task Design Decisions

### D1: One task for the parser, its docstrings and its tests
- **Decision**: a single task changes both script copies and the test module.
- **Rationale**: the two copies must change together and stay byte-identical
  (FR10); one case table drives both; the tests are written first and must run
  against the changed parser in the same worktree; parallel tasks would all edit
  the same three files.
- **Affected tasks**: task0001.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The `)` reading changes the verdict of an existing row other than rows 661 and 672 | Low | Medium | The whole case table runs (TS-17); the condition requires a provisional innermost group, the shared separator condition and a `(` chain base (TM-3) |
| A check at `)` that walks the chain makes parsing quadratic | Medium | High | Constant-time check on values fixed at open; scale shapes TS-15 and TS-16 (TM-1) |
| A docstring edit drops a marker sentence or brings back a stale one | Medium | Low | The documentation tests run in the same suite (TS-18) |
| The two copies drift apart | Low | Medium | The byte-identity test (TS-19) |
| A `case` pattern's `)` inside a rescued chain triggers the rescue like any other unquoted `)`, e.g. `( function { :; } foo(a; case x in x) python3;; esac ) < /dev/null` turns from no output to deny | Low | Low | The present reader already reads such a `)` as a group close (no `case` grouping is read); the form needs `setopt nobadpattern`, an argument `(` holding a `;` and a `case` inside it. Not pinned by a row; see Open Questions |

## Open Questions
- [ ] SPEC.md AC5 lists the `}` rescue rows 641-676 except 672 as unchanged, but
      FR8 changes row 661, which lies in that range. The plan follows FR8 and
      treats row 661 as excluded from AC5 as well.
- [ ] The `case`-pattern form in Risk Assessment becomes a deny that zsh would
      not justify. It is left unpinned; whether to record it as a known false
      deny row is a review decision.
