# Feature: abort-phase-terminal

## Overview

`em-workflow/references/implement-phase.md` Step I.2.c's rejected path claims its terminal is `the same terminal as the "abort phase" option below`, but only the rejected path actually writes `implement` back to `failed`; Step I.1 sets `implement: in_progress` and the abort option never writes it back. This feature makes that equivalence claim true by giving the `- **abort phase**` option — and Step I.2.c's batch-mode second-failure abort — the same explicit refresh -> write `implement: failed` -> `commit-docs.sh` -> report terminal, and by synchronizing `em-workflow/references/batch-mode.md`'s `implement.failed-task` row with it. The deliverable is prose in two reference documents, updated byte pins in three Python test modules, and a lockstep version bump in two JSON manifests.

Requirements document: `feature-docs/abort-phase-terminal/REQUIREMENTS.md`.

## Objectives

- Make the equivalence claim in implement-phase.md Step I.2.c's rejected path — `the same terminal as the "abort phase" option below` — actually true, by giving the abort option the same explicit refresh -> write `implement: failed` -> commit-docs.sh -> report terminal that the rejected path already has. Today Step I.1 sets `implement: in_progress` and only the rejected path writes it back to `failed`, so choosing abort leaves the real status at `in_progress`. (BO1)
- Remove the develop-loop hazard the mismatch creates: with `implement` left `in_progress`, develop's stop condition 3 (fires on `failed`/`needs_update`) never fires after abort, so Step B re-runs implement and I.2.c re-offers the three choices until stop condition 2 (same step twice without progress) trips. After the fix, the stopping point after abort must be readable from the prose alone and be stop condition 3. (BO2)
- Restore the batch-mode grounding for "a second failure on the same task -> abort phase", and keep implement-phase.md I.2.c and batch-mode.md's `implement.failed-task` row describing one and the same terminal. (BO3)

## User Stories

### US1: Aborting the implement phase interactively leaves a readable, committed terminal state

As an agent executing the implement phase, I want the `- **abort phase**` option in Step I.2.c to prescribe the same refresh / `implement: failed` write / `commit-docs.sh` / report sequence the rejected path prescribes, so that the phase's real status matches what the document claims and develop stops via stop condition 3.

**Acceptance Criteria:**
- [ ] AC-1 (FR1, NFR2): In implement-phase.md's I.2.c section the `- **abort phase**` bullet states, in order, the worktree refresh, the tip capture, the `implement` step `status: failed` write, and a `commit-docs.sh` invocation carrying that captured tip as its third argument; the phrase `` leave `implement` as `failed` for manual handling `` no longer appears anywhere in the section.
- [ ] AC-3 (FR3): Both abort paths state that the terminal status write and its commit are the only side effect — explicitly no `create-plan` `needs_update`, no task-status/notes reset, no worktree or branch cleanup; the rejected path's existing `There is no route-back write set, no worktree/branch cleanup and no route-back commit on this path` sentence and its `the terminal status write and its own commit are the ONLY side effect` clause are unchanged.
- [ ] AC-4 (FR4): Both abort paths name develop's stop condition 3 and state that it fires on the next Step B iteration reading `implement: failed`.
- [ ] AC-5 (FR5): The literal `the same terminal as the "abort phase" option below` is still present in the rejected-path branch.

### US2: Batch mode's second-failure abort is grounded in a single terminal description

As an agent executing the implement phase in batch mode, I want Step I.2.c's batch-mode paragraph and batch-mode.md's `implement.failed-task` row to describe one and the same terminal, so that neither document asserts a status that no write produces.

**Acceptance Criteria:**
- [ ] AC-2 (FR2): The I.2.c batch-mode paragraph describes the second-failure abort with the same refresh / write / `commit-docs.sh` / report sequence, still names the Non-packet gates table and `implement.failed-task`, and remains the last content of the section; the phrase "implement stays `failed`, report and stop" no longer appears there.
- [ ] AC-7 (FR7): batch-mode.md's `implement.failed-task` row describes the FR2 terminal and retains its gate id, its retry-once clause, its never-auto-route-back clause and its Full-detail pointer.

### US3: The change lands without breaking the document's byte pins or its recovery model

As a maintainer of the em-workflow plugin, I want the new commit call site enumerated on the bounded side of exit-4 recovery, every byte pin of the batch-mode paragraph updated in the same change, and the plugin version bumped in lockstep, so that the suite stays green and the plugin cache picks the change up.

**Acceptance Criteria:**
- [ ] AC-6 (FR6): The Branch & Worktree Model's exit-4 bullet enumerates the abort terminal status commit as bound by the bounded recovery, still names `Step I.1's baseline commit`, `Step I.2.b's wake-phase commit` and `Step I.2.c's rejected-path terminal status commit`, and still names Step I.2.c's route-back commit as the single carve-out; no closed-set claim about the number of exit-4-capable call sites is introduced.
- [ ] AC-8 (FR8): All three byte-pin literals — `tests/test_implement_routeback_gate.py`, `tests/test_recycled_task_id_consistency.py`, `tests/test_routeback_reset_scope_consistency.py` — equal the post-change batch-mode paragraph, and each module's pin assertion passes.
- [ ] AC-9 (FR9): `em-workflow/.claude-plugin/plugin.json` and the `em-workflow` entry in `.claude-plugin/marketplace.json` both read `0.1.44`.
- [ ] AC-10 (FR10): `em-workflow/skills/develop/SKILL.md`, `em-workflow/references/workflow-patch.md`, `em-workflow/scripts/validate-worker-output.py` and `feature-docs/routeback-gate-postcondition/SPEC.md` are unmodified by this change.
- [ ] AC-11 (NFR1, NFR3): The normalized I.2.c section contains neither `rework` nor `append`; implement-phase.md contains no bare `git commit` / `git add` lines.
- [ ] AC-12 (NFR5): `python3 -m unittest discover -s tests` exits 0.

## Technical Requirements

### Functional Requirements

- **FR1 — Interactive abort option gets an explicit write-and-commit terminal:** In `em-workflow/references/implement-phase.md` Step I.2.c, the `- **abort phase**` option must state the same ordered terminal the rejected path states: refresh the integration worktree (`git -C "$WT_ROOT/integration" reset --hard em-workflow/{feature}/integration`), capture the tip into a variable (mirroring the rejected path's `TERMINAL_TIP=$(git -C "$WT_ROOT/integration" rev-parse HEAD)`), set the `implement` step's `status` to `failed` in workflow.yaml, and commit exactly that write with `commit-docs.sh "$WT_ROOT/integration" "docs({feature}): ..." "$TERMINAL_TIP"`. The current wording `` leave `implement` as `failed` for manual handling `` — which asserts a status no write produces — must not survive. The bullet must still open with the literal `- **abort phase**` (two test modules use it as a slice end-anchor).

- **FR2 — Batch-mode abort gets the identical terminal:** Step I.2.c's batch-mode paragraph must describe the second-failure abort with the same refresh -> write `implement: failed` -> `commit-docs.sh` -> report-and-stop sequence rather than the present "implement stays `failed`, report and stop". The paragraph must remain the final content of the I.2.c section (all three byte-pin assertions slice from `` Batch mode (`references/batch-mode.md` `` to the section end), and must keep naming `references/batch-mode.md`'s Non-packet gates table and the `implement.failed-task` gate id.

- **FR3 — Abort's side-effect set is bounded to the terminal write and its commit:** Both abort paths must state that the terminal status write and its own commit are the ONLY side effect: no route-back write set, no `create-plan: needs_update`, no `tasks.{T}.status` reset, no `tasks.{T}.notes` failure-reason write set, and no worktree/branch cleanup (`git worktree remove` / `git branch -D`). This mirrors the rejected path's existing `There is no route-back write set, no worktree/branch cleanup and no route-back commit on this path` sentence, which must remain intact where it stands.

- **FR4 — The post-abort stopping point is stated uniquely:** Both abort paths must name develop's stop condition 3 as the stopping point and state that it fires on the NEXT Step B iteration reading `implement: failed` — the same formulation the rejected path already uses (`` reports and returns control to the user via develop's stop condition 3, which fires on the next Step B iteration reading `implement: failed` ``). This is required because `skills/develop/SKILL.md` Step B's 「停止条件 3 との優先関係」 evaluates stop condition 3 once, at the point Step B identifies the step it is about to run, and does not re-fire on a status intentionally held during that step's own phase execution.

- **FR5 — The equivalence claim is kept, not deleted:** The chosen direction is the write-side fix, not the claim-deletion alternative offered in finding dbb12002e43e113d. The rejected path's sentence `the same terminal as the "abort phase" option below` must survive verbatim; after FR1/FR2 it is a true statement. (It is additionally pinned as `ABORT_PHASE_TERMINAL_PHRASE` in `tests/test_recycled_task_id_consistency.py` L143 and asserted present in the rejected-path slice at L350.)

- **FR6 — The new commit call site falls on the bounded side of exit-4 recovery:** The Branch & Worktree Model's exit-4 recovery bullet (implement-phase.md L43-80) must enumerate the new abort terminal status commit among the call sites bound by the bounded recovery (refresh, re-capture tip, re-apply the same transition re-derived from source, retry once; a second exit 4 stops the phase with a report). The single carve-out must remain exactly Step I.2.c's route-back commit — the abort call site is never added to the carve-out, and the existing enumeration entries (`Step I.1's baseline commit`, `Step I.2.b's wake-phase commit`, `Step I.2.c's rejected-path terminal status commit`) must all survive. The enumeration is introduced by `for example` and is not closed, so adding an entry is admissible; the withdrawn closed-set claim `` the three `commit-docs.sh` call sites in this phase where exit 4 can occur `` must not reappear.

- **FR7 — batch-mode.md's implement.failed-task row is synchronized:** `em-workflow/references/batch-mode.md`'s Non-packet gates row for `implement.failed-task` (L60) currently reads `` A second failure on the SAME task → **abort phase** (`implement` stays `failed`) ``. It must be restated to the FR2 terminal (the `implement: failed` write plus its commit), keeping the row's gate id `implement.failed-task`, its `Auto-select **retry** once per task` clause, its `Route-back-to-planning is never taken automatically` clause, and its `` Full detail: `references/implement-phase.md` Step I.2.c `` pointer, so `tests/test_batch_policies.py`'s Non-packet-gate id list and its (description, substring) pairing keep matching.

- **FR8 — Every byte pin of the I.2.c batch-mode paragraph is updated:** The batch-mode paragraph is pinned byte-identically in THREE test modules, all of which must be updated to the post-change text in the same change: (a) `tests/test_implement_routeback_gate.py` — module constant `PRE_CHANGE_BATCH_MODE_PARAGRAPH` (L111-120), asserted by `test_batch_mode_paragraph_is_byte_identical` (L706-710); (b) `tests/test_recycled_task_id_consistency.py` — module constant `PRE_CHANGE_BATCH_MODE_PARAGRAPH` (L116-125), asserted by `test_batch_mode_paragraph_is_byte_identical_tail` (L480-484); (c) `tests/test_routeback_reset_scope_consistency.py` — function-local literal inside `test_batch_mode_paragraph_is_byte_identical_tail` (L594-613). Each pin asserts equality against the section slice starting at `` Batch mode (`references/batch-mode.md` `` and running to the end of the I.2.c section.

- **FR9 — Plugin version bump in lockstep:** Because files under `em-workflow/` change, `em-workflow/.claude-plugin/plugin.json` `version` and the `em-workflow` entry's `version` in root `.claude-plugin/marketplace.json` must both move from the current `0.1.43` to `0.1.44` in the same change. `tests/test_implement_routeback_gate.py::TestPluginVersionBumpedInLockstep` asserts the two values are equal and that (major, minor) == (0, 1) with patch > 42, so the two files must never diverge.

- **FR10 — Synchronization scope, exactly four documents, one explicit non-goal:** The prose change set is exactly: (1) `em-workflow/references/implement-phase.md` Step I.2.c's `- **abort phase**` bullet (FR1), (2) the same section's batch-mode paragraph (FR2), (3) the same file's Branch & Worktree Model exit-4 recovery bullet (FR6), and (4) `em-workflow/references/batch-mode.md`'s `implement.failed-task` row (FR7). Explicit NON-GOAL: `em-workflow/skills/develop/SKILL.md` is not edited — in particular stop condition 5's parenthetical 「batch: 三択の代わりにタスクごと 1 回だけ自動 retry、2 回目の failed で中断 — `batch-mode.md` の Non-packet gates 表、`implement.failed-task`」 (SKILL.md L38-40) stays unchanged, since it describes the batch gate's selection mechanics and already delegates the terminal's detail to batch-mode.md. Stop conditions 2 and 3 and Step B's 「停止条件 3 との優先関係」 are likewise untouched. Also frozen and untouched: `em-workflow/references/workflow-patch.md` and `em-workflow/scripts/validate-worker-output.py`. Out of scope entirely: exit-4 recovery applicability (findings 2394334a18ac6901 / 397c2a098d705a55) and any revision of `feature-docs/routeback-gate-postcondition/SPEC.md` (298809a29d50c663 and siblings) — both are separately filed tasks.

### Non-Functional Requirements

- **NFR1 - Forbidden tokens in I.2.c:** The normalized I.2.c section must contain neither the substring `rework` nor `append` anywhere, enforced by `tests/test_recycled_task_id_consistency.py::test_no_rework_or_append_anywhere_in_i2c` and, over the rejected-path slice, by `tests/test_implement_routeback_gate.py::test_no_rework_or_append_handoff`. New abort wording must avoid those substrings, including inflections.

- **NFR2 - Structural anchors preserved:** `### I.2.c: Failed handling` stays byte-identical; the abort bullet keeps the exact opening `- **abort phase**`; the rejected-path marker `When the gate does not hold` and its asserted phrases (`` create-plan` is NOT set to `needs_update` ``, `` sets the `implement` step's `status` to `failed` ``, `the single write this path makes`, `commits exactly that write`, `No retry loop, no alternative recovery route, and no degraded route back is offered`) stay present; the batch-mode paragraph stays the section's final content; the paragraph after the option list (`There is NO skip option: …`) stays.

- **NFR3 - No bare git commit/add lines:** `tests/test_implement_routeback_gate.py::test_no_bare_git_commit_or_add_lines` scans the whole implement-phase.md; every commit the new prose prescribes must go through `commit-docs.sh`, never a raw `git commit` or `git add -A` line.

- **NFR4 - Documentation-only change:** No runtime behavior code changes: `em-workflow/scripts/commit-docs.sh` (whose RECOVERY CONTRACT already names implement-phase.md I.2.c's route-back commit as the single unreachability carve-out) is not modified, and neither are the hooks or any other script. The change set is prose plus the three test modules plus the two version manifests.

- **NFR5 - Suite green:** `python3 -m unittest discover -s tests` passes from the repository root with no external dependencies (test/README.md: Python standard-library unittest only).

- **NFR6 - Internal consistency of the terminal description:** The abort terminal, the rejected-path terminal, and batch-mode.md's row must describe one and the same sequence; no document may state a terminal the others contradict, and no document may claim `implement` reaches `failed` without naming the write that produces it.

## Implementation Approach

### Architecture

This feature has no runtime component. The artifacts it changes are agent-facing protocol documents and the tests that pin them:

```
em-workflow/references/implement-phase.md
├── Branch & Worktree Model
│   └── exit-4 recovery bullet (L43-80)          <- FR6: enumerate abort terminal commit
└── ### I.2.c: Failed handling
    ├── option list
    │   └── - **abort phase**                    <- FR1: explicit write-and-commit terminal
    ├── "There is NO skip option: …" paragraph   (unchanged, NFR2)
    ├── "When the gate does not hold" branch     (unchanged, NFR2 / FR3 / FR5)
    └── "Batch mode (`references/batch-mode.md`" <- FR2: identical terminal, stays last

em-workflow/references/batch-mode.md
└── Non-packet gates table
    └── `implement.failed-task` row (L60)        <- FR7: synchronized to the FR2 terminal

tests/                                            <- FR8: three byte pins updated
├── test_implement_routeback_gate.py             (PRE_CHANGE_BATCH_MODE_PARAGRAPH, L111-120)
├── test_recycled_task_id_consistency.py         (PRE_CHANGE_BATCH_MODE_PARAGRAPH, L116-125)
└── test_routeback_reset_scope_consistency.py    (function-local literal, L594-613)

em-workflow/.claude-plugin/plugin.json            <- FR9: 0.1.43 -> 0.1.44
.claude-plugin/marketplace.json                   <- FR9: em-workflow entry 0.1.43 -> 0.1.44
```

### Terminal sequence (the single procedure both abort paths describe)

The rejected-path terminal at implement-phase.md L459-470 is the template both abort paths copy (assumption A1):

```
1. refresh   git -C "$WT_ROOT/integration" reset --hard em-workflow/{feature}/integration
2. capture   TERMINAL_TIP=$(git -C "$WT_ROOT/integration" rev-parse HEAD)
3. write     workflow.yaml: the `implement` step's `status` -> `failed`
4. commit    commit-docs.sh "$WT_ROOT/integration" "docs({feature}): ..." "$TERMINAL_TIP"
5. report    stop; control returns via develop's stop condition 3, which fires on the
             next Step B iteration reading `implement: failed`
```

Side effects outside steps 3 and 4 are excluded by FR3: no route-back write set, no `create-plan: needs_update`, no `tasks.{T}.status` reset, no `tasks.{T}.notes` failure-reason write set, no `git worktree remove` / `git branch -D`.

Per assumption A4, the two abort call sites (the interactive option and the batch second failure) may share one described procedure via an explicit cross-reference within I.2.c rather than duplicating the command sequence, provided each path's terminal is readable without leaving the section.

Per assumption A3, the commit message for the abort commit is left to implementation; it must be distinct enough from `docs({feature}): implement route-back gate rejected` to be legible in history. No test pins it, so no exact string is prescribed.

### Failure handling of the new commit call site

`commit-docs.sh` exit 4 at the new abort call site falls on the bounded side of the Branch & Worktree Model's exit-4 recovery (FR6): refresh, re-capture the tip, re-apply the same transition re-derived from source, retry once; a second exit 4 stops the phase with a report. The abort call site is never added to the single carve-out, which stays exactly Step I.2.c's route-back commit.

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/implement-phase.md` L459-470 (rejected-path terminal): the template the abort paths copy. Assumption A1 records it as verified present in the integration worktree following PR #6's merge.
- `em-workflow/references/implement-phase.md` L43-80 (Branch & Worktree Model exit-4 recovery bullet): supplies the recovery semantics for the new call site.
- `em-workflow/skills/develop/SKILL.md` Step B 「停止条件 3 との優先関係」 and stop conditions 2/3/5: read-only grounding for FR4 and FR10; not edited.
- `em-workflow/scripts/commit-docs.sh` RECOVERY CONTRACT: read-only; already names I.2.c's route-back commit as the single unreachability carve-out. Not modified (NFR4).

**External Dependencies:**
- None. Tests use the Python standard library's `unittest` only (test/README.md, assumption A7). No package manifest and no LICENSE file exist at the repository root (assumption A5), so no SPDX id is recorded.

## Declared Change Set

Feature-specific paths this change creates or modifies:

- `em-workflow/references/implement-phase.md`
- `em-workflow/references/batch-mode.md`
- `tests/test_implement_routeback_gate.py`
- `tests/test_recycled_task_id_consistency.py`
- `tests/test_routeback_reset_scope_consistency.py`
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/abort-phase-terminal/**`
- `test-docs/abort-phase-terminal/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`workflow.yaml`, `phase-state/`, `tasks/`, `reviews/roundN.yaml`,
`VERIFICATION.md`, `retrospect.yaml`, and the design artifacts the design
step produces. These are generated and owned by the phase documents and by
`references/phase-state.md`; this section cites them and restates none of
their rules.

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

Explicitly outside the declared change set (FR10, NFR4): `em-workflow/skills/develop/SKILL.md`, `em-workflow/references/workflow-patch.md`, `em-workflow/scripts/validate-worker-output.py`, `em-workflow/scripts/commit-docs.sh`, the hooks, and `feature-docs/routeback-gate-postcondition/SPEC.md`.

## Test Scenarios

All tests run with `python3 -m unittest discover -s tests` from the repository root.

### Unit Tests

- [ ] **TS-1** (FR1, NFR2): Normal path / unit (document contract): slice implement-phase.md from `### I.2.c: Failed handling` to `### Supporting cast`, normalize whitespace, take the slice from `- **abort phase**` to the batch-mode paragraph's start, and assert it contains the refresh command literal `reset --hard em-workflow/{feature}/integration`, a `rev-parse HEAD` tip capture, a phrase writing the `implement` step's `status` to `failed`, and a `commit-docs.sh` call with a third argument; assert `` assertNotIn("leave `implement` as `failed` for manual handling", section) ``.
- [ ] **TS-2** (FR2): Normal path / unit: on the same normalized section, the slice starting at `` Batch mode (`references/batch-mode.md` `` contains the same refresh / write / `commit-docs.sh` / report elements and no longer contains "implement stays `failed`, report and stop"; the raw (un-normalized) slice still ends the section (nothing follows it before `### Supporting cast`).
- [ ] **TS-3** (FR3, FR4): Normal path / unit: both abort slices assert the presence of a no-other-side-effect statement (no `create-plan` `needs_update`, no worktree/branch cleanup) and of `stop condition 3` together with the `next Step B iteration` formulation; the rejected-path slice's own side-effect sentences are still asserted present.
- [ ] **TS-5** (FR6): Normal path / unit: over the normalized Branch & Worktree Model section, assert the new abort terminal commit is named in the bounded-recovery enumeration, assert `Step I.1's baseline commit`, `Step I.2.b's wake-phase commit` and `Step I.2.c's rejected-path terminal status commit` are still named, assert the route-back commit is still described as the single carve-out, and `` assertNotIn('the three `commit-docs.sh` call sites in this phase where exit 4 can occur', section) ``.
- [ ] **TS-6** (FR7): Normal path / unit: read batch-mode.md, locate the row containing `` `implement.failed-task` ``, and assert it contains the write-and-commit terminal wording, still contains `Auto-select **retry** once per task`, `Route-back-to-planning is never taken automatically` and `` Full detail: `references/implement-phase.md` Step I.2.c ``, and no longer contains `` `implement` stays `failed` ``. `tests/test_batch_policies.py` must stay green unchanged.
- [ ] **TS-9** (FR9): Normal path / unit: `tests/test_implement_routeback_gate.py::TestPluginVersionBumpedInLockstep` passes — plugin.json and the marketplace `em-workflow` entry agree, (major, minor) == (0, 1), patch > 42; both read 0.1.44.

### Regression Tests

- [ ] **TS-4** (FR5): Regression / unit: `` assertIn('the same terminal as the "abort phase" option below', rejected_path_slice) `` — i.e. `tests/test_recycled_task_id_consistency.py::test_rejected_path_cites_stop_condition_3_and_abort_phase` and `tests/test_implement_routeback_gate.py::test_control_returns_via_stop_condition_3` still pass unchanged.
- [ ] **TS-7** (FR8, NFR5): Regression / unit: run all three pin-bearing modules — `tests/test_implement_routeback_gate.py`, `tests/test_recycled_task_id_consistency.py`, `tests/test_routeback_reset_scope_consistency.py` — and confirm each pin assertion passes against the post-change paragraph. Negative proof: reverting any single one of the three literals to its pre-change value makes exactly that module fail.

### Integration Tests

- [ ] **TS-10** (FR10, NFR4, NFR5): Integration / manual+unit: `git status --porcelain` after the change touches only implement-phase.md, batch-mode.md, the three test modules and the two version manifests — develop/SKILL.md, workflow-patch.md, validate-worker-output.py and routeback-gate-postcondition/SPEC.md are absent from the diff; `python3 -m unittest discover -s tests` exits 0 with no failures or errors.

### E2E Tests

**Existing E2E tests**: None (assumption A6: `resolved_input_paths.e2e` is empty; no E2E infrastructure exists).
**Run command**: Not detected.

### Edge Cases

- [ ] **TS-8** (NFR1, NFR3): Abnormal path / unit: `assertNotIn('rework', normalized_i2c)` and `assertNotIn('append', normalized_i2c)` after the edit; whole-file scan for bare `git commit` / `git add` lines in implement-phase.md returns an empty list.
- [ ] Exit 4 at the new abort commit call site: covered by prose, not by a runtime test — the bounded recovery of FR6 applies (refresh, re-capture tip, re-apply the same transition re-derived from source, retry once; a second exit 4 stops the phase with a report).

### Performance Tests

Not applicable. No performance requirement is present in the resolved requirements.

## Security Considerations

Not applicable. This is a documentation-only change (NFR4) with no authentication, authorization, input-handling, data-storage or network surface.

## Error Handling

| Condition | Handling |
|---|---|
| `commit-docs.sh` exits 4 at the new abort terminal commit | Bounded exit-4 recovery per FR6: refresh, re-capture tip, re-apply the same transition re-derived from source, retry once; a second exit 4 stops the phase with a report. The abort call site is never added to the single carve-out (Step I.2.c's route-back commit). |
| A second failure on the SAME task in batch mode | The `implement.failed-task` gate auto-selects **retry** once per task; the second failure takes the abort terminal (FR2, FR7). Route-back-to-planning is never taken automatically. |
| Abort taken while `implement` is `in_progress` | The terminal write sets `implement` to `failed` and commits exactly that write; control returns via develop's stop condition 3 on the next Step B iteration (FR4). |

## Success Criteria

- [ ] All functional requirements FR1–FR10 are implemented and verified against the changed prose or the test suite.
- [ ] All non-functional requirements NFR1–NFR6 hold.
- [ ] All test scenarios TS-1 through TS-10 pass.
- [ ] `python3 -m unittest discover -s tests` exits 0 from the repository root.
- [ ] `em-workflow/.claude-plugin/plugin.json` and the `em-workflow` entry in `.claude-plugin/marketplace.json` both read `0.1.44`.
- [ ] The actual change set is contained in the Declared Change Set above.
- [ ] Code review is completed.

## Open Questions

None. Every functional and non-functional requirement in this SPEC has `status: resolved`; no requirement is carried as `tbd`.

## Assumptions

- **A1**: PR #6 is merged; implement-phase.md L459-470's rejected-path terminal (`TERMINAL_TIP` capture, `implement: failed` write, `docs({feature}): implement route-back gate rejected` commit) is the template the abort paths copy. Verified present in the integration worktree.
- **A2**: Baseline versions confirmed as `0.1.43` in both `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`, so the lockstep target is `0.1.44`.
- **A3**: The commit message for the abort commit is left to implementation; it must be distinct enough from `docs({feature}): implement route-back gate rejected` to be legible in history. No test pins it, so no exact string is prescribed here.
- **A4**: Two abort call sites (interactive option, batch second failure) may share one described procedure via an explicit cross-reference within I.2.c rather than duplicating the command sequence, provided each path's terminal is readable without leaving the section.
- **A5**: No LICENSE file exists at the repository root and no package manifest exists, per the envelope; license detection therefore yields no SPDX id.
- **A6**: No E2E infrastructure exists (`resolved_input_paths.e2e` is empty); there is no e2e_test_command to record.
- **A7**: The only test command is `python3 -m unittest discover -s tests`, run from the repository root (test/README.md). There is no build, lint or format command defined anywhere in CLAUDE.md or test/README.md.

## Design Step

Skipped. The feature is a documentation-consistency fix inside two markdown protocol documents (`em-workflow/references/implement-phase.md`, `em-workflow/references/batch-mode.md`) plus three test modules and two version manifests. It ships no user interface, no visual surface, no CSS/token/theme artifact and no new user-facing interaction — it only makes an existing agent-facing protocol statement true. There is nothing for a designer worker to produce. The `create-spec.design-step` gate was resolved in batch as `decide_autonomously`, accepting this recommendation.

## References

- Requirements document: `feature-docs/abort-phase-terminal/REQUIREMENTS.md`
- Implement phase protocol: `em-workflow/references/implement-phase.md` (Step I.2.c; Branch & Worktree Model exit-4 recovery bullet L43-80; rejected-path terminal L459-470)
- Batch mode protocol: `em-workflow/references/batch-mode.md` (Non-packet gates table; `implement.failed-task` row L60)
- develop skill: `em-workflow/skills/develop/SKILL.md` (stop conditions 2/3/5; Step B 「停止条件 3 との優先関係」 L38-40) — non-goal, unmodified
- Commit helper: `em-workflow/scripts/commit-docs.sh` (RECOVERY CONTRACT) — unmodified
- Byte-pin test modules: `tests/test_implement_routeback_gate.py`, `tests/test_recycled_task_id_consistency.py`, `tests/test_routeback_reset_scope_consistency.py`
- Batch gate test module: `tests/test_batch_policies.py`
- Test invocation: `test/README.md`
- Version manifests: `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`
