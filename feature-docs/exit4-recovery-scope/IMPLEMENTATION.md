# Implementation Plan: exit4-recovery-scope

## Overview

Restore the implement phase's exit-4 bounded-recovery contract to a universally
quantified scope over every `commit-docs.sh` call site in that phase with exactly
one named carve-out, and pin the new wording with tests plus a lockstep plugin
version bump. The change is documentation prose plus two version fields; no
executable line of any script changes (NFR1).

## Technology Stack

- **Markup**: Markdown — the protocol documents under `em-workflow/references/`
  and `em-workflow/skills/` are the artifacts this feature edits and reads.
- **Data format**: JSON — the two plugin manifests carrying the `version` field.
- **Test framework**: Python standard-library `unittest`, discovered from the
  repository's `tests/` directory (the project test command in workflow.yaml).
- **New dependencies**: none. Nothing is added to any manifest beyond the version
  value, so there is no new dependency license to record. `project.license` is
  `none`, so no license compatibility constraint applies to this feature.

## Layer Structure

Four document layers, with a one-way dependency direction:

| Layer | Member | Role in this feature |
|---|---|---|
| Definition (sole owner) | `em-workflow/references/implement-phase.md`, the `**exit-4 recovery**` bullet in `## Branch & Worktree Model (READ FIRST)` | Owns the bounded-recovery procedure AND its scope. The only file edited for FR1-FR4. |
| Citing | `em-workflow/scripts/commit-docs.sh` RECOVERY CONTRACT header; `em-workflow/skills/develop/SKILL.md` exit-4 paragraph | Cite the carve-out; already in universal-with-one-exclusion form (A6). Read-only here. |
| Pinning | `tests/test_implement_routeback_gate.py` | Asserts the wording of the definition and citing layers. Extended, never reduced. |
| Packaging | `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | Carry the duplicated `version` value that gates plugin-cache freshness. |

Allowed direction of dependency: the pinning layer reads the definition and
citing layers; the citing layer cites the definition layer. Never the reverse —
a test assertion never justifies moving a rule out of the definition layer, and
a citing document never grows into a second definition of the enumeration
(NFR5).

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| exit-4 recovery bullet (definition layer) | Single owner of the bounded-recovery procedure and of which call sites it binds | **Pre**: a `commit-docs.sh` invocation in the implement phase returned exit 4. **Post**: the reader can decide, for that call site, whether the bounded recovery applies — the answer is "yes" for every call site in the phase except the one carve-out named in the same bullet. The bullet is the only place the procedure itself is stated. | task0001 |
| Version-field pair | Plugin-cache freshness signal | **Pre**: both fields read the pre-change value. **Post**: both fields read the identical bumped value, changed within the same commit. Divergence between the two files is a defect regardless of which value is "newer". | task0001 |

Both entries are consumed by a single task in this feature; they are recorded
here because the definition-layer bullet is cited by documents outside this
feature's change set, so its contract must survive the edit unchanged in
substance.

## Conventions

### Wording constraints on the definition-layer bullet

The edit is constrained simultaneously by presence and absence requirements. All
of them are objectively checkable string conditions and are the reason the task
plan and the test module are written together.

- **Must be present** (FR5): the site names "Step I.1's baseline commit",
  "Step I.2.b's wake-phase commit", "Step I.2.c's rejected-path terminal status
  commit"; the carve-out sentence beginning "The single carve-out is Step I.2.c's
  **route-back** commit"; the unreachability-chain phrasing; the
  ref-advancing-paths phrasing; and the recovery-procedure sentences containing
  "retry `commit-docs.sh` once", "second exit 4" and "stops the phase".
- **Must be absent** (FR5, EC4): the phrase the tests track as
  OLD_EXIT4_ENUMERATION_TAIL — the exact comma-and sequence "Step I.2.b's
  wake-phase commit, and Step I.2.c's route-back commit" — and the phrase tracked
  as OLD_EXIT4_MERGETASK_ONLY_PHRASE. Widening the enumeration must not
  accidentally reproduce that exact word order.
- **Must become absent** (FR1): the closed-enumeration tail that today claims
  exhaustiveness — "the three `commit-docs.sh` call sites in this phase where
  exit 4 can occur".
- **Must become present** (FR1, FR2): a universal quantifier over every
  `commit-docs.sh` call site in the implement phase, and explicit mention of
  Step I.2.a's launch-time status/branch write and Step I.3's completion write
  on the bound side.

Exact replacement wording is not fixed by this plan (A5): what is required is the
universal quantifier plus exactly one named exclusion, with the enumeration
readable as illustrative rather than closed (EC1).

### Test-module conventions (NFR6)

- Content assertions run against the module's whitespace-normalized copy of the
  document, not the raw text.
- Every new absence assertion is paired with a regression proof — in the module's
  existing regressions test class — showing that the same matcher flags the
  pre-change wording. An absence assertion with no such pair is indistinguishable
  from a matcher that never matches anything.
- Tests are only added. No test is deleted, renamed away, or skipped, and the
  module's test-method count does not decrease (NFR3).

### Edit containment

The edit stays inside the Branch & Worktree Model bullet. Two existing tests
operate on wider scopes — a byte-identity check on a batch-mode paragraph and a
bare-git-command check over the Step I.2.c section — and neither may be disturbed
(EC3). Two files are frozen and must not be modified to reach this outcome:
`em-workflow/references/workflow-patch.md` and
`em-workflow/scripts/validate-worker-output.py` (NFR2).

### Citation, not restatement (NFR5)

Rules owned elsewhere — the write-then-commit rule that produces the Step I.2.a
and Step I.3 commits, and the widened Step I.2.c gate — are cited, never restated
in the bullet. The bullet stays the sole owner of the bounded-recovery procedure;
the two citing documents stay citations.

## Cross-task Design Decisions

### D1: Single task for all four files

The four files in the expected file set are one indivisible unit of work: the
test module pins the exact wording produced by the document edit, so splitting
them would put a task's acceptance criteria outside its own worktree. The version
bump is joined to the same task because it must land in the same change as the
behavior it announces, and because the two version fields must move together.
Consequence: this plan has no cross-task ordering problem and no integration
wiring to own.

### D2: Illustrative enumeration under a universal scope

The bullet keeps a list of call sites, but the list serves as examples under the
universal scope rather than as the definition of the bound set. This is the
anti-staleness property the feature exists to restore: adding a future
`commit-docs.sh` call site to the implement phase must not require editing this
bullet for the new site to be bound. A replacement that merely lengthens the
closed list from three sites to five satisfies FR2 but fails FR1 and EC1.

### D3: The carve-out count stays exactly one

The single carve-out remains Step I.2.c's route-back commit, and the
rejected-path terminal status commit at the same step stays explicitly on the
bound side. The unreachability proof that follows the carve-out sentence reasons
over the orchestrator's own `commit-docs.sh` calls elsewhere in the phase; that
reasoning stays valid once the bound set is widened and must not be narrowed to
only the newly enumerated sites (EC2).

### D4: Agreement reached by editing one document

Two of the three SSOTs already state the universal-with-one-exclusion form (A6),
so three-SSOT agreement (FR4) is reached by editing the definition layer alone.
Editing either citing document to "help" would violate NFR5 by creating a second
definition, and would enlarge the change set beyond NFR4.

### D5: Version bump is lockstep, not sequential

Both manifests carry a duplicate of the same plugin version. They are updated in
the same change to the same value (A2). A change that bumps only one of them is a
defect even though each file individually parses and each value individually
looks plausible.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Enumeration silently re-closes: a dash list after the universal phrase reads as exhaustive to a future maintainer (EC1) | Medium | High — reintroduces the exact defect this feature removes | D2: the list must be lexically marked as examples; a test asserts the universal-scope phrasing is present and the exhaustiveness claim absent |
| Unreachability proof narrowed to the newly enumerated sites (EC2) | Low | Medium — weakens the carve-out justification | D3: the proof sentences survive unchanged; existing assertions cover the carve-out sentence and chain phrasing |
| Old comma-and phrasing reproduced while widening the list (EC4) | Medium | Medium — an existing absence assertion fails | Word the widened list so the forbidden exact sequence never forms; existing absence assertion catches it |
| Wide-scope tests disturbed by an edit that spills outside the bullet (EC3) | Low | Medium | Edit containment convention; full-suite run is the gate |
| Another test module also pins the bullet's wording (A4) | Medium | Medium | Discharged by the full-suite run, never by inspection |
| New absence assertion written with a matcher that can never match | Low | Medium — a green test proving nothing | NFR6 pairing rule: every new absence assertion has a regression proof against the pre-change text |
| Only one of the two version fields bumped | Low | Medium — stale plugin cache or inconsistent manifests | D5 plus an explicit acceptance criterion naming both files |

## Open Questions

- [ ] None. Every FR/NFR maps to at least one task and at least one test
      scenario; there are no `tbd` requirements and no unresolved design
      decisions for this feature.
