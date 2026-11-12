# Threat Model: verify-pass-resolves-deferred-findings

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md and REQUIREMENTS.md at the `full` tier (no DESIGN.md; the
design step is skipped). The feature's inputs are the free text of review
findings in the latest review round record, the text of VERIFICATION.md and
SPEC.md, the mapping the orchestrator builds from them, `workflow.yaml`, and
the verified commit. Two trust boundaries exist: untrusted document text
entering the orchestrator's verify-pass judgment (TB-1), and the
orchestrator-built mapping plus the YAML records entering the script that
rewrites the review round record (TB-2). What an attacker gains across
either boundary is the same: a blocking critical/high finding turned into
`fixed`, which removes the merge preflight's stop. Because FR11 keeps the
preflight's own rule unchanged, the round record is the only lever, so both
boundaries are analysed at deep depth (`input-handling`, `data-persistence`,
`external-io`).

Not boundaries: `workflow.yaml`'s `result` / `round` and the verified commit
are written or captured by the orchestrator itself; the IDs inside
`passed_ids` are derived from untrusted documents and are covered under TB-1
(TM-2). `merge-preflight.py` is unchanged and reading the record is not a new
crossing.

Domain consistency: task0003 declares `data-persistence` while its files
(`em-workflow/references/review-phase.md`, `em-workflow/references/batch-mode.md`
and its test module) appear in no `Boundary files` line. It documents the
round record's new field and the batch audit item; it adds no runtime
crossing. The record is written only by the script in TB-2.

## Trust Boundaries

### TB-1: Untrusted document text into the orchestrator's verify-pass judgment
Crossing: the free text of findings in the latest review round record
(reviewer-written, may quote diff content), VERIFICATION.md and SPEC.md text,
interpolated into the orchestrator's judgment that records `passed_ids` and
builds the stable_id-to-criteria mapping.
Boundary files: em-workflow/skills/develop/SKILL.md
Depth: deep (input-handling, data-persistence)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | Instruction-shaped text in a finding, VERIFICATION.md or SPEC.md steers the orchestrator into mapping a finding that is not the non-attainment of a passed criterion (for example a code defect that merely names a criterion ID), so a blocking finding becomes fixed and the merge preflight stop disappears (FR3, NFR1, FR11) | TM-1 | The judgment runs only in a round whose verify result is pass, and only on findings with resolution deferred, severity critical/high and category spec; a mapping requires the finding's content to be the non-attainment itself of specific passed criteria; an ID appearing in the text is not enough; ambiguous findings and findings with any other content are left out; all such text is read as data | task0002 AC-2 | VERIFICATION.md TM-1 (TS-7, manual walk-through) |
| Tampering | `passed_ids` gains IDs that were not evaluated in the round or that belong to excluded requirements, so a mapping to them passes the script's membership check (FR2) | TM-2 | `passed_ids` holds only IDs evaluated with a pass outcome in that round; IDs tied to excluded requirements and unevaluated IDs are left out; the set is replaced every round | task0002 AC-1 | VERIFICATION.md TM-2 (TS-7) |

### TB-2: Orchestrator-built mapping and YAML records into the record-rewriting script
Crossing: the mapping (produced by TB-1's judgment over untrusted text), the
latest review round record (reviewer free text) and `workflow.yaml` enter the
new script, which rewrites the record that the merge preflight trusts.
Boundary files: em-workflow/scripts/resolve-verified-findings.py
Depth: deep (input-handling, data-persistence, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A mapping entry names a finding that is not eligible (absent from the latest round, not deferred, below high, not category spec) or criteria outside `passed_ids`, and the script rewrites it anyway (FR4, FR8) | TM-3 | Every entry is re-checked against the structured values of `workflow.yaml` and the latest round record; an entry that fails any condition leaves its finding unchanged | task0001 AC-2 | VERIFICATION.md TM-3 (TS-2) |
| Tampering | A YAML tag in a round record or `workflow.yaml` makes the loader construct language-native objects (NFR6) | TM-4 | YAML is read with safe load only; a document that safe load refuses is a structural error and nothing is written | task0001 AC-7 | VERIFICATION.md TM-4 (TS-10) |
| Tampering | Malformed input leaves a partially rewritten or corrupted round record, or a write lands on a file other than the latest round record (FR4, NFR6) | TM-5 | All inputs and the verified commit are validated before any write; a structural error exits non-zero with nothing written; the latest round record is the only file written, replaced as a whole | task0001 AC-6, task0001 AC-7 | VERIFICATION.md TM-5 (TS-6, TS-10) |
| Elevation of privilege | Free text from a finding or from the mapping is relayed through the script's stdout / stderr into the orchestrator's context and its reports (NFR1) | TM-6 | The script outputs only validated structured values: stable_ids that conform to the token format and exist in the record, IDs that are members of `passed_ids`, round numbers, counts and fixed error codes | task0001 AC-7 | VERIFICATION.md TM-6 (TS-10) |
| Repudiation | A finding becomes fixed with no durable trace of which verify round, commit and criteria justified it (FR5, FR6) | TM-7 | The rewritten finding carries the fixed-format `resolution_reason` and the `verify_resolution` record (verify round, verified commit, criteria IDs, previous resolution and reason), committed in the same commit-docs.sh commit as the verify result | task0001 AC-1, task0002 AC-3 | VERIFICATION.md TM-7 (TS-1, TS-7) |
