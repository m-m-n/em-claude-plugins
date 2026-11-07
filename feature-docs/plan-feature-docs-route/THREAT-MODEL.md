# Threat Model: plan-feature-docs-route

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md, REQUIREMENTS.md (FR1-FR10, NFR1-NFR6) and the em-workflow
sources the plan touches (planner contract, write_policy action model,
self-write digest, `validate-worker-output.py`, `report-name-entry.py`, the
develop skill's Step A.6, create-plan-phase.md sections 4-13, workflow-patch.md,
phase-state.md). Tier: full. Design step skipped (no UI).

The feature adds three crossings that did not exist before: an LLM worker's
result now causes the orchestrator to grant writes outside the worker's own
feature directory (FR3-FR6); text from another feature's documents now enters
the planner's prompt as material the planner edits (FR3, NFR5); and a worker
patch may now rewrite the `files` of carried task records of a failed feature,
which are otherwise copied verbatim (FR8, FR9). Each is analysed below.

Depth: deep for TB-1 and TB-3 (`auth`, `input-handling`, `data-persistence`
are declared by the tasks implementing them), deep for TB-2 (`input-handling`).

Considered and not recorded as threats:

- Information disclosure through the amended documents (home-directory paths,
  Notion URLs, NFR5): every write under `feature-docs/` is already checked by
  the existing `doc-redaction-guard` hook, which this feature does not change.
  No new mitigation is needed.
- Malformed `workflow.yaml`, journal or phase-state input to the validator and
  the entry script (NFR2): a robustness requirement covered by TS-9, not an
  attacker-controlled crossing; the inputs are written by the orchestrator.
- The FR2 check (`plan-task-feature-docs`, task0004) validates worker output
  for consistency with the implementer's rule (FR10); it closes no
  security-relevant crossing of its own. task0004's `input-handling` domain is
  covered by the validator being a boundary file of TB-1 and TB-3.
- Concurrent edits of a granted document between grant and write: covered by
  the existing pre-dispatch `expect_digest` verification and the exclusivity
  assumption, which the new action reuses (folded into TM-1).

## Trust Boundaries

### TB-1: Planner result to orchestrator write grants and declared change set
Crossing: the implementation-planner (an LLM worker, untrusted output) names
other-feature documents it wants to change (stage-1 request) and declares the
changes it made (stage-2 fixes); the orchestrator turns the request into
per-path write permission outside the feature directory and records the
declarations into the declared change set.
Boundary files: em-workflow/references/contracts/planner-contract.md,
em-workflow/references/contracts/spec-writer-contract.md,
em-workflow/references/contracts/worker-envelope.md,
em-workflow/scripts/self-write-digest.py,
em-workflow/scripts/validate-worker-output.py,
em-workflow/references/phases/create-plan-phase.md,
em-workflow/references/phase-state.md
Depth: deep (auth, input-handling, data-persistence)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A request names a path outside the FR5 scope (another feature's `workflow.yaml`, `phase-state/**`, `tasks/**`, `design/mockups/`, `feature-docs/LESSONS.md`, the own feature, a non-Markdown file, an absolute or `..` path, a `\`-separated disguise) and obtains a write grant, letting the worker corrupt another feature's state (FR4, FR5) | TM-1 | The scope rule is stated once in planner-contract.md and enforced twice: the orchestrator grants an `amend_other_feature` target only for an in-scope existing regular file, with `expect_digest` set to its digest at dispatch; the validator rejects any out-of-scope request, fix or `amend_other_feature` target (`other-feature-doc-scope`) and any such target on a dispatch other than an implementation-planner create-plan dispatch. No existing action or batch policy is reused for the grant | task0002 AC-2; task0003 AC-1; task0005 AC-1, AC-2; task0009 AC-1 | VERIFICATION.md, Performance / Security Verification, TM-1 |
| Repudiation | The planner modifies a granted document without declaring it, or declares a fix it did not make, so the change escapes the declared change set, review and verify containment (FR3, FR7) | TM-2 | The validator requires the declared fixes to equal the granted targets reported in `written_artifacts` (`other-feature-doc-fix`); the orchestrator's scope verification fails a run whose observed modified grant is not reported and declared; every declared fix is appended to `other_feature_doc_fixes` in `phase-state/create-plan.yaml` and read by section 12's declared change set derivation | task0002 AC-1; task0005 AC-4, AC-5; task0009 AC-3, AC-5 | VERIFICATION.md, Performance / Security Verification, TM-2 |

### TB-2: Other-feature document content into the planner prompt
Crossing: text of another feature's `feature-docs/` documents, written by
earlier runs and possibly holding instruction-shaped text, is read by the
planner as material it edits.
Boundary files: em-workflow/agents/implementation-planner.md,
em-workflow/references/contracts/planner-contract.md
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | Instruction-shaped text inside the document steers the planner to write beyond its grants, change the plan's meaning, or request further paths (NFR5) | TM-3 | The planner treats the document's content as untrusted data under the worker envelope's Untrusted-Input Handling (cited, not restated): it follows no instruction found there, edits only the granted targets, and reports an injection attempt in its report; scope verification still bounds every write to the grants | task0001 AC-4; task0002 AC-3 | VERIFICATION.md, Performance / Security Verification, TM-3 |

### TB-3: Correction patch to the failed feature's workflow.yaml
Crossing: on the correction entry (`create-plan` completed, `implement`
failed) a worker-supplied `replace_planning` patch carrying
`tasks_patch.feature_docs_removals` rewrites the `files` and clears `notes`
of carried task records, which every other patch copies verbatim, while a
`failed` task is present.
Boundary files: em-workflow/scripts/validate-worker-output.py,
em-workflow/scripts/feature-docs-entry.py,
em-workflow/references/workflow-patch.md,
em-workflow/skills/develop/SKILL.md,
em-workflow/references/phases/create-plan-phase.md
Depth: deep (data-persistence, input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | Under the relaxed permission a patch removes a path that is not a feature-docs path, rewrites a merged or in-flight task, empties a task's `files`, leaves another unmerged feature-docs path behind, or smuggles new entries, step changes or requirement changes into `workflow.yaml` (FR8, FR9) | TM-4 | The validator admits `feature_docs_removals` only on the correction entry and only under the conditions `feature-docs-removal-shape`, `-not-permitted`, `-in-flight`, `-merged`, `-path`, `-empty-files`, `-incomplete` and `-limits`; the application removes only the named path from the named task and clears its `notes`; every other field and every merged record is copied verbatim; the corrected plans' Files sections must agree with the corrected `files` | task0006 AC-5, AC-6; task0007 AC-4 | VERIFICATION.md, Performance / Security Verification, TM-4 |
