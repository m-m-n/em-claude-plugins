# Implementation Plan: codex-guard-case-paren-rescue

## Overview

A narrow fix to codex-hook-interactive-guard (the em-workflow and em-review
copies): a case mark on provisional groups — the number of unfinished
`case`s, decremented by a bare `esac` at an FR1 position and inherited along
the provisional chain — refuses the paren rescue while it is 1 or more.
task0001 (merged) introduced the mark under the first SPEC; task0002 brings
the merged code into conformance with the revised SPEC, closing review round
1 findings 285d9bc33784bb3d, df4afa83e782d56a and b374e6b3c3d4b471.

## Technology Stack

- **Language**: Python 3, standard library only — the existing guard scripts
  and their unittest suite.
- **New dependencies**: none (`project.license` is `none`; no license record
  is needed).

## Layer Structure

| Layer | Files | Responsibility |
|-------|-------|----------------|
| Guard (two copies) | `em-workflow/scripts/codex-hook-interactive-guard.py`, `em-review/scripts/codex-hook-interactive-guard.py` | Read the proposed command text and decide deny or silent |
| Tests | `tests/test_codex_hook_interactive_guard.py` | Run the CASES table, the byte-identity check, the docstring-marker checks and the depth / linearity checks against both copies |

Allowed dependency direction: tests load both guard copies; the two copies
never depend on each other.

## Shared Components

The two tasks never build against each other in parallel: task0001 is
merged, and task0002 changes that merged code in place. What both tasks
touch is the pair of per-group values and the paren-rescue exception built
on them; their contract under the revised SPEC is pinned here.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Case mark (`_Group.case_mark`) | Number of `case`s counted on a provisional group that no `esac` has closed yet | Pre: changes only while its group is the innermost open group and is provisional. Post: never negative; +1 per bare command-position `case`; −1 per bare `esac` at an FR1 position while it is 1 or more (FR1); field name unchanged (A8) | task0001 (introduced), task0002 (redefined as a count with the esac decrement) |
| Inherited value (`_Group.case_inherited`) | The parent chain's unfinished `case`s, as seen by a provisional child | Pre: fixed once, when `_mark_provisional` opens the group. Post: parent provisional → parent's case mark plus parent's inherited value at that moment, else 0; afterwards changes only by the FR1 `esac` decrement, and only when the own case mark is 0 (A7); never negative; held apart from `outer_blocked`; never read by the `}` rescue (A2) | task0001 (introduced), task0002 (redefined as a sum with the esac decrement) |
| Paren-rescue exception (`_closes_paren_after_rescue`) | Refuse the `)` rescue on a marked group | Post: answers no rescue when the innermost group's case mark or inherited value is 1 or more, reading only those two values; otherwise its answer is unchanged (FR3, FR4) | task0001 (introduced), task0002 (reads counts) |

## Conventions

- **Byte identity**: the em-review copy is byte-identical to the em-workflow
  copy after every commit that touches either (NFR2;
  `.claude/rules/hook-tests.md`).
- **CASES rows**: `(expected, label, command)` with expected `deny` or
  `silent`; the same table runs against both copies; existing rows are never
  edited or removed (SPEC.md constraint A5).
- **Parser cost**: linear in input length, no recursion; per-word,
  per-opened-group and per-`)` work is constant time (NFR1).
- **Docstring markers**: every marker the existing tests check is kept
  verbatim (FR5).

## Cross-task Design Decisions

### D1: One task per change set covers both copies and the test table

- **Decision**: a guard change, its replication into the second copy and the
  CASES rows that pin it belong to the same task.
- **Rationale**: the two copies must change byte-identically in the same
  commit (FR6, NFR2), and the CASES table is the TDD contract for both;
  splitting them would put parallel edits on the same files with no ordering
  between tasks.
- **Affected tasks**: task0001, task0002.

### D2: The revised SPEC is met by a conformance task on the merged code

- **Decision**: task0001 stays as merged, and its plan stays unchanged as the
  record of the first-generation design (a mark never cleared, a yes/no
  inherited value, a leading reserved-word run that did not check quoting or
  escaping). task0002 changes the merged code in place to the revised
  behavior. Where task0001's plan and the revised SPEC disagree, SPEC.md and
  task0002's plan govern.
- **Rationale**: re-planning carries the merged task verbatim and numbers new
  work above it; one follow-up task keeps both copies and the CASES table
  changing in one commit (D1).
- **Affected tasks**: task0001, task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The `esac` decrement fires too eagerly (argument position, quoted, the inner `esac` of a nested `case`), re-enabling the rescue on a pattern `)` | Medium | High | Decrement only for a bare `esac` at an FR1 position, count semantics (FR1, A6); TS-16, TS-18, TS-19 expect deny; THREAT-MODEL.md TM-4 |
| The `esac` decrement fires too rarely (a command-position `esac` after `;;` absorbed into the reserved-word run, or the after-`in` shape not tracked), leaving a stale mark | Medium | High | TS-11, TS-12, TS-13, TS-17 expect deny; THREAT-MODEL.md TM-3 |
| The bare-run or after-`in` state shares the state `_names_function` / `_names_anonymous_function` use, changing their decisions | Medium | Medium | Separate state (FR1); every existing CASES row unchanged (TS-10) |
| The A9 forms (newline between `case x` and `in esac`; zsh's brace form) end up decrementing through the reserved-word run | Low | Medium | A9 tests in task0002; a conflict with FR1 is reported as a plan deviation, not special-cased |
| Inheritance or the paren check implemented as an ancestor walk, making the parse super-linear | Low | High | Value fixed from the parent alone when the child opens (FR2); depth / linearity tests (TS-10); THREAT-MODEL.md TM-2 |
| The inherited value folded into `outer_blocked`, changing the brace rescue | Low | High | Separate value (FR2, A2); existing brace-rescue rows unchanged (TS-10) |
| The two copies drift | Low | Medium | Byte-identity test (TS-10) |
| A docstring rewrite drops a marker the tests check, or keeps a statement that the mark is permanent | Low | Low | Docstring-marker tests including the new `esac` checks (TS-10); task0002 acceptance criteria |

## Open Questions

- None.
