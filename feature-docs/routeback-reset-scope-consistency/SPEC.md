# Feature: routeback-reset-scope-consistency

## Overview

Step I.2.c of `em-workflow/references/implement-phase.md` derives its
route-back admissibility gate, its workflow.yaml write set, and its
worktree/branch cleanup from three different task-state sources. This feature
makes all three derive from one source — Step I.2.b step 1's reconciled
state — by widening the gate's `merged` conjunct into the same two-source
union shape the `in_progress` conjunct already uses, and by re-expressing the
reset and cleanup scopes in reconciled-state terms. It is a
documentation-only change accompanied by a document-contract test module and
a plugin version bump.

Requirements source: `feature-docs/routeback-reset-scope-consistency/REQUIREMENTS.md`.

## Objectives

- Make Step I.2.c's route-back derive admissibility, the workflow.yaml write
  set, and the worktree/branch cleanup from one and the same task-state
  derivation source, restoring the single derivation rule I.2.a / I.2.b
  established ("task state comes from step 1's reconciled state").
- Ensure no task whose work is already merged into the integration branch can
  have its branch deleted, or its record erased by a planner `replace_all`
  renumber, as a side effect of route-back.

## User Stories

### US1: Merged work survives route-back
As an em-workflow orchestrator, I want the route-back gate and cleanup to
consult the reconciled state, so that a task whose journal last event is
`merged` (ancestor-verified) is never reset or branch-deleted regardless of
what workflow.yaml's `status` says.

**Acceptance Criteria:**
- [ ] AC-2: When a task's journal last event is `merged` (ancestor-verified),
      its worktree and branch are never route-back cleanup targets —
      regardless of what workflow.yaml's `status` says for that task.
- [ ] AC-3: The document states that `git branch -D` on this path targets only
      tasks confirmed not merged.

### US2: One derivation source across the whole route-back path
As an em-workflow orchestrator, I want admissibility, the write set and
cleanup to all name Step I.2.b step 1's reconciled state, so that the single
derivation rule is not silently broken inside I.2.c.

**Acceptance Criteria:**
- [ ] AC-1: I.2.c's route-back admissibility, write set, and cleanup all name
      the same state derivation source (Step I.2.b step 1's reconciled state).

### US3: The change is machine-checked
As a maintainer of em-workflow, I want document-contract tests and a version
bump shipped with the change, so that the new wording cannot silently
regress and the plugin cache picks the change up.

**Acceptance Criteria:**
- [ ] AC-4: Document-contract tests equivalent to TS-3 / TS-4 exist under
      `tests/`, each new absence/new-wording matcher paired with a negative
      proof and a non-vacuity guard.
- [ ] AC-5: `python3 -m unittest discover -s tests` passes.
- [ ] AC-6: `tests/test_implement_routeback_gate.py` and
      `tests/test_recycled_task_id_consistency.py` pass unmodified.
- [ ] AC-7: `em-workflow/.claude-plugin/plugin.json` and
      `.claude-plugin/marketplace.json` carry the same bumped version.

## Technical Requirements

### Functional Requirements

- **FR1 — The `merged` gate conjunct becomes a two-source union:** In I.2.c,
  the route-back gate's `merged` conjunct is restated as a union of two
  independent sources, either of which blocks — exactly parallel to the
  `in_progress` conjunct's existing union: workflow.yaml reporting a task
  `merged`, OR Step I.2.b step 1's reconciled state reporting a task `merged`
  (journal last event `merged`, verified by
  `git merge-base --is-ancestor` as that step already requires). Step I.2.b is
  cited as the owning rule, never restated. The existing literal "no task has
  status `merged`" survives; the union is added around it, not substituted
  for it.
- **FR2 — The reset (write set) target set is defined by the reconciled
  state:** The ordered workflow.yaml write set resets the status of every task
  whose Step I.2.b step 1 reconciled state is `failed`, replacing the current
  workflow.yaml-`status: failed` basis. The four write instructions and their
  order (`create-plan` → `needs_update`; `implement` → `pending`; failure
  reason into `tasks.{T}.notes`; `tasks.{T}.status` back to `pending`) are
  unchanged, and the `replace_planning` / `replace_all` citation of
  `references/workflow-patch.md` stays a citation.
- **FR3 — Cleanup targets only tasks confirmed not merged:** The post-commit
  cleanup (`git worktree remove --force`; `git branch -D`) applies to exactly
  the tasks just reset by FR2, and the text states in so many words that those
  are tasks confirmed not merged — a task whose reconciled state is `merged`
  is never a cleanup target. The commit-before-cleanup order and the
  leftover-state sentence are preserved.
- **FR4 — The rejected path enumerates the new blocker:** The "When the gate
  does not hold" branch adds the FR1 source to its reason enumeration (a task
  the reconciled state reports `merged` even though workflow.yaml does not),
  alongside the existing `merged` / `in_progress` / in-flight reasons. Its
  terminal is unchanged: no `needs_update`, `implement` set to `failed` and
  committed as the single write, control back via develop's stop condition 3.
- **FR5 — Cross-references describing the gate stay true:** Every site that
  describes the I.2.c gate is updated in the same change so it still reads
  correctly: I.2.a's unreachability sentence ("Given I.2.c's route-back
  precondition below, which admits only tasks with a terminal journal last
  event…") and the Branch & Worktree Model's exit-4 unreachability proof ("The
  widened I.2.c gate's union rule — blocked when workflow.yaml reports a task
  `in_progress` OR …").
- **FR6 — Route-back's own recursion invariant is stated:** The document
  states why FR1 cannot deadlock a later route-back through a recycled id:
  because route-back proceeds only when no task is `merged` under either
  source, no retired id can leave a `merged` last event behind for a
  renumbered task to inherit, so the I.2.a recycled-task-id carve-out stays
  correctly scoped to `failed` only.
- **FR7 — Document-contract tests:** A new `tests/test_*.py` module asserts
  FR1..FR4 and FR6 against `em-workflow/references/implement-phase.md` (the
  TS-3 / TS-4 equivalents named in the acceptance criteria), in the
  established style: whitespace-normalized section slices for prose, raw text
  for byte-identity, one negative proof per new matcher against captured
  pre-change wording, plus non-vacuity guards on those samples.
- **FR8 — Plugin version bump:** `em-workflow/.claude-plugin/plugin.json` and
  `.claude-plugin/marketplace.json` both move from `0.1.38` to the same new
  patch version in this change.

### Non-Functional Requirements

- **NFR1 — Byte-identity regression:** Byte-identity constraints already
  asserted by `tests/test_implement_routeback_gate.py` and
  `tests/test_recycled_task_id_consistency.py` hold unchanged: the I.2.c
  heading, and the batch-mode paragraph as the byte-identical TAIL of the
  I.2.c section (all new prose is inserted before it).
- **NFR2 — Protected line wraps:** Line-wrap literals outside I.2.c are not
  reflowed — Step I.0's "in `tasks` whose\n   `status == pending`", Step
  I.2.a's "`tasks.*.status`. Select\nunlaunched tasks (…) ascending", and Step
  I.2.b step 3's `commit-docs.sh` two-line literal.
- **NFR3 — Ordering invariants:** Orderings asserted over the normalized I.2.c
  section survive: the first occurrence of `tasks.{T}.status` still has
  `pending` within 60 characters (so no earlier mention may be introduced by
  the new gate wording); the four write tokens precede
  `git worktree remove --force`; `commit-docs.sh` precedes cleanup, which
  precedes "End the phase with a"; the literal "terminal journal last event
  (`merged` or `failed`)" survives and still precedes "`create-plan` to
  `needs_update`".
- **NFR4 — Rejected-path containment:** Rejected-path containment survives:
  the normalized text after "When the gate does not hold" contains none of
  "make one ordered workflow.yaml write set", "git worktree remove --force",
  "ROUTEBACK_TIP"; and the strings "rework" and "append" appear nowhere in the
  I.2.c section.
- **NFR5 — Retained gate literals:** "no task has status `merged`", "no task
  has status `in_progress`" joined in one sentence, "re-read from workflow.yaml
  task statuses", "not inferred from the drain above", "a union of two
  independent sources".
- **NFR6 — No bare git write commands:** No bare `git … commit` /
  `git … add -A` line is introduced into implement-phase.md.
- **NFR7 — Test environment:** Tests use only the Python standard library
  (`unittest`), live in the repository-root `tests/`, and the full suite
  `python3 -m unittest discover -s tests` passes from the project root.
- **NFR8 — Documentation-only:** No runtime script, hook, or shell behavior is
  modified; the file set is implement-phase.md, the new test module, and the
  two version files (plus any doc that restates the gate, per FR5).

## Implementation Approach

### Architecture

This is a prose-contract change to a single reference document plus its test
harness. The relevant structure is the derivation chain inside the implement
phase:

```
journal (append-only)  ──┐
                         ├──> I.2.b step 1 reconciled state ──> I.2.c gate      (FR1)
git merge-base ──────────┘                                 ├──> I.2.c write set (FR2)
                                                           └──> I.2.c cleanup   (FR3)
workflow.yaml tasks.{T}.status ─────────────────────────────> union second source
```

Before the change, the gate's `merged` conjunct, the write set and the
cleanup each read `workflow.yaml` status directly; after the change, all
three name the reconciled state, with workflow.yaml retained only as the
second member of the gate's unions (union semantics, not replacement — EC-6).

### Data Flow

```
task failure → drain → user/batch chooses "route back to planning"
  → gate: merged-union (FR1) AND in_progress-union (existing)
      ├─ holds  → refresh + ROUTEBACK_TIP → ordered write set over
      │            reconciled-`failed` tasks (FR2) → commit
      │            → cleanup of exactly those tasks (FR3) → end phase
      └─ fails  → enumerate reasons incl. reconciled-`merged` (FR4)
                   → refresh + TERMINAL_TIP → implement=failed → commit
                   → develop stop condition 3
```

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/implement-phase.md`: the document under change
  (Branch & Worktree Model, Steps I.2.a / I.2.b / I.2.c).
- `em-workflow/references/workflow-patch.md`: owns the `replace_planning` /
  `replace_all` permission conditions; referenced by citation only (FR2).
- `skills/develop/SKILL.md` Step B stop condition 3: the terminal the rejected
  path returns through (FR4).
- `tests/test_implement_routeback_gate.py`,
  `tests/test_recycled_task_id_consistency.py`: existing contract tests that
  must pass unmodified (AC-6, NFR1).

**External Dependencies:**
- Python standard library `unittest` only (NFR7).

### File Structure

```
em-workflow/references/implement-phase.md      # FR1-FR6 wording changes
em-workflow/.claude-plugin/plugin.json         # FR8: 0.1.38 -> 0.1.39
.claude-plugin/marketplace.json                # FR8: 0.1.38 -> 0.1.39
tests/test_*.py                                # FR7: new document-contract module
```

## Test Scenarios

### Document-Contract Tests

- [ ] **TS-1** (FR1, AC-1): The I.2.c gate's `merged` conjunct is stated as a
      union of workflow.yaml status and Step I.2.b's reconciled state, citing
      I.2.b as owner; the pre-change wording (workflow.yaml-only) is absent.
- [ ] **TS-2** (FR2, AC-1): The write set's reset target is expressed in
      reconciled-state terms; the workflow.yaml-`status: failed`-only phrasing
      is absent.
- [ ] **TS-3** (FR3, AC-2, AC-3): The cleanup sentence names its targets as
      the tasks just reset and states they are confirmed not merged;
      `git branch -D` appears only within that scoped sentence.
- [ ] **TS-4** (FR4, NFR4): The rejected branch enumerates the
      reconciled-state-`merged` blocker and keeps its single terminal
      (`implement` set to `failed`, committed, stop condition 3), with no
      route-back instruction leaking into it.
- [ ] **TS-5** (FR5): I.2.a's unreachability sentence and the Branch &
      Worktree Model's exit-4 union-rule sentence still describe the gate as
      it now reads.
- [ ] **TS-6** (FR6): The recursion-invariant sentence (no retired id can
      carry a `merged` last event) is present, and the I.2.a carve-out remains
      scoped to `failed`.

### Regression Tests

- [ ] **TS-7** (NFR1, NFR2, NFR3, NFR4, NFR6): Regression guards: heading and
      batch-mode-paragraph byte identity; the three protected line-wrap
      literals; the four normalized I.2.c orderings including the
      60-character `tasks.{T}.status`/`pending` window; absence of
      "rework"/"append" in I.2.c; no bare git commit/add line.
- [ ] **TS-8** (FR7, AC-4): Every new-wording matcher in TS-1..TS-6 has a
      negative proof against a verbatim pre-change sample, and each sample
      carries a retained anchor asserted positively.
- [ ] **TS-9** (FR8, AC-7): Both version files report the same, bumped version
      string.

### E2E Tests

**Existing E2E tests**: None
**Run command**: `python3 -m unittest discover -s tests`
- [ ] The full suite passes from the project root (AC-5).
- [ ] `tests/test_implement_routeback_gate.py` and
      `tests/test_recycled_task_id_consistency.py` pass unmodified (AC-6).

### Edge Cases

- [ ] **EC-1**: Journal last event `merged` (ancestor-verified) +
      workflow.yaml `status: failed`. Reachable today: I.2.b step 3 writes
      `failed` for a task "whose report is `failed`/malformed", a clause that
      can match the same task the `merged` clause matches. Both current gate
      conjuncts pass, the task is reset to `pending` and its branch
      `git branch -D`d. This is the live instance of the reported bug and FR1
      must close it.
- [ ] **EC-2**: Journal last event `merged` + workflow.yaml
      `status: in_progress` (the scenario the review finding names). Already
      blocked by the existing `in_progress` conjunct; after FR1 it is blocked
      for the `merged` reason as well, and the rejected path must report a
      reason that is true of it.
- [ ] **EC-3**: A `merged` claim that fails `git merge-base --is-ancestor` is
      NOT merged (I.2.b step 1 is authoritative) and must not block route-back
      through the new conjunct.
- [ ] **EC-4**: A task with no journal event at all has nothing to inherit and
      never blocks route-back; it stays `pending` and is not a cleanup target.
      Already stated in the document; must survive the edit.
- [ ] **EC-5**: Recycled id after a previous route-back + `replace_all`: a
      renumbered task must not inherit a retired id's `merged` event and
      permanently block a second route-back. FR6 states why this cannot arise.
- [ ] **EC-6**: workflow.yaml `status: merged` with no `merged` journal event
      (lost or truncated journal): the workflow.yaml source of the FR1 union
      still blocks. Union semantics, not replacement.

## Security Considerations

Not applicable — documentation-only change with no runtime, script, hook or
shell behavior modified (NFR8).

## Success Criteria

- [ ] All functional requirements (FR1..FR8) are implemented and tested.
- [ ] All test scenarios (TS-1..TS-9) pass.
- [ ] All acceptance criteria (AC-1..AC-7) are satisfied.
- [ ] `python3 -m unittest discover -s tests` passes from the project root.
- [ ] Documentation is complete.
- [ ] Code review is completed.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None — every requirement is `status: resolved`.

## Assumptions

- **A-1**: Reviewer option (a) is adopted over option (b): the reset/cleanup
  scope is defined by Step I.2.b step 1's reconciled state, and the gate's
  `merged` conjunct is widened into the same two-source union shape the
  `in_progress` conjunct already uses.
- **A-2**: I.2.b step 3's own precedence ambiguity (a task matching both the
  "verified merged" clause and the "report is `failed`/malformed" clause) is
  left as-is, out of scope.
- **A-3**: Version bump is 0.1.38 → 0.1.39 (patch).
- **A-4**: The new test module is a single new file under `tests/`; neither
  protected module is edited.
- **A-5**: Scope is limited to `em-workflow/references/implement-phase.md`,
  the new test module and the two version files; other documents are touched
  only where FR5 requires them to stay true.

## Context Note

The review record's original description ("write set が pending でない全タスクに
広がっている") no longer matches the document at this base revision. The live
divergence is journal-`merged` + workflow.yaml-`failed` (EC-1); these
requirements are written against the document as it actually reads now.

## Design Step

Skipped. Reason: documentation + Python-unittest repository with no UI, no
rendered output and no design-system inputs; design-system candidate
discovery returned zero candidates.

## References

- Requirements document: `feature-docs/routeback-reset-scope-consistency/REQUIREMENTS.md`
- Document under change: `em-workflow/references/implement-phase.md`
- Patch permission conditions: `em-workflow/references/workflow-patch.md`
- Existing contract tests: `tests/test_implement_routeback_gate.py`,
  `tests/test_recycled_task_id_consistency.py`
- Version files: `em-workflow/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`
