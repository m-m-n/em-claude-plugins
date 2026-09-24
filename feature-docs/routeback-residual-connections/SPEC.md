# Feature: routeback-residual-connections

## Overview

Close the three connections left unproven in `em-workflow/references/implement-phase.md` I.2.a / I.2.c after PR #7 (routeback-reset-scope-consistency) moved the route-back path to a single derivation source. The change is documentation and document-contract tests only, plus the plugin version bump. Requirements document: `feature-docs/routeback-residual-connections/REQUIREMENTS.md`.

## Objectives

- Close the three connections left unproven in `em-workflow/references/implement-phase.md` I.2.a / I.2.c after PR #7 (routeback-reset-scope-consistency) moved the route-back path to a single derivation source (verify items MANUAL-1 / MANUAL-2 / MANUAL-3; review stable_ids 69fc571959dc36a1, e3a4f2b026841bf6, 477a18556a3587e3, 0acedde04c24cb8d, 5a9c94c87a6f7c4f, cbe1e5e8ca5cf4df).
- Every claim on the route-back path follows from what the document verifies, and each connection is pinned by a document-contract test.

## Acceptance Criteria

No user stories apply (documentation-and-test-only change to a protocol reference file).

- [ ] AC-1: I.2.a's reference to the I.2.c gate reads `below` and resolves to the I.2.c conjunct that blocks on a journal `merged` last event. No reference to the I.2.c gate as `above` remains in I.2.a. (Already true on base; pinned by test.)
- [ ] AC-2: I.2.a contains a sentence stating that the recycled-task-id carve-out applies only when the journal's last event is `failed`, so Step I.2.b step 1's `merged` (and in-flight) classification never consults it and the carve-out / gate / reconciled-state chain terminates.
- [ ] AC-3: The I.2.c reset target set names both `failed` sources, with the reconciled-state literal verbatim and leading. One sentence cites Step I.2.b step 3 for the divergence and ties the union to the postcondition and to workflow-patch.md's `replace_all` permission conditions over workflow.yaml statuses.
- [ ] AC-4: The cleanup sentence gives the gate as the reason reconciled-`merged` tasks are excluded, and both retained cleanup literals survive.
- [ ] AC-5: The unqualified "confirmed not merged" is gone. The not-merged claim is qualified by the two sources. A residual sentence placed after the leftover-state sentence records the merged-branch-without-journal-event window as undetected.
- [ ] AC-6: Document-contract tests equivalent to TS-10 / TS-11 / TS-12 exist under `tests/`, with a negative proof and a non-vacuity guard for each new matcher.
- [ ] AC-7: `plugin.json` and `marketplace.json` both carry em-workflow version 0.2.1.
- [ ] AC-8: `python3 -m unittest discover -s tests` passes from the repository root, with the two edit-forbidden modules unmodified.

## Technical Requirements

### Functional Requirements

- **FR1:** I.2.a forward reference to the I.2.c gate points below, at the conjunct that blocks on a journal `merged`. Step I.2.a's recycled-task-id paragraph refers to the I.2.c route-back gate as `below` and names a site in I.2.c that actually blocks route-back on a `merged` journal last event. Current main already meets this: the text reads "Because Step I.2.c's route-back gate below blocks route-back whenever any task's journal last event is `merged` — read from the journal directly, independent of the ancestor check", and I.2.c's third conjunct defines exactly that block. The old "(the widened I.2.c gate above)" wording is gone. This requirement therefore needs no document edit. It asks only for a regression test that pins the direction and the referent.
- **FR2:** The carve-out / gate / reconciled-state ownership chain has a stated termination point. I.2.a gains one sentence that ends the chain I.2.a recycled-task-id carve-out <- I.2.c gate <- I.2.b step 1 reconciled state <- I.2.a carve-out. The sentence says the carve-out reclassifies only a `failed` journal last event paired with workflow.yaml `pending`. It never touches a `merged` or `launched` last event. So Step I.2.b step 1's `merged` and in-flight classifications, which are the gate's inputs, never consult the carve-out, and the chain is not circular. Current main has no such sentence, so this requirement is still open.
- **FR3:** The route-back reset target set covers both `failed` sources, connected to the postcondition and `replace_all`. In I.2.c's route-back write set, the reset target set is the union of two sets: every task whose Step I.2.b step 1 reconciled state is `failed` (this literal stays verbatim and is the leading member), and every task that workflow.yaml reports `status: failed`. One sentence says the two sets can diverge, citing Step I.2.b step 3 as the owning rule for the workflow.yaml `failed` write without restating it. The same sentence says the postcondition "no task is left `merged` or `in_progress` or `failed`" and `references/workflow-patch.md`'s `replace_all` permission conditions / protocol-error rule are read off workflow.yaml's own statuses, and covering both sets is what makes the postcondition true.
- **FR4:** Excluding reconciled-`merged` tasks from cleanup is stated as a consequence of the gate. The cleanup sentence names the gate above as the reason no reconciled-`merged` task is ever a cleanup target: the gate already refused route-back for any such task, so the set the write set just reset contains none. The gate stays the single owner of the decision. Both literals survive: "clean up worktrees and branches for exactly the tasks the write set just reset" and "a task whose reconciled state is `merged` is never a cleanup target, whatever workflow.yaml says".
- **FR5:** The cleanup not-merged claim matches what is verified, and the residual is recorded. The unqualified "confirmed not merged" is replaced by a claim limited to the two sources this path reads: workflow.yaml `status` and Step I.2.b step 1's reconciled state. A residual-state sentence follows the existing "this order's one residual leftover state" sentence. It records what neither source can see: a task whose merge already advanced the integration branch (merge-task.sh's `git update-ref`) while its `merged` event never reached the journal. That happens when the script's journal write fails, which the script reports as a warning and still exits 0, or when the implementer stops in the window between the ref update and the journal write with no report. Such a task is indistinguishable here from a failed task, so route-back can still reset it and delete its branch. The sentence presents this as a known residual that the gate does not close. No new verification step and no behaviour change is added.
- **FR6:** Document-contract tests equivalent to TS-10 / TS-11 / TS-12. New stdlib-only unittest assertions in `tests/test_routeback_reset_scope_consistency.py` cover FR1 to FR5 in the established D8 style. Each new-wording literal is one module-level constant, read by both the positive assertion and a negative proof. Each negative proof runs against a verbatim pre-change excerpt of implement-phase.md captured at base revision 9f9502487a8da29220aece87f253058becda432e. Each excerpt has a non-vacuity guard asserting a retained anchor. The docstring holds the matcher inventory and records the capture revision.
- **FR7:** Plugin version bump. Bump em-workflow from 0.2.0 to 0.2.1 (patch) in `em-workflow/.claude-plugin/plugin.json` and in the em-workflow entry of `.claude-plugin/marketplace.json`, with identical values, in the same change. This replaces task0003's "no further version bump" item (IMPLEMENTATION.md D9 item 4), which no longer applies because 0.1.39/0.2.0 have already shipped.

### Non-Functional Requirements

- **NFR1 - Documentation-only:** No change to `em-workflow/scripts/merge-task.sh`, hooks, agents, skills or any runtime behaviour. The only plugin file changed besides the manifests is `em-workflow/references/implement-phase.md`.
- **NFR2 - Edit-forbidden modules:** `tests/test_recycled_task_id_consistency.py` and `tests/test_implement_routeback_gate.py` are not modified, and every assertion in them keeps passing.
- **NFR3 - Existing assertions:** Every pre-existing assertion in `tests/test_routeback_reset_scope_consistency.py` and `tests/test_routeback_reset_scope_version_bump.py` keeps passing unchanged.
- **NFR4 - Forbidden substrings in I.2.c:** The normalized I.2.c section contains neither the substring "append" nor "rework". This rules out "journal append", "appended" and "reworked" in the new prose.
- **NFR5 - I.2.c anchors:** Anchors that must be preserved in I.2.c: the first `tasks.{T}.status` occurrence has `pending` within the next 60 normalized characters (so no earlier mention of that token is added); the four write tokens precede `git worktree remove --force`; order is gate < ROUTEBACK_TIP < reset --hard < "make one ordered workflow.yaml write set" < "Commit that write set next, BEFORE any cleanup" < "Only once that commit"; `git branch -D` occurs exactly once, between the cleanup-scope phrase and the leftover-state sentence; commit-docs.sh < git worktree remove --force < "End the phase with a"; nothing after "When the gate does not hold" contains the write-set / cleanup / ROUTEBACK_TIP tokens; the heading and the batch-mode paragraph stay the byte-identical tail; the retained gate literals survive.
- **NFR6 - I.2.a anchors:** Anchors that must be preserved in I.2.a: the raw `Select` line-wrap literal is not reflowed. The span from "Because Step I.2.c's route-back gate below blocks route-back whenever any task's journal last event is `merged`" to the first "correctly scoped to `failed` only." keeps exactly one "Because " and exactly one " so ", so the FR2 sentence goes after that span. The unreachability sentence, RECURSION_INVARIANT_PHRASE, "This carve-out is deliberately scoped to `failed` only", the in-flight sentence, TWO_PARTIES_PHRASE and the hook-group slices survive. I.2.a contains none of "task0001", "renumber", "governs only", "the third route-back gate conjunct above", or "Because route-back proceeds only when no task is `merged` under either source".
- **NFR7 - No git command lines:** No line of implement-phase.md, after stripping indentation and backticks, starts with `git ` and contains `commit` or `add -A`. Prose mentioning `git update-ref` stays inside a sentence.
- **NFR8 - Cite, do not restate:** New sentences cite owning rules (Step I.2.b step 3, workflow-patch.md's `replace_all` permission conditions, merge-task.sh's journal-write behaviour) and do not restate them.
- **NFR9 - Test placement:** Tests use only the Python standard library, live in the repository-root `tests/`, and are discovered by `python3 -m unittest discover -s tests`.

## Implementation Approach

### Architecture

Not applicable. No runtime component changes (NFR1). The design step was skipped: documentation-and-test-only change to a protocol reference file, with no UI, visual or interaction design surface.

### Edit Sites

| Site | Requirement |
|------|-------------|
| `em-workflow/references/implement-phase.md` Step I.2.a (recycled-task-id paragraph) | FR1 (no edit; pinned by test), FR2 |
| `em-workflow/references/implement-phase.md` Step I.2.c (route-back write set) | FR3 |
| `em-workflow/references/implement-phase.md` Step I.2.c (cleanup) | FR4, FR5 |
| `tests/test_routeback_reset_scope_consistency.py` | FR6 |
| `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | FR7 |

Sites are identified by text, not by line number (A-6).

### Dependencies

**Internal Dependencies:**
- Step I.2.b step 1 (reconciled state) and Step I.2.b step 3 (workflow.yaml `failed` write): cited by FR2 / FR3 / FR5.
- `references/workflow-patch.md` `replace_all` permission conditions / protocol-error rule: cited by FR3.
- `em-workflow/scripts/merge-task.sh` (`git update-ref`, journal write behaviour): cited by FR5.
- `tests/test_recycled_task_id_consistency.py`, `tests/test_implement_routeback_gate.py`: invariants, not modified (NFR2, A-7).

**External Dependencies:**
- None (Python standard library only, NFR9).

### File Structure

```
em-workflow/
├── .claude-plugin/plugin.json          # FR7
└── references/implement-phase.md       # FR2, FR3, FR4, FR5
.claude-plugin/marketplace.json         # FR7
tests/
└── test_routeback_reset_scope_consistency.py   # FR6
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/routeback-residual-connections/**`
- `test-docs/routeback-residual-connections/**`

`feature-docs/routeback-residual-connections/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/routeback-residual-connections/**` covers `test-docs/routeback-residual-connections/{T}.tests.yaml`, the
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

### Unit Tests

- [ ] TS-1 (FR1, AC-1; equivalent of TS-12, direction half; document contract): Normalized I.2.a contains the journal-`merged` premise naming Step I.2.c's gate as `below`, and no I.2.c-gate reference reads `above`. The referenced conjunct phrase exists in normalized I.2.c. Negative proof against the pre-change wording already captured in the repo ("(the widened I.2.c gate above)").
- [ ] TS-2 (FR2, AC-2; equivalent of TS-12, termination half; document contract): The chain-termination sentence is present in I.2.a after the single-causal-construction span. The recursion-invariant sentence still follows "can never arise.". The carve-out and in-flight sentences survive. Negative proof against a verbatim base-revision I.2.a excerpt.
- [ ] TS-3 (FR3, AC-3; equivalent of TS-10; document contract): The reset target set names the reconciled-state literal (leading) and the workflow.yaml `status: failed` member. The divergence/postcondition sentence cites Step I.2.b step 3 and `replace_all`. The 60-character window and the four write-token order still hold. Negative proof against the base write-set excerpt.
- [ ] TS-4 (FR4, FR5, AC-4, AC-5; equivalent of TS-11; document contract): The cleanup sentence attributes the exclusion to the gate. The not-merged claim is source-qualified, and the bare "confirmed not merged" is absent. The residual sentence follows the leftover-state sentence. `git branch -D` still occurs exactly once inside the scoped sentence. "append"/"rework" are absent from I.2.c. Negative proof against the base cleanup excerpt.
- [ ] TS-5 (FR7, AC-7; JSON): Both manifests parse. The em-workflow version is strictly greater than 0.2.0 by per-component numeric comparison, and the two registries are equal. Negative proof with forged 0.2.0 and forged differing pairs.

### Integration Tests

- [ ] TS-6 (AC-8, NFR2, NFR3; suite): `python3 -m unittest discover -s tests` exits 0. git diff against the base shows neither edit-forbidden module changed.

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] EC-1 (MANUAL-1): workflow.yaml `status: failed` for a task with no journal event (a malformed or missing report written as `failed` by I.2.b step 3). Its reconciled state is unlaunched, so only the FR3 union puts it in the reset set. Without the union it stays `failed` and the re-plan hits workflow-patch.md's `replace_all` protocol error ("A `replace_all` received while any task is `in_progress` or `failed` is a protocol error").
- [ ] EC-2 (MANUAL-2): merge-task.sh advances the integration ref via `git update-ref` and then calls append_merged_event. A journal-write failure only prints a WARNING and exits 0. The "already contained" early exit also depends on that same journal write. If the implementer stops before the journal write with no report, the failure net records `failed`, the reconciled state is `failed`, the gate passes, and route-back resets and deletes the branch. The branch's commits are still reachable from the integration branch, so `git branch -D` loses no commits. The concrete harm is that an already-merged task is reset to `pending` and re-planned.
- [ ] EC-3: A task that falls in the FR3 union only through workflow.yaml `failed` with no journal event may have no worktree or branch. The current cleanup text does not say how `git worktree remove --force` / `git branch -D` behave on an absent target. Any runtime change is out of scope (NFR1).
- [ ] EC-4: The ancestor-check-failed case (journal `merged`, reconciled `failed`) stays blocked by I.2.c's third conjunct. The FR3 union must not turn it admissible, and it does not, because the gate is evaluated before the write set.

### Performance Tests

Not applicable.

## Security Considerations

Not applicable (documentation-and-test-only change).

## Error Handling

Not applicable (no runtime behaviour change, NFR1).

## Performance Optimization

Not applicable.

## Assumptions

All assumptions are reversible.

- A-1: MANUAL-2 is resolved by option (b): document the residual and weaken the claim. Option (a), a per-candidate `git merge-base --is-ancestor` check before cleanup, is not taken, as recorded in routeback-reset-scope-consistency IMPLEMENTATION.md D9 item 3. The task description's AC explicitly accepts "不足分の残余状態が明記されている".
- A-2: MANUAL-3's direction defect was already fixed on main by later work (test_recycled_task_id_consistency.py pins "Because Step I.2.c's route-back gate below ..." and asserts "the third route-back gate conjunct above" absent). This feature adds only the termination sentence and a pinning test, and does not re-edit the premise sentence.
- A-3: The orphaned task0003 worktree (`.claude/worktrees/em-workflow/routeback-reset-scope-consistency/task0003`) no longer exists. Its uncommitted edits are discarded and not reused.
- A-4: The version goes 0.2.0 -> 0.2.1 (patch: behaviour-clarifying documentation fix) per `.claude/rules/core-plugin-version-bump.md`. This overrides task0003's D9 item 4.
- A-5: New document-contract assertions (TS-10/11/12 equivalents) extend the existing module `tests/test_routeback_reset_scope_consistency.py` rather than a new module; every existing assertion in it keeps passing (orchestrator batch resolution after Codex consultation, recorded in `phase-state/batch-audit.yaml` as create-spec.test-module-placement). Its docstring line 19 ("confirmed not merged") is prose only, not an assertion.
- A-6: Line numbers in the task description (219 / 372 / 67) are stale against current main. The I.2.a premise is around line 249, I.2.c starts at line 787, and the exit-4 bullet is around lines 43-82. Sites are identified by text, not by line.
- A-7: The existing literal assertions in `tests/test_recycled_task_id_consistency.py` and `tests/test_implement_routeback_gate.py` are invariants and must not be modified (fact pinned by existing tests).
- A-8: Other version-bump modules not in the scan set (e.g. `tests/test_recycled_task_id_version_bump.py`) are assumed to assert a lower baseline plus equality in the same shape as `tests/test_routeback_reset_scope_version_bump.py`, so 0.2.1 keeps them green. Not verified directly because the file is outside reference_scan_targets.

## Out of Scope

- The failure-net gap where a watchdog kill leaves the journal stuck at `launched` (filed separately).
- Any change to merge-task.sh ordering, the journal writers, or hooks.
- I.2.b step 3's own precedence ambiguity between its "verified merged" and "report is failed/malformed" clauses (routeback-reset-scope-consistency SPEC.md A-2).

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Acceptance criteria AC-1 to AC-8 are met

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None.

## References

- Requirements: `feature-docs/routeback-residual-connections/REQUIREMENTS.md`
- `em-workflow/references/implement-phase.md` (Steps I.2.a / I.2.b / I.2.c)
- `em-workflow/references/workflow-patch.md` (`replace_all` permission conditions)
- `em-workflow/scripts/merge-task.sh`
- `feature-docs/routeback-reset-scope-consistency/IMPLEMENTATION.md` (D9)
- `feature-docs/routeback-reset-scope-consistency/tasks/task0003.md`
- `.claude/rules/core-plugin-version-bump.md`
