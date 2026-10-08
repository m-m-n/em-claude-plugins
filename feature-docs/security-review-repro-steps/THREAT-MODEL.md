# Threat Model: security-review-repro-steps

## Verdict
threats-identified

## Rationale
Inspected SPEC.md and REQUIREMENTS.md (FR1-FR13, NFR1-NFR5) at the full tier,
together with the files each task changes. The feature adds one
attacker-influenceable text field, `reproduction`: reviewers write it while
reading code under review, which the review protocols already treat as
untrusted, and three new consumers act on it — the verifiers (the em-workflow
review-evaluator subagent and the orchestrator main session of both plugins,
all holding read and shell tools), the write-capable review-editor through the
auto-fix finding JSON, and later rounds through persisted round records. These
are TB-1 to TB-3.

Domains set the depth: `input-handling` (task0003, task0004, task0005) and
`data-persistence` (task0004, task0005) make all three boundaries deep.
task0001 and task0002 declare only `api-contract` and own no boundary file:
the schemas, protocols and SCA scanner define the field's shape and emit null,
and the perspective-skill text the codex-reviewer interpolates into the Codex
prompt is plugin-shipped content, not untrusted data.

Information disclosure was considered for TB-1 and TB-3: a `reproduction`
persisted in a round record could carry a secret copied from the reviewed code,
but `description` already carries the same exposure and this feature changes
nothing about where round records live, so no row is added for it.

SPEC.md's Security Considerations (NFR1, NFR2) state what is protected; this
document states how it can be broken and how the design prevents it.

## Trust Boundaries

### TB-1: Reviewer `reproduction` text to verifiers
Crossing: text a reviewer wrote while reading untrusted code (attacker-influenceable, including prompt injection planted in that code) is read and acted on by the em-workflow review-evaluator subagent and by the orchestrator main session of em-workflow and em-review, all of which hold read and shell tools.
Boundary files: em-workflow/references/review-evaluation-contract.md, em-workflow/agents/review-evaluator.md, em-workflow/references/review-phase.md, em-review/references/review-phase.md
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A verifier runs a command, script or test written in `reproduction` (a destructive shell line, an injected instruction) with the user's privileges (NFR1, NFR2) | TM-1 | No verifier executes anything written in `reproduction`; verification is code reading plus the read-only commands each plugin's review protocol already permits; no file change, commit, network access or package installation | task0003 AC-4; task0004 AC-3; task0005 AC-4 | VERIFICATION.md Performance / Security Verification, TM-1 (TS6, TS13, TS20) |
| Tampering | A deliberately wrong or misleading `reproduction` makes a real security issue look refuted, so it leaves the fix / residual / rework targets and its dismissal suppresses later reports (FR5, FR6, FR7, FR8) | TM-2 | `not reproduced` only when reading positively confirms the stated steps do not hold; any failure to finish verification is `unverifiable` and goes to judgment, never to dismissal on that ground; every dismissal or decline is persisted with its reason (`dismissed_sites` reason, `resolution_reason`) | task0003 AC-2, AC-3; task0004 AC-2; task0005 AC-2 | VERIFICATION.md Performance / Security Verification, TM-2 (TS6, TS7, TS8, TS14) |
| Denial of service | An oversized `reproduction`, or one that leads the verifier through many files, floods the verifier's context or exhausts the evaluator's read budget so that other perspectives go uninspected (FR9, NFR2) | TM-3 | `reproduction` is capped at 4096 bytes at aggregation, and a truncated or over-limit value is `unverifiable`; the evaluator's verification reads come from its fixed 10-file budget, never raised, and exhaustion yields `unverifiable` rather than more reads | task0003 AC-3, AC-4; task0004 AC-1; task0005 AC-1 | VERIFICATION.md Performance / Security Verification, TM-3 (TS6, TS7, TS8, TS14) |

### TB-2: Auto-fix finding JSON to review-editor
Crossing: the auto-fix dispatch hands an untrusted finding to the review-editor subagent, which can edit the target file.
Boundary files: em-workflow/references/review-phase.md, em-review/references/review-phase.md
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | Instruction-shaped text in `reproduction` reaches the write-capable editor and steers its edit of the target file (FR9) | TM-4 | The finding JSON handed to review-editor keeps its existing field set and excludes `reproduction` | task0004 AC-4; task0005 AC-5 | VERIFICATION.md Performance / Security Verification, TM-4 (TS19) |

### TB-3: Persisted round records to the next round's round_context
Crossing: a decision recorded in one round (a round record on disk) is read back in a later round, after the code may have changed, and suppresses findings and verification there.
Boundary files: em-workflow/references/review-phase.md, em-review/references/review-phase.md, em-workflow/references/review-evaluation-contract.md
Depth: deep (data-persistence)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A carried not-reproduced decision keeps suppressing a security finding at that site after the code there changed, hiding an issue that is now real (FR13) | TM-5 | A not-reproduced decision is carried only while the site's file is unchanged since the recording round's head_commit; once it changed, the finding is verified again; the carried entry matches only security findings at the same site | task0003 AC-5; task0004 AC-5; task0005 AC-5 | VERIFICATION.md Performance / Security Verification, TM-5 (TS7, TS8, TS15) |
