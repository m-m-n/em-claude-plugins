# Implementation Plan: codex-guard-anon-arg-backquote-comment

## Overview
Restore the deny of an anonymous function body's explicit `python3 -i` when
the function's argument range returns to group reading through a backquote
and holds a `#` after whitespace, by giving such groups the single comment
exception of SPEC FR2 to FR4. The feature is one task (task0001); this
document records only the feature-wide conventions and decisions.

## Technology Stack
- **Language**: Python 3, standard library only (NFR2)
- **Tests**: unittest; the table-driven CASES in `tests/test_codex_hook_interactive_guard.py`, run against both copies
- **New dependencies**: none — no license to record (`project.license` is `none`)

## Layer Structure
One module, shipped as two byte-identical copies:
`em-workflow/scripts/codex-hook-interactive-guard.py` and
`em-review/scripts/codex-hook-interactive-guard.py`. Inside it the flow is
unchanged: hook input → command parser (group stack, comment reading,
separator reading) → rescue and connection rules → decision output. This
feature changes only the parser's per-group state, its comment reading and
its separator reading. No new dependency direction is introduced.

## Shared Components
| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| none | The feature has one task; no component is built by one task and consumed by another | — | — |

## Conventions
- **Byte-identical copies (FR6)**: every edit lands in both copies in the same change; `TestCopies.test_the_two_copies_are_byte_identical` is the arbiter.
- **Constraints (NFR1, NFR2)**: standard library only; no file, network or child-process access; the decision depends only on the command string; parsing stays linear in the command length; no recursion.
- **CASES format**: rows are (expected decision, label, command) with expected decision `deny` or `silent`; the same table runs against both copies; existing rows keep their expected decision and are never removed (FR7, NFR3).
- **Hook-test rule**: a change to either copy runs `python3 -m unittest tests.test_codex_hook_interactive_guard` in the same change.
- **Commands under test are input only**: they are fed to the hook as `tool_input.command`, never executed.

## Cross-task Design Decisions

### D1: Single task
- **Decision**: one task covers both copies, the CASES rows and the docstring markers.
- **Rationale**: FR6 requires both copies to change in the same change and stay byte-identical; the new CASES rows fail until the parser change lands, so a test-only task could not reach "tests pass = task done" in its own worktree; the three files are one coherent unit within one implementer session.
- **Affected tasks**: task0001.

### D2: Regression rows versus edge-case checks
- **Decision**: CASES gains exactly the four rows FR7 names. The SPEC Edge Cases not already covered by an existing row are checked by direct hook invocation (task0001 AC-3 and AC-4, VERIFICATION.md TS-9 to TS-13), not added as rows.
- **Rationale**: FR7 enumerates the rows to add.
- **Affected tasks**: task0001; VERIFICATION.md.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The exception reads `#` as a word character where it must stay a comment, turning a deny into no output | Medium | High | Exception set only by the FR2 condition, inherited only at open, cleared by FR4's direct separators; FR5 readings untouched; SPEC TS4 row and every existing row (THREAT-MODEL.md TM-2) |
| The new state adds per-character cost or recursion on deep nesting | Low | High | State fixed at group open, innermost-only checks; existing performance and recursion-check tests (TM-3) |
| The two copies drift | Low | High | Byte-identity test |
| The new docstring text contradicts the kept marker sentence "a backquote and a comment get no special reading" | Medium | Low | The exception is stated next to the kept sentence |
| SPEC A4 (zsh reading of whitespace and `#` inside a mid-word parenthesis range) is unverified | Low | Medium | Accepted by SPEC as an assumption; out of scope |

## Open Questions
- [ ] SPEC A4 is not verified against zsh (REQUIREMENTS.md 14.2); the plan follows SPEC in treating it as an assumption.
