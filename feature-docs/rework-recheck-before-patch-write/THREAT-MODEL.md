# Threat Model: rework-recheck-before-patch-write

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1-FR4, NFR1-NFR4, Unchanged Documents), workflow.yaml
(tier `reduced`; REQUIREMENTS.md and the design step were reduced away), the
"Return-time digest" paragraph of `em-workflow/references/rework-task-synthesis.md`
section 10, application rules 15 and 16 of `em-workflow/references/workflow-patch.md`,
and Rule R1 of `em-workflow/references/contracts/worker-envelope.md` ("Order",
"Known limit"). The single task declares `concurrency` and `data-persistence`;
`data-persistence` sets deep depth for the one boundary found.

The feature changes protocol text and a document test only. It adds no runtime
input path, network call or privilege change. The paragraph it changes decides
when the orchestrator turns a rework-planner result into persistent workflow
state (the rule 15 write to workflow.yaml and the rule 16 commits) while another
local process can still reach the integration worktree's files. That crossing
is a trust boundary, and Tampering applies to it. No other STRIDE category
realistically applies: no identity is asserted (Spoofing), nothing confidential
is handled (Information disclosure), no audit claim is made beyond the workflow
state itself (Repudiation), no privilege changes hands (Elevation of privilege),
and a stale result only triggers the existing re-dispatch path (Denial of
service).

The window after a passing recheck is not changed by this feature. Rule R1
"Known limit" and the exclusivity assumption still govern it, and SPEC.md keeps
both documents unchanged. No threat is recorded for it here.

`tests/test_recheck_dispatch_sites_docs.py` reads repository documents only and
crosses no boundary; it is the verification vehicle. The task that declares
`data-persistence` has its document file in the `Boundary files` line below.

## Trust Boundaries

### TB-1: Integration worktree files between scope verification and the rework patch application
Crossing: file content of a rework-planner self-write-set path written by a
process other than the orchestrator and the dispatched worker, after the scope
verification of the rework-planner result. The result then becomes persistent
workflow state through step 3's application of the rework patch (another
process -> the orchestrator's return-time procedure -> workflow.yaml and the
integration branch).
Boundary files: em-workflow/references/rework-task-synthesis.md
Depth: deep (data-persistence)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | Another process rewrites a self-write-set path after the scope verification. The return-time recheck detects it, but section 10 places the recheck after step 3 validates and applies the patch. The new rework tasks and the `implement: pending` transition are therefore already written to workflow.yaml and committed. The stale handling resets only to the integration ref, so the stale result's workflow changes stay on the integration branch (FR1; SPEC Objectives). | TM-1 | Section 10's Return-time digest paragraph places the return-time recheck after step 3's validation (application rules 1-14, including the rule 1 comparison) and before step 3's application (the rule 15 single Write to workflow.yaml and the rule 16 R2 commits). It states that the patch is applied only after a passing recheck, so a recheck mismatch or a recheck that cannot run makes the result stale before any workflow.yaml write or commit by the patch (FR1, FR2). A regression probe pins the order and fires on the base-revision paragraph (FR4). | task0001 AC-1, AC-2, AC-3 | VERIFICATION.md, Performance / Security Verification, TM-1 |
