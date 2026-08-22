# Feature: tip-capture-idiom-unification

## Overview

`em-workflow/references/implement-phase.md`, the SSOT for the implement phase, currently
prescribes one tip-capture idiom at two of its seven tip-carrying `commit-docs.sh` call
sites and, at the other five, an idiom its own newly added prose declares dangerous. This
feature unifies all seven call sites on the single safe idiom, makes each site's
first-attempt procedure state the same order as the Branch & Worktree Model's exit-4
recovery bullet, and adds a test that detects any later drift back to the old form. The
change set is protocol prose, shell comments, three test assertions, one new test module
and two version manifests; no executable behaviour changes.

Requirements document: `feature-docs/tip-capture-idiom-unification/REQUIREMENTS.md`.

## Objectives

- **OBJ1:** Unify all seven `commit-docs.sh` call sites in `implement-phase.md` on the
  single safe idiom, so the document stops prescribing and condemning the same operation.
- **OBJ2:** Make the first-attempt procedure at each call site state the same order as the
  Branch & Worktree Model's exit-4 recovery bullet, removing the "old idiom on first
  attempt, new idiom on retry" inconsistency.
- **OBJ3:** Make the uniformity machine-checkable so the idiom cannot silently drift back
  on a later edit, satisfying the standing NFR that the call sites read as one consistent
  mechanism.

## User Stories

The resolved requirements carry business objectives rather than actor-phrased user
stories, and this feature has no interactive user surface. The objectives above stand in
their place; each is traced to acceptance criteria here.

### US1: OBJ1 — one idiom across all seven sites

**Acceptance Criteria:**
- [ ] AC1: All seven in-scope sites in `em-workflow/references/implement-phase.md` capture
      the tip from the branch ref, refresh with the branch name as target, and place the
      capture before the refresh. *(satisfies FR1, FR2, FR3, FR4, FR5, NFR1, NFR5)*
- [ ] AC3: Both prose blocks in `em-workflow/scripts/commit-docs.sh` — the
      `expected_base_tip` description and the RECOVERY CONTRACT recovery steps — are
      consistent with the new idiom; the carve-out sentence and every executable line are
      unchanged. *(satisfies FR8, NFR4)*

### US2: OBJ2 — first attempt and exit-4 retry are the same procedure

**Acceptance Criteria:**
- [ ] AC2: The Branch & Worktree Model's exit-4 recovery bullet and each site's own body
      procedure state the SAME order (capture then refresh), so first attempt and exit-4
      retry are the same procedure. *(satisfies FR1, NFR1)*

### US3: OBJ3 — the uniformity is machine-checked and the change stays contained

**Acceptance Criteria:**
- [ ] AC4: `python3 -m unittest discover -s tests` passes, with
      `tests/test_implement_routeback_gate.py` modified only in the three assertions FR7
      names and every other pre-existing module unmodified. *(satisfies FR7, NFR2, NFR3)*
- [ ] AC5: A test exists that detects idiom uniformity across the seven sites and fails if
      any site reverts to the post-refresh `rev-parse HEAD` form or targets `reset --hard`
      at anything other than the branch name. *(satisfies FR9, NFR5)*
- [ ] AC6: `em-workflow/.claude-plugin/plugin.json` and the root
      `.claude-plugin/marketplace.json` carry the same bumped version, higher than 0.1.45.
      *(satisfies FR10)*

## Technical Requirements

### Functional Requirements

- **FR1 — Canonical tip-capture idiom:** The single idiom for every tip-carrying
  `commit-docs.sh` call site is: (a) capture the tip from the BRANCH REF —
  `<VAR>=$(git -C <integration worktree> rev-parse em-workflow/{feature}/integration)`;
  (b) refresh the integration worktree with
  `git -C <integration worktree> reset --hard em-workflow/{feature}/integration`, whose
  target is always the BRANCH NAME, never a captured SHA; (c) capture PRECEDES refresh. The
  Branch & Worktree Model's exit-4 recovery bullet (`implement-phase.md` lines 43-82)
  already states exactly this order and is the normative reference; it is not modified.
  *(status: resolved)*

- **FR2 — Convert the five old-idiom sites:** Rewrite the five `refresh -> rev-parse HEAD`
  sites to FR1's idiom: Step I.1 `BASE_COMMIT` (`implement-phase.md` ~158-176), Step I.2.b
  step 2 `RECONCILE_TIP` (~389-406), Step I.2.c route-back `ROUTEBACK_TIP` (~459-477), Step
  I.2.c rejected-path `TERMINAL_TIP` (~504-510), Step I.2.c abort-phase `ABORT_TIP`
  (~518-524). Each keeps its own variable name, its own commit message literal, and its own
  exit-4 cross-reference. *(status: resolved)*

- **FR3 — PR 17 sites are the reference form, unchanged:** Step I.2.a `LAUNCH_TIP`
  (~258-266) and Step I.3 `COMPLETION_TIP` (~651-658) already carry FR1's idiom and their
  content is not changed by this feature. They serve as the reference form the other five
  are brought to. The Step I.2.a rationale prose (~275-297) explaining why post-refresh
  `rev-parse HEAD` is unsafe stays as written. *(status: resolved)*

- **FR4 — In-scope site set:** The in-scope set is all SEVEN tip-carrying `commit-docs.sh`
  invocations: Step I.1, Step I.2.a, Step I.2.b, Step I.2.c route-back, Step I.2.c
  rejected, Step I.2.c abort, Step I.3. The route-back site's exit-4 unreachability
  carve-out prose stays intact — it concerns exit-4 reachability, not tip capture, and the
  carve-out remains a carve-out after this change. *(status: resolved)*

- **FR5 — Step I.1 treatment (capture-then-refresh):** Step I.1 adopts the FULL idiom, not
  merely the capture form: capture `BASE_COMMIT` from the branch ref, then ADD a
  `git -C "$WT_ROOT/integration" reset --hard em-workflow/{feature}/integration` refresh
  that the step does not have today, then write `workflow.yaml`, then commit.
  `$BASE_COMMIT` remains both the value recorded as `workflow[implement].base_commit`
  (first-entry-only semantics unchanged) and the `commit-docs.sh` third argument, and the
  literal `"docs({feature}): implement phase start" "$BASE_COMMIT"` pinned by
  `tests/test_review_implement_develop_lock_contracts.py` is unchanged. *(status: resolved)*

- **FR6 — Step I.2.b capture-line placement preserving the frozen ordering pin:** In Step
  I.2.b step 2 the capture line is placed so that
  `tests/test_review_implement_develop_lock_contracts.py`'s
  `TestImplementPhaseWakePhaseOrdering` keeps passing untouched: that class pins only the
  relative order of `"Refresh the integration worktree FIRST"` <
  `"Update workflow.yaml, then commit"` < the wake-phase commit literal, plus the presence
  of `phase reconcile" "$RECONCILE_TIP"` and `"(exit-4 recovery: Branch & Worktree"`.
  Inserting the capture immediately BEFORE the
  `**Refresh the integration worktree FIRST**` sentence satisfies both FR1's
  capture-precedes-refresh order and every one of those pins. *(status: resolved)*

- **FR7 — Frozen-module assertion amendments:** `tests/test_implement_routeback_gate.py` is
  explicitly IN SCOPE for exactly three narrowly-targeted assertion amendments, re-pinning
  the new idiom: (1) the route-back order pin in
  `TestGateDecisionPrecedesAllSideEffects.test_admitted_path_order_gate_refresh_tip_writeset_commit_cleanup`
  (~486-502), whose `assertLess(refresh_idx, tip_idx)` inverts to tip before refresh;
  (2) the abort-path `rev-parse HEAD` literal assertion `test_states_tip_capture`
  (~817-818), which becomes the branch-ref capture form; (3) the abort-path order pin
  `test_order_refresh_before_tip_before_write_before_commit` (~829-841), whose refresh/tip
  ordering inverts. Every OTHER assertion in that module stays untouched — including
  `test_rejected_path_order_gate_terminal_write_terminal_commit` (~504-512), which pins only
  gate < `TERMINAL_TIP` < commit-message and survives unchanged. *(status: resolved)*

- **FR8 — commit-docs.sh prose alignment (both blocks):** Align BOTH prose blocks in
  `em-workflow/scripts/commit-docs.sh` with FR1's idiom: (a) the `expected_base_tip`
  argument description (lines ~13-21, whose "captured at the caller's last refresh (e.g.
  right after its `git reset --hard`)" wording describes the old idiom), and (b) the
  RECOVERY CONTRACT's recovery steps (lines ~39-50, whose step (1) describes
  refresh-then-implicit-recapture). The RECOVERY CONTRACT's carve-out sentence naming
  `implement-phase.md` Step I.2.c's route-back commit is left untouched. No executable line
  of the script changes — comments only. *(status: resolved)*

- **FR9 — Idiom-uniformity test:** Add a new Python unittest module under `tests/` (no such
  module exists today) that detects, across all seven in-scope sites in
  `implement-phase.md`, that the capture is taken from the branch ref, that every
  `reset --hard` target in those sites is the branch name (never a captured SHA or HEAD),
  and that the capture precedes the refresh at each site. Absence of the post-refresh
  `rev-parse HEAD` form at these sites is part of the check, so a regression fails the
  suite. *(status: resolved)*

- **FR10 — Plugin version bump:** Because files under `em-workflow/` change, bump `version`
  in `em-workflow/.claude-plugin/plugin.json` (currently 0.1.45) and the matching
  `em-workflow` entry in the repository-root `.claude-plugin/marketplace.json` to the same
  new value, per the repository's plugin-version-bump rule. *(status: resolved)*

### Non-Functional Requirements

- **NFR1 - SSOT internal consistency:** After the change, `implement-phase.md` contains no
  place where the old `refresh -> rev-parse HEAD` idiom is prescribed for a tip-carrying
  `commit-docs.sh` call, and all seven sites read as a single consistent mechanism together
  with the Branch & Worktree Model's exit-4 recovery bullet.

- **NFR2 - Test-suite scope containment:** `tests/test_implement_routeback_gate.py` is the
  ONLY pre-existing test module modified, and only through FR7's three assertion
  amendments. Every other pre-existing test module stays byte-unmodified, including
  `tests/test_review_implement_develop_lock_contracts.py`,
  `tests/test_recycled_task_id_consistency.py` and
  `tests/test_routeback_reset_scope_consistency.py` — the last two observe only
  commit-message literal survival. `python3 -m unittest discover -s tests` passes in full.

- **NFR3 - Frozen-pin discipline:** Protocol prose is never shaped to satisfy an existing
  test. Where a frozen pin contradicts FR1, the pin is amended (FR7) and the amendment is
  justified by the idiom change, not the reverse. Where a pin does NOT contradict FR1 (the
  wake-phase ordering class, the commit-message literal checks), the prose is placed so the
  pin keeps passing untouched (FR6).

- **NFR4 - No executable change to commit-docs.sh:** The `commit-docs.sh` change is
  comment-only. Its argument handling, exit codes, locking and staleness comparison are
  byte-identical after the change.

- **NFR5 - reset --hard target safety invariant:** No site may target `reset --hard` at a
  captured SHA. The integration worktree has an attached HEAD, so resetting to a SHA rewinds
  the branch ref itself and silently discards a concurrent `merge-task.sh` merge commit
  (detected as critical in PR 17's review). Every refresh target stays the branch name
  `em-workflow/{feature}/integration`.

- **NFR6 - No scope creep:** Documentation, shell comments, three test assertions, one new
  test module and two version manifests are the whole change set. Commit-message literals,
  `$BASE_COMMIT`'s recorded-value semantics, the route-back exit-4 unreachability carve-out
  and its proof, the widened I.2.c gate conditions, and the PR 17 sites' content are all
  preserved.

### Requirement-to-criterion traceability

| Acceptance criterion | Requirements satisfied |
|---|---|
| AC1 | FR1, FR2, FR3, FR4, FR5, NFR1, NFR5 |
| AC2 | FR1, NFR1 |
| AC3 | FR8, NFR4 |
| AC4 | FR7, NFR2, NFR3 |
| AC5 | FR9, NFR5 |
| AC6 | FR10 |

FR6 is a placement constraint that the resolved requirements attach to no acceptance
criterion of its own; it is exercised through AC4's untouched-pin condition.

## Implementation Approach

### Architecture

**System Architecture:** Not applicable — this feature has no runtime application. The
artifacts changed are a protocol document, a shell script's comments, Python test modules
and two JSON version manifests.

**Component Diagram:** Not applicable for the same reason. The relevant relationships are
document-to-document references:

```
implement-phase.md
  ├─ Branch & Worktree Model, exit-4 recovery bullet (lines 43-82)  [normative, unchanged]
  ├─ Step I.1        BASE_COMMIT      [convert: FR2, FR5]
  ├─ Step I.2.a      LAUNCH_TIP       [reference form, unchanged: FR3]
  ├─ Step I.2.b      RECONCILE_TIP    [convert: FR2, placement per FR6]
  ├─ Step I.2.c      ROUTEBACK_TIP    [convert: FR2; carve-out prose intact: FR4]
  ├─ Step I.2.c      TERMINAL_TIP     [convert: FR2]
  ├─ Step I.2.c      ABORT_TIP        [convert: FR2]
  └─ Step I.3        COMPLETION_TIP   [reference form, unchanged: FR3]

commit-docs.sh
  ├─ expected_base_tip argument description (~13-21)  [align: FR8]
  └─ RECOVERY CONTRACT recovery steps (~39-50)        [align: FR8; carve-out sentence intact]

tests/
  ├─ test_implement_routeback_gate.py   [three assertion amendments: FR7]
  └─ <new idiom-uniformity module>      [new: FR9]
```

### Data Flow

Not applicable — no runtime data flows through this change. The canonical idiom FR1
prescribes at each site is:

```
capture:  VAR=$(git -C <integration worktree> rev-parse em-workflow/{feature}/integration)
refresh:  git -C <integration worktree> reset --hard em-workflow/{feature}/integration
commit:   commit-docs.sh ... "$VAR"
```

with capture strictly preceding refresh, and the refresh target always the branch name.

### API Design

Not applicable — this feature defines and changes no API endpoints.

### Database Schema

Not applicable — this feature has no persistent data model.

#### Entity Relationship Diagram

Not applicable (no entities).

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/implement-phase.md`: the SSOT whose seven call sites are
  unified; its Branch & Worktree Model exit-4 recovery bullet is the normative reference
  for the idiom's order.
- `em-workflow/scripts/commit-docs.sh`: the script whose `expected_base_tip` contract the
  prose describes; its comments are aligned, its executable body is not.
- `tests/test_implement_routeback_gate.py`: pins route-back and abort-path ordering and
  literals; three assertions are re-pinned.
- `tests/test_review_implement_develop_lock_contracts.py`: pins wake-phase ordering and
  commit-message literals; stays untouched, constraining FR6's placement.

**External Dependencies:**
- `python3` unittest (standard library): runner for the existing and new test modules; no
  new framework or runner is introduced.

### File Structure

```
em-workflow/
├── references/
│   └── implement-phase.md          # seven call sites unified (FR1-FR6)
├── scripts/
│   └── commit-docs.sh              # comment-only prose alignment (FR8, NFR4)
└── .claude-plugin/
    └── plugin.json                 # version bump (FR10)
.claude-plugin/
└── marketplace.json                # matching version bump (FR10)
tests/
├── test_implement_routeback_gate.py    # three assertion amendments (FR7)
└── <new idiom-uniformity module>       # new uniformity test (FR9)
```

## Declared Change Set

Feature-specific paths:

- `em-workflow/references/implement-phase.md`
- `em-workflow/scripts/commit-docs.sh`
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `tests/test_implement_routeback_gate.py`
- `tests/**` (the new idiom-uniformity module FR9 adds)

Every SPEC declares, by default, the following two workflow-generated entries in addition
to the feature-specific paths above:

- `feature-docs/tip-capture-idiom-unification/**`
- `test-docs/tip-capture-idiom-unification/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`, `workflow.yaml`,
`phase-state/`, `tasks/`, `reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and
the design artifacts the design step produces. These are generated and owned by the phase
documents and by `references/phase-state.md`; this section cites them and restates none of
their rules.

`test-docs/{feature}/**` covers `test-docs/{feature}/{T}.tests.yaml`, the per-task test
record. It is generated and owned by `implement-phase.md`; this section cites it and
restates none of its rules.

These two default entries are part of the declaration unless the SPEC author explicitly
removes them; their absence is never assumed by silence — removal is a deliberate, explicit
narrowing.

This declaration is a SUPERSET assertion: the actual change set observed at verification
time must be CONTAINED IN the declared set, not equal to it. A feature that produces no
implement tasks generates no `test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared path that never
materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] **TS-1** (automated, covers AC1 → FR1, FR2, FR3, FR4, FR5, NFR1, NFR5): The new
      uniformity test parses `implement-phase.md`, locates the seven tip-carrying
      `commit-docs.sh` call sites (`BASE_COMMIT`, `LAUNCH_TIP`, `RECONCILE_TIP`,
      `ROUTEBACK_TIP`, `TERMINAL_TIP`, `ABORT_TIP`, `COMPLETION_TIP`), and asserts for each:
      the capture expression contains `rev-parse em-workflow/{feature}/integration`, no
      capture uses `rev-parse HEAD`, every `reset --hard` in the site targets
      `em-workflow/{feature}/integration`, and the capture index is less than the refresh
      index.
- [ ] **TS-2** (automated, covers AC2 → FR1, NFR1): A test asserts the Branch & Worktree
      Model exit-4 recovery bullet states re-capture from the branch ref before the refresh,
      and that this order matches the order asserted per-site in TS-1 (same
      capture-before-refresh relation), so first attempt and retry cannot diverge.
- [ ] **TS-3** (automated, covers AC3 → FR8, NFR4): A test reads
      `em-workflow/scripts/commit-docs.sh` and asserts that the `expected_base_tip`
      description and the RECOVERY CONTRACT block describe capture from the branch ref
      before/independent of the refresh, that the old "captured at the caller's last refresh
      (e.g. right after its `git reset --hard`)" phrasing is gone, and that the carve-out
      sentence naming `implement-phase.md` Step I.2.c's route-back commit is still present
      verbatim.
- [ ] **TS-4** (automated, covers AC3 → FR8, NFR4): A test asserts `commit-docs.sh`'s
      executable body is unchanged: every non-comment line of the script is byte-identical
      to the pre-change version (e.g. by comparing the comment-stripped source against a
      pinned expectation), confirming the change is comment-only.

### Integration Tests

- [ ] **TS-5** (command, covers AC4 → FR7, NFR2, NFR3): Run
      `python3 -m unittest discover -s tests` from the integration worktree root; the whole
      suite passes, including the amended `tests/test_implement_routeback_gate.py` and the
      untouched `tests/test_review_implement_develop_lock_contracts.py`,
      `tests/test_recycled_task_id_consistency.py` and
      `tests/test_routeback_reset_scope_consistency.py`.
- [ ] **TS-6** (manual-diff, covers AC4 → FR7, NFR2, NFR3): Inspect `git diff` over
      `tests/`: the only pre-existing module touched is
      `tests/test_implement_routeback_gate.py`, and within it only the route-back order pin
      (~486-502), the abort tip-capture literal (~817-818) and the abort order pin
      (~829-841) changed; no other assertion or module in the diff.

### E2E Tests

**Existing E2E tests**: None — no E2E input paths were resolved for this feature.
**Run command**: Not detected.

### Edge Cases

- [ ] **TS-7** (negative, covers AC5 → FR9, NFR5): With the new uniformity test in place,
      temporarily reverting one converted site to the post-refresh `rev-parse HEAD` capture
      form makes that test fail, and reverting the change makes it pass again — the test
      genuinely detects drift rather than trivially passing.
- [ ] **TS-8** (manual-diff, covers AC6 → FR10): Read
      `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` and
      confirm both carry the identical new version string, greater than 0.1.45 by one patch
      step.

### Performance Tests

Not applicable — the change has no runtime execution path to load- or stress-test.

## Security Considerations

- **Authentication:** Not applicable — no authenticated surface is introduced or changed.
- **Authorization:** Not applicable — no authorization decision is introduced or changed.
- **Input Validation:** Not applicable — `commit-docs.sh`'s argument handling is
  byte-identical after the change (NFR4).
- **Data Protection:** Not applicable — no data at rest or in transit is involved.
- **XSS Prevention:** Not applicable — no rendered user interface.
- **SQL Injection Prevention:** Not applicable — no database.
- **CSRF Protection:** Not applicable — no HTTP request surface.
- **Repository-state safety (NFR5):** the one safety-relevant invariant. No site may target
  `reset --hard` at a captured SHA; because the integration worktree has an attached HEAD,
  such a reset rewinds the branch ref itself and silently discards a concurrent
  `merge-task.sh` merge commit. Every refresh target stays the branch name
  `em-workflow/{feature}/integration`, and TS-1 checks this mechanically.

## Error Handling

### Error Codes

Not applicable — this feature defines no error codes. `commit-docs.sh`'s exit codes,
including exit 4, are unchanged (NFR4); the exit-4 recovery procedure the prose references
lives in `implement-phase.md`'s Branch & Worktree Model bullet and is not modified (FR1).

### Error Flow

The only error path the documents describe, unchanged in mechanism and now stated
identically at first attempt and on retry:

```
commit-docs.sh exits 4 (stale expected_base_tip)
  → re-capture the tip from the branch ref
  → refresh the integration worktree with the branch name as target
  → re-write the docs and retry the commit
```

## Performance Optimization

### Performance Goals

Not applicable — no runtime performance target attaches to a documentation, comment and
test change.

### Optimization Strategies

Not applicable (same reason).

### Caching Strategy

Not applicable at runtime. The only cache-adjacent concern is plugin distribution: FR10's
version bump is what causes an installed plugin cache to pick up the changed files.

## Success Criteria

- [ ] All functional requirements (FR1-FR10) are implemented.
- [ ] All non-functional requirements (NFR1-NFR6) are satisfied.
- [ ] All acceptance criteria AC1-AC6 hold.
- [ ] All test scenarios TS-1 through TS-8 pass.
- [ ] `python3 -m unittest discover -s tests` passes in full (AC4 / TS-5).
- [ ] The change set is contained in the Declared Change Set above (NFR6).
- [ ] Documentation is complete: `implement-phase.md` and `commit-docs.sh` prose are
      internally consistent (NFR1, AC3).
- [ ] Code review is completed.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None. FR1-FR10 and NFR1-NFR6 are all `resolved`; no requirement carries `status: tbd`.

## Implementation Phases (if applicable)

Not applicable — the resolved requirements define no phased delivery. The design step is
`skipped`: the change touches only protocol prose (`implement-phase.md`), shell comments
(`commit-docs.sh`), Python test assertions and two version manifests, with no visual
surface, no user-facing interaction surface, and no design tokens or screens to define, so
DESIGN.md and mockups would carry no content.

## Assumptions

These are the resolved requirements' assumptions, carried through unchanged. The full
Japanese rendering is in `REQUIREMENTS.md` section 14.1.

- **a1-base-is-pr17-head:** This feature's integration branch is based on
  `em-workflow/exit4-tip-argument/integration` — PR 17's head — NOT on `main`. The two PR 17
  sites (Step I.2.a `LAUNCH_TIP`, Step I.3 `COMPLETION_TIP`) and the exit-4 recovery
  bullet's branch-ref wording are therefore already present in the working base. If the base
  were `main`, the "5 sites to convert, 2 already correct" split would be wrong and the whole
  change set would change shape.
- **a2-seven-sites-canonical:** The seven enumerated invocations are the complete set of
  tip-carrying `commit-docs.sh` call sites in `implement-phase.md`. Other mentions of
  `commit-docs.sh` in that document (the Branch & Worktree Model bullets, the exit-4
  recovery prose, the Step I.2.c failure prose at ~541) are references to the mechanism, not
  additional call sites, and are edited only where FR8/FR1 consistency requires it.
- **a3-carveout-untouched:** The Step I.2.c route-back exit-4 unreachability carve-out —
  both in `implement-phase.md` and in `commit-docs.sh`'s RECOVERY CONTRACT — remains valid
  and unmodified. It reasons about whether exit 4 can occur at that site, which is orthogonal
  to how the tip is captured; converting that site's capture form does not weaken or
  strengthen the proof.
- **a4-wake-phase-pin-analysis-valid:** `TestImplementPhaseWakePhaseOrdering` pins only the
  relative order of "Refresh the integration worktree FIRST" / "Update workflow.yaml, then
  commit" / the wake-phase commit literal, and constrains neither the capture line's position
  nor the capture command's form. Verified against the module's current source during
  analysis.
- **a5-step-i1-gains-a-refresh:** Step I.1 has no `reset --hard` today. FR5's
  capture-then-refresh resolution therefore ADDS a refresh operation to that step. This is
  accepted as intended: the integration worktree never carries uncommitted state across turns
  (NFR2 of `implement-phase.md`), so the added refresh is safe and makes the baseline commit
  consistent with every other site.
- **a6-version-bump-is-patch:** The bump is a single patch step (0.1.45 -> 0.1.46). No
  behavior of any executable changes, so neither minor nor major applies.
- **a7-new-test-is-python-unittest-in-tests:** The new uniformity test is a Python unittest
  module placed under `tests/` so `python3 -m unittest discover -s tests` picks it up,
  matching every existing protocol-document consistency test in this repository. No new test
  framework or runner is introduced.
- **a8-task-description-site-count:** The task description's "6 sites" framing is superseded
  by FR4's seven-site set. The description omitted the Step I.2.c rejected-path
  `TERMINAL_TIP` site, which is bound by the same bounded exit-4 recovery as the others.

## References

- Requirements document (Japanese):
  `feature-docs/tip-capture-idiom-unification/REQUIREMENTS.md`
- Implement-phase SSOT: `em-workflow/references/implement-phase.md`
- Docs-commit script: `em-workflow/scripts/commit-docs.sh`
- Amended test module: `tests/test_implement_routeback_gate.py`
- Untouched pinning modules: `tests/test_review_implement_develop_lock_contracts.py`,
  `tests/test_recycled_task_id_consistency.py`,
  `tests/test_routeback_reset_scope_consistency.py`
- Version manifests: `em-workflow/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`
