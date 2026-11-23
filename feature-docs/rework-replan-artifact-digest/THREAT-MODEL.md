# Threat Model: rework-replan-artifact-digest

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1-FR7, NFR1-NFR4, Error Handling, Assumptions A1-A8), workflow.yaml (tier `reduced`; REQUIREMENTS.md and the design step were reduced away), and the domains of the single task (`api-contract`, `input-handling`). The feature edits the orchestrator's create-plan action decision in `em-workflow/references/contracts/spec-writer-contract.md`, adds citations of it in `em-workflow/references/phases/create-plan-phase.md`, and adds document tests. It adds no executable code.

The action decision is what keeps a planning artifact that someone other than the planning lineage changed from being overwritten without the `create-plan.artifact-overwrite` gate or the batch policy. The feature widens what counts as the lineage's own output by reading a second phase-state file, `phase-state/rework.yaml`. Two boundaries follow: the file the decision now reads (TB-1, deep depth because the task declares `input-handling`) and the existing target files the decision protects (TB-2, standard depth).

The batch stop that FR1 removes is a functional defect, not an adversary-driven threat, so it is not recorded as a threat. A target whose content equals the last rework.yaml entry while create-plan.yaml holds a later entry for the same path also gets `replace_own` under A2. That content is planning-lineage output that is already committed, so no change unique to the user is lost, and it is not recorded as a threat. Rework's action choice and the Layer 5 recording destinations stay unchanged (NFR1, NFR2), so the place where rework.yaml entries are written is not altered by this feature. The create-plan-phase.md sections only cite the owner, and `tests/test_artifact_digest_docs.py` implements no boundary; it is the verification vehicle.

## Trust Boundaries

### TB-1: phase-state/rework.yaml -> orchestrator create-plan action decision
Crossing: the content of `feature-docs/{feature}/phase-state/rework.yaml`, which the orchestrator reads as evidence that an existing planning artifact is the planning lineage's own output. The rework dispatch site's Layer 5 recording writes the file, but when the decision runs, the file may be absent, unreadable or malformed. It may also hold a mapping of another phase or another feature (for example, a copied feature directory), or it may have been edited by the user or another process.
Boundary files: `em-workflow/references/contracts/spec-writer-contract.md` (section "How the orchestrator chooses each target's action before dispatch")
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Spoofing | A rework.yaml whose mapping is not this feature's rework record (its phase is not `rework`, or its feature differs from the workflow's) is accepted as a planning-lineage record. A target the user changed then gets `replace_own` and is overwritten without the overwrite gate (FR1, FR5). | TM-1 | A rework.yaml record counts only when the file's mapping has phase `rework` and a feature equal to the workflow's feature (FR5). | task0001 AC-3 | VERIFICATION.md, Performance / Security Verification, TM-1 |
| Tampering | An absent, unreadable or malformed rework.yaml, or one with no `artifacts` entry for the path, is treated as a match or makes the decision skip its comparison. A changed target then reaches the dispatch as `replace_own` (FR5, FR2). | TM-2 | Each of these cases counts as no record from rework.yaml. The decision then rests on the `phase-state/create-plan.yaml` comparison alone, and with no match there the target takes the unchanged digest-mismatch branch (FR5, FR2). | task0001 AC-3 | VERIFICATION.md, Performance / Security Verification, TM-2 |

### TB-2: Existing planning artifacts in the integration worktree -> create-plan overwrite decision
Crossing: the current content of an existing create-plan target (IMPLEMENTATION.md, VERIFICATION.md, THREAT-MODEL.md, task plans), which the user or another process may have changed after the planning lineage last wrote it. The action decision is what keeps such a change from being overwritten without the `create-plan.artifact-overwrite` gate in interactive mode or the `references/batch-policies.yaml` decision in batch mode.
Boundary files: `em-workflow/references/contracts/spec-writer-contract.md` (section "How the orchestrator chooses each target's action before dispatch"); `em-workflow/references/phases/create-plan-phase.md` (sections "4. Planner dispatch", "13. Final-path correction dispatch" and "Feature-docs correction dispatch", which apply the decision by citation)
Depth: standard

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | The widened match is worded more broadly than FR1, so a target whose current digest matches neither last entry is overwritten without the gate or the batch policy (FR1, FR2, FR6). Examples of such wording: any recorded entry for the path instead of the last one, any phase-state file, entries for other paths, a looser test than the Legacy records equality for rework.yaml values, or `replace_own` granted by the spec-change transition itself. | TM-3 | `replace_own` for a create-plan target requires its current digest to equal the last `artifacts` entry for that path in `phase-state/create-plan.yaml` or in `phase-state/rework.yaml`. A recorded value that differs is compared as `references/artifact-digest.md` "Legacy records" states, cited and not restated. Every other existing target takes the unchanged digest-mismatch branch (FR1, FR2, FR6). | task0001 AC-1, AC-2, AC-3 | VERIFICATION.md, Performance / Security Verification, TM-3 |
