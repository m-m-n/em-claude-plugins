# Implementation Plan: create-plan-status-conflict

## Overview

Remove the protocol contradiction that makes every conformant create-plan run
fail with `replace-all-not-permitted`, by exempting the create-plan step from
develop Step B's pre-dispatch `in_progress` update, adding a deterministic
interrupt-recovery rule to the create-plan phase protocol, and pinning the
deliberately unchanged consumer side (rule 5 and the validator) with
regression tests.

## Technology Stack

- **Language / Framework**: Markdown (plugin SSOT prose), Python 3 standard
  library `unittest` (repository-root `tests/`), JSON (validator fixtures and
  the plugin manifest).
- **Key libraries**: none. This change introduces **no new dependency**, so
  there is no license to record; `project.license` is `none`, therefore no
  license compatibility constraint applies to this feature.

## Layer Structure

Three layers with a one-way dependency direction. This feature changes only
the first two; the third is frozen and merely pinned.

| Layer | Artifacts | Responsibility |
|---|---|---|
| L1 Producer | `em-workflow/skills/develop/SKILL.md` (Step B) | Decides what the create-plan step's `status` is at planner-dispatch time |
| L2 Recovery | `em-workflow/references/phases/create-plan-phase.md` (§3), `em-workflow/references/phase-state.md` | Normalizes an interrupted status before dispatch, and describes Step B's placement without contradicting it |
| L3 Consumer | `em-workflow/references/workflow-patch.md` (rule 5 / `replace_all` permission conditions), `em-workflow/scripts/validate-worker-output.py` (dry-run apply permission check) | Reads that status and permits or rejects a `replace_all` patch |

Allowed direction: L1 and L2 may **cite** L3 by document and section name;
they must never restate L3's condition text (NFR3). L3 never references L1 or
L2. Nothing in this feature moves a responsibility between layers.

## Shared Components

The "components" of this feature are three normative statements. Every task
below implements or relies on them, so they are pinned here rather than in any
single task plan.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| **S1 create-plan status discipline** | create-plan is never `in_progress` at planner-dispatch time; its entry status is carried into dispatch unchanged | Precondition: at dispatch, the create-plan step status is `pending` (first planning) or `needs_update` (explicit re-plan). Postcondition: the step becomes `completed` (with `completed_at_commit`, rule R2) only after the proposed patch has been applied and committed successfully; if either fails, the status is left as it was | task0001 states it; task0002 relies on it; task0003 pins the consumer that reads it |
| **S2 interrupt normalization** | An entry status of `in_progress` is resolved before any dispatch decision | Precondition: on entry the create-plan step is `in_progress`. Postcondition: if the proposed patch is **not** applied, the step is reset to `pending`, that reset is committed, and only then is the planner dispatched; if the patch **is** already applied, no reset happens and only the transition to `completed` is performed, per create-plan-phase.md §11 and phase-state.md's Resume decision table (`applying_patch`, applied) | task0002 defines it; task0001 must not state anything that contradicts it |
| **S3 rule-5 citation discipline** | The permission conditions have exactly one owner | Any document that needs the `replace_all` permission conditions cites `references/workflow-patch.md`'s `replace_all` permission-conditions section / application rule 5 by name. Copying its condition wording (the `pending` / `needs_update` enumeration) into another document is a violation | task0001, task0002 (and the assertions added by both) |

## Conventions

- **Document language**: new prose matches the host document. `skills/develop/SKILL.md`
  is Japanese; `references/phases/create-plan-phase.md`, `references/phase-state.md`
  and `references/workflow-patch.md` are English. Do not switch a document's
  language.
- **Step B layout**: the exemption paragraph reuses the layout of the existing
  design-system backfill rationale block in the same section — a bold label
  followed by the reasons — so the two exceptions read alike.
- **Tests**: repository-root `tests/`, standard-library `unittest` only, no
  third-party runner, no new dependency. Documentation requirements are
  verified by literal/structural assertions over the markdown; validator
  requirements by running the CLI against fixture directories. Each new test
  class names the acceptance criterion it covers, following the existing
  files' convention.
- **Existing literal assertions are a contract**: several tests locate text by
  exact substring. Changing a document that another task's test file asserts
  on is a reportable plan deviation, never a silent cross-task edit.
- **Error-handling policy**: unchanged. No new failure mode is introduced; a
  patch or commit failure leaves the step status untouched (S1).

## Cross-task Design Decisions

### D1 — Producer-side change only

The contradiction is resolved by changing what the producer (Step B) does,
never by relaxing the consumer (rule 5 / the validator). Consequence for every
task: `references/workflow-patch.md` and `em-workflow/scripts/validate-worker-output.py`
must remain byte-identical at the end of this feature. Any task that finds
itself wanting to edit either file has misread its scope.

### D2 — The generic Step B sentence is narrowed, not rewritten

The Step B sentence that states the generic "update the step to `in_progress`
before executing it" rule is currently located by an exact-substring assertion
in `tests/test_develop_skill_rewiring.py` (the backfill-ordering check). The
create-plan exemption is therefore added as a separate, clearly labelled block
placed after that sentence, narrowing it, instead of rewriting the sentence in
place. Rationale: the ordering assertion keeps working, the generic rule stays
readable, and the exception reads as an exception. If the implementer
concludes the sentence itself must change, the paired test file is inside the
same task's file set (D3), so the change stays coherent within one task.

### D3 — One document, one paired test file, one task

Test ownership is assigned so that no test file is claimed by two tasks and no
task edits a document another task also edits:

| Document | Paired test file | Owning task |
|---|---|---|
| `skills/develop/SKILL.md` | `tests/test_develop_skill_rewiring.py` | task0001 |
| `references/phases/create-plan-phase.md` | `tests/test_phase_protocols.py` | task0002 |
| `references/phase-state.md` | `tests/test_phase_state_doc.py` | task0002 |
| `references/workflow-patch.md` (frozen) | `tests/test_workflow_patch_doc.py` | task0003 |
| `scripts/validate-worker-output.py` (frozen) | `tests/test_validate_worker_output.py` + fixture directories | task0003 |

Since all tasks run in parallel in separate worktrees, this partition is what
keeps them conflict-free.

### D4 — The FR7 consistency sweep result is pre-computed

The planner swept every occurrence of the `in_progress` token under
`em-workflow/`. Exactly one place restates the pre-dispatch update in a way
that contradicts S1: the `project.design_system backfill` section of
`references/phase-state.md`, which describes Step B's normal sequence as
"select the first incomplete step → set it `in_progress` → execute the phase"
and, in its numbered steps, tells the reader to proceed to set the step
`in_progress` after backfill — and `create-plan` is one of the two
backfill-target steps. task0002 owns that single edit. Everything else
inspected is not a contradiction and must be left alone: `workflow-schema.md`
(status vocabulary and task-status transitions), `implement-phase.md` (task
statuses), the queue guard hook (reads the `implement` step only),
`workflow-patch.md` (the rule-5 condition text itself). Finding any further
contradiction is a reportable deviation, not licence to widen scope.

### D5 — Exactly one task owns the version bump

task0003 owns `em-workflow/.claude-plugin/plugin.json` (0.1.34 → 0.1.35). The
root `.claude-plugin/marketplace.json` carries no `version` field for
em-workflow and is not touched by any task. A second task bumping the version
in parallel would produce a pointless merge conflict.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Editing Step B breaks an exact-substring assertion that another task owns | Medium | Medium | D2 (narrow, do not rewrite) + D3 (the paired test is in the same task) |
| The exemption lands in Step B while a sibling SSOT still asserts the generic rule, recreating the contradiction in a new place | Medium | High | D4 pre-computed sweep, owned by task0002; FR7 is verified explicitly in VERIFICATION.md |
| New validator fixtures fail on a staleness/anchor error rather than the intended permission error, so the regression proves nothing | Medium | Low | task0003 asserts the specific `replace-all-not-permitted` identifier and the create-plan-status wording, not merely a non-zero exit |
| Two documents drift into subtly different statements of the same rule | Low | Medium | S1/S2 are stated once here; both tasks implement against them rather than against each other's prose |
| A frozen file is edited "for consistency" | Low | High | D1 states the freeze; task0003's criteria include the frozen files being unmodified |

## Open Questions

- [ ] None blocking. EC5 was checked during planning (the queue guard hook
      reads only the `implement` step and task statuses), and EC3's two
      sources already agree; both remain as verification items rather than
      open design questions.

## Rework Round 1 (review finding `cmp-stopcond3-universal-claim`)

Appended by the review-sourced rework of round 1. Everything above this
heading is unchanged; S4 and D6 below extend the Shared Components and
Cross-task Design Decisions sections respectively, because task0004 edits a
document whose cross-task contracts (S1, S3, D2, D3) are stated there.

### S4 — Automatic-re-entry carve-out

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| **S4 automatic-re-entry carve-out** | Separates the `needs_update` values that mean "a user must intervene" from those a phase protocol set in order to have its phase re-entered automatically | Precondition: Step B has selected a step whose status is `needs_update`. Postcondition: the loop stops (stop condition 3) UNLESS the owning phase protocol prescribes automatic re-entry for the transition that set it — today exactly the create-plan route back to planning (`references/implement-phase.md`) and the create-spec rework spec-change transition (`references/rework-task-synthesis.md` §10, `references/contracts/rework-planner-contract.md`), the latter distinguished from a `create-spec.stalled` abort by an unconsumed spec-change record in `phase-state/rework.yaml`. In the carve-out case the phase is executed with the entry status unchanged | task0004 states it; it generalizes the precedence note task0001 introduced |

S4 is orthogonal to **S1**: S1 governs which step skips the pre-dispatch
`in_progress` update (create-plan, and only create-plan), while S4 governs
which `needs_update` values stop the develop loop. Widening either one into
the other is a contract violation — in particular, S4's generalization must
never be read as making a second step exempt under S1.

S4 is stated in `skills/develop/SKILL.md` by **citation** of the two owning
documents, under the same rule-5 citation discipline as **S3**: the rework
spec-change transition's five steps and per-step status assignments belong to
`references/rework-task-synthesis.md` / `references/contracts/rework-planner-contract.md`
and are never reproduced in Step B. Both documents are frozen for this feature
(NFR1 names `rework-task-synthesis.md` explicitly): the fix makes SKILL.md
consistent with them, never the reverse.

### D6 — Sequential rework inherits task0001's file set

D3's "one document, one paired test file, one task" partition exists to keep
tasks running in parallel worktrees conflict-free. task0004 is a rework task
dispatched after task0001 … task0003 are all `merged`, and it is the only
pending task, so it inherits — rather than shares — task0001's pair:

| Document | Paired test file | Owning task after rework round 1 |
|---|---|---|
| `skills/develop/SKILL.md` | `tests/test_develop_skill_rewiring.py` | task0004 (inherited from the merged task0001) |

Consequence: task0004 may edit both files, and must keep every pre-existing
assertion in that test file passing (task0001's acceptance criteria remain in
force). No other document or test file changes owner, and D1's freeze on
`references/workflow-patch.md` and `scripts/validate-worker-output.py` stands
unchanged. D5 also stands: the version bump remains task0003's single
0.1.34 → 0.1.35 change, and this rework ships inside the same feature merge
without a second bump.

## Rework Round 2 (verify failed items `TS-5` / `AC5`)

Appended by the verify-sourced rework. Everything above this heading is
unchanged. D7 below extends the Cross-task Design Decisions section, because
task0005 brings four repository-root test files that no existing task owns
into the feature, and one of them asserts on a document D3 already assigns to
another task.

### D7 — Verify-sourced rework: fix direction and test-file ownership

**Fix direction.** The five suite failures are stale assertions: each pins text
that an intentional, already-merged change replaced, and all five fail
identically at `workflow[implement].base_commit` (`ca1a189`), so none is this
feature's regression. The production documents and agent files are correct as
they stand. Every fix therefore runs **test → current production text**, never
the reverse. Where an assertion still guards something meaningful, it is
re-expressed against the current text; where the guarded behaviour no longer
exists at all, it is replaced by an assertion over the behaviour that took its
place. Deleting, skipping or hollowing out an assertion to reach exit 0 is a
contract violation, not a fix. This is a strict extension of **D1**'s
producer-side-only principle: D1 froze the consumer side of the create-plan
contradiction; D7 freezes the production side of every assertion this rework
touches.

**Test-file ownership.** D3's "one document, one paired test file, one task"
partition is extended, not amended:

| Production artifact (frozen, read-only) | Paired test file | Owning task |
|---|---|---|
| `em-workflow/agents/designer.md`, `em-workflow/agents/implementation-planner.md` | `tests/test_refitted_worker_agents.py` | task0005 |
| `em-workflow/README.md` | `tests/test_planner_designer_worktree_docs.py` | task0005 |
| `em-workflow/references/batch-mode.md` | `tests/test_batch_policies.py` | task0005 |
| `em-workflow/skills/develop/SKILL.md` (Step A) | `tests/test_review_implement_develop_lock_contracts.py` | task0005 |

The last row is the only place this rework meets an existing task: D3 and D6
give `em-workflow/skills/develop/SKILL.md` and
`tests/test_develop_skill_rewiring.py` to task0004. The boundary is by
**document section and by test file**, and it is asymmetric — task0005 owns a
second test file that *reads* SKILL.md's Step A, while the document itself
stays task0004's and is not in task0005's file set at all. task0005 must
therefore not edit SKILL.md, and must leave every assertion in
`tests/test_develop_skill_rewiring.py` (Step B) untouched. Since task0001 …
task0004 are all `merged` and task0005 is the only pending task, this is a
sequential inheritance of read access, not a parallel share.

D5 continues to stand: task0005 touches only repository-root `tests/`, nothing
under `em-workflow/`, so FR9's single 0.1.34 → 0.1.35 bump is not revisited.
