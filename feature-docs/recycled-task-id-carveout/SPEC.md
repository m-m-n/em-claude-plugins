# Feature: recycled-task-id-carveout

## Overview

`em-workflow/references/implement-phase.md` I.2.a states the recycled-task-id rule with a scope sentence that contradicts itself: the literal "governs only the orchestrator's interpretation of the journal" is immediately followed by a declared exception for `queue_stop_guard.py`. The test that should pin this design invariant, `tests/test_recycled_task_id_consistency.py::TestRecycledTaskIdRuleScopedToOrchestrator`, only checks that each of the four hook filenames appears somewhere in the I.2.a section, so it stays green with its meaning inverted. This feature rewrites the I.2.a scope statement into a single non-contradictory rule, scopes the Supporting-cast Stop-hook bullet to the carve-out, and replaces the filename-presence test with separated claims backed by a two-layer pin joining the documentation to the hook implementations.

Requirements source: `feature-docs/recycled-task-id-carveout/REQUIREMENTS.md`.

## Objectives

- Remove the self-contradiction in `em-workflow/references/implement-phase.md` I.2.a, where the literal "governs only the orchestrator's interpretation of the journal" is immediately followed by a declared exception for `queue_stop_guard.py`.
- Restore an actually-enforced pin on the design invariant that three of the four queue hooks (`queue_launch_guard.py`, `queue_failure_net.py`, `queue_taskstop_net.py`) derive task state from the journal's last event alone and never consult `tasks.{T}.status`, while `queue_stop_guard.py` is the single, explicit carve-out.
- Close the gap in which `TestRecycledTaskIdRuleScopedToOrchestrator` stays green with its meaning inverted: its assertions only check that each hook filename appears somewhere in the I.2.a section, which the post-stopguard-retired-failed wording satisfies by naming `queue_stop_guard.py` as the exception.
- Reduce the triple statement of the carve-out (I.2.a prose, the Supporting-cast Stop-hook bullet, `queue_stop_guard.py`'s implementation) from three unconnected sites to a documented SSOT mechanically joined to the implementation by test.

## User Stories

### US1: An unambiguous scope statement in I.2.a

As the implement-phase orchestrator, I want I.2.a to state one non-contradictory rule about which components the recycled-task-id rule governs, so that reading the SSOT yields a single interpretation of its scope.

**Acceptance Criteria:**
- [ ] AC-1 (FR1): The I.2.a recycled-task-id paragraph contains no sentence that both restricts the rule to the orchestrator and then exempts a hook from that restriction; the literal "governs only the orchestrator's interpretation of the journal" is absent from the document.
- [ ] AC-2 (FR1): The revised I.2.a wording states, as one rule, that `queue_stop_guard.py` applies the recycled-task-id carve-out and that `queue_launch_guard.py`, `queue_failure_net.py` and `queue_taskstop_net.py` decide from the journal's last event alone and never consult `tasks.{T}.status`.
- [ ] AC-3 (FR1): Neither "never read workflow.yaml" nor "never reads workflow.yaml" occurs anywhere in `implement-phase.md` (the pre-existing regression guard still holds).
- [ ] AC-4 (FR2): The Supporting-cast Stop-hook bullet's equivalence claim is limited to the carve-out and is consistent with the revised I.2.a; I.2.b step 1's citation of I.2.a is unchanged.
- [ ] AC-10 (FR6): I.2.a explicitly records the unlaunched-definition divergence between its own "no journal event and status != merged" wording and the hook's status-blind treatment of a task with no journal event, marked as deliberate; `queue_stop_guard.py`'s classification logic is byte-unchanged.

### US2: A test suite that fails when the documentation drifts from the hooks

As an em-workflow maintainer, I want the documented hook classification pinned to the hook sources and to `queue_stop_guard.py`'s observable behavior, so that no wording satisfies the test merely by mentioning a filename.

**Acceptance Criteria:**
- [ ] AC-5 (FR3): `TestRecycledTaskIdRuleScopedToOrchestrator` asserts the three-hook journal-only claim and the `queue_stop_guard.py` exception as two separate assertions; no surviving assertion in that class is satisfied merely by a hook filename occurring somewhere in the I.2.a section.
- [ ] AC-6 (FR3): The module docstring's description of this class matches what the class now asserts, and no module-level constant is left with only one reader after the `ORCHESTRATOR_ONLY_SCOPE_PHRASE` revision.
- [ ] AC-7 (FR4, layer 1): A static scan test reads the sources of `queue_launch_guard.py`, `queue_failure_net.py` and `queue_taskstop_net.py` and fails if any of them performs a per-task workflow.yaml status read; its matcher keys on the status-read identifiers, and the string "workflow.yaml" alone never causes a failure.
- [ ] AC-8 (FR4, layer 2): A behavioral test runs `queue_stop_guard.py` as a subprocess against a temporary fixture and observes exit 2 with the task named in the BLOCK line when journal last event is `failed` and that task's workflow.yaml status is `pending`, and exit 0 for the same journal state when the status is not `pending`.
- [ ] AC-9 (FR5): Each new matcher has a paired negative proof demonstrating it fails on wording (or hook source) that violates the claim, and each pre-change/violating sample carries a positively-asserted retained anchor so no proof can degrade into a tautology.
- [ ] AC-11 (FR7): `em-workflow/.claude-plugin/plugin.json` and the em-workflow entry in `.claude-plugin/marketplace.json` both read the same bumped version (0.1.45), changed in this same change set.
- [ ] AC-12 (FR8): `python3 -m unittest discover -s tests` exits 0 from the repository root.

## Technical Requirements

### Functional Requirements

- **FR1 - I.2.a scope sentence made internally consistent:** Rewrite the closing scope sentence of the I.2.a recycled-task-id paragraph (`em-workflow/references/implement-phase.md`, currently lines 226-236) so it states a single non-contradictory rule: the recycled-task-id rule applies to the orchestrator's interpretation of the journal AND to `queue_stop_guard.py`, while the other three hooks (`queue_launch_guard.py`, `queue_failure_net.py`, `queue_taskstop_net.py`) derive a task's state from the journal's last event alone and never consult `tasks.{T}.status`. The literal "governs only the orchestrator's interpretation of the journal" is removed, since it is what the following clause contradicts. The weaker, true claim about workflow.yaml reads is preserved: the document must nowhere contain "never read workflow.yaml" or "never reads workflow.yaml".
- **FR2 - Supporting-cast Stop-hook bullet scoped to the carve-out:** Align the Stop-hook bullet under "Supporting cast: journal, hooks, resume" (`implement-phase.md`, currently lines 517-527) with the revised I.2.a: its equivalence claim ("applying the same recycled-task-id carve-out as I.2.a above") is limited in scope to the carve-out itself — the failed-plus-pending reclassification — and does not assert that `queue_stop_guard.py` reproduces every other aspect of I.2.a's unlaunched definition. I.2.a remains the SSOT and the bullet remains the citing consumer; the two sites must not restate the rule in independently-driftable form.
- **FR3 - TestRecycledTaskIdRuleScopedToOrchestrator split into two claims:** Rework `tests/test_recycled_task_id_consistency.py::TestRecycledTaskIdRuleScopedToOrchestrator` so it asserts two separated claims against the I.2.a section instead of one filename-presence conjunction over all four hooks: (a) the three journal-only hooks are named as deriving state from the journal's last event alone and never consulting `tasks.{T}.status`; (b) `queue_stop_guard.py` is named as the explicit, single exception that applies the carve-out. A test that is satisfied merely by each of the four filenames occurring somewhere in the section is no longer acceptable. The module constant `ORCHESTRATOR_ONLY_SCOPE_PHRASE` and its paired negative proof (`test_orchestrator_only_scope_matcher_flags_absence_in_pre_change_wording`) are updated or retired together with the positive matcher, and the module docstring's AC-6 description is corrected to state the new contract.
- **FR4 - Two-layer pin joining the documented classification to the hook implementations:** Pin the documentation-to-implementation correspondence with BOTH layers. Layer 1 — a static source scan over `em-workflow/hooks/queue_launch_guard.py`, `queue_failure_net.py` and `queue_taskstop_net.py` proving the negative claim that none of them reads a per-task workflow.yaml status. The scan matches on the status read itself — the identifiers that constitute such a read, e.g. `queue_stop_guard.py`'s `task_statuses_from_workflow` helper and its `TASK_STATUS_RE` / `TASKS_SECTION_RE` line-scan regexes — and NEVER on the bare substring "workflow.yaml" (`queue_taskstop_net.py`'s module docstring contains that substring while reading nothing). Layer 2 — a behavioral test of `queue_stop_guard.py`'s carve-out, invoking the hook as a subprocess with JSON on stdin per `test/README.md`'s hook-contract pattern, over a temporary worktree layout: journal last event `failed` plus that task's own workflow.yaml `status: pending` reclassifies the task as unlaunched and produces the BLOCK (exit 2) naming it, while the same journal state with a non-`pending` task status yields no block (exit 0).
- **FR5 - Non-vacuity discipline for every new matcher:** Every new assertion introduced by FR3 and FR4 carries the module's established discipline: each new-wording matcher keeps its literal in a single module-level constant shared by its positive test and its negative-proof test (Contract 1), each negative proof runs against a captured pre-change wording sample rather than a paraphrase (Contract 2), and each sample is guarded for non-vacuity by a RETAINED-anchor assertion in `TestPreChangeSampleGuards` (Contract 4). The FR4 static scan in particular carries a negative proof that it would flag a hook source that DID read a task status, so the scan cannot degrade into an assertion that passes over any input.
- **FR6 - Unlaunched-definition divergence documented rather than closed:** Leave `queue_stop_guard.py`'s classification logic untouched and state the divergence explicitly in I.2.a as a deliberate, documented divergence. The divergence to state: I.2.a defines unlaunched as "no journal event yet AND status != merged", whereas `queue_stop_guard.py`'s `evaluate_feature` classifies a task with no journal event as unlaunched without consulting its workflow.yaml status at all — so on a missing/truncated journal a task whose workflow.yaml status reads `merged` can be named in the hook's launch list. The documented text records this as intended hook behavior (the hook is a fail-open net, not an authority), not as a defect to be fixed by this feature.
- **FR7 - Plugin version bump:** Because files under `em-workflow/` change, bump `version` in `em-workflow/.claude-plugin/plugin.json` and in the em-workflow entry of `.claude-plugin/marketplace.json` in the same change. Both currently read 0.1.44 and must end at the same new value; a patch-level bump (0.1.45) matches CLAUDE.md's stated versioning rule.
- **FR8 - Whole suite green:** `python3 -m unittest discover -s tests` passes from the repository root after the change, including every pre-existing module in `tests/` and every pre-existing matcher in `test_recycled_task_id_consistency.py` that this feature does not deliberately revise (TS-7 raw-literal guards, TS-8 commit literal, TS-9 byte-identity, TS-10 orderings, and the AC-1..AC-5 groups).

### Non-Functional Requirements

- **NFR1 - Test-code dependency floor:** New and revised tests import only the Python standard library (unittest, pathlib, re, json, subprocess, tempfile). No third-party package is imported and none is assumed installed, per `test/README.md`.
- **NFR2 - Test placement and naming:** All test code stays in the repository-root `tests/` directory. Revisions land in `tests/test_recycled_task_id_consistency.py`; any new module is named `test_<target>.py`, with `Test<Behavior>` classes and `test_<condition>_<expected_result>` methods, and is picked up by `unittest discover` with no registration step.
- **NFR3 - Line-wrap robustness of document assertions:** Assertions over `implement-phase.md` prose compare against a whitespace-normalized copy of the relevant section (the module's existing `_normalize_ws` helper), so a reflow never makes an assertion brittle. The exception is the byte-identity and raw-literal guards (TS-7, TS-8, TS-9), which must keep comparing raw un-normalized text.
- **NFR4 - Hook runtime behavior unchanged:** No behavioral change to any of the four hooks. `queue_stop_guard.py`'s fail-open convention (every unexpected condition exits 0), its lazy read of task statuses, its consecutive-block cap of 3, and its sidecar handling are all preserved; the behavioral test of FR4 observes the hook, it does not require the hook to change.
- **NFR5 - Test isolation:** The behavioral subprocess test builds its entire fixture under `tempfile.TemporaryDirectory()` — worktrees root, integration worktree, `feature-docs/<feature>/workflow.yaml`, `journal.jsonl` and the stop-guard sidecar — and never reads or writes real `~/.claude` state or the repository's own `.claude/worktrees` tree.
- **NFR6 - SSOT singularity preserved:** After the change, I.2.a remains the sole normative statement of the recycled-task-id rule; the Supporting-cast bullet cites it rather than restating it independently, and the existing I.2.b step 1 citation ("the recycled-task-id rule in I.2.a above") is unchanged.

## Implementation Approach

### Architecture

**System Architecture:**

```
┌──────────────────────────────────────────────────────────┐
│  SSOT prose                                              │
│  em-workflow/references/implement-phase.md I.2.a         │
│    - recycled-task-id rule (single, non-contradictory)   │
│    - deliberate unlaunched-definition divergence note    │
├──────────────────────────────────────────────────────────┤
│  Citing consumers (no independent restatement)           │
│    - Supporting cast: Stop-hook bullet (carve-out scope) │
│    - I.2.b step 1 citation (unchanged)                   │
├──────────────────────────────────────────────────────────┤
│  Pin layer (tests/)                                      │
│    - wording matchers over the normalized I.2.a section  │
│    - Layer 1: static source scan of 3 journal-only hooks │
│    - Layer 2: subprocess behavior test of stop guard     │
├──────────────────────────────────────────────────────────┤
│  Implementation (unchanged)                              │
│    queue_launch_guard.py / queue_failure_net.py /        │
│    queue_taskstop_net.py   — journal last event only     │
│    queue_stop_guard.py     — the single carve-out        │
└──────────────────────────────────────────────────────────┘
```

**Component Diagram:**

```
implement-phase.md I.2.a  ──cited by──>  Supporting-cast Stop-hook bullet
        │                                        │
        │                                  cited by I.2.b step 1
        │
        └── pinned by ──> tests/test_recycled_task_id_consistency.py
                              │  wording matchers (+ negative proofs)
                              │
                              ├── Layer 1 static scan ──> 3 journal-only hook sources
                              └── Layer 2 subprocess  ──> em-workflow/hooks/queue_stop_guard.py
```

### Data Flow

Layer 1 (static scan):

```
hook source file → read text → status-read identifier matcher → violation list → assertion
                                   (never matches bare "workflow.yaml")
```

Layer 2 (behavioral subprocess):

```
tempfile fixture (worktrees root, integration worktree,
feature-docs/<feature>/workflow.yaml, journal.jsonl, stop-guard sidecar)
      → JSON on stdin → queue_stop_guard.py subprocess
      → exit code + stderr → assertion (exit 2 + BLOCK naming task0001 | exit 0)
```

### API Design

Not applicable. This feature exposes no API. The only process-level interface exercised is the existing hook contract: `queue_stop_guard.py` reads a JSON object on stdin and communicates via exit code (0 = allow, 2 = block) and stderr, per `test/README.md`'s hook-contract pattern.

### Database Schema

Not applicable. No persistent data model is added or changed.

### Dependencies

**Internal Dependencies:**

- `em-workflow/references/implement-phase.md`: the SSOT document whose I.2.a section and Supporting-cast Stop-hook bullet are revised.
- `em-workflow/hooks/queue_launch_guard.py`, `queue_failure_net.py`, `queue_taskstop_net.py`: the journal-only hooks whose sources Layer 1 scans; unchanged.
- `em-workflow/hooks/queue_stop_guard.py`: the carve-out hook Layer 2 invokes as a subprocess; unchanged, including its `task_statuses_from_workflow` helper and `TASK_STATUS_RE` / `TASKS_SECTION_RE` regexes, which supply the identifiers Layer 1's matcher keys on.
- `tests/test_recycled_task_id_consistency.py`: the module whose `TestRecycledTaskIdRuleScopedToOrchestrator`, `ORCHESTRATOR_ONLY_SCOPE_PHRASE` constant, `_normalize_ws` helper and `TestPreChangeSampleGuards` class are revised or extended.
- `test/README.md`: source of the hook-contract pattern and the standard-library-only test policy.
- `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`: the two version-carrying files.

**External Dependencies:**

- Python standard library only: `unittest`, `pathlib`, `re`, `json`, `subprocess`, `tempfile`. No third-party package is imported or assumed installed (NFR1).

### File Structure

```
.
├── .claude-plugin/
│   └── marketplace.json                      # em-workflow entry version → 0.1.45
├── em-workflow/
│   ├── .claude-plugin/
│   │   └── plugin.json                       # version → 0.1.45
│   ├── hooks/
│   │   ├── queue_launch_guard.py             # unchanged; Layer 1 scan target
│   │   ├── queue_failure_net.py              # unchanged; Layer 1 scan target
│   │   ├── queue_taskstop_net.py             # unchanged; Layer 1 scan target
│   │   └── queue_stop_guard.py               # unchanged; Layer 2 subprocess target
│   └── references/
│       └── implement-phase.md                # I.2.a + Supporting-cast bullet revised
└── tests/
    ├── test_recycled_task_id_consistency.py  # class split, constants, docstring, samples
    └── test_<target>.py                      # optional new module (NFR2 naming)
```

## Declared Change Set

Feature-specific paths:

- `em-workflow/references/implement-phase.md`
- `tests/test_recycled_task_id_consistency.py`
- `tests/test_*.py` (any new test module this feature adds, per NFR2's naming rule)
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/recycled-task-id-carveout/**`
- `test-docs/recycled-task-id-carveout/**`

`feature-docs/recycled-task-id-carveout/**` covers `REQUIREMENTS.md`,
`SPEC.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/recycled-task-id-carveout/**` covers
`test-docs/recycled-task-id-carveout/{T}.tests.yaml`, the per-task test
record. It is generated and owned by `implement-phase.md`; this section
cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/recycled-task-id-carveout/` directory at all; the declared
`test-docs/recycled-task-id-carveout/**` entry is still correct in that
case — a declared path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] TS-1 (AC-1, AC-3): Normalized I.2.a section does not contain the contradictory scope literal; the whole document contains neither "never read workflow.yaml" nor "never reads workflow.yaml". Negative proof: the matcher flags a captured sample of the current (contradictory) I.2.a wording.
- [ ] TS-2 (AC-2, AC-5): Normalized I.2.a names the three journal-only hooks in a claim that they never consult `tasks.{T}.status`. Negative proof: the matcher fails on a sample in which `queue_stop_guard.py` is included in that same three-hook claim.
- [ ] TS-3 (AC-2, AC-5): Normalized I.2.a names `queue_stop_guard.py` as the explicit exception applying the carve-out. Negative proof: the matcher fails on the pre-stopguard-retired-failed wording where `queue_stop_guard.py` appeared only in the four-hook "never consults" list.
- [ ] TS-4 (AC-4): Normalized Supporting-cast Stop-hook bullet states the carve-out-scoped equivalence and cites I.2.a; the I.2.b step 1 citation literal survives unchanged.
- [ ] TS-8 (AC-10): Normalized I.2.a contains the divergence statement naming the missing-journal-event case and marking it deliberate. Negative proof: the matcher is absent from the pre-change I.2.a paragraph sample.
- [ ] TS-9 (AC-11): Both version files parse as JSON and their em-workflow version values are equal and greater than 0.1.44.
- [ ] TS-10 (AC-6, AC-9): `TestPreChangeSampleGuards` asserts a retained anchor in every new sample introduced by this feature.

### Integration Tests

- [ ] TS-5 (AC-7): Static scan over the three journal-only hook sources finds no per-task status read. Negative proof: the same scan applied to a source sample containing such a read reports a violation, and a sample containing only the substring "workflow.yaml" in a docstring does not.
- [ ] TS-6 (AC-8): Subprocess run of `queue_stop_guard.py` on a fixture where task0001's journal last event is `failed` and workflow.yaml `tasks.task0001.status` is `pending` — exit 2, stderr BLOCK line names task0001.
- [ ] TS-7 (AC-8): Same fixture with `tasks.task0001.status: in_progress` (or any non-`pending` value) — exit 0, no BLOCK.
- [ ] TS-11 (AC-12): The full suite, including the pre-existing TS-7/TS-8/TS-9/TS-10 guards of this module and every other module in `tests/`, runs green.

(Note on numbering: TS-1..TS-11 above are this feature's scenario IDs. The
"pre-existing TS-7/TS-8/TS-9/TS-10 guards" named in TS-11 and FR8 are the
existing IDs inside `tests/test_recycled_task_id_consistency.py`, a
separate namespace that this feature does not renumber.)

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

- [ ] Not applicable — no E2E surface exists for this feature.

### Edge Cases

- [ ] `queue_taskstop_net.py`'s module docstring contains the substring "workflow.yaml" while reading nothing — Layer 1's matcher must not flag it (FR4, TS-5).
- [ ] A hook that read a task status by an entirely novel mechanism (e.g. a YAML library) is not caught by the identifier-based scan — accepted as the boundary of a source-text pin (see Open Questions / assumptions).
- [ ] Missing or truncated journal: a task whose workflow.yaml status reads `merged` can be named in `queue_stop_guard.py`'s launch list because `evaluate_feature` classifies a task with no journal event as unlaunched without consulting its status — documented in I.2.a as intended fail-open behavior, not fixed (FR6, TS-8).
- [ ] Journal last event `failed` with a non-`pending` task status — no block, exit 0 (TS-7).

### Performance Tests

Not applicable. No performance goal is stated for this feature.

## Security Considerations

- **Authentication:** Not applicable — no authenticated surface.
- **Authorization:** Not applicable — no authorization surface.
- **Input Validation:** The behavioral test feeds JSON on stdin to `queue_stop_guard.py` per the existing hook contract; the hook's fail-open convention (every unexpected condition exits 0) is preserved unchanged (NFR4).
- **Data Protection:** The behavioral test builds its entire fixture under `tempfile.TemporaryDirectory()` and never reads or writes real `~/.claude` state or the repository's own `.claude/worktrees` tree (NFR5).
- **XSS Prevention:** Not applicable.
- **SQL Injection Prevention:** Not applicable.
- **CSRF Protection:** Not applicable.

## Error Handling

### Error Codes

Not applicable — this feature introduces no error codes. The only exit-code
contract exercised is the existing hook contract observed by the FR4 Layer 2
test:

| Exit code | Condition | Observable output |
|-----------|-----------|-------------------|
| 2 | Journal last event `failed` and that task's workflow.yaml `status: pending` | stderr BLOCK line naming the task |
| 0 | Same journal state, task status not `pending`; and every unexpected condition (fail-open) | No BLOCK |

### Error Flow

```
Assertion violated → unittest failure → `python3 -m unittest discover -s tests` exits non-zero
```

## Performance Optimization

Not applicable. No performance goal, optimization strategy or caching
strategy is specified for this feature.

## Success Criteria

- [ ] All functional requirements (FR1-FR8) are implemented and tested.
- [ ] All test scenarios (TS-1..TS-11) pass.
- [ ] All non-functional requirements (NFR1-NFR6) are satisfied.
- [ ] `python3 -m unittest discover -s tests` exits 0 from the repository root (AC-12).
- [ ] `em-workflow/.claude-plugin/plugin.json` and the em-workflow entry in `.claude-plugin/marketplace.json` both read 0.1.45 (AC-11).
- [ ] `queue_stop_guard.py`'s classification logic is byte-unchanged (AC-10, NFR4).

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None. Every requirement (FR1-FR8, NFR1-NFR6) is `status: resolved`.

Assumptions carried into this specification:

- Recorded as assumption (batch codex consultation, question `recycled-carveout.pin-test-mechanism`): both pin layers are built — a static source scan for the three journal-only hooks and a behavioral subprocess test for `queue_stop_guard.py`'s carve-out — rather than either alone.
- Recorded as assumption (batch codex consultation, question `recycled-carveout.unlaunched-divergence`): the unlaunched-definition divergence is documented in I.2.a as deliberate rather than closed by changing the hook; `queue_stop_guard.py` stays untouched, matching the task description's stated scope exclusion.
- The version bump is a patch bump to 0.1.45, per CLAUDE.md's patch-level bump rule; only the two files named in FR7 carry the version.
- The static scan matches identifiers rather than semantics — it detects a status read of the shape `queue_stop_guard.py` uses (line-based workflow.yaml scanning helpers/regexes). A hook that read a task status by an entirely novel mechanism (e.g. a YAML library) would not be caught; this is accepted as the boundary of a source-text pin.
- No file outside `em-workflow/references/implement-phase.md`, `tests/` (this module plus any new test module), `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` is expected to change.

## Implementation Phases (if applicable)

### Phase 1: Documentation SSOT

**Goals:** Make I.2.a internally consistent and scope its citing consumers.
**Deliverables:**
- Revised I.2.a recycled-task-id paragraph (FR1) including the deliberate unlaunched-definition divergence statement (FR6)
- Revised Supporting-cast Stop-hook bullet (FR2), with I.2.b step 1's citation unchanged

### Phase 2: Pin layer

**Goals:** Join the documented classification to the hook implementations by test.
**Deliverables:**
- Split `TestRecycledTaskIdRuleScopedToOrchestrator` with updated constants and module docstring (FR3)
- Layer 1 static source scan over the three journal-only hooks (FR4)
- Layer 2 behavioral subprocess test of `queue_stop_guard.py` (FR4)
- Negative proofs and `TestPreChangeSampleGuards` anchors for every new matcher (FR5)

### Phase 3: Version and suite

**Goals:** Complete the change set and confirm the suite.
**Deliverables:**
- Version bump to 0.1.45 in both version-carrying files (FR7)
- `python3 -m unittest discover -s tests` green from the repository root (FR8)

## References

- Requirements document: `feature-docs/recycled-task-id-carveout/REQUIREMENTS.md`
- SSOT under revision: `em-workflow/references/implement-phase.md` (I.2.a recycled-task-id paragraph, currently lines 226-236; Supporting-cast Stop-hook bullet, currently lines 517-527)
- Test module under revision: `tests/test_recycled_task_id_consistency.py`
- Hook-contract pattern and test dependency policy: `test/README.md`
- Hook implementations pinned by this feature: `em-workflow/hooks/queue_stop_guard.py`, `queue_launch_guard.py`, `queue_failure_net.py`, `queue_taskstop_net.py`
- Version-carrying files: `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`
- Versioning rule: `CLAUDE.md`
