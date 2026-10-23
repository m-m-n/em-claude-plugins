# Implementation Plan: codex-guard-delim-subst-undecidable

## Overview
Fix the fail-open regression in the guard's shared substitution skip so that a
heredoc delimiter `${ ... }` containing a `$( ... )` with a same-line `<<`, a
command-position arithmetic `((`, or a parenthesis inside an argument word is
read to the same end zsh uses, and a following `python3 -i` is denied again.
The feature is one task (task0001).

## Technology Stack
- **Language**: Python 3 (standard library only), the existing hook script.
- **Test framework**: the standard library unit-test runner, through the existing table-driven module `tests/test_codex_hook_interactive_guard.py`.
- **New dependencies**: none. `project.license` is `none`, so there is no license constraint to check.

## Layer Structure
Not applicable: the change stays inside one existing method family of one
script (the shared substitution skip and helpers reachable from it). No layer
is added and no dependency direction changes.

## Shared Components
No component is shared between tasks: the feature is a single task. The
invariants below bind that task and any rework task later added to this
feature.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Shared substitution skip (`_skip_substitution`) | Skip one `$( ... )` from just after its opener to just after its closing `)`, or report undecidable | Pre: called only from the shared quoted-unit reader (`_read_quoted_unit`), positioned just after the opener. Post: either the position just after the matching `)` at the same place zsh closes it, or undecidable; never recurses; work stays linear in input length (NFR1, NFR2) | task0001 |

## Conventions
- **Two copies, one change**: `em-workflow/scripts/codex-hook-interactive-guard.py` and `em-review/scripts/codex-hook-interactive-guard.py` are edited in the same change and stay byte-identical (FR4). Every task on this feature edits both or neither.
- **Test table**: new cases go into `CASES` as (expected verdict, label, command), with the verdict `deny` or `silent`; the table runs against both copies. Existing rows are never removed and their verdicts never changed (FR5, NFR3).
- **Undecidable stays silent**: an undecidable reading produces no output, as today. No form that is decided today becomes undecidable (NFR3).
- **Call structure**: only the shared quoted-unit reader calls the shared substitution skip; no method reachable from the skip calls the skip itself, the quoted-unit reader, the top-level parse, or the range-quote remover (NFR2).
- **Plugin version**: no task touches either plugin's `plugin.json` or the root marketplace file (NFR4).

## Cross-task Design Decisions

### Single task
All six functional requirements change the same method in two byte-identical
files plus one shared test table. Splitting would make parallel tasks edit the
same method in the same files, and FR4 requires both copies to change
together, so the work is one task. Affected tasks: task0001.

### Reading model fixed by SPEC.md
The three readings are already decided in SPEC.md (Assumptions A4, A5, A6,
backed by the zsh 5.9 measurements): same-line `<<` in a substitution
(shared_same_line), command-position `((` as arithmetic with a subshell
fallback (arith_or_subshell), and a word-parenthesis context for
non-command-position `(` (word_ctx_all_chars). Tasks implement these readings
and do not reopen them. Affected tasks: task0001.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A wider reading turns a form that is decided today into undecidable, or changes its verdict | Medium | High (fail-open or false deny) | Existing CASES rows kept unchanged and run against both copies; regression rows TS10, TS11, TS14, TS15 (THREAT-MODEL.md TM-1) |
| The `((` fallback re-read makes the parser super-linear | Low | High (hook timeout, no decision) | One re-read per `((`, a total re-read cap with undecidable beyond it, explicit stack (THREAT-MODEL.md TM-2) |
| The two copies drift | Low | High (one plugin keeps the regression) | Byte-identity check in verification (TS18) |
| The TS13 expectation (line-split glob qualifier in a delimiter) disagrees with zsh | Medium | Low | Confirm with zsh 5.9 during implementation; otherwise use the same-line `*(#qN)` form SPEC.md names |

## Open Questions
- [ ] TS13's expected verdict is confirmed by a zsh 5.9 measurement during implementation (SPEC.md TS13; REQUIREMENTS.md 14.2).
