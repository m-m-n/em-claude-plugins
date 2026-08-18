# Implementation Plan: i2c-routeback-reconciliation

## Overview

This feature delivers one markdown verification record that discharges SPEC.md AC1-AC12 against
text that is already merged into `main`. Nothing executable is built, and every source consulted —
the protocol document, both document-contract test modules, both source SPECs and both plugin
manifests — is a read-only input (FR7, NFR2).

## Technology Stack

- **Language / Framework**: markdown only. The record is a document; the feature adds no code, no
  hook, no script and no test matcher (NFR4).
- **Key libraries**: none. No new dependency is introduced by this feature, so no new license enters
  the project. `project.license` is `none` (no LICENSE file in the repository), which imposes no
  compatibility constraint; the observed plugin/marketplace version pair is evidence to be recorded,
  never a file to edit (FR5).
- **Verification tooling**: the project's single command, `python3 -m unittest discover -s tests`,
  run over the unmodified suite. No new mechanical checker is added (NFR4).

## Layer Structure

Three layers, with a strictly one-way dependency direction:

1. **Read-only evidence sources** — `em-workflow/references/implement-phase.md`
   (`### I.2.c: Failed handling`), `tests/test_implement_routeback_gate.py`,
   `tests/test_recycled_task_id_consistency.py`, `feature-docs/recycled-task-id-consistency/SPEC.md`,
   `feature-docs/routeback-gate-postcondition/SPEC.md`,
   `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, and the
   orchestrator observations carried in SPEC.md ASM2.
2. **The verification record** — `feature-docs/i2c-routeback-reconciliation/RECONCILIATION-RECORD.md`.
   Depends on layer 1 by citation only.
3. **Workflow verification artifacts** — `VERIFICATION.md` and the per-task test record under
   `test-docs/i2c-routeback-reconciliation/`. These check layer 2; layer 2 never depends on them.

**Allowed write set for this feature** (the dependency direction stated as a rule): only
`feature-docs/i2c-routeback-reconciliation/**` and `test-docs/i2c-routeback-reconciliation/**`.
Layer 1 is never written. Any path under `em-workflow/` or `tests/`, and either of
`em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`, appearing in the
change set is a defect, not a permitted extension (FR7, NFR2, AC11).

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| `RECONCILIATION-RECORD.md` | The feature's single verification record | Pre: every claim it carries has been re-observed from a layer-1 source during the same session that writes it. Post: it exposes exactly the seven sections named in "Record section contract" below, in that order, each section self-contained (a reader can re-check it without reading the others), and every claim carries an anchor in the "Anchor format" form | task0001, and any rework task later appended to this feature |
| Departure table | The single place every merged-vs-source departure is enumerated | Pre: a departure is listed here if and only if the merged text differs from a source SPEC's literal wording. Post: exactly three columns — source statement, merged statement, authoritative document — containing at minimum the two rows SPEC.md names, and no departure presented as "satisfied" (NFR3) | task0001, and any rework task later appended to this feature |

### Record section contract

The record's section order is fixed so a later reader (and any appended rework task) can address a
section without re-reading the whole document:

1. Merged gate condition (FR1)
2. Admitted-path ordering (FR2)
3. Rejected-path side effect (FR3)
4. Test-suite evidence (FR4)
5. Settled dispositions — version-bump non-applicability and PR #5 (FR5, FR6)
6. Departure table (NFR3)
7. Change-set scope statement (FR7, NFR2)

## Conventions

- **Anchor format (NFR1)**: every claim carries either (a) a quoted phrase from the merged text plus
  its containing section and the line range observed at writing time, or (b) a test module path plus
  a test-method name. The quoted phrase is the PRIMARY anchor and the line range the secondary one:
  a reader who finds the line numbers shifted locates the claim by the quoted phrase.
- **Classification vocabulary (NFR3)**: each source-SPEC statement compared against the merged text
  is classified as exactly one of `satisfied-verbatim`,
  `satisfied-under-the-reconciled-reading`, or `superseded`. The last two always name the
  authoritative document.
- **Identifier notation (NFR5)**: file paths, requirement IDs, status values, commit messages and
  test-method names are written in backticks; source-feature requirement IDs are always qualified by
  their feature name, because both source features use `FR`/`AC` numbering of their own.
- **Observation wording**: a recorded fact states what was observed and by which command or read
  (for example a test count, a version string, a diff listing). No claim rests on the task
  description's narrative (NFR1).
- **No rationale beyond the requirements (NFR5)**: the record states what holds and where it is
  anchored. It does not argue for the design decisions of either source feature.

## Cross-task Design Decisions

### D1: One record, therefore one task

SPEC.md's Implementation Approach names a single markdown verification record as the deliverable,
and FR7 makes it the feature's sole artifact. Splitting it across files would create a second
artifact; splitting one file across parallel tasks would make those tasks non-independent (all tasks
run fully in parallel, so two tasks rewriting the same record cannot be sequenced). The feature is
therefore decomposed into one task that owns the record end to end. The Shared Components contract
above still applies, because a rework task appended after review or verify writes the same file.

### D2: Read-only input boundary is a plan-time invariant

The reconciliation this feature is about is already merged. Correcting, improving or re-wording the
merged text is out of scope even where a reader might think it could be clearer: the record's job is
to state and anchor what is there. A discovered defect in a layer-1 source is reported as a finding,
never fixed inside this feature (FR7, NFR2).

### D3: Evidence precedes claim

Every claim is written only after its anchor has been re-observed in the current worktree. Line
ranges cited by SPEC.md are treated as starting points to be confirmed, not as facts to be copied:
when the observed range differs, the record carries the observed range and notes the difference.
This is what makes NFR1's "re-checkable without re-deriving the history" true rather than asserted.

### D4: The acceptance bar is the unmodified suite plus document reading

No new checker, matcher, hook or script is introduced (NFR4). Automated evidence comes from running
`python3 -m unittest discover -s tests` unchanged and from naming the existing test methods that pin
the merged form; everything else is document reading recorded with anchors.

### D5: Superseded statements are never presented as satisfied

Where the merged text departs from a source SPEC's literal wording, the departure table names the
source statement, the merged statement and the authoritative document. A superseded statement is
classified `superseded`, never quietly folded into a "satisfied" claim (NFR3, AC12). The reconciled
reading of the rejected path's "nothing" is stated as a reading with its adopting document named,
not as a plain restatement of either source.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Cited line ranges drift from the merged document's current state | Medium | Medium | Quote-first anchoring (Conventions); the observed range is recorded and any difference from SPEC.md's cited range is noted (D3) |
| A source statement that was superseded is recorded as satisfied | Medium | High | Fixed three-value classification vocabulary and the mandatory departure table (D5, NFR3) |
| The record edits or is believed to license editing a read-only input | Low | High | The allowed write set is stated as a rule in Layer Structure; the change-set scope statement (record section 7) and AC11 both check it |
| The record repeats the stale premise (PR #5 unmergeable) as current | Low | Medium | The disposition section states the premise as stale and names the evidence that superseded it |
| A quoted phrase occurs more than once in the merged text, making the anchor ambiguous | Low | Medium | Anchors pair the quoted phrase with its containing section, not with the phrase alone |

## Open Questions

- [ ] NFR5 (local documentation conventions) has no SPEC.md test scenario of its own; it is verified
      by the manual item in VERIFICATION.md rather than by a `TS-` scenario. Recorded here so the
      empty `tests` mapping for NFR5 in `workflow.yaml` reads as deliberate, not as an oversight.
