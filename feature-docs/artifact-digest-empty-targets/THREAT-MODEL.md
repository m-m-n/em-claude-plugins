# Threat Model: artifact-digest-empty-targets

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1-FR4, NFR1-NFR3, Edge Cases, Assumptions), workflow.yaml (tier `reduced`; REQUIREMENTS.md and the design step were reduced away), and the domains of the single task (`api-contract`, `input-handling`). The feature edits the procedure text of the orchestrator's two digest checks in `em-workflow/references/artifact-digest.md` and adds documentation tests. It adds no executable code and leaves `em-workflow/scripts/artifact-digest.py` unchanged (FR3).

Both checks the feature edits sit on a trust boundary. Pre-dispatch verification guards existing write-target files that a party other than the orchestrator may have changed after the write action was decided. Layer 5 recording processes the `written_artifacts` list a worker declares about itself. The new zero-case rules narrow when each check runs. At each boundary, the realistic threat is that the rule is worded so that it also skips a case the check must still cover. TB-2 is analysed at deep depth because the task declares `input-handling` (validation of worker output). TB-1 is analysed at standard depth.

The repeated stale judgement that FR1 removes is a functional defect, not an adversary-driven threat, so it is not recorded as a threat. `tests/test_artifact_digest_docs.py` implements no boundary. It is the verification vehicle.

## Trust Boundaries

### TB-1: Existing write-target files -> orchestrator pre-dispatch verification
Crossing: the current content of existing write-target files in the integration worktree, which the user or another process may change between the time the orchestrator decides a target's action and the dispatch. The orchestrator compares that content against the target's `expect_digest` before it lets a worker write.
Boundary files: `em-workflow/references/artifact-digest.md` (Pre-dispatch verification section)
Depth: standard

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | The zero-target rule (FR1) is keyed on whether non-null `expect_digest` values are present instead of whether a target's action requires one. A target that requires an `expect_digest` but arrives without one would then be dispatched unverified, and a file changed after the action was decided could be overwritten. | TM-1 | The zero-target condition counts the targets whose action requires an `expect_digest`; the requirement is the write-policy model's, which the document cites. When one or more such targets exist, the existing procedure and every mismatch condition apply unchanged (FR1, NFR1). | task0001 AC-1 | VERIFICATION.md, Performance / Security Verification, TM-1 |

### TB-2: Worker result -> orchestrator Layer 5 recording
Crossing: a worker's `completed` result, specifically its self-declared `written_artifacts` list. The worker processes untrusted envelope content (`em-workflow/references/contracts/worker-envelope.md`, Untrusted-Input Handling), so the orchestrator validates its declarations instead of trusting them.
Boundary files: `em-workflow/references/artifact-digest.md` (Layer 5 recording section)
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | Under the zero-artifact rule (FR2), a `completed` result that declares no `written_artifacts` no longer fails layer 5. If the rule is worded as an acceptance of such a result, a worker that wrote files but declared none would pass with no digest recorded for those files. | TM-2 | The zero-artifact rule states only that Calculation is not run and nothing is recorded. It states that the rules of the layer handling the result decide whether an empty `completed` result is acceptable, and it adds no wording that accepts the result. The procedure for one or more artifacts, including its artifact-validation failure conditions, stays unchanged (FR2, NFR1). | task0001 AC-2 | VERIFICATION.md, Performance / Security Verification, TM-2 |
