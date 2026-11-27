# Threat Model: orchestrator-spec-edit-overwrite

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md and REQUIREMENTS.md (FR1-FR7, NFR1-NFR4, Error Handling, Assumptions A-1 to A-11), and workflow.yaml (tier `full`; the design step is skipped). Also inspected: the two tasks' domains, task0001 (`api-contract`, `auth`, `input-handling`) and task0002 (`api-contract`, `data-persistence`). The feature changes the orchestrator's create-spec action decision in `em-workflow/references/contracts/spec-writer-contract.md` and adds a citation in `em-workflow/references/phases/create-spec-phase.md`. It also adds the `orchestrator_doc_edits` record to `em-workflow/references/phase-state.md` and its writer procedure to `em-workflow/skills/develop/SKILL.md`, plus document tests. It adds no executable code.

The action decision is what keeps an existing SPEC.md or REQUIREMENTS.md that someone other than the orchestrator changed from being overwritten without the `create-spec.artifact-overwrite` gate or the batch policy. The feature widens what counts as the orchestrator's own output by reading a record that the orchestrator writes during create-plan. Three boundaries follow:
- TB-1: the record file that the decision now reads. Depth deep (`input-handling`, `auth`).
- TB-2: the existing create-spec targets that the decision protects. Depth deep (`auth`).
- TB-3: the point where the orchestrator writes the record, which later grants an overwrite. Depth deep (`data-persistence`).

Not recorded as threats:
- The batch stop that the feature removes is a functional defect, not an adversary-driven threat.
- A target whose content returns to the bytes of a recorded version also gets `replace_own` (SPEC A-9). That version was committed by the orchestrator, so no change unique to the user is lost.
- A feature already stopped by an unrecorded edit is not recovered (SPEC A-7); this changes no protection.
- The record holds only the feature's own SPEC.md and REQUIREMENTS.md paths (SPEC A-4). These are never create-plan or design targets, so the record could not grant `replace_own` to such a target even if a wording leaked outside create-spec. FR5 keeps those decisions unchanged as a design rule, not as a mitigation.
- The decision compares only an entry's `path` and `sha256`. The `reason` text is not part of the decision, and phase-state content is data to the orchestrator, as every other phase-state field is.

`tests/test_orchestrator_doc_edits_action_docs.py` (task0001) and `tests/test_orchestrator_doc_edits_record_docs.py` (task0002) implement no boundary; they are the verification vehicle.

## Trust Boundaries

### TB-1: phase-state/create-plan.yaml orchestrator_doc_edits -> orchestrator create-spec action decision
Crossing: the content of `feature-docs/{feature}/phase-state/create-plan.yaml`, which the orchestrator reads as evidence that an existing SPEC.md or REQUIREMENTS.md is a version it committed itself. The orchestrator's create-plan procedure writes the file. When the decision runs, though, the file may be absent, unreadable or malformed, may hold a mapping of another phase or another feature (for example, a copied feature directory), or may have been edited by the user or another process.
Boundary files: `em-workflow/references/contracts/spec-writer-contract.md` (section "How the orchestrator chooses each target's action before dispatch")
Depth: deep (input-handling, auth)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Spoofing | A create-plan.yaml whose mapping is not this feature's create-plan record (its phase is not `create-plan`, or its feature differs from the workflow's) is accepted as the orchestrator's record. A SPEC.md the user changed then gets `replace_own` and is overwritten without the overwrite gate (FR3, FR4). | TM-1 | The record counts only when the file's mapping has phase `create-plan` and a feature equal to the workflow's feature (FR4). | task0001 AC-3 | VERIFICATION.md, Performance / Security Verification, TM-1 |
| Tampering | An absent, unreadable or malformed create-plan.yaml, or one with no `orchestrator_doc_edits` entry for the path, is treated as a match or makes the decision skip its comparison. A changed target then reaches the dispatch as `replace_own` (FR4, FR3). | TM-2 | Each of these cases counts as no record from create-plan.yaml. The decision then rests on the `phase-state/create-spec.yaml` comparison alone, and with no match there the target takes the unchanged digest-mismatch branch (FR4, FR3). | task0001 AC-3, AC-2 | VERIFICATION.md, Performance / Security Verification, TM-2 |

### TB-2: Existing create-spec targets in the integration worktree -> create-spec overwrite decision
Crossing: the current content of an existing SPEC.md or REQUIREMENTS.md, which the user or another process may have changed after the last create-spec output or the last recorded orchestrator edit. The action decision is what keeps such a change from being overwritten without the `create-spec.artifact-overwrite` gate in interactive mode or the `references/batch-policies.yaml` decision in batch mode.
Boundary files: `em-workflow/references/contracts/spec-writer-contract.md` (section "How the orchestrator chooses each target's action before dispatch", and the `replace_own` row of "The `write_policy` actions"); `em-workflow/references/phases/create-spec-phase.md` (section "9. Spec writer dispatch", which applies the decision by citation)
Depth: deep (auth)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | The widened match is worded more broadly than FR3, in the owner section or in a place that cites it. A target whose current digest matches neither last entry is then overwritten without the gate or the batch policy (FR3, FR4, FR6). Examples of such wording: any recorded entry for the path instead of the last one, any phase-state file, entries for other paths, a looser test than the Legacy records equality, `replace_own` granted by the spec-change record itself, or a citing place that states its own match target. | TM-3 | `replace_own` for a create-spec target requires its current digest to equal the last `artifacts` entry for that path in `phase-state/create-spec.yaml` or the last `orchestrator_doc_edits` entry for that path in `phase-state/create-plan.yaml`. A recorded value that differs is compared as `references/artifact-digest.md` "Legacy records" states, cited and not restated. Every other existing target takes the unchanged digest-mismatch branch, and no other condition gives `replace_own`. The `replace_own` row and section 9 cite the owner section and state no match target of their own (FR3, FR5, FR6). | task0001 AC-1, AC-2, AC-4, AC-6 | VERIFICATION.md, Performance / Security Verification, TM-3 |

### TB-3: Orchestrator's own document edit during create-plan -> persisted overwrite evidence
Crossing: the body of SPEC.md or REQUIREMENTS.md at the moment the orchestrator writes an `orchestrator_doc_edits` entry. The entry later lets a create-spec decision overwrite that body without the gate. Between the edit and its commit, the worktree can change: an exit 4 of `commit-docs.sh` refreshes the tree to a tip that carries other commits, and the edit has to be re-created there. The digest calculation can also fail.
Boundary files: `em-workflow/skills/develop/SKILL.md` (Step B, the recording paragraph); `em-workflow/references/phase-state.md` (`## Schema`, the `orchestrator_doc_edits` example and row)
Depth: deep (data-persistence)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | An entry holds a digest that is not that of the body the orchestrator committed: one taken before the edit, one kept from before an exit-4 re-creation, or a value written although the calculation failed. A version the orchestrator never committed, for example a user's version, then matches the record and is overwritten without the gate (FR1, FR3). | TM-4 | The orchestrator calculates the digest of the changed document by `references/artifact-digest.md` `Calculation` and commits the entry in the same commit as the document change. On an exit 4 it re-creates the edit on the refreshed tree and recalculates the digest from the re-created body before retrying with the entry. When the calculation fails it writes no entry (FR1, SPEC A-10). | task0002 AC-3, AC-4 | VERIFICATION.md, Performance / Security Verification, TM-4 |
