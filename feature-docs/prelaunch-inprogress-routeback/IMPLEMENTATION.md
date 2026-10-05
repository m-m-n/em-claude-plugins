# Implementation Plan: prelaunch-inprogress-routeback

## Overview

Move Step I.2.a's launch-state capture / refresh / write / commit sequence in
`em-workflow/references/implement-phase.md` behind the `project_commands`
approval gate and the `Task()` launch loop, so that only tasks whose launch the
re-read journal confirms are committed as `in_progress`; rewrite the I.2.a
sentence that claims the `pending` + `launched` combination can never arise;
add document-contract tests that fail on the old wording.

## Technology Stack

- **Protocol document**: Markdown — `em-workflow/references/implement-phase.md`
  is the normative text the develop orchestrator executes.
- **Tests**: Python 3, standard library `unittest` only (`test/README.md`).
- **New dependencies**: none (no license entry required).
- **Commands**: `python3 -m unittest discover -s tests` (repo-tests),
  `python3 em-workflow/scripts/check-plugin-invariants.py .` (plugin-invariants).

## Layer Structure

| Layer | Content | Allowed dependency direction |
|-------|---------|------------------------------|
| Protocol document | `em-workflow/references/implement-phase.md` | none — it is the SSOT the tests read |
| Document-contract tests | `tests/test_*.py` modules that slice the protocol text by heading and assert wording and ordering | read-only on the protocol document; a test module never imports another test module |

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Step I.2.a Region P (selection rules) | The I.2.a text from the `### I.2.a: Launch phase` heading up to, not including, the paragraph that opens "For each selected task T" | Only task0002 edits Region P, and only the sentence that opens "Given I.2.c's route-back precondition below" and ends "can never arise." (FR5). Every other byte of Region P is unchanged after both tasks merge. In particular the in-flight sentence ("A task whose journal last event is `launched` is always in-flight, regardless of workflow.yaml `status`") stays verbatim, so Region L can cite it as "the in-flight rule" without restating it. | task0001 (cites), task0002 (edits) |
| Step I.2.a Region L (launch sequence) and the Step I.2 intro | Region L: the I.2.a text from the paragraph that opens "For each selected task T" up to the `### I.2.b: Wake phase` heading. Step I.2 intro: the paragraphs between the `## Step I.2:` heading and the `### I.2.a: Launch phase` heading | Only task0001 edits these. | task0001 |
| Term "launch-state commit" | The name of the commit made by the moved sequence (the `commit-docs.sh` call whose third argument is `"$LAUNCH_TIP"`) | Postcondition of task0001: Region L uses the literal term `launch-state commit` for that commit at least once. Postcondition of task0002: the rewritten Region P sentence refers to that commit with the same literal term (for example "Step I.2.a's launch-state commit below"). Neither side restates the other's rule. | task0001, task0002 |
| Protected text (NFR1) | The `### I.2.c: Failed handling` section and the `## Branch & Worktree Model` section, including its exit-4 recovery bullet | No task edits either section; both stay byte-identical to the implement base. Region L cites the exit-4 recovery bullet instead of restating it. | task0001, task0002 |
| Test-module ownership | Where each task's tests live | task0001 creates `tests/test_prelaunch_inprogress_launch_order.py`. task0002 creates `tests/test_prelaunch_inprogress_pending_launched.py` and is the only task that edits existing test modules (`tests/test_routeback_reset_scope_consistency.py`, `tests/test_recycled_task_id_consistency.py`). No task edits the other task's new module. | task0001, task0002 |

## Conventions

- **Test module shape** (both new modules):
  - Reads only `em-workflow/references/implement-phase.md`; imports no other
    test module; standard library only; discovered by
    `python3 -m unittest discover -s tests` with no registration.
  - Slices sections by heading text, the same boundaries existing modules use
    (`### I.2.a: Launch phase` to `### I.2.b: Wake phase`; the Step I.2 intro
    from the `## Step I.2:` heading to the I.2.a heading).
  - Content assertions run on whitespace-normalized text; byte-identity
    assertions run on raw text; the two are never mixed in one assertion.
  - Every literal asserted as new wording is a module-level constant read by
    both its positive test and its negative-proof test.
  - Every new-wording matcher has a negative proof against a verbatim
    pre-change sample of the same region, captured from the document as it
    reads at the task's base revision (never reconstructed), plus a
    non-vacuity guard: an anchor present in both the sample and the live
    document.
  - Ordering assertions search each later element starting after the earlier
    element's match, so a shared substring cannot satisfy the order by
    accident.
- **Document wording**:
  - New prose cites owning rules (the Branch & Worktree Model exit-4 recovery
    bullet, the I.2.a in-flight rule, `references/batch-mode.md`'s marker line)
    by reference and does not restate them.
  - No new git command is introduced, and no line that starts with `git` and
    commits or adds is introduced (a whole-file invariant pinned by existing
    tests).
  - No backtick-quoted residual reason code is introduced into I.2.a.
- **Existing tests**: an existing test module is edited only to follow wording
  this feature changes (NFR3).
- **Plugin version**: this repository is exempt (plan-writing skill, Plugin
  Version Handling); no task changes any plugin version.

## Cross-task Design Decisions

### D1: Disjoint edit regions inside Step I.2.a

FR1–FR4 rewrite the launch sequence (Region L); FR5 rewrites one sentence in
the selection rules (Region P). Splitting the section into two owned regions
lets both tasks run in parallel without textual overlap in
`implement-phase.md`, and each task's own worktree keeps the full suite green
on its own: task0001 leaves the old Region P sentence and the tests that pin it
untouched, and task0002 leaves the old launch order untouched.
Affected tasks: task0001, task0002.

### D2: The launch-state commit is the shared reference point

The rewritten Region P sentence (task0002) describes the window in which the
`pending` + `launched` combination arises — between a task's launch and the
commit that records it — and the case where that commit is not reached. That
commit is defined in Region L (task0001). Both sides name it with the literal
term "launch-state commit" (Shared Components), so the cross-reference
resolves after merge without either task reading the other's text.
Affected tasks: task0001, task0002.

### D3: The fix is entirely inside Step I.2.a

Step I.2.c's route-back gate, reset set and cleanup targets, and the Branch &
Worktree Model's exit-4 recovery bullet are unchanged (NFR1). No task text
implies a change to them; Region L applies the exit-4 recovery by citing it.
Affected tasks: task0001, task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Restructuring Region L breaks a literal pinned by an existing module that must pass unmodified | Medium | Medium | task0001's plan lists the pinned literals; the full suite runs in the task worktree |
| Region P's rewritten sentence and Region L describe different windows | Low | Medium | D2 shared term; manual reading item in VERIFICATION.md |
| Both tasks edit `implement-phase.md` and conflict on merge | Low | Low | D1 disjoint regions; parent-side adoption protocol |
| The commit now runs while implementers may already merge, so exit 4 occurs more often | Medium | Low | the existing bounded exit-4 recovery plus the journal re-read before every write set (task0001) |

## Open Questions

- None.
