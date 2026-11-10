# Threat Model: spec-change-rework-reentry

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md, REQUIREMENTS.md, the five protocol documents the feature
changes (`rework-task-synthesis.md` Sections 10 and 11,
`contracts/rework-planner-contract.md`, `agents/rework-planner.md`,
`skills/develop/SKILL.md` 「verify フェーズ」 item 6,
`implement-phase.md` Step I.0) and the planned test modules; tier `full`.

The feature adds no network, authentication or process boundary. Returning
`verify` to `pending` in the SPEC-change transition (FR1), the scope of
Invariant 1 (FR5) and the SKILL.md citation (FR6) only change which steps the
orchestrator itself sets from its own state; no data crosses a trust boundary
there. The test modules read repository documents only.

The one place data crosses a trust boundary is the new SPEC-change re-entry
identification in Step I.0 (FR2, FR4): the orchestrator decides whether to
skip the protocol-error ABORT, and runs git ancestry checks, on values read
from repository-controlled files (`workflow.yaml`, `phase-state/rework.yaml`),
which Step I.0's existing identifier gate already treats as
attacker-influenceable, and FR4 forbids taking that decision from worker
natural-language output or session memory. Both boundaries are analysed deep
because task0003 declares `input-handling`.

Domain consistency: task0003 declares `input-handling` and its file
`em-workflow/references/implement-phase.md` is the boundary file of TB-1 and
TB-2; task0001 and task0002 declare `api-contract` only. A batch run that
returns to a failing verify after a SPEC-change re-entry stays bounded by the
existing verify-rework caps, which this feature leaves unchanged (A6), so no
denial-of-service row is recorded.

## Trust Boundaries

### TB-1: Repository-controlled workflow state into the Step I.0 entry decision
Crossing: values from `feature-docs/{feature}/workflow.yaml` (step statuses,
`completed_at_commit`, task statuses), the `spec_change` record of
`feature-docs/{feature}/phase-state/rework.yaml` (`recorded_at_commit`,
`consumed`, `replan_authorized`) and the integration branch's commit history,
from repository content (attacker-influenceable in a cloned repository) into
the orchestrator's Step I.0 admissibility decision and the git commands it
runs for the ancestry checks.
Boundary files: em-workflow/references/implement-phase.md
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A commit value read for the identification (`completed_at_commit`, `recorded_at_commit`) carries shell metacharacters or a leading `-` and is interpolated into the git ancestry check, running commands or injecting options in the orchestrator's shell (FR2, FR4) | TM-1 | Each commit value is checked against the full hexadecimal commit object-id shape before it appears in any git command; a non-matching value means the entry is not a SPEC-change re-entry, and the value is never sanitised | task0003 AC-5 | VERIFICATION.md Performance / Security Verification, TM-1 (TS-10) |
| Tampering | A `spec_change` record that does not belong to the current cycle (left over from an earlier cycle, written by the tier-upgrade procedure, or carried in with edited state) makes an entry that FR4 requires to ABORT look like a SPEC-change re-entry, so `implement` completes with no work and the protocol-error safeguard is bypassed (FR2, FR4) | TM-2 | Identification requires all five committed-fact conditions together (SPEC.md Data Flow, A2), including the ancestry binding of the record between the prior `completed_at_commit` and the current tip and the commit-history evidence that the transition returned `implement` to `pending`; an entry failing any condition falls to the existing immediate ABORT | task0003 AC-2, AC-4 | VERIFICATION.md Performance / Security Verification, TM-2 (TS-3, TS-10) |

### TB-2: Worker output and session memory into the Step I.0 entry decision
Crossing: natural-language output of workers (shaped by untrusted SPEC.md and
finding text) and the orchestrator's own session memory, into the decision
whether an entry is a SPEC-change re-entry.
Boundary files: em-workflow/references/implement-phase.md
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Spoofing | A worker's natural-language output (for example induced by injected text in a finding) or a stale session belief asserts that the entry is a SPEC-change re-entry, admitting a state that FR4 requires to ABORT | TM-3 | Step I.0 states that the identification reads committed facts only and never uses session memory or worker natural-language output | task0003 AC-2 | VERIFICATION.md Performance / Security Verification, TM-3 (TS-10) |
