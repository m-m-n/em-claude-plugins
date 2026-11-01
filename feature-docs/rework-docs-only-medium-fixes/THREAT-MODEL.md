# Threat Model: rework-docs-only-medium-fixes

## Verdict
threats-identified

## Rationale
Inspected SPEC.md and REQUIREMENTS.md (tier: full; the design step was skipped, so there is no DESIGN.md). The feature changes the checks `em-workflow/scripts/validate-worker-output.py` applies to rework-planner output before the orchestrator applies that output to `workflow.yaml`. That output is LLM-generated and untrusted (`em-workflow/references/contracts/worker-envelope.md`, Untrusted-Input Handling). The post-change VERIFICATION.md read through `--feature-dir` lies in the rework round's write scope. The validator therefore sits on a trust boundary, and its acceptance decision is the protected asset (SPEC.md Security Considerations, NFR1).

Depth is deep because task0001, task0002 and task0003 declare `input-handling`; their boundary file is listed under TB-1. task0004 edits SSOT documents only and declares none of the four depth domains. Fixtures and tests are test data and implement no boundary.

The TM-n identifiers in this document are local to it. They are unrelated to the TM-n of other features' threat models.

## Trust Boundaries

### TB-1: Rework-planner output into the workflow-state gate
Crossing: the rework-planner result (rework_index, payload.doc_corrections, workflow_patch) and a standalone workflow patch, together with the post-change VERIFICATION.md under `--feature-dir`, cross from the LLM worker into the validator. Acceptance lets the orchestrator apply the patch to `workflow.yaml`. The orchestrator-built input envelope (rework_source) is read alongside as the reference value.
Boundary files: em-workflow/scripts/validate-worker-output.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A result declares a scenario rename whose `to` is not in the post-change VERIFICATION.md, whose `from` is still present there, or whose `from` never existed in the baseline. A finding is then recorded as covered by an existing scenario that does not verify it (FR1). | TM-1 | A declared rename is accepted only when the document diff confirms every FR1 condition. When the diff is unavailable, the check fails closed with a distinct message. | task0001 AC-1, AC-2 | VERIFICATION.md Performance / Security Verification, TM-1 (TS-1 to TS-6) |
| Tampering | A result lists as covered_by_existing the old ID that its own rename removed, or an ID absent from the post-change VERIFICATION.md (FR2). | TM-2 | The check rejects the `from` of every declared pair. When the diff is available, every covered ID must be in the post-change scenario-ID set. | task0001 AC-3, AC-4 | VERIFICATION.md Performance / Security Verification, TM-2 (TS-7 to TS-9) |
| Elevation of privilege | A docs-only-round patch changes workflow steps beyond the single origin-step reset the worker is permitted: it targets implement, resets a non-origin step, or sets a status other than pending. Or it claims an origin step that differs from the envelope's rework_source (FR3). | TM-3 | A structural check requires exactly one step patch. Its step_id must be the origin step resolved from the envelope (fallback: verify or review; a malformed rework_source fails closed), and its set.status must be pending. Any implement entry is rejected. | task0002 AC-1, AC-2, AC-3, AC-4, AC-5 | VERIFICATION.md Performance / Security Verification, TM-3 (TS-10 to TS-16) |
| Tampering | A tests_replace whose from set and to set overlap (chain or swap) drops scenario references from a requirement's tests when its pairs are applied in sequence. This breaks traceability (FR4). | TM-4 | The check rejects any from/to overlap within one requirements_patch entry, structurally and independent of `--dry-run-apply`. | task0003 AC-1, AC-2, AC-3 | VERIFICATION.md Performance / Security Verification, TM-4 (TS-17 to TS-19) |
| Denial of service | Malformed output makes a new check raise, so the validator exits with 2 instead of reporting the rejection as exit 1 with JSON details (NFR1). Examples: a non-mapping rework_source, a non-string type, a non-mapping step patch, a broken tests_replace pair, an unreadable VERIFICATION.md. | TM-5 | Every new check reports a malformed shape as an error and never raises an exception. | task0001 AC-7, task0002 AC-7, task0003 AC-6 | VERIFICATION.md Performance / Security Verification, TM-5 (TS-21) |
