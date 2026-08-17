# Feature: exit4-recovery-scope

Requirements document: `feature-docs/exit4-recovery-scope/REQUIREMENTS.md`.
Every requirement below is a rendering of that document; this SPEC adds no
requirement of its own.

## Overview

`em-workflow/references/implement-phase.md` currently scopes the `commit-docs.sh`
exit-4 bounded recovery to a closed three-site enumeration, while the other two
SSOTs — `em-workflow/scripts/commit-docs.sh`'s RECOVERY CONTRACT header and
`em-workflow/skills/develop/SKILL.md`'s exit-4 paragraph — scope it universally
with exactly one carve-out. This feature restores the universal-with-one-exclusion
form in implement-phase.md so that the orchestrator's exit-4 behavior is defined at
every `commit-docs.sh` call site in the implement phase, and pins the new wording
with tests plus a lockstep version bump.

## Objectives

- Restore a single, unambiguous exit-4 recovery contract for the implement phase,
  defined at EVERY `commit-docs.sh` call site in that phase.
- Put Step I.2.a's launch/refill status commit and Step I.3's completion commit
  explicitly on the bound side — they are today neither bound nor carved out,
  undefined precisely in the refill window where a concurrent `merge-task.sh` ref
  advance (exit 4) is most likely.
- Bring implement-phase.md into agreement with the two SSOTs that already state
  the universal-with-one-exclusion form, without editing either of them.
- Keep the enumeration from going stale again when a new call site is added, by
  making it illustrative under a universal scope rather than a closed set.

## User Stories

### US1: Defined exit-4 behavior at the refill window
As the em-workflow orchestrator, I want the exit-4 recovery bullet to bind every
`commit-docs.sh` call site in the implement phase, so that when Step I.2.a's
launch/refill status commit or Step I.3's completion commit returns exit 4 I know
that the bounded recovery applies.

**Acceptance Criteria:**
- [ ] AC1: implement-phase.md's exit-4 recovery bullet scopes the bounded recovery
      universally over every `commit-docs.sh` call site in the implement phase, and
      the carve-out is exactly one site: Step I.2.c's route-back commit.
- [ ] AC2: Step I.2.a's launch/refill status commit and Step I.3's completion
      commit are named explicitly on the bound side of that bullet.

### US2: Three SSOTs that agree
As a reader of the protocol documents, I want implement-phase.md,
`commit-docs.sh`'s RECOVERY CONTRACT header and `develop/SKILL.md`'s exit-4
paragraph to say the same thing, so that whichever document I read I reach the same
conclusion about which call sites are bound and which single site is carved out.

**Acceptance Criteria:**
- [ ] AC3: The three documents state the same thing about the carved-out site and
      about the universal binding of every other site.

### US3: The new wording stays pinned
As a maintainer of this repository, I want the new wording pinned by tests and the
plugin version bumped in lockstep, so that a future edit cannot silently re-close
the enumeration and so that the installed plugin cache picks up the change.

**Acceptance Criteria:**
- [ ] AC4: All strings `tests/test_implement_routeback_gate.py` currently fixes
      remain satisfied (presences listed in FR5; absence of
      OLD_EXIT4_ENUMERATION_TAIL maintained).
- [ ] AC5: The removed closed-enumeration wording gets its own absence assertion
      plus a paired regression proof against the pre-change text.
- [ ] AC6: `python3 -m unittest discover -s tests` passes.
- [ ] AC7: `em-workflow/.claude-plugin/plugin.json` and
      `.claude-plugin/marketplace.json` both read `0.1.43`.

## Technical Requirements

### Functional Requirements

- **FR1 — Exit-4 recovery scope restored to universal quantification:** The
  `**exit-4 recovery**` bullet in implement-phase.md's `## Branch & Worktree Model
  (READ FIRST)` section scopes the bounded recovery over EVERY `commit-docs.sh`
  call site in the implement phase, with exactly one exclusion named in the same
  bullet. The closed-enumeration phrasing currently at lines 43-46 ("applies to
  Step I.1's baseline commit, Step I.2.b's wake-phase commit and Step I.2.c's
  rejected-path terminal status commit — the three `commit-docs.sh` call sites in
  this phase where exit 4 can occur") no longer claims exhaustiveness.
  *(status: resolved)*
- **FR2 — I.2.a and I.3 commits explicitly on the bound side:** The bullet's
  illustrative enumeration explicitly includes Step I.2.a's launch-time
  `tasks.{T}.status = in_progress` / `tasks.{T}.branch` write and Step I.3's
  `implement = completed` / `completed_at_commit` write, alongside the three sites
  named today. The enumeration reads as examples under the universal scope, never
  as a closed set that can go stale again when a new call site is added.
  *(status: resolved)*
- **FR3 — Single carve-out, unchanged:** The sole carve-out remains Step I.2.c's
  **route-back** commit. The existing sentence "The single carve-out is Step
  I.2.c's **route-back** commit — distinct from the rejected-path terminal status
  commit enumerated above, which IS bound by this bounded recovery" and the
  unreachability-proof sentences that follow it survive. *(status: resolved)*
- **FR4 — Three-SSOT agreement on the carve-out:** After the change,
  implement-phase.md, `commit-docs.sh`'s RECOVERY CONTRACT header and
  `develop/SKILL.md`'s exit-4 paragraph state the same thing about which call sites
  are bound and which single site is carved out. The latter two already state the
  universal-with-one-exclusion form, so satisfying this requirement needs no edit
  to either file (assumption A6). *(status: resolved)*
- **FR5 — Existing pinned strings preserved:** Every string
  `tests/test_implement_routeback_gate.py` currently fixes stays satisfied:
  presence of "Step I.1's baseline commit", "Step I.2.b's wake-phase commit",
  "Step I.2.c's rejected-path terminal status commit", "The single carve-out is
  Step I.2.c's **route-back** commit", the unreachability-chain and
  ref-advancing-paths phrases, the recovery-procedure sentences ("retry
  `commit-docs.sh` once" / "second exit 4" / "stops the phase"); and continued
  absence of OLD_EXIT4_ENUMERATION_TAIL ("Step I.2.b's wake-phase commit, and Step
  I.2.c's route-back commit") and OLD_EXIT4_MERGETASK_ONLY_PHRASE.
  *(status: resolved)*
- **FR6 — Version bump in lockstep:** `em-workflow/.claude-plugin/plugin.json` and
  the `em-workflow` entry in `.claude-plugin/marketplace.json` are both bumped from
  `0.1.42` to `0.1.43` in the same change. *(status: resolved)*

### Non-Functional Requirements

- **NFR1 — Documentation/comment-only change:** No executable line of any script
  changes. The change touches implement-phase.md prose plus the two version fields;
  no runtime behavior of `commit-docs.sh` or any hook is altered.
- **NFR2 — Frozen files untouched:** `em-workflow/references/workflow-patch.md` and
  `em-workflow/scripts/validate-worker-output.py` are frozen and are not modified
  to reach this outcome.
- **NFR3 — Suite green, no test lost:** `python3 -m unittest discover -s tests`
  passes. No test is removed, renamed away, or skipped;
  `test_implement_routeback_gate.py`'s test method count does not decrease.
- **NFR4 — Minimal, contained file set:** Expected file set:
  `em-workflow/references/implement-phase.md`,
  `tests/test_implement_routeback_gate.py`,
  `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`.
- **NFR5 — SSOT discipline preserved:** The Branch & Worktree Model bullet stays
  the sole owner of the bounded recovery procedure; the other two documents keep
  citing the carve-out without becoming a second definition of the enumeration. No
  rule owned elsewhere (NFR2's write-then-commit rule, the widened I.2.c gate) is
  restated — only cited, as today.
- **NFR6 — Test-module conventions:** New assertions follow the module's
  established discipline: content assertions against a whitespace-normalized copy,
  and every new absence assertion paired with a regression proof that its matcher
  flags the pre-change wording (mirroring TestValidationDetectsRegressions).

## Implementation Approach

### Architecture

This change has no runtime architecture: per NFR1 it is a documentation/comment-only
change plus two version fields. The relevant structure is the relationship between
the three SSOTs and the test module that pins their wording.

**Document Diagram:**
```
┌──────────────────────────────────────────────────────────────┐
│ em-workflow/references/implement-phase.md                    │
│   ## Branch & Worktree Model (READ FIRST)                    │
│     - **exit-4 recovery** bullet   <-- SOLE OWNER (NFR5)     │
│         universal scope + exactly one named carve-out         │
│         (THE ONLY FILE EDITED for FR1-FR4)                    │
└──────────────────────────────────────────────────────────────┘
        ▲ cites (no second definition)      ▲ cites
        │                                    │
┌───────┴──────────────────────┐  ┌─────────┴────────────────────┐
│ em-workflow/scripts/         │  │ em-workflow/skills/develop/  │
│   commit-docs.sh             │  │   SKILL.md                    │
│   RECOVERY CONTRACT header   │  │   exit-4 paragraph            │
│   already universal+1 (A6)   │  │   already universal+1 (A6)    │
│   NOT EDITED                 │  │   NOT EDITED                  │
└──────────────────────────────┘  └──────────────────────────────┘
        ▲                ▲                 ▲
        └────────────────┴─────────────────┘ pins wording
                         │
┌────────────────────────┴─────────────────────────────────────┐
│ tests/test_implement_routeback_gate.py                        │
│   TestExit4EnumerationExcludesRouteBackCommit  (extended)     │
│   TestExit4CarveOutStatedInAllThreeSSOTs       (unchanged)    │
│   TestValidationDetectsRegressions             (extended)     │
└──────────────────────────────────────────────────────────────┘
```

### Data Flow

The exit-4 control flow the bullet governs, after the change:

```
Step I.x artifact write → commit-docs.sh → exit 4 (concurrent merge-task.sh ref advance)
   → bullet's universal scope: is this site the single carve-out (I.2.c route-back)?
       no  → bounded recovery: reset --hard, re-capture tip, re-apply same
             transition re-derived from source, retry commit-docs.sh once
               → second exit 4 → stop phase with a report naming the call site
       yes → the carve-out's own unreachability proof + stop-with-report terminal
```

Call sites on the bound side after the change include Step I.1's baseline commit,
Step I.2.a's launch-time `tasks.{T}.status = in_progress` / `tasks.{T}.branch`
write, Step I.2.b's wake-phase commit, Step I.2.c's rejected-path terminal status
commit, and Step I.3's `implement = completed` / `completed_at_commit` write — as
examples under the universal scope, not as a closed set (FR2).

### API Design

Not applicable. No interface is added or changed (NFR1).

### Database Schema

Not applicable. No data model is involved (NFR1).

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/implement-phase.md`: the edit target; sole owner of the
  bounded recovery procedure (NFR5).
- `em-workflow/scripts/commit-docs.sh`: RECOVERY CONTRACT header; already states
  the universal-with-one-exclusion form, read-only here (FR4, A6).
- `em-workflow/skills/develop/SKILL.md`: exit-4 paragraph; already states the
  universal-with-one-exclusion form, read-only here (FR4, A6).
- `tests/test_implement_routeback_gate.py`: pins the bullet's wording; extended by
  TS1-TS3 (FR5, NFR6).
- `em-workflow/references/workflow-patch.md`,
  `em-workflow/scripts/validate-worker-output.py`: frozen; not modified (NFR2).

**External Dependencies:**
- `python3` `unittest`: the suite runner for NFR3 / AC6
  (`python3 -m unittest discover -s tests`).

### File Structure

```
em-workflow/
├── references/
│   └── implement-phase.md          # exit-4 recovery bullet rewritten (FR1-FR3)
└── .claude-plugin/
    └── plugin.json                 # version 0.1.42 -> 0.1.43 (FR6)
tests/
└── test_implement_routeback_gate.py  # new assertions (TS1-TS3), none removed
.claude-plugin/
└── marketplace.json                # em-workflow version 0.1.42 -> 0.1.43 (FR6)
```

## Declared Change Set

Feature-specific paths (NFR4's expected file set):

- `em-workflow/references/implement-phase.md`
- `tests/test_implement_routeback_gate.py`
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/exit4-recovery-scope/**`
- `test-docs/exit4-recovery-scope/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`workflow.yaml`, `phase-state/`, `tasks/`, `reviews/roundN.yaml`,
`VERIFICATION.md`, `retrospect.yaml`, and the design artifacts the design
step produces. These are generated and owned by the phase documents and by
`references/phase-state.md`; this section cites them and restates none of
their rules.

`test-docs/{feature}/**` covers `test-docs/exit4-recovery-scope/{T}.tests.yaml`,
the per-task test record. It is generated and owned by `implement-phase.md`;
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
- [ ] **TS1** (FR1): Assert the bullet states a universal scope (e.g. an "every
      `commit-docs.sh` call site in this phase" matcher) — extends
      TestExit4EnumerationExcludesRouteBackCommit in
      `tests/test_implement_routeback_gate.py`.
- [ ] **TS2** (FR2): Assert Step I.2.a's launch-time write and Step I.3's
      completion write are both named inside the bullet's bound enumeration.
- [ ] **TS3** (FR1, FR5): Absence assertion for the closed-enumeration phrase
      ("the three `commit-docs.sh` call sites in this phase where exit 4 can
      occur"), plus a matcher-flags-pre-change-wording proof in
      TestValidationDetectsRegressions.
- [ ] **TS4** (FR3, FR4, FR5): Existing assertions in
      TestExit4EnumerationExcludesRouteBackCommit and
      TestExit4CarveOutStatedInAllThreeSSOTs run unchanged and pass.

### Integration Tests
- [ ] **TS5** (NFR3): Whole-suite run: `python3 -m unittest discover -s tests`
      green, catching any other module that pins the bullet's wording.
- [ ] **TS6** (FR6): Plugin-invariant / version consistency: the two version
      fields agree at `0.1.43`.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] **EC1** (FR1, FR2): Re-closing the enumeration: if the replacement keeps a
      dash-list after the universal phrase, a future reader may still read the list
      as exhaustive. The wording must make the list illustrative under the
      universal scope.
- [ ] **EC2** (FR3): The unreachability proof for the carve-out already reasons
      over "the orchestrator's own `commit-docs.sh` calls elsewhere in this phase",
      which stays correct after widening the bound set — the proof must not be
      narrowed to the newly enumerated sites.
- [ ] **EC3** (NFR3): `test_batch_mode_paragraph_is_byte_identical` and
      `test_no_bare_git_commit_or_add_lines` operate on the whole file / the I.2.c
      section; the edit is confined to the Branch & Worktree Model bullet and must
      not disturb either.
- [ ] **EC4** (FR5): OLD_EXIT4_ENUMERATION_TAIL ("Step I.2.b's wake-phase commit,
      and Step I.2.c's route-back commit") must stay absent — the widened
      enumeration must not reintroduce that exact comma-and phrasing.

### Performance Tests
Not applicable. Per NFR1 no executable line changes, so there is no runtime
behavior to load- or stress-test.

## Security Considerations

Not applicable. Per NFR1 this is a documentation/comment-only change plus two
version fields; no authentication, authorization, input-handling, or data-protection
surface is touched.

## Error Handling

The bullet this feature rewrites is itself the error-handling contract for
`commit-docs.sh`'s exit 4. After the change it reads as follows.

| Exit code | Scope after the change | Defined handling |
|---|---|---|
| 4 (stale worktree) | Universally bound: EVERY `commit-docs.sh` call site in the implement phase, except the single carve-out (FR1) | Bounded recovery: refresh the integration worktree, re-capture the tip, re-apply the same intended state transition re-derived from source, retry `commit-docs.sh` once |
| 4, second occurrence at a bound site | Same bound set | Stop the phase immediately with a report naming the call site and the task(s) involved; never loop unbounded |
| non-zero at Step I.2.c's route-back commit | The single carve-out (FR3) | Covered by that call site's own unreachability proof and its stop-with-report terminal, unchanged by this feature |

### Error Flow

```
commit-docs.sh exit 4 → consult the exit-4 recovery bullet's universal scope
  → bound site   → bounded recovery (one retry) → second exit 4 → stop with report
  → carve-out    → unreachability proof + route-back site's stop-with-report terminal
```

## Performance Optimization

Not applicable (NFR1).

## Success Criteria

- [ ] All functional requirements (FR1-FR6) are implemented.
- [ ] All test scenarios (TS1-TS6) pass.
- [ ] AC1: the bullet's bounded recovery is universally scoped over every
      `commit-docs.sh` call site in the implement phase, with exactly one carve-out
      (Step I.2.c's route-back commit).
- [ ] AC2: Step I.2.a's launch/refill status commit and Step I.3's completion
      commit are named explicitly on the bound side.
- [ ] AC3: the three SSOTs state the same thing about the carved-out site and the
      universal binding of every other site.
- [ ] AC4: every string `tests/test_implement_routeback_gate.py` currently fixes
      remains satisfied.
- [ ] AC5: the removed closed-enumeration wording has its own absence assertion
      plus a paired regression proof.
- [ ] AC6: `python3 -m unittest discover -s tests` passes.
- [ ] AC7: `em-workflow/.claude-plugin/plugin.json` and
      `.claude-plugin/marketplace.json` both read `0.1.43`.
- [ ] NFR2: frozen files (`workflow-patch.md`, `validate-worker-output.py`)
      untouched.
- [ ] NFR4: the change set is contained in the expected four-file set plus the
      declared workflow-generated entries.
- [ ] NFR5: the Branch & Worktree Model bullet remains the sole owner of the
      bounded recovery procedure.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None. Every functional requirement is `status: resolved`; there are no `tbd`
requirements for this feature.

## Assumptions

Carried verbatim in substance from the resolved requirements analysis; the
implementation must hold to them.

- **A1:** PR #6 is merged into `main` and this integration branch forks from that
  merged `main` (orchestrator-verified), so the task description's "fix on PR #6's
  branch if unmerged" alternative does not apply.
- **A2:** The task description names only `plugin.json` for the version bump, but
  the repository keeps a duplicate `version` for `em-workflow` in
  `.claude-plugin/marketplace.json` (currently `0.1.42`). Both are bumped to
  `0.1.43` in lockstep.
- **A3:** Step I.2.a and Step I.3 have no textually explicit `commit-docs.sh`
  invocation in implement-phase.md — their commits exist only via the Branch &
  Worktree Model's NFR2 write-then-commit rule. Adding explicit invocation lines at
  those steps is NOT in scope; the exit-4 bullet names them as the commits that
  rule produces.
- **A4:** Test modules other than `tests/test_implement_routeback_gate.py` may also
  pin the exit-4 bullet's wording; discharged by the full-suite run, not by
  inspection.
- **A5:** The architecture reviewer's suggested replacement text is treated as a
  starting point, not a byte-for-byte requirement. What is required is the
  universal quantifier plus exactly one named exclusion.
- **A6:** Verified by reading both files: `commit-docs.sh` already reads "binding on
  every caller EXCEPT ... today exactly one such site: ... Step I.2.c's route-back
  commit", and `develop/SKILL.md` already reads "commit-docs.sh の全呼び出し箇所で
  共通 ... ただし ... Step I.2.c の route-back コミットは対象外". Only
  implement-phase.md diverges, so AC3 is reached by editing implement-phase.md
  alone.

## Design Step

Skipped. No UI surface whatsoever. The change is protocol-document prose plus two
version fields; there is no user-visible interface, no styling and no design-system
involvement.

## References

- Requirements document: `feature-docs/exit4-recovery-scope/REQUIREMENTS.md`
- Edit target and sole owner of the bounded recovery procedure:
  `em-workflow/references/implement-phase.md`
- RECOVERY CONTRACT header (already universal-with-one-exclusion):
  `em-workflow/scripts/commit-docs.sh`
- exit-4 paragraph (already universal-with-one-exclusion):
  `em-workflow/skills/develop/SKILL.md`
- Wording-pinning test module: `tests/test_implement_routeback_gate.py`
- Version fields: `em-workflow/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`
