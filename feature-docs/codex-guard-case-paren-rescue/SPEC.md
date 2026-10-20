# Feature: codex-guard-case-paren-rescue

## Overview

Remove the deny-to-silent regressions in the `)` rescue of the two copies of
`codex-hook-interactive-guard.py` (em-workflow / em-review). The targets are
review finding 5e71ff00fdbe5aff and the round 1 findings 285d9bc33784bb3d,
df4afa83e782d56a and b374e6b3c3d4b471. Requirements are in
`feature-docs/codex-guard-case-paren-rescue/REQUIREMENTS.md`.

## Objectives

- Remove the deny-to-silent regressions in both copies of
  codex-hook-interactive-guard.py (em-workflow / em-review), covering review
  finding 5e71ff00fdbe5aff and round 1 findings 285d9bc33784bb3d,
  df4afa83e782d56a and b374e6b3c3d4b471.

## Technical Requirements

### Functional Requirements

- **FR1:** Increment and decrement a provisional group's case mark on `case` and `esac` at command position.
  - The case mark (`_Group.case_mark`) holds the number of `case` words read
    in that group that no `esac` has closed yet. The field name is unchanged.
  - When the main reader appends a word to a simple command and the innermost
    open group is a provisional group, the mark changes as follows:
    1. Increment: the word is at command position, its text is `case`, and it
       contains no quoting, escaping or expansion. Increment by 1.
    2. Decrement: the word's text is `esac`, it contains no quoting, escaping
       or expansion, and either (a) it is at command position, or (b) within
       the same simple command it comes immediately after the three words
       `case` (counted by step 1), any one word, and a bare `in`. Then: if the
       group's own case mark is 1 or more, decrement it by 1; otherwise, if
       the inherited value (FR2) is 1 or more, decrement that by 1; if both
       are 0, do nothing.
  - Command position is the first word that `_append_word` keeps after the
    leading run of bare reserved words.
  - A bare reserved word is a word in RESERVED_WORDS that contains no
    quoting, escaping or expansion. A bare `-p` immediately after a bare
    `time` is also part of the run.
  - A reserved word containing quoting or escaping (`"time"`, `\!`) is not
    counted in the run, and the run ends at that word.
  - The state for this bare run and the state for judging 2(b) are held
    separately from the state used by `_names_function` and
    `_names_anonymous_function` (`run_open`, `after_time`, `lone_function`).
  - The mark is in effect only while a `)` that ends a pattern is awaited. A
    group whose mark has returned to 0 through `esac` is read the same as a
    group with no mark.
  - `! case` and `time case` are included.
- **FR2:** Inherit the case mark along a chain of provisional groups.
  - When `_mark_provisional` opens a provisional group whose parent is also a
    provisional group, it fixes, in constant time, the sum of the parent's
    case mark and the parent's inherited value as the child's inherited value
    (`_Group.case_inherited`; the field name is unchanged). If the parent is
    not a provisional group, the value is 0.
  - After that, the child's inherited value changes only through the `esac`
    decrement of FR1 step 2. It does not follow later changes to the parent's
    values.
  - The inherited value is held separately from `outer_blocked`.
  - The `}` rescue (`_closes_after_rescue` / `_close_after_rescue`) does not
    read this value.
- **FR3:** Do not apply the `)` rescue to a marked provisional group.
  - `_closes_paren_after_rescue` returns False when the group's own case mark
    or its inherited value is 1 or more.
  - That `)` follows the existing reading of `_close_paren`: if the innermost
    open group is a `(` group (here, the provisional group itself) it closes
    it; otherwise it is treated as a separator.
  - Only the innermost group's values are used for this decision.
- **FR4:** Leave every other reading unchanged.
  - Unchanged: the `}` rescue; the end-of-input rescue
    (`_rescue_argument_groups`); the `)` rescue for a group whose case mark
    and inherited value are both 0; the decisions of `_names_function` and
    `_names_anonymous_function`; the reading of any input in which, while a
    provisional group is innermost, no bare `case` or `esac` is read at an
    FR1 position.
  - An `esac` not at an FR1 position (one in argument position, or one
    containing quoting, escaping or expansion) does not decrement the mark.
  - Outside provisional groups, the main reader does not track case pattern
    terminators (TS-9).
- **FR5:** Keep the docstrings in step.
  - Describe that the case mark is the number of unfinished `case`s, that it
    is decremented by `esac` at an FR1 position, how the inherited value is
    fixed and decremented, the run of bare reserved words, and the exception
    to the `)` rescue, in: step 4 of the module docstring (the `)` rescue
    paragraph), the `_Parser` class docstring, the `_Group` field list,
    `_mark_provisional`, `_append_word`, `_close_paren`, and
    `_closes_paren_after_rescue`. If the run state is placed in
    `_start_words`, include its docstring as well.
  - Remove statements that the mark is permanent, such as "The mark is never
    cleared", "It is never cleared" and "for the rest of its life".
  - Keep every existing docstring marker the tests check (including
    `case mark`, `inherited value`, `case_mark` and `case_inherited`).
- **FR6:** Fix both copies in the same change.
  - Apply the same change to `em-workflow/scripts/codex-hook-interactive-guard.py`
    and `em-review/scripts/codex-hook-interactive-guard.py` in the same
    change, keeping them byte-identical.
- **FR7:** Keep the tests in step.
  - Add rows for TS-11 through TS-19 to CASES in
    `tests/test_codex_hook_interactive_guard.py` in the form
    `(expected, label, command)`. The table runs against both copies.
  - Keep the existing TS-1 to TS-9, TS-7b and TS-8b rows unchanged.
  - Revise the CASES comment that explains the case mark so that it states
    the mark is decremented by `esac`.
  - Add to the case-mark docstring test in `TestGuardDocumentation` checks
    that the word `esac` appears in the module docstring, `_Parser`, `_Group`
    and `_append_word`.

### Non-Functional Requirements

- **NFR1 - Performance:** Reading stays linear in input length and uses no
  recursion. Updating the case mark, the bare reserved-word run state, and
  the state that judges an `esac` right after `in` takes constant time per
  appended word. Fixing the inherited value takes constant time per opened
  group, and the decision at `)` takes constant time.
- **NFR2 - Maintainability:** The two guard copies stay byte-identical.

## Implementation Approach

### Files

- `em-workflow/scripts/codex-hook-interactive-guard.py` (FR1 to FR5)
- `em-review/scripts/codex-hook-interactive-guard.py` (identical to the above, FR6)
- `tests/test_codex_hook_interactive_guard.py` (FR7)

### Constraints and Assumptions

- **A1:** Narrow fix only. `case` and `esac` are counted only on provisional
  groups. A broader fix that tracks case pattern terminators outside
  provisional groups is a separate feature; TS-9 stays silent.
- **A2:** The inherited value is held separately from `outer_blocked`, and
  the `}` rescue does not read it. The behavior of the `}` rescue does not
  change.
- **A3:** Command position is the first word `_append_word` keeps after the
  leading run of bare reserved words. Only reserved words containing no
  quoting, escaping or expansion, and a bare `-p` immediately after a bare
  `time`, count in the run. `case` and `esac` themselves must also be bare.
- **A4:** The plugin version is not changed. GitHub Actions bumps the patch
  version on push to main.
- **A5:** The existing deny / silent CASES rows (including TS-1 to TS-9,
  TS-7b and TS-8b) are kept unchanged.
- **A6:** The case mark is held as the number of unfinished `case`s, not as a
  boolean.
- **A7:** `esac` decrements the group's own case mark first, and decrements
  the inherited value only when the own mark is 0.
- **A8:** The field names `case_mark` and `case_inherited` are unchanged.
- **A9:** `esac` in the following positions does not decrement the mark: the
  form where a newline follows `case x` and `in esac` comes on the next
  line; zsh's `case x { ... }` form.

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/codex-guard-case-paren-rescue/**`
- `test-docs/codex-guard-case-paren-rescue/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/{feature}/**` covers `test-docs/{feature}/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests: existing CASES rows (unchanged)

- [ ] TS-1 (deny; FR1, FR3): `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in x) < /dev/null :;; esac; )'`
  - Reproduction of review 5e71ff00fdbe5aff.
- [ ] TS-2 (deny; FR1, FR3): `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; ! case x in x) < /dev/null :;; esac; )'`
  - `case` after a bare `!`.
- [ ] TS-3 (deny; FR1, FR3): `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; time case x in x) < /dev/null :;; esac; )'`
  - `case` after a bare `time`.
- [ ] TS-4 (deny; FR2, FR3): `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case ${v:-${x:-}; function { :; } bar(b; x} in x) < /dev/null :;; y) :;; esac; )'`
  - Chain inheritance. `x)` closes P2, which holds an inherited value; `y)`
    closes P. `esac` is read inside G1, so it does not affect the mark.
- [ ] TS-5 (silent; FR1, FR3): `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in x) :;; esac; ) < /dev/null'`
- [ ] TS-6 (silent; FR1, FR3): `zsh -c 'setopt nobadpattern; echo x | ( function { python3; } foo(a; case x in x) :;; esac; )'`
- [ ] TS-7 (silent; FR1, FR4): `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; echo case x in x) < /dev/null'`
  - TS-7b is kept as well.
- [ ] TS-8 (silent; FR1, FR4): `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; "case" x in x) < /dev/null'`
  - TS-8b is kept as well.
- [ ] TS-9 (silent; FR4): `zsh -c '( python3; case x in x) < /dev/null :;; esac; )'`
  - Known miss, out of scope. Unchanged.

### Unit Tests: new CASES rows (FR7)

- [ ] TS-11 (deny; FR1, FR3): `zsh -c 'setopt nobadpattern; ( function { python3 -i; } foo(a; case x in esac; )'`
  - Reproduction of finding 285d9bc33784bb3d. The `esac` right after `in`
    returns the mark to 0, and the final `)` rescues the chain and closes G1.
- [ ] TS-12 (deny; FR1, FR3): `zsh -c 'setopt nobadpattern; ( function { :; } foo(a; case x in esac; python3 -i; )'`
  - Finding df4afa83e782d56a. Launch after an empty `case`.
- [ ] TS-13 (deny; FR1, FR3): `zsh -c 'setopt nobadpattern; ( function { :; } foo(a; case x in (x) :;; esac; python3 -i; )'`
  - Finding df4afa83e782d56a. `(x)` opens and closes as an ordinary `(`
    group. The command-position `esac` after `;;` returns the mark to 0.
- [ ] TS-14 (deny; FR1): `zsh -c 'setopt nobadpattern; ( function { :; } foo(a; "time" case; python3 -i; )'`
  - Finding b374e6b3c3d4b471. A quoted `time` does not count in the run, so
    `case` gets no mark.
- [ ] TS-15 (deny; FR1): `zsh -c 'setopt nobadpattern; ( function { :; } foo(a; \! case; python3 -i; )'`
  - Finding b374e6b3c3d4b471. An escaped `!` does not count in the run.
- [ ] TS-16 (deny; FR1, FR3): `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in (x) case y in (y) :;; esac;; z) < /dev/null :;; esac; )'`
  - Nested `case`. After the inner `esac` the mark is still 1, and `z)`
    closes P. With a boolean mark, the rescue would apply here and the result
    would be silent.
- [ ] TS-17 (deny; FR1, FR2, FR3): `zsh -c 'setopt nobadpattern; ( function { python3 -i; } foo(a; case ${v:-${x:-}; function { :; } bar(b; x} in (x) :;; esac; )'`
  - Inherited-value decrement. The command-position `esac` inside P2 brings
    P2's inherited value to 0, and the final `)` rescues the chain (P2, P)
    and closes G1.
- [ ] TS-18 (deny; FR1, FR4): `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in (y) echo esac;; x) < /dev/null :;; esac; )'`
  - An `esac` in argument position does not decrement the mark, and `x)`
    closes P.
- [ ] TS-19 (deny; FR1, FR4): `zsh -c 'setopt nobadpattern; ( function { python3; } foo(a; case x in (y) "esac";; x) < /dev/null :;; esac; )'`
  - A quoted `esac` does not decrement the mark.

### Test Suite

- [ ] TS-10 (pass; FR5, FR6, FR7, NFR1, NFR2): `python3 -m unittest tests.test_codex_hook_interactive_guard`
  - Run from the repository root. Includes the existing CASES rows,
    `test_the_two_copies_are_byte_identical`, the docstring marker tests,
    and the depth and linearity tests.

### Edge Cases

- [ ] A9: an `esac` on the line after `case x` (newline between `case x` and
  `in esac`), and an `esac` in zsh's `case x { ... }` form, do not decrement
  the mark.

## Success Criteria

- [ ] AC1: Both guards return deny for TS-1.
- [ ] AC2: Both guards return deny for TS-2 and TS-3.
- [ ] AC3: Both guards return deny for TS-4.
- [ ] AC4: TS-5 to TS-8 stay silent, and the existing TS-7b and TS-8b stay deny.
- [ ] AC5: The result of TS-9 (silent) is unchanged.
- [ ] AC6: TS-10 passes.
- [ ] AC7: Both guards return deny for TS-11, TS-12 and TS-13 (`esac` removes
  the mark; findings 285d9bc33784bb3d, df4afa83e782d56a).
- [ ] AC8: Both guards return deny for TS-14 and TS-15 (reserved words
  containing quoting or escaping do not count in the run; finding
  b374e6b3c3d4b471).
- [ ] AC9: Both guards return deny for TS-16 and TS-17 (nested `case` is held
  as a count; the inherited value is also decremented by `esac`).
- [ ] AC10: Both guards return deny for TS-18 and TS-19 (an `esac` in
  argument position and a quoted `esac` do not decrement the mark).

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- None.

## References

- Requirements document: `feature-docs/codex-guard-case-paren-rescue/REQUIREMENTS.md`
