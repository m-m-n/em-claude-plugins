# Feature: exit4-tip-argument

## Overview

`em-workflow/scripts/commit-docs.sh` accepts an optional third argument, `expected_base_tip`, which its own header documents as the authoritative staleness check closing the window between a caller's refresh+edit and the script's internal BEFORE_TIP read. Inside `em-workflow/references/implement-phase.md`, four call sites already capture a tip and pass it, but two sites that the same document's exit-4 recovery bullet enumerates — Step I.2.a's launch-time task status / task branch write and Step I.3's implement-completed / completed-commit write — state no refresh, no tip capture and no `commit-docs.sh` invocation at all. This feature writes the missing refresh / capture / write / commit-with-tip sequences into those two steps so every call site the exit-4 recovery bullet names passes a captured `expected_base_tip`.

Requirements source: `feature-docs/exit4-tip-argument/REQUIREMENTS.md`.

## Objectives

- Close the gap where two implement-phase doc writes fall back to `commit-docs.sh`'s weaker start-vs-under-lock check and can commit on top of a tip a concurrent `merge-task.sh` has already moved past.
- Make all six call sites enumerated by the exit-4 recovery bullet read as one consistent mechanism.
- Keep the change documentation-only: `commit-docs.sh` is untouched and the existing test suite stays green with no test file edited.

## User Stories

### US1: Launch-time write is committed against a freshly captured tip
As the em-workflow orchestrator, I want Step I.2.a to state an explicit refresh / capture / write / commit-with-tip sequence, so that the launch-time `tasks.{T}.status` / `tasks.{T}.branch` write is validated against the tip I actually built it on.

**Acceptance Criteria:**
- [ ] AC1: Step I.2.a's text contains, in order, the `reset --hard em-workflow/{feature}/integration` refresh, a `rev-parse HEAD` tip capture, the `tasks.{T}.status = in_progress` / `tasks.{T}.branch` workflow.yaml write, and a `commit-docs.sh` invocation whose third argument is that captured tip.
- [ ] AC6: Every call site named in the exit-4 recovery bullet's enumeration has a corresponding `commit-docs.sh` invocation with a three-argument form in its own step's text.

### US2: Phase-completion write is committed against a freshly captured tip
As the em-workflow orchestrator, I want Step I.3 to state the same sequence for the implement-completed / completed-commit write, so that phase completion cannot be committed on a stale base.

**Acceptance Criteria:**
- [ ] AC2: Step I.3's text contains the same four elements in the same order for the implement-completed / completed-commit write.
- [ ] AC3: The exact pinned string asserted by `test_completed_at_commit_wording_is_unchanged` is present in `implement-phase.md` byte-for-byte, and `tests/test_rework_synthesis_contract.py` is unchanged in the diff.

### US3: Refill re-entry cannot reuse a stale tip
As a reader arriving at Step I.2.a from Step I.2.b step 5's refill path, I want the document to state that a fresh tip is captured on every entry, so that I cannot conclude the already-captured `$RECONCILE_TIP` is reusable.

**Acceptance Criteria:**
- [ ] AC4: Step I.2.a's (or the refill boundary's) text states that a fresh tip is captured on every entry including the refill re-entry, and that `$RECONCILE_TIP` is not reused.
- [ ] AC5: `$RECONCILE_TIP` does not appear anywhere in Step I.2.a's text as the value passed to `commit-docs.sh`.

### US4: The change ships as an installable plugin version
As a user of the em-workflow plugin, I want the version bumped in both locations, so that the installed plugin cache picks up the corrected protocol document.

**Acceptance Criteria:**
- [ ] AC9: `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` both carry the same new patch-bumped version.
- [ ] AC8: `em-workflow/scripts/commit-docs.sh` is absent from the diff.

## Technical Requirements

### Functional Requirements

- **FR1 — Every enumerated implement-phase commit-docs.sh call site passes a captured expected_base_tip:** `em-workflow/references/implement-phase.md` must state, for every `commit-docs.sh` call site its "exit-4 recovery" bullet enumerates (Step I.1's baseline commit, Step I.2.a's launch-time task status / task branch write, Step I.2.b's wake-phase commit, Step I.2.c's rejected-path terminal status commit, Step I.2.c's abort-phase terminal status commit, Step I.3's implement-completed / completed-commit write), an explicit invocation that passes a tip captured after that site's own refresh as `commit-docs.sh`'s third argument. After this change no enumerated site relies on the script's secondary start-vs-under-lock check alone.

- **FR2 — Step I.2.a states the refresh / capture / write / commit-with-tip sequence:** Step I.2.a (Launch phase) must state, as an explicit ordered sequence in the step's own text, that the orchestrator (1) refreshes the integration worktree — `git -C {integration_worktree} reset --hard em-workflow/{feature}/integration`; (2) captures the tip — `LAUNCH_TIP=$(git -C {integration_worktree} rev-parse HEAD)`; (3) writes `tasks.{T}.status = in_progress` and `tasks.{T}.branch` into workflow.yaml on the worktree just refreshed; (4) commits that write with the captured tip as the third argument — `commit-docs.sh {integration_worktree} "docs({feature}): {summary}" "$LAUNCH_TIP"`, the message following the document's existing `docs({feature}): {summary}` convention; and cross-references the Branch & Worktree Model's exit-4 recovery for the exit-4 case. The ordering is normative: the refresh precedes the capture, the capture precedes the write, and the write precedes the commit. The wording mirrors the pattern Step I.2.b steps 2-3 already use.

- **FR3 — Step I.3 states the refresh / capture / write / commit-with-tip sequence:** Step I.3 (Phase completion) must state, as an explicit ordered sequence, the same four-part mechanism for its implement-completed / completed-commit write: (1) `git -C {integration_worktree} reset --hard em-workflow/{feature}/integration`; (2) `COMPLETION_TIP=$(git -C {integration_worktree} rev-parse HEAD)`; (3) the workflow.yaml write of `implement` step `status = completed` and `completed_at_commit`; (4) `commit-docs.sh {integration_worktree} "docs({feature}): {summary}" "$COMPLETION_TIP"`, with a cross-reference to the exit-4 recovery bullet. Worded to match Step I.2.b's existing pattern, subject to FR4's placement constraint.

- **FR4 — Step I.3's pinned sentence stays byte-identical and its test is not edited:** The Step I.3 sentence pinned by `tests/test_rework_synthesis_contract.py`'s `test_completed_at_commit_wording_is_unchanged` must survive byte-identically, including its internal newline. Every mechanism FR3 adds is placed strictly before or strictly after that sentence; no character inside it, and no character of the substring the assertion matches, is altered, re-wrapped or re-indented. `tests/test_rework_synthesis_contract.py` is NOT edited by this feature.

- **FR5 — The refill re-entry into Step I.2.a captures a fresh tip, never reusing $RECONCILE_TIP:** Step I.2.b step 5's refill path re-enters Step I.2.a within the same turn, at which point `RECONCILE_TIP` (captured at Step I.2.b step 2) is already stale: it was captured BEFORE Step I.2.b step 3's own `commit-docs.sh` commit, which advances the branch tip. Step I.2.a's sequence must therefore perform its own refresh and capture a NEW tip on every entry, including the refill re-entry, and must never reuse `$RECONCILE_TIP` (or any other previously captured tip) as its third argument. The document must make this explicit at the refill boundary so a reader arriving from Step I.2.b step 5 cannot conclude the already-captured tip is reusable.

- **FR6 — Plugin version bump accompanies the change:** Because files under `em-workflow/` are modified, the change must bump the plugin version in both locations to the same value: `em-workflow/.claude-plugin/plugin.json` `version` (currently `0.1.44`) and the `em-workflow` entry's `version` in `.claude-plugin/marketplace.json`. A documentation/protocol correction is a patch-level bump.

### Non-Functional Requirements

- **NFR1 - Wording parity with the existing tip-passing call sites:** The sequences FR2 and FR3 add use the same shape, variable-capture idiom and cross-reference phrasing that Step I.1 (`BASE_COMMIT`) and Step I.2.b steps 2-3 (`RECONCILE_TIP`) already use, so all six enumerated call sites read as one consistent mechanism rather than as per-step variants.

- **NFR2 - Documentation-only change:** `em-workflow/scripts/commit-docs.sh` is not modified: its `expected_base_tip` third argument, its exit-code semantics and its RECOVERY CONTRACT already support this change as-is. No hook, script or agent definition changes behavior; the change is confined to protocol prose plus the FR6 version bump.

- **NFR3 - Existing test suite stays green without edits:** `python3 -m unittest discover -s tests` passes with no test file modified — in particular `tests/test_rework_synthesis_contract.py`, whose `test_completed_at_commit_wording_is_unchanged` and `test_regression_precondition_stated_before_launch_selection` both assert on `implement-phase.md` substrings and orderings that this change must not disturb.

- **NFR4 - Internal consistency of the exit-4 recovery enumeration:** After the change, the Branch & Worktree Model's exit-4 recovery bullet and the per-step text agree: every call site the bullet names has a matching explicit invocation in its own step, and Step I.2.c's route-back carve-out remains the sole documented exception.

## Implementation Approach

### Architecture

The artifact under change is protocol prose, not code. The relevant structure is the set of `commit-docs.sh` call sites inside `em-workflow/references/implement-phase.md` and the exit-4 recovery bullet in the Branch & Worktree Model that enumerates them.

**Call-site map (target state):**

```
Branch & Worktree Model — exit-4 recovery bullet
  |
  +-- Step I.1   baseline commit ............... BASE_COMMIT      (already passes tip)
  +-- Step I.2.a launch-time status/branch write LAUNCH_TIP       (FR2 — added)
  +-- Step I.2.b wake-phase commit ............. RECONCILE_TIP    (already passes tip)
  +-- Step I.2.c rejected-path terminal status . TERMINAL_TIP     (already passes tip)
  +-- Step I.2.c abort-phase terminal status ... TERMINAL_TIP     (already passes tip)
  +-- Step I.3   implement-completed write ..... COMPLETION_TIP   (FR3 — added)

  Step I.2.c route-back (ROUTEBACK_TIP) — the sole documented carve-out (NFR4)
```

**Uniform four-part mechanism (NFR1):**

```
1. refresh   git -C {integration_worktree} reset --hard em-workflow/{feature}/integration
2. capture   {NAME}_TIP=$(git -C {integration_worktree} rev-parse HEAD)
3. write     the step's own workflow.yaml edit, on the worktree just refreshed
4. commit    commit-docs.sh {integration_worktree} "docs({feature}): {summary}" "${NAME}_TIP"
             exit 4 -> Branch & Worktree Model's exit-4 recovery
```

The ordering in steps 1-4 is normative (FR2).

### Data Flow

```
merge-task.sh (concurrent)  ->  advances em-workflow/{feature}/integration tip
orchestrator: refresh -> capture TIP -> edit workflow.yaml -> commit-docs.sh(..., TIP)
commit-docs.sh: compares TIP against the branch tip under lock
  match     -> commit
  mismatch  -> exit 4 -> exit-4 recovery (refresh, re-apply, retry)
```

Without the third argument the comparison degrades to the script's start-vs-under-lock check, which cannot see the window between the caller's refresh and the script's BEFORE_TIP read. FR1 removes that degraded path from every enumerated site.

### Refill boundary (FR5)

```
Step I.2.b step 2  capture RECONCILE_TIP
Step I.2.b step 3  commit-docs.sh(..., RECONCILE_TIP)   <-- advances the branch tip
Step I.2.b step 5  refill -> re-enter Step I.2.a  (same turn; RECONCILE_TIP now stale)
Step I.2.a         MUST refresh again and capture a NEW tip; MUST NOT reuse $RECONCILE_TIP
```

### API Design

Not applicable. No API surface is introduced or changed.

### Database Schema

Not applicable. No persisted data model is introduced or changed.

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/implement-phase.md`: the document whose Step I.2.a, Step I.3 and refill boundary this feature edits.
- `em-workflow/scripts/commit-docs.sh`: supplies the `expected_base_tip` third argument, the exit-code semantics and the RECOVERY CONTRACT the new prose relies on. Read-only for this feature (NFR2, AC8).
- `tests/test_rework_synthesis_contract.py`: pins Step I.3 wording and the precondition/launch-selection ordering. Read-only for this feature (FR4, NFR3).
- `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`: version bump targets (FR6).

**External Dependencies:**
- None. No dependency is introduced.

### File Structure

```
em-workflow/
├── references/
│   └── implement-phase.md          # FR1-FR5: Step I.2.a, Step I.3, refill boundary
├── scripts/
│   └── commit-docs.sh              # NOT modified (NFR2, AC8)
└── .claude-plugin/
    └── plugin.json                 # FR6: version bump (currently 0.1.44)
.claude-plugin/
└── marketplace.json                # FR6: em-workflow entry version, same value
tests/
├── test_rework_synthesis_contract.py   # NOT modified (FR4, NFR3)
└── ...                                 # TS3-TS5: new contract-style assertions
```

## Declared Change Set

- `em-workflow/references/implement-phase.md`
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `tests/**` — the TS3 / TS4 / TS5 contract tests. `tests/test_rework_synthesis_contract.py` is explicitly not modified (FR4).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/exit4-tip-argument/**`
- `test-docs/exit4-tip-argument/**`

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

## Test Scenarios

Test command: `python3 -m unittest discover -s tests`. No build command, no format command and no e2e command are detected for this project.

### Unit Tests
- [ ] TS1 (existing, unmodified) — `test_completed_at_commit_wording_is_unchanged`: run the existing suite and confirm the Step I.3 pin still matches after the FR3 insertion. Covers FR4, NFR3.
- [ ] TS2 (existing, unmodified) — `test_regression_precondition_stated_before_launch_selection`: confirm the FR2 insertion into I.2.a does not reorder the precondition relative to the launch-selection wording. Covers FR2, NFR3.
- [ ] TS3 (new, contract-style, following the existing assertIn pattern in `tests/`): assert Step I.2.a's text contains the refresh, the tip capture and a `commit-docs.sh` call whose third argument is the captured tip variable. Covers FR1, FR2.
- [ ] TS4 (new): assert Step I.3's text contains the same three elements, and separately re-assert the pinned sentence's byte-identity. Covers FR1, FR3, FR4.
- [ ] TS5 (new): assert the fresh-capture-on-refill statement is present — e.g. that the refill/I.2.a text names `RECONCILE_TIP` only in the context of NOT reusing it. Covers FR5.

### Integration Tests
- None. The change is protocol prose; the contract-style assertions above are the full automated surface.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Not applicable — no e2e surface exists for this feature.

### Edge Cases
- [ ] Refill re-entry (FR5): re-entering Step I.2.a from Step I.2.b step 5 within the same turn, where `RECONCILE_TIP` is already stale because Step I.2.b step 3's commit advanced the branch tip. Expected handling: Step I.2.a refreshes again and captures a new tip; `$RECONCILE_TIP` is never passed as the third argument (AC4, AC5).
- [ ] Concurrent `merge-task.sh` (FR1): the integration branch tip moves between the caller's refresh and the script's BEFORE_TIP read. Expected handling: `commit-docs.sh` detects the mismatch against the passed tip and returns exit 4, routing to the exit-4 recovery.
- [ ] Step I.3 pin adjacency (FR4): FR3's insertion sits adjacent to the pinned sentence. Expected handling: mechanics are placed strictly before or strictly after it; no character inside the pinned substring is altered, re-wrapped or re-indented (AC3).

### Manual / Review
- [ ] TS6 (manual/review): read the exit-4 recovery bullet's six-site enumeration against the per-step text and confirm one-to-one correspondence. Covers FR1, NFR4.

### Performance Tests
- None. No performance-sensitive surface is introduced.

## Security Considerations

- **Authentication:** Not applicable — no authentication surface is introduced or changed.
- **Authorization:** Not applicable — no authorization surface is introduced or changed.
- **Input Validation:** Not applicable — the change is protocol prose; `commit-docs.sh`'s argument handling is unchanged (NFR2).
- **Data Protection:** Not applicable — no sensitive data is handled.
- **XSS Prevention:** Not applicable — no UI surface.
- **SQL Injection Prevention:** Not applicable — no database access.
- **CSRF Protection:** Not applicable — no HTTP surface.

## Error Handling

### Error Codes

`commit-docs.sh`'s existing exit codes are unchanged by this feature (NFR2). The only code this feature's prose routes on:

| Code | Description | Handling |
|------|-------------|----------|
| exit 4 | The passed `expected_base_tip` does not match the branch tip observed under lock | Follow the Branch & Worktree Model's exit-4 recovery, cross-referenced from Step I.2.a (FR2) and Step I.3 (FR3) |

### Error Flow

```
commit-docs.sh(..., TIP) -> exit 4 -> exit-4 recovery: refresh, re-apply the write,
                                       capture a fresh tip, retry the commit
```

## Performance Optimization

Not applicable. Documentation-only change with no runtime performance surface.

## Success Criteria

- [ ] All functional requirements (FR1-FR6) are implemented.
- [ ] All test scenarios (TS1-TS6) pass.
- [ ] AC7: `python3 -m unittest discover -s tests` exits 0.
- [ ] AC8: `em-workflow/scripts/commit-docs.sh` is absent from the diff.
- [ ] AC9: `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` both carry the same new patch-bumped version.
- [ ] AC10: `test_regression_precondition_stated_before_launch_selection` still passes — the pending-task precondition still precedes the I.2.a launch-selection wording after the insertion.
- [ ] Code review is completed.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- None. Every requirement (FR1-FR6, NFR1-NFR4) has `status: resolved`.

## Assumptions

Recorded by requirements-analyst; carried here unchanged.

- **A1**: Recorded per the create-spec-run-q0002 answer to `requirement.approach` (batch codex consultation, record_as_assumption: true): the remedy is an explicit step sequence written into Step I.2.a and Step I.3, mirroring Step I.2.b's existing wording, rather than a shared/extracted helper procedure or a generic rule stated only in the Branch & Worktree Model bullet.
- **A2**: Recorded per the create-spec-run-q0002 answer to `testing.i3-pin-handling` (batch codex consultation): the Step I.3 pin is honored by placing new mechanics outside the pinned sentence, and `tests/test_rework_synthesis_contract.py` is not edited. The pin is an assertIn substring check (`tests/test_rework_synthesis_contract.py:209-217`), so this is achievable.
- **A3**: Established by the Codex second-opinion review: `RECONCILE_TIP` is captured at Step I.2.b step 2, before Step I.2.b step 3's own commit, so it is stale by the time the refill path re-enters Step I.2.a. FR5 follows from this.
- **A4**: Tip variable names `LAUNCH_TIP` (Step I.2.a) and `COMPLETION_TIP` (Step I.3) are proposed to match the existing `BASE_COMMIT` / `RECONCILE_TIP` / `ROUTEBACK_TIP` / `TERMINAL_TIP` naming. The names themselves are not load-bearing; any name consistent with that series satisfies FR2/FR3.
- **A5**: The commit messages for the two new invocations follow the document's existing `docs({feature}): {summary}` convention; the exact summary text is not constrained by these requirements.
- **A6**: No LICENSE file exists at the project root, so no SPDX identifier is recorded and the create-plan license-consistency check has no license to check new dependencies against. This feature introduces no dependencies, so the gap is inert here.

## Design Step

Skipped. The change is confined to protocol prose in `em-workflow/references/implement-phase.md` plus a version-number bump. There is no UI, no user-facing visual surface, no new component or screen, and the design-system candidate, project design system and visual input categories are all empty. Nothing exists for a designer worker to produce.

## References

- Requirements document: `feature-docs/exit4-tip-argument/REQUIREMENTS.md`
- Protocol document under change: `em-workflow/references/implement-phase.md`
- `expected_base_tip` / exit-code / RECOVERY CONTRACT definition: `em-workflow/scripts/commit-docs.sh` (not modified)
- Pinned wording and ordering assertions: `tests/test_rework_synthesis_contract.py` (not modified)
