# Implementation Plan: routeback-gate-postcondition

## Overview

Documentary fix to em-workflow's own protocol documents: the Step I.2.c
route-back gate is widened so that it actually establishes the postcondition
`replace_all` requires, its rejected path gets a single defined terminal, and
the Branch & Worktree Model's exit-4 recovery enumeration loses the entry the
widened gate makes unreachable. A plugin version bump accompanies the change.

## Technology Stack

- **Markup**: Markdown — the protocol documents under `em-workflow/references/`
  are the artifacts being changed.
- **Language**: Python (standard library `unittest` only) — the existing
  document-contract test suite under `tests/`.
- **New dependencies**: none. No library is added, so the license constraint
  is vacuous here (`project.license: none`; nothing to record).

## Layer Structure

Three document layers, with a one-way dependency direction:

| Layer | Members | Role |
|-------|---------|------|
| Protocol SSOT | `em-workflow/references/*.md` | Normative behavior. Each rule has exactly one owning document; other documents cite it. |
| Contract tests | `tests/*.py` | Read protocol documents as text and assert their contracts. Tests depend on documents; documents never mention tests. |
| Plugin metadata | `em-workflow/.claude-plugin/plugin.json` | Version identity of the plugin. Depends on nothing. |

Ownership boundaries relevant to this change:

- `em-workflow/references/implement-phase.md` owns the route-back gate (Step
  I.2.c) **and** the Branch & Worktree Model's exit-4 recovery enumeration —
  both edited surfaces live in this single file.
- `em-workflow/references/workflow-patch.md` owns the `replace_all`
  admissibility condition. It is READ-ONLY for this change (NFR1): the gate
  cites it as the owner and never restates its condition set.
- `em-workflow/skills/develop/SKILL.md`, `references/batch-mode.md` and
  `references/workflow-schema.md` reference the route back but delegate the
  condition to `implement-phase.md`; they therefore need no companion edit
  (verified during planning — see D3).

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Route-back admissibility gate (`implement-phase.md` Step I.2.c) | Decides whether route back to planning may proceed | pre: workflow.yaml task statuses are readable; post (admitted): after the unchanged write set, every existing task is `pending`, so `replace_all` admissibility holds; post (rejected): `implement` is `failed`, nothing committed, nothing cleaned up | task0001 |
| `replace_all` admissibility condition (`references/workflow-patch.md`) | Frozen SSOT for when a `replace_planning` patch is accepted | Read-only. May be cited by path/operation name; its condition set must never be restated in another document | task0001 (read-only) |
| Route-back document-contract test module (`tests/test_implement_routeback_gate.py`) | Sole home of the assertions pinning the I.2.c section and the exit-4 enumeration | pre: exists with assertions pinning the pre-change prose; post: same module asserts the post-change prose, with no test skipped or removed | task0001 (exclusive writer) |
| Plugin version field (`em-workflow/.claude-plugin/plugin.json`) | Single source of the plugin version | pre: reads `0.1.36`; post: reads `0.1.37`; JSON stays parseable and all other fields unchanged | task0002 (exclusive writer) |
| Exit-4 recovery carve-out (owned by `implement-phase.md`'s Branch & Worktree Model bullet) | Says which `commit-docs.sh` call sites the bounded recovery binds, and on what proof a site may be exempt | pre: every caller is bound (`commit-docs.sh`'s RECOVERY CONTRACT header); post: a site is exempt only when its owning protocol document states BOTH an unreachability proof over the paths that can advance the integration branch ref AND a defined terminal for an unexpected non-zero exit — today exactly one site, Step I.2.c's route-back commit. `commit-docs.sh`'s header and `skills/develop/SKILL.md`'s exit-4 paragraph carry the carve-out by citation and never restate the proof | task0003 (exclusive writer of all three surfaces) |
| Step I.2.c rejected-path terminal (`implement-phase.md`) | Persists the terminal state the rejected route-back path halts on | pre: the gate rejected; post: `implement` is `failed` in workflow.yaml AND committed, so develop Step B stop condition 3 fires on the next step selection; no route-back write set, no worktree/branch cleanup, no route-back commit | task0003 (exclusive writer) |

## Conventions

- **Cite, never restate**: a rule owned by another document is referenced by
  document path plus rule/operation name. Copying the rule text into a second
  document is the defect class this feature exists to fix.
- **Token stability**: phrases that existing tests assert on are treated as a
  contract. A phrase may be changed only when the asserting test is updated in
  the same task; a phrase that no in-scope task owns must be left byte-stable.
- **Whitespace-tolerant assertions**: text assertions run against a
  whitespace-normalized copy of the sliced section so that line-wrap choices do
  not make an assertion brittle; byte-identity assertions use the raw text.
  This is the pattern the existing module already follows — keep it.
- **No new mechanical checker** (FR5): no new script, validator rule, hook or
  test module. Changes to test expectations land inside the existing module
  that already pins the affected prose.
- **Document language**: the protocol documents are written in English; the
  `skills/develop/SKILL.md` Japanese layer is out of scope.

## Cross-task Design Decisions

### D1: File-set partition, and single ownership of the version bump

The two tasks have disjoint file sets: task0001 owns
`em-workflow/references/implement-phase.md` and
`tests/test_implement_routeback_gate.py`; task0002 owns
`em-workflow/.claude-plugin/plugin.json` and nothing else.

**task0001 must NOT bump the plugin version**, even though the project's
general habit is to bump within the same change. The bump for this feature is
owned solely by task0002, which merges into the same integration branch, so the
feature as a whole still carries exactly one bump. Two tasks editing the same
version field would produce a conflict with no correct parent-side resolution.

Rationale: both defects live in a single file, so a defect-by-defect split
would overlap on `implement-phase.md`. Splitting by file instead keeps every
task independently mergeable.

### D2: Frozen files

These must be byte-identical before and after the feature (NFR1, FR5). No task
may edit them, and no task may add a file that enforces them mechanically:

- `em-workflow/scripts/validate-worker-output.py`
- `em-workflow/references/workflow-patch.md`
- everything under `em-workflow/references/contracts/`
- the repository-root `.claude-plugin/marketplace.json` (its em-workflow entry
  carries no `version` field, so nothing needs syncing — FR6)

### D3: Scope containment — no companion documents to edit

Every other document that mentions the route back delegates the condition
rather than restating it: `skills/develop/SKILL.md` names the transition and
points at `references/implement-phase.md` (I.2.c); `references/batch-mode.md`
records only the batch decision ("route back is never taken automatically")
and points at the same section; `references/workflow-schema.md` states only
that a `failed` task resolves by retry or by routing back. None of them names
the admissibility condition, so widening it creates no second site to update.
A task that believes it must edit one of these files has found a plan
deviation and reports it instead of expanding scope.

### D4: Tests that pin removed prose are rewritten, never deleted

An assertion that pins prose this feature removes is replaced by an assertion
of the new contract (typically: absence of the removed phrase plus presence of
its replacement), keeping the module's negative-matcher discipline — every
absence assertion is paired with a proof that the matcher would flag the
pre-change wording. Deleting or skipping such a test to reach green violates
NFR3.

### D5: The exit-4 carve-out is a cross-document contract (rework round 1)

Added by the round-1 rework. D3 recorded that no companion document needed
editing, because every other document that mentions the route back delegates
the *admissibility condition*. Review round 1 found a second, different
cross-document surface that D3 did not cover: the exit-4 recovery obligation.
`em-workflow/scripts/commit-docs.sh` declares its RECOVERY CONTRACT "binding on
every caller" and `em-workflow/skills/develop/SKILL.md` scopes its exit-4
paragraph to every call site, so removing one call site from that obligation in
`implement-phase.md` alone leaves three SSOTs disagreeing about one event.

The carve-out is therefore a shared contract, owned by `implement-phase.md`'s
Branch & Worktree Model bullet and cited (never restated) by the other two.
task0003 is the exclusive writer of all three surfaces in one task, because a
partial edit is exactly the defect being repaired. This NARROWS D3 for the
rework round: `skills/develop/SKILL.md` is in scope for task0003, for this
paragraph only. D3's statement stands unchanged for the admissibility
condition, and `references/batch-mode.md` and `references/workflow-schema.md`
remain out of scope.

`commit-docs.sh` is a script but not a frozen file (D2 lists the frozen set,
and it is not in it). Its edit is confined to comment text: no executable
line changes, so `tests/test_commit_docs.py` — which tests exit codes and
behavior, not header prose — must stay green unmodified.

### D6: The version bump is not repeated for rework

The feature's single bump to `0.1.37` is owned by task0002 and is already
merged. SPEC AC6 and VERIFICATION TS9/TS16 pin that exact value, so a second
bump for the rework round would fail them. No rework task edits
`em-workflow/.claude-plugin/plugin.json`; the one bump covers the feature
including its rework, since nothing has been released between the rounds. D1's
single-ownership rule extends unchanged to task0003 and task0004.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| An existing test outside the edited module (e.g. the lock-contract or phase-state suites) pins a sentence the edit touches, going red without an owner | Medium | High | Those suites pin the exit-4 *recovery procedure* sentences and the I.2.b call site, not the enumeration entry; task0001's acceptance requires the full suite green with those files unmodified |
| The two edited surfaces of the same file end up disagreeing about which condition guarantees exit-4 exclusion | Medium | High | The unreachability justification must be tied to the widened gate, not to the drain step alone (FR4/TS8); both surfaces are owned by one task |
| Removing the drain-based justification also removes the retry / abort options users still need | Low | High | Only the *route-back* path's admissibility reasoning changes; the sibling retry and abort options and the batch-mode paragraph stay as they are |
| An implementer bumps the plugin version "for good hygiene" from task0001 | Medium | Medium | D1 states single ownership explicitly, and task0001's file set excludes the file |
| Enforcement stays prose, so a future edit can re-break the postcondition | Medium | Medium | Accepted by ASM4 (no new mechanical checker); the existing document-contract test module is the standing regression net |

## Open Questions

- [ ] The Step I.2.c route-back commit currently carries an inline pointer to
      the bounded exit-4 recovery procedure. Once that call site is removed
      from the recovery enumeration as unreachable (FR4), the pointer and the
      enumeration disagree. task0001 resolves this by replacing the pointer
      with an unreachability note plus a stop-with-report terminal for an
      unexpected non-zero exit; SPEC.md does not decide it, so review may
      revisit the choice.
