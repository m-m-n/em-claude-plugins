# Verification Document: routeback-admissibility-exits

## Overview

**Feature**: routeback-admissibility-exits /
**SPEC.md**: `feature-docs/routeback-admissibility-exits/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/routeback-admissibility-exits/IMPLEMENTATION.md`

This document covers the INTEGRATED verification of the feature, run after
every task is merged into the integration branch. Task-level criteria live in
`feature-docs/routeback-admissibility-exits/tasks/task0001.md` and
`feature-docs/routeback-admissibility-exits/tasks/task0002.md`.

## Build Verification

- Command: none — `project.components.main.build_command` is empty; this is a
  Markdown-and-Python-tests change with no build step.
- Expected: not applicable.

## Test Verification

- Command: `python3 -m unittest discover -s tests`, run from the repository
  root of the integration worktree.
- Expected: exit code 0, zero failures, zero errors, zero skips.
- Coverage target: not applicable — the project configures no coverage
  tooling. The equivalent guard is NFR2's discipline: no test removed or
  skipped and neither named module's test-method count decreased.

### Test Scenarios from SPEC.md

TS-1 through TS-7 are SPEC.md's own scenarios. TS-8 and TS-9 are verification-
plan additions covering the two requirement groups whose SPEC traceability row
carries no numbered scenario (FR5 / NFR1's solution-shape constraint, and
NFR4's aggregate run). TS-10 through TS-13 are review-round-1 rework additions
(task0002): TS-1 and TS-2 assert that the two exits are STATED, which the
delivered text satisfies while both exits remain unreachable in the states they
exist for — reachability is what the four scenarios below add.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Document contract: the I.2.c admissibility text states the exit or unreachability AC-1 requires, asserted against a whitespace-normalized slice of the I.2.c section | The gate blocks route-back whenever any task's journal last event reports a merge, sourced from the last-event replay alone and independent of the ancestor verification | Unit |
| TS-2 | Document contract: the stale-launched recovery of AC-2 is present and I.2.b step 1's existence check has a stated outcome | I.2.b step 1 states the failure condition, its effect, the recovery ending in a terminal journal event, and the residual unresolvable case; I.2.c cites it without restating | Unit |
| TS-3 | Absence plus paired negative proof: the falsified I.2.a justification is gone | The pre-change premise is absent from the normalized I.2.a section; the negative proof flags it in the verbatim pre-change sample captured from base 9f5d7ae; the retained-anchor guard passes | Unit |
| TS-4 | Matcher-update regression proofs for every rewritten pinned literal, each with a non-vacuity retained-anchor guard | Every rewritten literal has a paired proof against the pre-change bytes; no matcher is left unproven | Unit |
| TS-5 | Retention: the I.2.c heading byte-identity, the batch-mode paragraph as the byte-identical tail of I.2.c, I.2.b step 3's commit line-wrap literal, I.2.a's selection literal and Step I.0's pending-status literal | All five survive byte-for-byte | Unit |
| TS-6 | Invariants: the two forbidden tokens stay absent from the whole I.2.c section; no banned phrase in I.2.a; no banned workflow.yaml claim anywhere; no bare git commit or add line | All absence assertions hold | Unit |
| TS-7 | Version lockstep: the plugin manifest and the marketplace entry agree, with patch strictly greater than 47 | Both read the same version, patch greater than 47 | Unit |
| TS-8 | Hook non-modification and hook-contract consistency: no file under the hooks directory appears in the feature's change set, the hook classification table is byte-unchanged, and every pre-existing hook-contract module passes unmodified | Empty hook diff; hook pin modules green | Integration |
| TS-9 | Aggregate suite run from the repository root, covering TS-1 through TS-8 together with the pre-existing suite | Exit code 0, no failures, no errors, no skips | Integration |
| TS-10 | Reachable exit for a journal-reported merge the ancestor check refutes: the document states an outcome for that state other than the gate-rejected/abort terminal, reached without the user selecting abort, and the gate-rejected branch enumerates every condition that sends a task there — the journal-last-event conjunct's condition included | The state has a non-terminal outcome; the cause enumeration is complete; every immutable I.2.c literal still occurs and no path admits route-back while a recycled id could inherit a journal merge the launch guard denies | Unit |
| TS-11 | Trigger reachability for the stale-launched recovery: the in-flight verification's failure condition is satisfied by a task whose journal last event is launched while its worktree and its branch both exist, and that state reaches the recovery's primary outcome rather than the residual | The failure condition holds in the allowed-but-never-started state; the pre-change conjunctive condition is absent with its paired negative proof; the residual enumeration does not include a launch that never started | Unit |
| TS-12 | Defined inputs for the recovery: either the identifier lookup (entry selection, multiple-candidate rule, unresolvable/ambiguous → no stop) is owned by one site and named in the wake/resume state-source enumeration with I.2.b step 1 citing it, or the recovery consumes no such lookup | The adopted branch's assertions hold; no step of the recovery depends on an input the document leaves undefined | Unit |
| TS-13 | I.2.a's premise citation of the gate conjunct: it names the owning section, states its position relative to I.2.a correctly, and carries a single causal construction | The corrected premise is present, the pre-change premise absent with its paired negative proof, and the pinned conclusion, carve-out, always-in-flight sentence and slice anchors all survive | Unit |

## Code Quality Verification

- Format: none — `format_command` is empty for this project.
- Static analysis: none configured.
- Documentation discipline (NFR3): each rule this change touches is stated at
  exactly one site and cited elsewhere; verified by reading the four edited
  sites against IMPLEMENTATION.md's Layer Structure table.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | An automatically-recoverable exit, or a stated unreachability covering the ancestor-check failure, exists for a renumbered task that inherited a merged journal event | TS-1 and TS-10, plus a read of the I.2.c gate text and its gate-rejected branch |
| AC-2 | A recovery path other than abort exists for a plan carrying a stale launched state, and I.2.b step 1's existence check has a stated outcome | TS-2, TS-11 and TS-12, plus a read of I.2.b step 1 |
| AC-3 | I.2.a no longer asserts the falsified justification; the failed-only carve-out is re-justified consistently with AC-1's mechanism | TS-3 and TS-13, plus a read of the I.2.a paragraph |
| AC-4 | Requirements, acceptance criteria and test scenarios match AC-1..AC-3, and the two named modules assert them with the paired regression proofs | TS-4 plus this document's traceability table |
| AC-5 | The suite passes | TS-9 |
| AC-6 | Both manifests agree on one version strictly greater than 0.1.47 | TS-7 |
| AC-7 | Every surviving pinned literal is byte-identical; every rewritten literal has its matcher updated with a negative proof | TS-4, TS-5, TS-6 |
| SC-SEC | No new attack surface; hook defenses preserved | TS-8 plus the manual hook-diff check below |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0002 | TS-1, TS-10 |
| FR2 | task0001, task0002 | TS-1, TS-3, TS-10, TS-13 |
| FR3 | task0001, task0002 | TS-2, TS-11, TS-12 |
| FR4 | task0001, task0002 | TS-2, TS-11 |
| FR5 | task0001, task0002 | TS-8 |
| FR6 | task0001, task0002 | TS-4 |
| FR7 | task0001, task0002 | TS-7 |
| NFR1 | task0001, task0002 | TS-8 |
| NFR2 | task0001, task0002 | TS-4, TS-5, TS-6 |
| NFR3 | task0001, task0002 | TS-4, TS-5, TS-6, TS-12, TS-13 |
| NFR4 | task0001, task0002 | TS-9 |
| NFR5 | task0001, task0002 | TS-4, TS-5, TS-6 |

## E2E Testing

No E2E framework exists in this project and SPEC.md records none. Omitted.

## Manual Testing (E2E Not Possible)

- [ ] Change-set containment: the diff from the implement baseline touches
      only the paths SPEC.md declares — the protocol document, the two named
      test modules, the two manifests, and the feature-docs / test-docs
      directories. No path under the hooks directory, and no third test
      module.
- [ ] Test-method count per named module is greater than or equal to its
      pre-change count, and no test is decorated as skipped.
- [ ] Read-through of the four edited sites for single-source discipline: the
      recovery mechanics are stated once (I.2.b / Supporting cast) and only
      cited from I.2.c.
- [ ] Protocol walk-through of the two defect scenarios against the edited
      text: a journal-reported merge that fails the ancestor check, and a
      stale launched state with no worktree, branch or live agent — each ends
      in a state the phase can leave.
- [ ] Version bump reporting: note in the completion report that the plugin
      cache only picks the change up after a Claude Code restart.
- [ ] No mockup comparison item — the design step is skipped for this feature.

## Performance / Security Verification

- Performance: not applicable; the change has no runtime surface.
- Security: no new attack surface. No hook is modified, so the existing hook
  defenses — the no-follow journal open, the flock-serialized
  compare-and-append, task-id and absolute-worktree-path validation, and the
  agent-index / journal same-directory containment — are preserved unchanged
  along with the fail-open convention. Verified by TS-8's empty hook diff.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 13 | 13 | 0 | 0 |
| Success criteria | 8 | 7 | 0 | 1 |
| Manual checks | 6 | 0 | 0 | 6 |
| Build / format | 0 | 0 | 0 | 0 |
