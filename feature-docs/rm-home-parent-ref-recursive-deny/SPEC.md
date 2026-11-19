# Feature: rm-home-parent-ref-recursive-deny

## Overview

Some `rm` operands match a protected self-config path (`SELF_CONFIG`) in their
raw form, leave the protected area once `..` is folded, and contain an
expansion, so `check_rm()` reports them as `rm-unresolvable`. Today the
`self-modification` ask of the same statement is selected ahead of that `rm`
ask. This feature makes `main()` in `em-workflow/hooks/destructive-guard.py`
select the `rm` ask (reason ID `rm-unresolvable`) for such a statement, while
`$HOME` stays an unresolved expansion.

## Objectives

- For an `rm` operand whose raw form matches `SELF_CONFIG`, which leaves the
  protected area once `..` is folded, and which becomes `rm-unresolvable`
  because it contains an expansion, the `rm` confirmation is not absorbed by
  the same statement's `self-modification` ask (the reason ID is something
  other than `self-modification`).
- `$HOME` keeps being treated as an unresolved expansion; the decision and
  reason ID of every existing fixed case that treats `$HOME` as unresolved are
  kept.

## Acceptance Criteria

- [ ] AC1: Without `CLAUDE_BATCH`, `rm -rf "$HOME/.claude/skills/../../valuable"`
  is `ask` / `rm-unresolvable` (the unquoted form as well).
- [ ] AC2: `rm -rf $HOME/.claude/skills/foo "$HOME/.claude/skills/../../valuable"`,
  placed next to a genuinely protected operand, is `ask` / `rm-unresolvable`.
- [ ] AC3: The substitution-headed form
  `$(printf rm) -rf $HOME/.claude/skills/foo "$HOME/.claude/skills/../../valuable"`
  is also `ask` / `rm-unresolvable`.
- [ ] AC4: The AC1 and AC2 forms with `CLAUDE_BATCH` set are
  `deny` / `rm-unresolvable`.
- [ ] AC5: The `${HOME}` spelling and the form that reassigns `HOME` within the
  same command are decided as TS-8 and TS-9 state.
- [ ] AC6: The decision and reason ID of the existing fixed cases that treat
  `$HOME` as unresolved, and of the mixed-rm-self-config-deny and
  rm-parent-ref-self-config-deny cases (including TS-5's `tmp/$X`), do not
  change.
- [ ] AC7: `python3 em-workflow/hooks/tests/run-destructive-guard.py` and
  `python3 -m unittest discover -s tests` pass in full.

## Technical Requirements

### Functional Requirements

- **FR1:** Select the `rm` ask ahead of the `self-modification` ask in a
  statement that has a qualifying operand.
  - In `main()` of `em-workflow/hooks/destructive-guard.py`, decide per
    statement whether a qualifying operand exists.
  - A qualifying operand exists only when the statement's `self-modification`
    ask is held (`self_modification_asked`). It is one of the statement's `rm`
    deletion targets (the counted operands not starting with `-`, the same set
    `rm_protected_operand_numbers()` judges) that satisfies all three of:
    - (a) its raw form matches `SELF_CONFIG`;
    - (b) it is not in the set returned by `rm_protected_operand_numbers()`
      (it leaves the protected area once `..` is folded);
    - (c) `check_rm()` emits an `rm-unresolvable` record for that operand
      number.
  - In a statement with at least one qualifying operand, at step 2 of
    `main()`'s selection order (the first held ask), the `rm` ask takes the
    position of that statement's `self-modification` ask. The `rm` ask is the
    ask returned by `strongest_rm_decision()`; its reason ID is
    `rm-unresolvable` and its reason text is built the same way as the current
    `rm` ask.
  - The decision is per statement and does not depend on where the
    statement's `self-modification` ask came from: whether it came from a
    genuinely protected operand or from a redirection target, the `rm` ask
    comes first when a qualifying operand exists.
  - The rank of asks held earlier by other statements does not change. The
    `rm` deny keeps top priority (step 1 of the selection order).
  - Statements without a qualifying operand are handled as today (for
    example mixed-rm-self-config-deny TS-5's `tmp/$X`, or a
    `self-modification` ask caused only by a redirection).
  - The ask-to-deny downgrade under `CLAUDE_BATCH` stays in `decide()`, after
    selection.
- **FR2:** Apply FR1 on both paths.
  - The plain `rm` path: `check_rm(args, rm_anchor)` and
    `rm_protected_operand_numbers(args)`.
  - The substitution-headed path:
    `route_substitution_headed_statement(shaped_words[skip_index:], ...)` and
    `rm_protected_operand_numbers(shaped_words[skip_index:])`.
  - On each path, operand numbers are counted the same way `check_rm()`
    numbers its records on that path.
- **FR3:** Do not change how `$HOME` is treated as unresolved.
  - `check_rm()`'s unresolved check (`rm-unresolvable` via
    `UNRESOLVED_EXPANSION`), `check_self_modification()`,
    `rm_protected_operand_numbers()`, `fold_parent_refs()` and
    `normalize_candidate()` are not changed.
  - `$HOME` is not expanded with the hook's `HOME` for `check_rm()`'s
    judgment.
- **FR4:** Update the selection-order explanation and the rule document.
  - Add the FR1 exception to the comment in `main()` that explains the
    selection order and to the comment that explains the exclusion.
  - Add one exception to the bullet list "そのようなケースが固定する優先順位" in
    `.claude/rules/hook-tests.md`, with this content: 「同じ rm の削除対象のうち、
    生の形が保護された自己設定パスに一致するが、`..` を畳むと保護範囲の外に出て
    rm-unresolvable になるものがあると、その文の self-modification の `ask` より
    rm の `ask` が先に選ばれる」.
  - Existing bullets are not rewritten.
- **FR5:** Add regression cases.
  - Append TS-1 through TS-15 below, each with `rule`, to the end of the table
    in `em-workflow/hooks/tests/destructive-guard-cases.json`.
  - Batch cases carry `"batch": true`.
  - Labels start with `rm-home-parent-ref-recursive-deny TS-` and contain no
    machine-specific path and no home-directory path.
  - Existing cases are not rewritten.

### Non-Functional Requirements

- **NFR1 - Direction of change:** The decision level (allow / ask / deny) does
  not change for any case. The only change is that, in a statement with a
  qualifying operand, the ask's reason ID becomes `rm-unresolvable` instead of
  `self-modification` (under `CLAUDE_BATCH`, the deny's reason ID changes the
  same way). No current deny is weakened.
- **NFR2 - Determinism:** The decision depends only on the command string and
  the `HOME` at hook start; the filesystem is not consulted.
- **NFR3 - Performance:** Stays within the current scan budget and linear work
  bound. No case exceeds `GUARD_TIMEOUT_SECONDS` (10 seconds).
- **NFR4 - Version:** This is a bug fix; the `version` in `plugin.json` and
  `marketplace.json` is not changed.

## Implementation Approach

### Components

- `em-workflow/hooks/destructive-guard.py`
  - `main()`: per-statement qualifying-operand check and the step-2 selection
    change (FR1, FR2); selection-order and exclusion comments (FR4).
  - `check_rm()`, `route_substitution_headed_statement()`,
    `rm_protected_operand_numbers()`, `strongest_rm_decision()`: existing
    sources of the records, operand sets and `rm` ask used by FR1. The
    functions listed in FR3 are not changed.
  - `decide()`: unchanged; applies the `CLAUDE_BATCH` downgrade after
    selection.
- `em-workflow/hooks/tests/destructive-guard-cases.json`: new cases (FR5).
- `.claude/rules/hook-tests.md`: one added exception bullet (FR4).

### Data Flow

```
statement
  ├─ check_rm() / route_substitution_headed_statement() → rm records (per operand number)
  ├─ rm_protected_operand_numbers()                      → protected operand set
  └─ check_self_modification()                           → self_modification_asked
        ↓
main(): qualifying operand? (raw SELF_CONFIG match ∧ not protected ∧ rm-unresolvable record)
        ↓ yes                                         ↓ no
step 2 holds strongest_rm_decision() ask       step 2 unchanged
        ↓
decide() (CLAUDE_BATCH: ask → deny)
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/rm-home-parent-ref-recursive-deny/**`
- `test-docs/rm-home-parent-ref-recursive-deny/**`

`feature-docs/rm-home-parent-ref-recursive-deny/**` covers `REQUIREMENTS.md`,
`SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/rm-home-parent-ref-recursive-deny/**` covers
`test-docs/rm-home-parent-ref-recursive-deny/{T}.tests.yaml`, the per-task
test record. It is generated and owned by `implement-phase.md`; this section
cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/rm-home-parent-ref-recursive-deny/` directory at all; the declared
`test-docs/rm-home-parent-ref-recursive-deny/**` entry is still correct in
that case — a declared path that never materializes is not a violation.

## Test Scenarios

All scenarios are cases in `em-workflow/hooks/tests/destructive-guard-cases.json`,
each fixing `[decision, rule]`. Cases without `batch` run with
`CLAUDE_BATCH` unset.

### Unit Tests

- [ ] TS-1: `rm -rf "$HOME/.claude/skills/../../valuable"` - [ask, rm-unresolvable]
- [ ] TS-2: `rm -rf $HOME/.claude/skills/../../valuable` (unquoted) - [ask, rm-unresolvable]
- [ ] TS-3: `rm -rf $HOME/.claude/skills/foo "$HOME/.claude/skills/../../valuable"`
  (the first operand is genuinely protected) - [ask, rm-unresolvable]
- [ ] TS-4: TS-1 with `batch: true` - [deny, rm-unresolvable]
- [ ] TS-5: TS-3 with `batch: true` - [deny, rm-unresolvable]
- [ ] TS-6: `$(printf rm) -rf $HOME/.claude/skills/foo "$HOME/.claude/skills/../../valuable"`
  (substitution-headed path) - [ask, rm-unresolvable]
- [ ] TS-7: `rm -rf "$HOME/.claude/skills/../../valuable" > ~/.claude/settings.json`
  (the same statement also has a redirection-caused self-modification) -
  [ask, rm-unresolvable]
- [ ] TS-8: `rm -rf "${HOME}/.claude/skills/../../valuable"` - neither the raw
  nor the normalized form matches `SELF_CONFIG`, so no self-modification ask
  is raised and the FR1 condition is not met; current behavior is kept -
  [ask, rm-unresolvable]
- [ ] TS-9: `HOME=/tmp/x; rm -rf "$HOME/.claude/skills/../../valuable"` -
  [ask, rm-unresolvable]; with `batch: true` - [deny, rm-unresolvable]
- [ ] TS-10: `rm "$HOME/.claude/skills/../../valuable"` (not recursive; there is
  no `rm` record, so the FR1 condition is not met) - [ask, self-modification]
- [ ] TS-11: `rm -rf "$HOME/.claude/skills/../hooks/x"` (stays inside the
  protected area after folding; genuinely protected) - [ask, self-modification]
- [ ] TS-12: `rm -rf "$HOME/.claude/skills/../../../../tmp/x"` (`$HOME` is
  unresolved, so it becomes `rm-unresolvable` before the safe-area exception)
  - [ask, rm-unresolvable]
- [ ] TS-13: `rm -rf $HOME/.claude/skills/foo /home/user/valuable "$HOME/.claude/skills/../../valuable"`
  (the `rm` deny keeps top priority) - [deny, rm-recursive]
- [ ] TS-14: `rm -rf tmp/$X > ~/.claude/settings.json` (self-modification caused
  only by a redirection; no qualifying operand) - [ask, self-modification]
- [ ] TS-15: `rm -rf ~/.claude/skills/../../$X` (with the `~` spelling, an
  operand that contains an expansion and leaves the protected area via `..`
  meets the FR1 condition) - [ask, rm-unresolvable]

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

## Assumptions

- A1: The decision goes to ask / `rm-unresolvable` (deny / `rm-unresolvable`
  in batch). `$HOME` stays an unresolved expansion.
- A2: When a genuinely protected operand and a qualifying operand are in the
  same statement (TS-3, TS-5, TS-6), and when a redirection-caused
  self-modification and a qualifying operand are in the same statement (TS-7),
  the `rm` ask is selected first. The displayed reason is only
  `rm-unresolvable`; the write to self-config in the same statement does not
  appear in the reason.
- A3: The FR1 exception is not limited to the `$HOME` spelling. An operand
  whose raw form matches `SELF_CONFIG`, which leaves the protected area via
  `..`, and which becomes `rm-unresolvable` is handled the same way with the
  `~` or `/home/<user>` spelling (TS-15).
- A4: The `${HOME}` spelling (TS-8) does not meet the FR1 condition and stays
  ask / `rm-unresolvable`. A case fixing this form is added.
- A5: The form that reassigns `HOME` within the same command (TS-9) is
  ask / `rm-unresolvable`, following the treatment of `$HOME` as unresolved.
- A6: The SPEC.md files of the previous features (mixed-rm-self-config-deny,
  rm-parent-ref-self-config-deny) are not rewritten.
- A7: There is no LICENSE file, package manifest, E2E mechanism or UI.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes in full
- [ ] `python3 -m unittest discover -s tests` passes in full
- [ ] Existing cases keep their decision and reason ID (AC6)

## Open Questions

None.
